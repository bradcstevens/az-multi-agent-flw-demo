# Preflight: the Copilot Studio pay-as-you-go meter on the Default environment

**Verdict: the Default environment is on an active pay-as-you-go billing plan that carries the
Copilot Studio meter, billed to the build subscription.** Verified 2026-08-12 (issue #6).

Re-check with `scripts/preflight/check-copilot-studio-meter.sh` — it exits non-zero if any of the
four findings below stops being true, and `--link` repairs the one that is repairable.

## Why this needed verifying rather than assuming

Pay-as-you-go on a **Default environment** is undocumented. [Set up
pay-as-you-go](https://learn.microsoft.com/power-platform/admin/pay-as-you-go-set-up) states that
"pay-as-you-go is available for **production** and **sandbox** environments" — it does not name the
Default environment, whose `environmentSku` is `Default` and not either of those. The tenant has
exactly one environment, `Default-0f87abfb-0840-4199-96b7-1882c01a998b` ("Contoso (default)"), so
there was no supported environment to fall back to.

Pay-as-you-go itself is a settled decision, not one this record reopens: a Microsoft 365 Copilot
licence does not entitle publishing to Direct Line, because that zero-rating is conditioned on the
agent running under an authenticated Microsoft 365 Copilot user's identity and a no-auth Direct Line
session has no such identity.

## Findings

| # | Finding | Evidence |
| --- | --- | --- |
| 1 | An **active** billing plan exists — `PowerPlatformPayGo`, `status: Enabled`, `type: TenantOwned`, region `unitedstates`. | `GET /licensing/billingPolicies` |
| 2 | It **carries the Copilot Studio meter specifically**: entitlement `MCSMessages` under product category `PowerVirtualAgent`, `payAsYouGoState: true`. This is the meter, not merely a billing attachment — the plan's other twelve entitlements (Dataverse, Power Apps, Power Automate, Power Pages, W365) would have been present with or without it. | `payGoEntitlements` on the same response |
| 3 | It is **attached to an Azure subscription**: `3523b0e6-bb53-4e87-8340-25c416e26093`, resource group `rg-copilot-paygo`, `provisioningStatus: Succeeded`. The corresponding hidden `Microsoft.PowerPlatform/accounts` resource exists in that resource group. | `billingInstrument`, plus `az resource show` |
| 4 | The **Default environment is linked to that plan** — and a `Default`-SKU environment *is* accepted, which is the undocumented part. | `POST /licensing/billingPolicies/{id}/environments/add` returned **200**, and the link is visible from both directions: the policy's `/environments` list and `GET /licensing/environments/{defaultEnvironmentId}/billingPolicy` |

### Finding 4 was not true when this ticket started

The plan already carried the meter, but its only linked environment was
`39bc9cf5-323a-e466-a0b6-8797aaeadf1e`, which **does not exist** in the tenant — the admin API
returns `EnvironmentNotFound` for it. A meter on a plan the Default environment is not linked to
bills nothing and raises no rate limit, so the capacity summary's *Pay-as-you-go credits* card would
have counted zero active plans for that environment. Reading only "is there a plan with the meter?"
would have reported a false pass, which is why the check tests the link separately.

The Default environment was linked, and the dangling reference to the deleted environment removed,
so the plan now lists exactly one environment.

## Rate limit

Copilot Studio's generative-AI-message quotas are per Dataverse environment
([Quotas and limits](https://learn.microsoft.com/microsoft-copilot-studio/requirements-quotas)):

| Tenant billing capability | Quota |
| --- | --- |
| **Pay-as-you-go environments** | **100 RPM / 2,000 RPH** |
| Trial or developer environments | 10 RPM / 200 RPH |
| 1–150+ prepaid message packs | 50–100+ RPM, by pack count |
| Microsoft 365 Copilot users | 100 RPM / 2,000 RPH |

So the 100 requests/minute figure the rehearsal relies on is a *consequence* of finding 4, not an
independent fact — which is why `format_report` derives the quota from the verdict rather than
printing 100 RPM unconditionally. Before the link, pay-as-you-go was not in effect on the
environment, so this quota did not apply; which quota did apply is *not* recorded, because prepaid
message packs and Microsoft 365 Copilot entitlement each set their own and neither was read.

This is the documented entitlement, taken at the moment the four findings above hold. It has not
been driven to the limit with live traffic; that measurement belongs to the rehearsal, once #17 has
published an agent to Direct Line.

## Scope

Verified: the meter, the plan, the subscription attachment, the environment link and the quota that
follows from them. **Not** verified here: DLP connector policy (#5), Dataverse System Administrator
rights (#2), and Dataverse search (#3) — each has its own ticket.
