# Preflight: Dataverse System Administrator in the Default environment

**Verdict: the build account does _not_ hold System Administrator in the Default environment.**
Observed 2026-08-12 (issue #2). It holds `Basic User` and `Environment Maker` only.

Re-check with `scripts/preflight/check-dataverse-admin-role.sh` — it exits non-zero while the
finding stands, and `--elevate` repairs it once the one interactive consent below has been given.
Pass `--environment <id>` with the identifier **shown in the Copilot Studio URL** to check the
environment a maker is actually in rather than the one the tenant calls Default.

## Why this needed verifying rather than assuming

Power Platform administrators are **no longer automatically granted** the System Administrator role
in the Default environment, so tenant-level admin membership does not answer the question. The build
account _is_ a Global Administrator — `GET /me/transitiveMemberOf` returns exactly
`Global Administrator` — and still holds neither `prvAssignRole` nor System Administrator in
Dataverse. Reading Power Platform admin centre membership would therefore have reported a false
pass; the check reads the **environment's own security-role list** instead, which is a different API
(the Dataverse Web API, not the admin API).

The role is not decoration. It gates the environment-level Dataverse search setting, which is #3 —
the longest lead-time item in the build — so this finding blocks the #3 → #17 → #18 chain.

## Findings

| # | Finding | Evidence |
| --- | --- | --- |
| 1 | The tenant's Default environment is `Default-0f87abfb-0840-4199-96b7-1882c01a998b` ("Contoso (default)", `environmentSku: Default`), and it is the **only** environment in the tenant — there is no personal Developer environment to be silently routed into today. | `GET /providers/Microsoft.BusinessAppPlatform/scopes/admin/environments` |
| 2 | Its Dataverse instance `https://org5dadb450.crm.dynamics.com/` is `Ready`, org id `d3c93f69-ac94-f011-8706-000d3a106522`. | `linkedEnvironmentMetadata` on the same response |
| 3 | The build account's Dataverse security roles are **`Basic User`, `Environment Maker`** — not System Administrator. | `GET /api/data/v9.2/systemusers({userId})/systemuserroles_association?$select=name`, user id from `WhoAmI` |
| 4 | Assigning the role from the Dataverse side is **refused**: `0x80040220`, "missing `prvAssignRole` privilege". So Dataverse is not the elevation path. | `POST /api/data/v9.2/systemusers({userId})/systemuserroles_association/$ref` → **403** |

## The elevation method

Microsoft's documented self-elevation
([Manage admin roles with Microsoft Entra PIM](https://learn.microsoft.com/power-platform/admin/manage-high-privileged-admin-roles#self-elevate-to-the-system-administrator-role))
is a single POST, callable only by a Global, Power Platform or Dynamics 365 admin:

```
POST https://api.powerplatform.com/usermanagement/environments/{environmentId}/user/applyAdminRole?api-version=2022-03-01-preview
```

It elevates **the calling user**, so it needs a *user* token — a service principal has no user to
elevate, and registering an application user in Dataverse would itself need System Administrator.

**This is where it stops without a human.** The token must carry the delegated scope
`https://api.powerplatform.com/UserManagement.Users.Apply`, and the Azure CLI is pre-authorised for
only `EnvironmentManagement.Environments.Read`, `CopilotStudio.Copilots.Test` and
`PowerPages.Websites.{Read,Write}` on that API — the call returns **403
`InsufficientDelegatedPermissions`**. Consenting to the scope is an interactive sign-in, which an
unattended run cannot complete. Microsoft's own sample sidesteps this with a purpose-made Entra app
registration; reusing the Azure CLI's is the smaller footprint, because it adds no app and no
tenant-wide grant.

So the recorded method is one interactive consent followed by a re-runnable step:

```bash
az login --scope "https://api.powerplatform.com/UserManagement.Users.Apply"
scripts/preflight/check-dataverse-admin-role.sh --elevate
```

`--elevate` re-reads the tenant afterwards and re-evaluates, so a pass means the role was observed in
the environment's security roles — not merely that the POST returned 200.

### What `--elevate` deliberately will not do

It refuses to elevate unless the environment's identity checks out first. Elevating into a personal
Developer environment a maker was silently routed into would grant the role somewhere the demo never
runs — and that environment is capped at 10 requests/minute against the Default environment's 100
(see `docs/preflight/copilot-studio-payg-meter.md`). A wrong-environment verdict therefore reports
"wrong environment — do not elevate here" and offers no consent step. The identity check is only
meaningful if it can be told what the maker actually sees, which is what `--environment` is for; an
identifier the tenant does not have is reported by name rather than silently falling back to the
Default environment.

It also distinguishes the two ways `applyAdminRole` says no, because they have opposite remedies: a
missing scope is a one-time consent, whereas "the user is not either a Global admin, Power Platform
admin, or Dynamics 365 admin" has no self-service path at all and must go to a tenant admin. A bare
`403 Forbidden` would conflate them.

## Scope

Verified: the Default environment's identity, its Dataverse instance state, the build account's
actual security roles, and that the Dataverse-side assignment is refused. **Not** verified here:
Dataverse search itself (#3, blocked by this), DLP connectors (#5), and the Copilot Studio meter
(#6, recorded separately and already passing).
