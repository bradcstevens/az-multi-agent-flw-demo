#!/usr/bin/env python3
"""Preflight: does the Default environment's Copilot Studio meter bill
pay-as-you-go?

Pay-as-you-go on a **Default environment** is undocumented — the Power Platform
docs name only production and sandbox environments — so the meter cannot be
assumed to be live just because a billing plan exists in the tenant. This module
turns that question into a re-runnable verdict.

`evaluate` is pure: it takes the licensing API's billing policies and the Default
environment's id and returns a `Verdict`. The live calls are in `main`.
"""

COPILOT_STUDIO_ENTITLEMENT_ID = "MCSMessages"


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


ACTIVE_STATUS = "Enabled"


def evaluate(policies, default_environment_id):
    """Return the `Verdict` for a tenant's billing policies. Pure.

    The checks narrow progressively — active plans, then those carrying the
    meter, then those covering the Default environment, then those that can
    bill Azure. So a passing verdict means **one** plan satisfies all four
    conditions, not that four plans each satisfy one.
    """
    active = [p for p in policies if p.get("status") == ACTIVE_STATUS]
    metered = [p for p in active if _is_metered(p)]
    covering = [
        p for p in metered if default_environment_id in p.get("environmentIds", [])
    ]
    billable = [p for p in covering if _instrument_of(p)]
    return Verdict(
        [
            _active_plan_check(active),
            _meter_check(metered),
            _linked_check(covering, metered, default_environment_id),
            _instrument_check(billable, covering),
        ]
    )


def _instrument_check(billable, covering):
    if billable:
        policy = billable[0]
        instrument = _instrument_of(policy)
        return Check(
            "azure-subscription-attached",
            True,
            f"billing plan {policy.get('name')!r} bills to Azure "
            f"subscription {instrument['subscriptionId']} "
            f"(resource group {instrument.get('resourceGroup')})",
        )
    names = [p.get("name") for p in covering]
    return Check(
        "azure-subscription-attached",
        False,
        f"no plan covering the Default environment has a provisioned Azure "
        f"billing instrument; covering plans: {names or 'none'}",
    )


def _instrument_of(policy):
    """Return the policy's billing instrument if it can bill Azure, else None."""
    instrument = policy.get("billingInstrument", {})
    if (
        instrument.get("subscriptionId")
        and instrument.get("provisioningStatus") == "Succeeded"
    ):
        return instrument
    return None


def metered_plan_id(policies):
    """Return the id of the active plan carrying the meter, or None. Pure."""
    for policy in policies:
        if policy.get("status") == ACTIVE_STATUS and _is_metered(policy):
            return policy.get("id")
    return None


def _is_metered(policy):
    """True when the policy carries the Copilot Studio meter *switched on*."""
    entitlement = _meter_of(policy)
    return bool(entitlement and entitlement.get("payAsYouGoState"))


def _meter_of(policy):
    """Return the policy's Copilot Studio entitlement, or None."""
    for entitlement in policy.get("payGoEntitlements", []):
        if entitlement.get("entitlementId") == COPILOT_STUDIO_ENTITLEMENT_ID:
            return entitlement
    return None


def _linked_check(covering, metered, default_environment_id):
    if covering:
        return Check(
            "default-environment-linked",
            True,
            f"Default environment {default_environment_id} is linked to "
            f"metered billing plan {covering[0].get('name')!r}",
        )
    linked = sorted({e for p in metered for e in p.get("environmentIds", [])})
    return Check(
        "default-environment-linked",
        False,
        f"Default environment {default_environment_id} is not linked to any "
        f"metered billing plan; those plans link {linked or 'no environments'}",
    )


def _active_plan_check(active):
    names = [p.get("name") for p in active]
    return Check(
        "active-billing-plan",
        bool(active),
        f"active billing plans: {names}" if names else "no active billing plan",
    )


def _meter_check(metered):
    if metered:
        return Check(
            "copilot-studio-meter",
            True,
            f"billing plan {metered[0].get('name')!r} carries the "
            f"{COPILOT_STUDIO_ENTITLEMENT_ID} meter with payAsYouGoState=True",
        )
    return Check(
        "copilot-studio-meter",
        False,
        f"no active billing plan carries the {COPILOT_STUDIO_ENTITLEMENT_ID} "
        f"meter switched on",
    )


# Generative-AI-message quotas per Dataverse environment, from
# https://learn.microsoft.com/microsoft-copilot-studio/requirements-quotas.
# Pay-as-you-go environments get 100 RPM / 2,000 RPH. A failing verdict does not
# imply the 10 RPM trial/developer figure: prepaid message packs and Microsoft 365
# Copilot entitlement each set their own quota, and this check reads neither.
PAYG_RATE_LIMIT = "100 RPM / 2,000 RPH"


def format_report(verdict):
    """Return the human-readable report for a `Verdict`. Pure."""
    lines = [f"  {'PASS' if c.ok else 'FAIL'}  {c.name}: {c.detail}" for c in verdict.checks]
    if verdict.ok:
        quota = f"{PAYG_RATE_LIMIT} (pay-as-you-go)"
    else:
        quota = (
            "not established — pay-as-you-go is not in effect, and the quota "
            "from any other entitlement is not read by this check"
        )
    lines.append(f"  ----  generative-AI-message quota: {quota}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Live reads. Everything above this line is pure.
# ---------------------------------------------------------------------------

LICENSING_API = "https://api.powerplatform.com/licensing"
BAP_API = "https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform"
API_VERSION = "2022-03-01-preview"


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


def read_tenant_live():
    """Return (billing policies, Default environment id) for the signed-in tenant."""
    policies = _get(
        f"{LICENSING_API}/billingPolicies?api-version={API_VERSION}",
        "https://api.powerplatform.com/",
    )["value"]
    environments = _get(
        f"{BAP_API}/scopes/admin/environments?api-version=2020-10-01",
        "https://api.bap.microsoft.com/",
    )["value"]
    default = next(
        (e for e in environments if e["properties"].get("isDefault")), None
    )
    if default is None:
        raise RuntimeError("the tenant has no Default environment")
    return policies, default["name"]


def link_default_environment(policy_id, environment_id):
    """Attach `environment_id` to a billing policy. Reversible via /remove."""
    import json
    import urllib.request

    url = (
        f"{LICENSING_API}/billingPolicies/{policy_id}/environments/add"
        f"?api-version={API_VERSION}"
    )
    body = json.dumps({"environmentIds": [environment_id]}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {_token('https://api.powerplatform.com/')}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        return response.status


def main(argv=None, read_tenant=read_tenant_live):
    import sys

    argv = sys.argv[1:] if argv is None else argv
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    link = "--link" in argv

    policies, default_environment_id = read_tenant()
    verdict = evaluate(policies, default_environment_id)

    if link and not verdict.check("default-environment-linked").ok:
        plan_id = metered_plan_id(policies)
        if plan_id is None:
            print("nothing to link: no active billing plan carries the meter")
        else:
            link_default_environment(plan_id, default_environment_id)
            print(f"linked {default_environment_id} to billing plan {plan_id}")
            policies, default_environment_id = read_tenant()
            verdict = evaluate(policies, default_environment_id)

    print("\nCopilot Studio pay-as-you-go meter — Default environment")
    print(format_report(verdict))
    return 0 if verdict.ok else 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
