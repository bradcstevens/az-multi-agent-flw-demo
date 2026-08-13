"""Tests for the Dataverse System Administrator preflight check (issue #2).

Power Platform administrators are no longer automatically granted the System
Administrator role in the Default environment, and that role is what lets the
environment-level Dataverse search setting be changed at all (#3). So the right
question is not "is the build account a Power Platform admin?" but "does the
environment's own security-role list name it a System Administrator?" — which is
a different fact, read from a different API.

The seam under test is the pure evaluation: given the tenant's Default
environment and the build account's Dataverse security roles, `evaluate` decides
whether the environment can be administered. The live HTTP calls sit outside it.
"""

from preflight.dataverse_admin_role import (
    DEFAULT_ENVIRONMENT_ID,
    SYSTEM_ADMINISTRATOR,
    app_user_request,
    role_reference,
    select_role,
    select_system_user,
    default_environment,
    disable_user_request,
    evaluate,
    elevation_error,
    format_report,
    is_propagation_delay,
    odata_url,
    main,
    select_environment,
)


def environment(**overrides):
    """A Power Platform environment shaped like the BAP admin API's."""
    properties = {
        "displayName": "Contoso (default)",
        "isDefault": True,
        "environmentSku": "Default",
        "linkedEnvironmentMetadata": {
            "instanceUrl": "https://org5dadb450.crm.dynamics.com/",
            "instanceState": "Ready",
            "uniqueName": "unqd3c93f69ac94f0118706000d3a106",
        },
    }
    properties.update(overrides.pop("properties", {}))
    env = {"name": DEFAULT_ENVIRONMENT_ID, "properties": properties}
    env.update(overrides)
    return env


ELEVATED_ROLES = ["Basic User", "Environment Maker", SYSTEM_ADMINISTRATOR]
UNELEVATED_ROLES = ["Basic User", "Environment Maker"]


ROOT_BUSINESS_UNIT = "65b61189-4a94-f011-b4cc-000d3a99ad6d"
CHILD_BUSINESS_UNIT = "11111111-2222-3333-4444-555555555555"


def role(role_id, business_unit, name=SYSTEM_ADMINISTRATOR):
    return {"roleid": role_id, "name": name, "_businessunitid_value": business_unit}


def test_given_a_bootstrap_app_user_when_torn_down_then_it_is_disabled_not_left_holding_the_role():
    """Deleting the Entra app does not remove its Dataverse user.

    The application user survives as an enabled System Administrator that no
    longer maps to any credential — inert, but indistinguishable from a live
    one to anyone reading the environment's user list.
    """
    assert disable_user_request() == {"isdisabled": True}


def test_given_an_odata_filter_with_spaces_then_the_url_is_encoded():
    """`urllib` refuses a URL with control characters, and OData wants %20.

    The role lookup filters on `name eq 'System Administrator'` — spaces and
    quotes both — so the query cannot be pasted together as a string.
    """
    url = odata_url(
        "https://org5dadb450.crm.dynamics.com/api/data/v9.2",
        "roles",
        {"$filter": "name eq 'System Administrator'", "$select": "roleid,name"},
    )

    assert " " not in url
    assert url.startswith(
        "https://org5dadb450.crm.dynamics.com/api/data/v9.2/roles?"
    )
    assert "%20" in url and "+" not in url


def test_given_a_bap_internal_error_when_registering_then_it_is_treated_as_propagation():
    """A freshly-created principal is not immediately visible to the BAP admin API.

    Registering it back-to-back answers `500 InternalServerError`, which is
    indistinguishable from a real fault except that it stops happening. The
    manual sequence only worked because minutes passed between the steps.
    """
    assert is_propagation_delay(500)


def test_given_a_refusal_when_registering_then_it_is_not_retried():
    """403 and 400 are answers, not delays — retrying them just wastes a minute."""
    assert not is_propagation_delay(403)
    assert not is_propagation_delay(400)


def test_given_a_role_per_business_unit_then_the_callers_business_unit_wins():
    """`System Administrator` is defined once per business unit, not once.

    Assigning the copy from another business unit is a different grant from the
    one the environment's settings answer to, so the name alone cannot pick it.
    """
    chosen = select_role(
        [
            role("aaaaaaaa-0000-0000-0000-000000000000", CHILD_BUSINESS_UNIT),
            role("6eb61189-4a94-f011-b4cc-000d3a99ad6d", ROOT_BUSINESS_UNIT),
        ],
        business_unit_id=ROOT_BUSINESS_UNIT,
    )

    assert chosen == "6eb61189-4a94-f011-b4cc-000d3a99ad6d"


def test_given_the_build_account_has_no_dataverse_user_then_selection_says_so():
    """An Entra account is not automatically a Dataverse user.

    An empty result is not "no role" — it is "no user to hold a role", and the
    role assignment would otherwise fail against a `None` id.
    """
    import pytest

    with pytest.raises(RuntimeError) as refusal:
        select_system_user([], "1d9e94c7-25c1-4fc5-9cd2-334052b43f47")

    assert "1d9e94c7" in str(refusal.value)


def test_given_one_dataverse_user_then_its_id_and_business_unit_are_returned():
    user_id, business_unit = select_system_user(
        [
            {
                "systemuserid": "a0456425-ad94-f011-b4cc-6045bdda641b",
                "_businessunitid_value": ROOT_BUSINESS_UNIT,
            }
        ],
        "1d9e94c7-25c1-4fc5-9cd2-334052b43f47",
    )

    assert user_id == "a0456425-ad94-f011-b4cc-6045bdda641b"
    assert business_unit == ROOT_BUSINESS_UNIT


def test_given_an_instance_url_with_a_trailing_slash_then_the_role_reference_is_well_formed():
    """`instanceUrl` comes back with a trailing slash; `@odata.id` must be absolute."""
    body = role_reference(
        "https://org5dadb450.crm.dynamics.com/",
        "6eb61189-4a94-f011-b4cc-000d3a99ad6d",
    )

    assert body == {
        "@odata.id": "https://org5dadb450.crm.dynamics.com/api/data/v9.2/"
        "roles(6eb61189-4a94-f011-b4cc-000d3a99ad6d)"
    }


def test_given_no_role_in_the_callers_business_unit_then_selection_fails_loudly():
    """Returning None here would surface as a confusing Dataverse 400 later."""
    import pytest

    with pytest.raises(RuntimeError) as refusal:
        select_role([role("aaaaaaaa-0000-0000-0000-000000000000",
                          CHILD_BUSINESS_UNIT)],
                    business_unit_id=ROOT_BUSINESS_UNIT)

    assert ROOT_BUSINESS_UNIT in str(refusal.value)


def test_given_the_bootstrap_app_when_registered_then_the_request_carries_both_identifiers():
    """The BAP admin API's `UserIdentity` needs the object id *and* the app id.

    Discovered by probing: `applicationId` is rejected as an unknown member,
    and the object id alone is rejected as `MissingServicePrincipalAppId`. Two
    identifiers for one principal is unintuitive enough to be worth pinning.
    """
    body = app_user_request(
        sp_object_id="b55310d0-8d9f-4662-b725-dfbf43670528",
        app_id="4e8a27ff-70a4-4ad4-ba5b-75fbc3b35f21",
    )

    assert body == {
        "objectId": "b55310d0-8d9f-4662-b725-dfbf43670528",
        "servicePrincipalAppId": "4e8a27ff-70a4-4ad4-ba5b-75fbc3b35f21",
    }


def test_given_the_default_environment_and_the_admin_role_when_evaluated_then_verdict_passes():
    verdict = evaluate(environment(), ELEVATED_ROLES)

    assert verdict.ok


def test_given_only_maker_roles_when_evaluated_then_only_the_admin_role_check_fails():
    verdict = evaluate(environment(), UNELEVATED_ROLES)

    assert not verdict.ok
    assert not verdict.check("system-administrator-role").ok
    assert verdict.check("default-environment-identity").ok
    assert verdict.check("dataverse-provisioned").ok
    assert "Environment Maker" in verdict.check("system-administrator-role").detail


DEVELOPER_ENVIRONMENT = {
    "name": "e7c1f0b2-1111-2222-3333-444455556666",
    "properties": {
        "displayName": "Brad Stevens' Environment",
        "isDefault": False,
        "environmentSku": "Developer",
        "linkedEnvironmentMetadata": {
            "instanceUrl": "https://orgdev1234.crm.dynamics.com/",
            "instanceState": "Ready",
        },
    },
}


def test_given_a_developer_environment_beside_the_default_one_then_the_default_is_selected():
    selected = default_environment([DEVELOPER_ENVIRONMENT, environment()])

    assert selected["name"] == DEFAULT_ENVIRONMENT_ID


def test_given_a_personal_developer_environment_when_evaluated_then_identity_fails_naming_the_cap():
    verdict = evaluate(DEVELOPER_ENVIRONMENT, ELEVATED_ROLES)

    identity = verdict.check("default-environment-identity")
    assert not identity.ok
    assert "Developer" in identity.detail
    assert "10 requests/minute" in identity.detail


def test_given_a_passing_verdict_when_reported_then_the_search_setting_reads_as_changeable():
    report = format_report(evaluate(environment(), ELEVATED_ROLES))

    assert "PASS" in report
    assert "Dataverse search" in report
    assert "can be changed" in report


def test_given_the_role_is_missing_when_reported_then_the_elevation_method_is_repeatable():
    report = format_report(evaluate(environment(), UNELEVATED_ROLES))

    assert "cannot be changed" in report
    assert "bootstrap application user" in report
    assert "--elevate" in report
    # No interactive consent: an operator told to sign in would sign in forever.
    assert "az login" not in report


def test_given_the_environment_is_not_the_default_one_when_reported_then_no_elevation_is_offered():
    report = format_report(evaluate(DEVELOPER_ENVIRONMENT, UNELEVATED_ROLES))

    assert "az login" not in report
    assert "wrong environment" in report


def reader(*states):
    """A `read_tenant` returning each (environment, roles) state in turn."""
    remaining = list(states)

    def read_tenant(observed_environment_id=None):
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    return read_tenant


def test_given_the_role_is_held_when_main_runs_then_it_exits_zero():
    assert main([], read_tenant=reader((environment(), ELEVATED_ROLES))) == 0


def test_given_the_role_is_missing_when_main_runs_without_elevate_then_it_exits_non_zero():
    assert main([], read_tenant=reader((environment(), UNELEVATED_ROLES))) == 1


class Elevator:
    """A stand-in for the live elevation, recording which environment it was given.

    It takes the whole environment, not just its identifier: the bootstrap
    application user is registered against the environment but assigns the role
    through that environment's own Dataverse instance.
    """

    def __init__(self, raises=None):
        self.calls = []
        self.raises = raises

    def __call__(self, environment):
        self.calls.append(environment["name"])
        if self.raises is not None:
            raise self.raises
        return {"elevated": "1d9e94c7-25c1-4fc5-9cd2-334052b43f47"}


def test_given_elevate_when_the_role_is_missing_then_it_elevates_and_rechecks():
    elevator = Elevator()

    exit_code = main(
        ["--elevate"],
        read_tenant=reader(
            (environment(), UNELEVATED_ROLES), (environment(), ELEVATED_ROLES)
        ),
        elevate=elevator,
    )

    assert elevator.calls == [DEFAULT_ENVIRONMENT_ID]
    assert exit_code == 0


def test_given_elevate_against_the_wrong_environment_then_it_refuses_to_elevate():
    elevator = Elevator()

    exit_code = main(
        ["--elevate"],
        read_tenant=reader((DEVELOPER_ENVIRONMENT, UNELEVATED_ROLES)),
        elevate=elevator,
    )

    assert elevator.calls == []
    assert exit_code == 1


def test_given_elevate_when_the_scope_is_unreachable_then_the_working_route_is_reported(capsys):
    # elevate_live raises the classified message, so the double raises one too.
    elevator = Elevator(
        raises=RuntimeError(
            elevation_error(403, '{"code":"InsufficientDelegatedPermissions"}')
        )
    )

    exit_code = main(
        ["--elevate"],
        read_tenant=reader((environment(), UNELEVATED_ROLES)),
        elevate=elevator,
    )

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "bootstrap application user" in out
    assert "az login" not in out


def test_given_dataverse_is_not_ready_when_evaluated_then_roles_read_as_unread_not_empty():
    provisioning = environment(
        properties={
            "linkedEnvironmentMetadata": {
                "instanceUrl": "https://org5dadb450.crm.dynamics.com/",
                "instanceState": "Provisioning",
            }
        }
    )

    verdict = evaluate(provisioning, None)

    assert not verdict.check("dataverse-provisioned").ok
    assert "not read" in verdict.check("system-administrator-role").detail
    assert "Nothing to elevate" in format_report(verdict)


def test_given_a_missing_scope_when_elevation_fails_then_it_is_not_offered_as_a_consent_step():
    """A missing scope and an unreachable one look identical from a 403.

    `UserManagement.Users.Apply` is unreachable to the Azure CLI whatever the
    tenant consents to, so this classification must not send an operator to a
    sign-in that cannot succeed.
    """
    message = elevation_error(
        403,
        '{"code":"Forbidden","innererror":{"code":"InsufficientDelegatedPermissions",'
        '"message":"Application missing required delegated permissions: '
        '[UserManagement.Users.Apply, All.All.ReadWrite]"}}',
    )

    assert "az login" not in message
    assert "bootstrap application user" in message


def test_given_first_party_preauthorization_is_missing_then_the_error_names_the_dead_end():
    """AADSTS65002 is the wall the consent remedy was recorded against.

    Consent between two Microsoft first-party applications is configured by the
    API owner, not by a tenant admin, so no amount of signing in adds
    `UserManagement.Users.Apply` to an Azure CLI token. An operator who reads
    "consent to the scope" here would sign in forever.
    """
    message = elevation_error(
        400,
        "AADSTS65002: Consent between first party application "
        "'04b07795-8ddb-461a-bbee-02f9e1bf7b46' and first party resource "
        "'8578e004-a5c6-46e7-913e-12f58912df43' must be configured via "
        "preauthorization",
    )

    assert "preauthoris" in message or "preauthoriz" in message
    assert "az login" not in message
    assert "bootstrap application user" in message


def test_given_the_caller_is_not_a_tenant_admin_when_elevation_fails_then_no_consent_is_offered():
    message = elevation_error(
        403,
        "Unable to assign System Administrator security role as the user is not "
        "either a Global admin, Power Platform admin, or Dynamics 365 admin.",
    )

    assert "az login" not in message
    assert "Global admin" in message


def test_given_the_environment_seen_in_the_copilot_studio_url_then_that_one_is_read():
    selected = select_environment(
        [DEVELOPER_ENVIRONMENT, environment()], DEVELOPER_ENVIRONMENT["name"]
    )

    assert selected["name"] == DEVELOPER_ENVIRONMENT["name"]


def test_given_no_observed_environment_then_the_tenants_default_one_is_read():
    selected = select_environment([DEVELOPER_ENVIRONMENT, environment()], None)

    assert selected["name"] == DEFAULT_ENVIRONMENT_ID


def test_given_an_observed_environment_the_tenant_does_not_have_then_identity_fails():
    selected = select_environment([environment()], "9f0dc0de-dead-beef-cafe-000000000000")

    identity = evaluate(selected, ELEVATED_ROLES).check("default-environment-identity")
    assert not identity.ok
    assert "9f0dc0de" in identity.detail


def test_given_an_observed_environment_argument_when_main_runs_then_it_is_passed_to_the_read():
    asked = []

    def read_tenant(observed_environment_id=None):
        asked.append(observed_environment_id)
        return DEVELOPER_ENVIRONMENT, UNELEVATED_ROLES

    exit_code = main(
        ["--environment", DEVELOPER_ENVIRONMENT["name"]], read_tenant=read_tenant
    )

    assert asked == [DEVELOPER_ENVIRONMENT["name"]]
    assert exit_code == 1


def test_given_the_caller_cannot_self_elevate_when_main_runs_then_no_consent_is_offered(capsys):
    elevator = Elevator(
        raises=RuntimeError(
            "HTTP 403: only a Global admin, Power Platform admin or Dynamics 365 "
            "admin can self-elevate."
        )
    )

    main(
        ["--elevate"],
        read_tenant=reader((environment(), UNELEVATED_ROLES)),
        elevate=elevator,
    )

    out = capsys.readouterr().out
    assert "can self-elevate" in out
    assert "az login" not in out
