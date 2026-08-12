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
"""

DEFAULT_ENVIRONMENT_ID = "Default-0f87abfb-0840-4199-96b7-1882c01a998b"
SYSTEM_ADMINISTRATOR = "System Administrator"
READY = "Ready"

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


# The recorded elevation method (issue #2). Self-elevation goes through the
# Power Platform API's applyAdminRole, which requires a *user* token carrying
# the UserManagement.Users.Apply delegated scope — the Azure CLI is
# pre-authorised for EnvironmentManagement.Environments.Read and
# CopilotStudio.Copilots.Test but not for this one, so the scope has to be
# consented interactively once. The caller must be a Global, Power Platform or
# Dynamics 365 admin; no other Entra role can self-elevate.
ELEVATION_INSTRUCTIONS = f"""
Remedy — self-elevate to {SYSTEM_ADMINISTRATOR} (Global / Power Platform /
Dynamics 365 admin only). One interactive consent, then a re-runnable step:

  az login --scope "{ELEVATION_SCOPE}"
  scripts/preflight/check-dataverse-admin-role.sh --elevate
"""

# The two ways applyAdminRole says no. They have opposite remedies, so a bare
# "403 Forbidden" is not enough for an operator to act on.
MISSING_SCOPE = "InsufficientDelegatedPermissions"
NOT_A_TENANT_ADMIN = "Global admin"


def elevation_error(status, body):
    """Return a readable message for a failed self-elevation. Pure."""
    if MISSING_SCOPE in body:
        return (
            f"HTTP {status}: the token does not carry {ELEVATION_SCOPE}. "
            f"{ELEVATION_INSTRUCTIONS}"
        )
    if NOT_A_TENANT_ADMIN in body:
        return (
            f"HTTP {status}: only a Global admin, Power Platform admin or "
            "Dynamics 365 admin can self-elevate. Ask a tenant admin to grant "
            f"{SYSTEM_ADMINISTRATOR} in {DEFAULT_ENVIRONMENT_ID}."
        )
    return f"HTTP {status}: {body}"


# ---------------------------------------------------------------------------
# Live reads. Everything above this line is pure.
# ---------------------------------------------------------------------------

BAP_API = "https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform"
DATAVERSE_API_VERSION = "v9.2"
ELEVATION_API_VERSION = "2022-03-01-preview"


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


def _get(url, resource):
    import json
    import urllib.request

    request = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {_token(resource)}"}
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


def elevate_live(environment_id):
    """Self-elevate the signed-in user to System Administrator.

    The documented Power Platform API path — see
    https://learn.microsoft.com/power-platform/admin/manage-high-privileged-admin-roles.
    Returns the response body; raises if the token lacks the scope.
    """
    import json
    import urllib.error
    import urllib.request

    url = (
        f"{POWER_PLATFORM_API}/usermanagement/environments/{environment_id}"
        f"/user/applyAdminRole?api-version={ELEVATION_API_VERSION}"
    )
    request = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={
            "Authorization": f"Bearer {_token(f'{POWER_PLATFORM_API}/')}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode() or "{}"
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            elevation_error(error.code, error.read().decode())
        ) from error
    return json.loads(body)


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
            elevate(environment["name"])
        except Exception as error:  # noqa: BLE001 — reported, not swallowed
            # The refusal already carries the remedy that fits it, and it is not
            # always the consent step — offering both would contradict itself.
            remedy = f"\nSelf-elevation was refused. {error}"
        else:
            print(f"self-elevated in {environment['name']}")
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
