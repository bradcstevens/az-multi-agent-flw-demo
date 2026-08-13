#!/usr/bin/env python3
"""Preflight: does the build account hold Dataverse System Administrator in the
Default environment?

Power Platform administrators are no longer automatically granted the System
Administrator role in the Default environment, so tenant-level admin membership
does not answer this question — the environment's own security-role list does,
and that is a different API. The role matters because the environment-level
Dataverse search setting cannot be changed without it (#3).

`evaluate` is pure: it takes the Default environment as the admin API returns it
and the build account's Dataverse security roles, and returns a `Verdict`. The
live calls are in `main`.

`--elevate` grants the role through a Bootstrap application user rather than
Microsoft's documented `applyAdminRole`, which the Azure CLI cannot obtain a
token for at all (see ELEVATION_INSTRUCTIONS below).
"""

DEFAULT_ENVIRONMENT_ID = "Default-0f87abfb-0840-4199-96b7-1882c01a998b"
SYSTEM_ADMINISTRATOR = "System Administrator"
READY = "Ready"
DATAVERSE_API_VERSION = "v9.2"

# Why the identity check exists at all: a maker who follows a Copilot Studio URL
# without an explicit environment can be routed into their personal Developer
# environment, whose generative-AI-message quota is 10 requests/minute against
# the Default environment's 100 (see docs/preflight/copilot-studio-payg-meter.md).
# Work done there is invisible to the demo and silently rate-capped.
DEVELOPER_REDIRECT_HAZARD = (
    "a personal Developer environment is capped at 10 requests/minute and is "
    "not the environment this build provisions"
)

POWER_PLATFORM_API = "https://api.powerplatform.com"
ELEVATION_SCOPE = f"{POWER_PLATFORM_API}/UserManagement.Users.Apply"

# The elevation route that works unattended (issue #2). Named here because the
# report, the error classification and the live steps all have to agree on it.
BOOTSTRAP_APPLICATION_USER = "bootstrap application user"


class Check:
    """One named precondition and whether the observed tenant state meets it."""

    def __init__(self, name, ok, detail):
        self.name = name
        self.ok = ok
        self.detail = detail


class Verdict:
    """The outcome of every check, and whether they all passed."""

    def __init__(self, checks):
        self.checks = checks

    @property
    def ok(self):
        return all(check.ok for check in self.checks)

    def check(self, name):
        """Return the named `Check`."""
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)


def evaluate(environment, roles, expected_environment_id=DEFAULT_ENVIRONMENT_ID):
    """Return the `Verdict` for the Default environment and its roles. Pure."""
    return Verdict(
        [
            _identity_check(environment, expected_environment_id),
            _dataverse_check(environment),
            _admin_role_check(roles),
        ]
    )


def _identity_check(environment, expected_environment_id):
    observed = (environment or {}).get("name")
    if observed == expected_environment_id:
        return Check(
            "default-environment-identity",
            True,
            f"the tenant's Default environment is {observed!r}",
        )
    return Check(
        "default-environment-identity",
        False,
        f"the environment read is {observed!r} "
        f"(SKU {_sku(environment)!r}), not the expected "
        f"{expected_environment_id!r} — {DEVELOPER_REDIRECT_HAZARD}",
    )


def _sku(environment):
    return ((environment or {}).get("properties") or {}).get("environmentSku")


def default_environment(environments):
    """Return the tenant's Default environment, or None. Pure.

    Default-environment routing can silently land a maker in a personal
    Developer environment, so the environment is selected by the admin API's
    `isDefault` flag rather than by whatever a Copilot Studio URL happened to
    carry.
    """
    for environment in environments:
        if (environment.get("properties") or {}).get("isDefault"):
            return environment
    return None


def select_environment(environments, observed_environment_id=None):
    """Return the environment to check. Pure.

    With no observation, the tenant's Default environment is the subject. When
    the operator passes the environment identifier **shown in the Copilot
    Studio URL**, that one is the subject instead — otherwise the check would
    answer a question nobody asked, confirming the Default environment while the
    maker sits in a personal Developer environment. An identifier the tenant
    does not have is returned as-is so the identity check fails on it by name.
    """
    if observed_environment_id is None:
        return default_environment(environments)
    for environment in environments:
        if environment.get("name") == observed_environment_id:
            return environment
    return {"name": observed_environment_id, "properties": {}}


def is_ready(environment):
    """True when the environment has a Dataverse instance to read roles from."""
    return _metadata(environment).get("instanceState") == READY


def _dataverse_check(environment):
    metadata = _metadata(environment)
    state = metadata.get("instanceState")
    return Check(
        "dataverse-provisioned",
        bool(metadata.get("instanceUrl")) and state == READY,
        f"Dataverse instance {metadata.get('instanceUrl')} is {state}",
    )


def _admin_role_check(roles):
    if roles is None:
        return Check(
            "system-administrator-role",
            False,
            "the environment's security roles were not read — an unread role "
            "list is not an empty one",
        )
    return Check(
        "system-administrator-role",
        SYSTEM_ADMINISTRATOR in roles,
        f"the build account's Dataverse security roles are {sorted(roles)}",
    )


def _metadata(environment):
    return ((environment or {}).get("properties") or {}).get(
        "linkedEnvironmentMetadata"
    ) or {}


def instance_url(environment):
    """Return the environment's Dataverse instance URL, or None. Pure."""
    return _metadata(environment).get("instanceUrl")


def format_report(verdict, remedy=None):
    """Return the human-readable report for a `Verdict`. Pure.

    The consequence — whether the environment-level Dataverse search setting
    (#3) can be changed — is derived from the verdict rather than stated
    unconditionally, because it is a consequence of holding the role and not an
    independent fact. An explicit `remedy` replaces the derived one, so a
    refusal that already carries its own next step is not contradicted by a
    generic one.
    """
    lines = [
        f"  {'PASS' if c.ok else 'FAIL'}  {c.name}: {c.detail}"
        for c in verdict.checks
    ]
    consequence = (
        "the environment-level Dataverse search setting can be changed"
        if verdict.ok
        else "the environment-level Dataverse search setting cannot be changed"
    )
    lines.append(f"  ----  Dataverse search (#3): {consequence}")
    if not verdict.ok:
        lines.append(remedy if remedy is not None else _remedy(verdict))
    return "\n".join(lines)


def _remedy(verdict):
    """Return the operator's next step for a failing verdict. Pure.

    Elevating into the *wrong* environment would be worse than not elevating —
    a Developer environment is rate-capped and invisible to the demo — so the
    elevation is only offered once the environment's identity is confirmed.
    """
    if not verdict.check("default-environment-identity").ok:
        return (
            "\nRemedy: wrong environment — do not elevate here. Re-run against "
            f"the tenant's Default environment ({DEFAULT_ENVIRONMENT_ID})."
        )
    if not verdict.check("dataverse-provisioned").ok:
        return (
            "\nRemedy: the environment has no ready Dataverse instance, so it "
            "has no security roles to hold. Nothing to elevate."
        )
    return ELEVATION_INSTRUCTIONS


# The recorded elevation method (issue #2), and why it is not Microsoft's
# documented self-elevation. `applyAdminRole` on the Power Platform API elevates
# the *calling user* and so needs a user token carrying
# UserManagement.Users.Apply — a scope the Azure CLI can never carry, because
# consent between two Microsoft first-party applications is configured by the API
# owner (preauthorisation), not by a tenant admin. Signing in does not help.
#
# What does work is a Bootstrap application user: an Entra app registration that
# the BAP admin API registers as a Dataverse application user *with* System
# Administrator, which then assigns the role to the build account and is deleted.
# It needs no user token beyond the tenant-admin one the Azure CLI already holds
# for the BAP admin API, so it runs unattended.
ELEVATION_INSTRUCTIONS = f"""
Remedy — elevate via a {BOOTSTRAP_APPLICATION_USER} (Global / Power Platform /
Dynamics 365 admin only). No interactive consent; re-runnable:

  scripts/preflight/check-dataverse-admin-role.sh --elevate
"""

# The ways elevation says no. They have different remedies, so a bare
# "403 Forbidden" is not enough for an operator to act on.
MISSING_SCOPE = "InsufficientDelegatedPermissions"
NOT_A_TENANT_ADMIN = "Global admin"
FIRST_PARTY_PREAUTHORISATION = "AADSTS65002"


def disable_user_request():
    """Return the patch that retires a Dataverse application user. Pure.

    Dataverse does not delete system users, so the bootstrap principal's user
    record outlives the Entra app registration that gave it meaning. Disabling
    is what stops it appearing as a live System Administrator.
    """
    return {"isdisabled": True}


def odata_url(base, entity, params):
    """Return an encoded Dataverse query URL. Pure.

    OData filters carry spaces and quotes (`name eq 'System Administrator'`),
    which `urllib` rejects outright as control characters in a URL. Percent
    encoding — not `+` — is what Dataverse reads back as a space.
    """
    from urllib.parse import quote, urlencode

    query = urlencode(params, quote_via=quote, safe="")
    return f"{base}/{entity}?{query}"


def is_propagation_delay(status):
    """True when a refusal is Entra propagation rather than an answer. Pure.

    A service principal created a moment ago is not yet visible to the BAP admin
    API, which answers `500 InternalServerError` rather than "not found". A 4xx
    is a decision — retrying it only spends a minute to hear the same thing.
    """
    return status >= 500


def select_system_user(users, object_id):
    """Return `(systemuserid, business unit id)` for an Entra object id. Pure.

    An Entra account is not automatically a Dataverse user, and an empty result
    means "no user to hold a role" rather than "no role" — a distinction that is
    invisible once a `None` id reaches the assignment call.
    """
    if len(users) != 1:
        raise RuntimeError(
            f"expected exactly one Dataverse user for Entra object {object_id}; "
            f"found {len(users)}"
        )
    return users[0]["systemuserid"], users[0]["_businessunitid_value"]


def role_reference(instance_url, role_id):
    """Return the `$ref` body associating a role with a user. Pure.

    `@odata.id` must be an absolute URL, and `instanceUrl` arrives with a
    trailing slash, so the join is not a concatenation.
    """
    base = f"{instance_url.rstrip('/')}/api/data/{DATAVERSE_API_VERSION}"
    return {"@odata.id": f"{base}/roles({role_id})"}


def select_role(roles, business_unit_id):
    """Return the id of `System Administrator` in `business_unit_id`. Pure.

    Dataverse defines the role once per business unit, so the name does not
    identify it. Assigning the copy from another business unit is a different
    grant from the one the environment's settings answer to.
    """
    named = [r for r in roles if r.get("name") == SYSTEM_ADMINISTRATOR]
    in_unit = [
        r for r in named if r.get("_businessunitid_value") == business_unit_id
    ]
    if len(in_unit) == 1:
        return in_unit[0]["roleid"]
    raise RuntimeError(
        f"expected exactly one {SYSTEM_ADMINISTRATOR!r} role in business unit "
        f"{business_unit_id}; found {len(in_unit)} of {len(named)} by that name"
    )


def app_user_request(sp_object_id, app_id):
    """Return the BAP admin API's `UserIdentity` for `addAppUser`. Pure.

    The endpoint wants *both* identifiers of the same principal: the service
    principal's directory object id and the application's client id. Sending
    `applicationId` is rejected as an unknown member of `UserIdentity`, and
    sending the object id alone is rejected as `MissingServicePrincipalAppId`.
    """
    return {"objectId": sp_object_id, "servicePrincipalAppId": app_id}


def elevation_error(status, body):
    """Return a readable message for a failed elevation. Pure."""
    if FIRST_PARTY_PREAUTHORISATION in body or MISSING_SCOPE in body:
        return (
            f"HTTP {status}: the Power Platform API's {ELEVATION_SCOPE} scope is "
            "reserved by first-party preauthorisation, so no sign-in can add it "
            f"to an Azure CLI token. {ELEVATION_INSTRUCTIONS}"
        )
    if NOT_A_TENANT_ADMIN in body:
        return (
            f"HTTP {status}: only a Global admin, Power Platform admin or "
            "Dynamics 365 admin can elevate. Ask a tenant admin to grant "
            f"{SYSTEM_ADMINISTRATOR} in {DEFAULT_ENVIRONMENT_ID}."
        )
    return f"HTTP {status}: {body}"


# ---------------------------------------------------------------------------
# Live reads. Everything above this line is pure.
# ---------------------------------------------------------------------------

BAP_API = "https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform"
BAP_RESOURCE = "https://api.bap.microsoft.com/"
BAP_API_VERSION = "2020-10-01"
# The bootstrap app registration's display name. Deliberately identifiable: if a
# run dies between creating it and deleting it, the leftover is obvious.
BOOTSTRAP_APP_NAME = "flw-dataverse-bootstrap"

# Nothing about a freshly-created Entra principal is usable immediately: the BAP
# admin API cannot see it, and its client secret is refused, for the first tens
# of seconds. Both are waited out rather than reported as failures.
PROPAGATION_ATTEMPTS = 8
PROPAGATION_DELAY_SECONDS = 10


def _token(resource):
    """Return an access token for `resource` from the signed-in Azure CLI."""
    import subprocess

    result = subprocess.run(
        ["az", "account", "get-access-token", "--resource", resource,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"could not get a token for {resource}; run:\n"
            f"  az login --scope \"{resource}/.default\"\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _get(url, resource, token=None):
    import json
    import urllib.request

    request = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + (token or _token(resource))},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def read_tenant_live(observed_environment_id=None):
    """Return (the environment under check, the build account's Dataverse roles).

    Roles are read from the *environment's own* security-role list, not from
    Power Platform admin centre membership — tenant admin membership no longer
    implies the role, which is the whole reason this check exists.

    The role read is skipped unless the Dataverse instance is `Ready`: a
    provisioning instance answers `WhoAmI` with an error, and crashing there
    would lose the verdict that says there is nothing to elevate yet.
    """
    environments = _get(
        f"{BAP_API}/scopes/admin/environments?api-version=2020-10-01",
        "https://api.bap.microsoft.com/",
    )["value"]
    environment = select_environment(environments, observed_environment_id)
    if not is_ready(environment):
        return environment, None
    return environment, read_roles_live(instance_url(environment))


def read_roles_live(url):
    """Return the signed-in user's Dataverse security role names."""
    base = f"{url.rstrip('/')}/api/data/{DATAVERSE_API_VERSION}"
    resource = f"{url.rstrip('/')}/"
    user_id = _get(f"{base}/WhoAmI", resource)["UserId"]
    roles = _get(
        f"{base}/systemusers({user_id})/systemuserroles_association?$select=name",
        resource,
    )["value"]
    return [role["name"] for role in roles]


def _az(args, redact=False):
    """Run an `az` command and return its stdout."""
    import subprocess

    result = subprocess.run(
        ["az", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        shown = args[0] if redact else " ".join(args)
        raise RuntimeError(f"az {shown} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _post(url, resource, body, token=None):
    """POST JSON and return the decoded response, classifying refusals."""
    import json
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": "Bearer " + (token or _token(resource)),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            elevation_error(error.code, error.read().decode())
        ) from error


def _create_bootstrap_app():
    """Create the short-lived app registration, its principal and a secret."""
    app_id = _az([
        "ad", "app", "create", "--display-name", BOOTSTRAP_APP_NAME,
        "--sign-in-audience", "AzureADMyOrg", "--query", "appId", "-o", "tsv",
    ])
    sp_object_id = _az([
        "ad", "sp", "create", "--id", app_id, "--query", "id", "-o", "tsv",
    ])
    secret = _az([
        "ad", "app", "credential", "reset", "--id", app_id, "--append",
        "--years", "1", "--query", "password", "-o", "tsv",
    ], redact=True)
    return {"app_id": app_id, "sp_object_id": sp_object_id, "secret": secret}


def _patch(url, resource, body, token=None):
    """PATCH JSON, classifying refusals the same way `_post` does."""
    import json
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={
            "Authorization": "Bearer " + (token or _token(resource)),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            response.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            elevation_error(error.code, error.read().decode())
        ) from error


def _retire_bootstrap(app, url):
    """Delete the bootstrap app registration and retire its Dataverse user.

    Teardown is unconditional and does both halves: the granted role outlives
    the bootstrap, so leaving a standing System Administrator behind would be a
    worse end state than the one this set out to repair. Deleting the Entra app
    alone is not enough — Dataverse keeps the application user, still enabled
    and still a System Administrator, merely with no credential left to use it.

    Disabling runs as the signed-in admin rather than as the bootstrap
    principal, which cannot disable itself and stay alive long enough to finish.
    """
    app_user = _find_app_user(url, app["app_id"])
    _az(["ad", "app", "delete", "--id", app["app_id"]])
    if app_user:
        _patch(
            f"{url.rstrip('/')}/api/data/{DATAVERSE_API_VERSION}"
            f"/systemusers({app_user})",
            f"{url.rstrip('/')}/",
            disable_user_request(),
        )


def _find_app_user(url, app_id):
    """Return the Dataverse user id for an application id, or None."""
    base = f"{url.rstrip('/')}/api/data/{DATAVERSE_API_VERSION}"
    found = _get(
        odata_url(base, "systemusers", {
            "$filter": f"applicationid eq {app_id}",
            "$select": "systemuserid",
        }),
        f"{url.rstrip('/')}/",
    )["value"]
    return found[0]["systemuserid"] if found else None


def _app_token(app, resource):
    """Return an app-only token, waiting out client-secret propagation.

    A secret is not usable the instant it is created; the first
    client-credentials request after `az ad app credential reset` is refused
    while it propagates, which is indistinguishable from a wrong secret except
    that it stops happening.
    """
    import json
    import time
    import urllib.error
    import urllib.parse
    import urllib.request

    tenant_id = _az(["account", "show", "--query", "tenantId", "-o", "tsv"])
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    form = urllib.parse.urlencode({
        "client_id": app["app_id"],
        "client_secret": app["secret"],
        "scope": f"{resource}.default",
        "grant_type": "client_credentials",
    }).encode()

    refusal = ""
    for attempt in range(PROPAGATION_ATTEMPTS):
        if attempt:
            time.sleep(PROPAGATION_DELAY_SECONDS)
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, data=form, method="POST")
            ) as response:
                return json.loads(response.read().decode())["access_token"]
        except urllib.error.HTTPError as error:
            refusal = error.read().decode()
    raise RuntimeError(
        f"the bootstrap application's credential never became usable: {refusal}"
    )


def _register_app_user(environment_id, app):
    """Register the bootstrap principal as a Dataverse System Administrator.

    The BAP admin API grants the role itself, which is the whole point: it is
    reachable with the tenant-admin token the Azure CLI already holds, whereas
    the Dataverse side refuses to assign the role at all (`prvAssignRole`).
    """
    import time
    import urllib.error

    url = (
        f"{BAP_API}/scopes/admin/environments/{environment_id}"
        f"/addAppUser?api-version={BAP_API_VERSION}"
    )
    body = app_user_request(app["sp_object_id"], app["app_id"])
    for attempt in range(PROPAGATION_ATTEMPTS):
        if attempt:
            time.sleep(PROPAGATION_DELAY_SECONDS)
        try:
            return _post(url, BAP_RESOURCE, body)
        except RuntimeError as refusal:
            status = getattr(refusal.__cause__, "code", None)
            if not isinstance(
                refusal.__cause__, urllib.error.HTTPError
            ) or not is_propagation_delay(status):
                raise
            last = refusal
    raise last


def _assign_system_administrator(url, token, object_id):
    """Assign System Administrator to an Entra principal, as the bootstrap app."""
    base = f"{url.rstrip('/')}/api/data/{DATAVERSE_API_VERSION}"
    resource = f"{url.rstrip('/')}/"
    users = _get(
        odata_url(base, "systemusers", {
            "$filter": f"azureactivedirectoryobjectid eq {object_id}",
            "$select": "systemuserid,_businessunitid_value",
        }),
        resource,
        token=token,
    )["value"]
    user_id, business_unit_id = select_system_user(users, object_id)
    roles = _get(
        odata_url(base, "roles", {
            "$filter": f"name eq '{SYSTEM_ADMINISTRATOR}'",
            "$select": "roleid,name,_businessunitid_value",
        }),
        resource,
        token=token,
    )["value"]
    _post(
        f"{base}/systemusers({user_id})/systemuserroles_association/$ref",
        resource,
        role_reference(url, select_role(roles, business_unit_id)),
        token=token,
    )


def elevate_live(environment):
    """Grant the signed-in user System Administrator via a bootstrap app user.

    Microsoft's documented self-elevation (`applyAdminRole` on the Power
    Platform API) is unreachable from here: it elevates the calling user and so
    needs a user token carrying `UserManagement.Users.Apply`, a scope the Azure
    CLI is not preauthorised for — and consent between two first-party
    applications is the API owner's to give, not a tenant admin's
    (AADSTS65002). No sign-in can obtain it.

    So the role is granted by something that already holds it. The BAP admin
    API registers a fresh app registration as a Dataverse application user
    *with* System Administrator; that principal has `prvAssignRole`, so it
    assigns the role to the signed-in user, and is then deleted.
    """
    environment_id = environment["name"]
    url = instance_url(environment)
    object_id = _az(["ad", "signed-in-user", "show", "--query", "id", "-o", "tsv"])

    app = _create_bootstrap_app()
    try:
        _register_app_user(environment_id, app)
        token = _app_token(app, f"{url.rstrip('/')}/")
        _assign_system_administrator(url, token, object_id)
    finally:
        _retire_bootstrap(app, url)
    return {"elevated": object_id, "environment": environment_id}


def main(argv=None, read_tenant=read_tenant_live, elevate=elevate_live):
    import sys

    argv = sys.argv[1:] if argv is None else argv
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    observed = _argument(argv, "--environment")

    environment, roles = read_tenant(observed)
    verdict = evaluate(environment, roles)
    remedy = None

    if "--elevate" in argv and _elevatable(verdict):
        try:
            elevate(environment)
        except Exception as error:  # noqa: BLE001 — reported, not swallowed
            # The refusal already carries the remedy that fits it, and it is not
            # always the consent step — offering both would contradict itself.
            remedy = f"\nElevation was refused. {error}"
        else:
            print(f"granted {SYSTEM_ADMINISTRATOR} in {environment['name']}")
            environment, roles = read_tenant(observed)
            verdict = evaluate(environment, roles)

    print("\nDataverse System Administrator — Default environment")
    print(format_report(verdict, remedy=remedy))
    return 0 if verdict.ok else 1


def _argument(argv, name):
    """Return the value following `name` in `argv`, or None."""
    if name in argv:
        position = argv.index(name) + 1
        if position < len(argv):
            return argv[position]
    return None


def _elevatable(verdict):
    """True when elevation is the right next step for this verdict. Pure.

    Elevating into a Developer environment the maker was silently routed into
    would grant the role somewhere the demo never runs, so identity and a ready
    Dataverse instance are both preconditions.
    """
    return (
        not verdict.check("system-administrator-role").ok
        and verdict.check("default-environment-identity").ok
        and verdict.check("dataverse-provisioned").ok
    )


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
