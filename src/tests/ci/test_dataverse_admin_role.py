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
    default_environment,
    evaluate,
    elevation_error,
    format_report,
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
    assert "az login" in report
    assert "https://api.powerplatform.com/UserManagement.Users.Apply" in report
    assert "--elevate" in report


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
    """A stand-in for the live self-elevation call, recording what it was asked."""

    def __init__(self, raises=None):
        self.calls = []
        self.raises = raises

    def __call__(self, environment_id):
        self.calls.append(environment_id)
        if self.raises is not None:
            raise self.raises
        return {"Code": "UserExists"}


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


def test_given_elevate_when_the_token_lacks_the_scope_then_the_remedy_is_reported(capsys):
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
    assert "az login" in capsys.readouterr().out


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


def test_given_a_missing_scope_when_elevation_fails_then_the_error_names_the_consent_step():
    message = elevation_error(
        403,
        '{"code":"Forbidden","innererror":{"code":"InsufficientDelegatedPermissions",'
        '"message":"Application missing required delegated permissions: '
        '[UserManagement.Users.Apply, All.All.ReadWrite]"}}',
    )

    assert "az login" in message


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
