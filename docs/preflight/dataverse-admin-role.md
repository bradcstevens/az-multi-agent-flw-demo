# Preflight: Dataverse System Administrator in the Default environment

**Verdict: the build account holds System Administrator in the Default environment.**
Granted and observed 2026-08-12 (issue #2). Its Dataverse security roles are `Basic User`,
`Environment Maker` and `System Administrator`.

Re-check with `scripts/preflight/check-dataverse-admin-role.sh` — it exits non-zero if the role is
ever lost, and `--elevate` grants it again unattended in about 25 seconds. Pass `--environment <id>`
with the identifier **shown in the Copilot Studio URL** to check the environment a maker is actually
in rather than the one the tenant calls Default.

## Why this needed verifying rather than assuming

Power Platform administrators are **no longer automatically granted** the System Administrator role
in the Default environment, so tenant-level admin membership does not answer the question. The build
account _is_ a Global Administrator — `GET /me/transitiveMemberOf` returns exactly
`Global Administrator` — and still held neither `prvAssignRole` nor System Administrator in
Dataverse. Reading Power Platform admin centre membership would therefore have reported a false
pass; the check reads the **environment's own security-role list** instead, which is a different API
(the Dataverse Web API, not the admin API).

The role is not decoration. It gates the environment-level Dataverse search setting, which is #3 —
the longest lead-time item in the build — so this finding gated the #3 → #17 → #18 chain.

## Findings

| # | Finding | Evidence |
| --- | --- | --- |
| 1 | The tenant's Default environment is `Default-0f87abfb-0840-4199-96b7-1882c01a998b` ("Contoso (default)", `environmentSku: Default`), and it is the **only** environment in the tenant — there is no personal Developer environment to be silently routed into today. | `GET /providers/Microsoft.BusinessAppPlatform/scopes/admin/environments` |
| 2 | Its Dataverse instance `https://org5dadb450.crm.dynamics.com/` is `Ready`, org id `d3c93f69-ac94-f011-8706-000d3a106522`. | `linkedEnvironmentMetadata` on the same response |
| 3 | The build account's Dataverse security roles were **`Basic User`, `Environment Maker`** — not System Administrator. They are now those two **and `System Administrator`**. | `GET /api/data/v9.2/systemusers({userId})/systemuserroles_association?$select=name`, user id from `WhoAmI` |
| 4 | Assigning the role from the Dataverse side **as the build account** is refused: `0x80040220`, "missing `prvAssignRole` privilege". So the build account cannot grant it to itself directly. | `POST /api/data/v9.2/systemusers({userId})/systemuserroles_association/$ref` → **403** |
| 5 | Microsoft's documented self-elevation is **unreachable from the Azure CLI**, and not for want of consent — see below. | `AADSTS65002` |

## The elevation method

`--elevate` grants the role through a **bootstrap application user**, with no interactive step:

1. Create an Entra app registration (`flw-dataverse-bootstrap`), its service principal and a client
   secret.
2. Register that principal as a Dataverse **application user** through the BAP admin API. The
   endpoint grants it System Administrator itself:
   `POST https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform/scopes/admin/environments/{environmentId}/addAppUser?api-version=2020-10-01`
   with `{"objectId": "<sp object id>", "servicePrincipalAppId": "<app id>"}`. Both identifiers are
   required — `applicationId` is rejected as an unknown member of `UserIdentity`, and the object id
   alone is rejected as `MissingServicePrincipalAppId`.
3. Acquire an **app-only** Dataverse token for that principal by client credentials. No user, so no
   MFA and no browser.
4. As that principal — which *does* hold `prvAssignRole` — assign System Administrator to the build
   account's `systemuser` record, matched by `azureactivedirectoryobjectid`.
5. Tear the bootstrap down: delete the app registration **and** disable the Dataverse application
   user it left behind.

The caller must still be a Global, Power Platform or Dynamics 365 admin — `addAppUser` is a
tenant-admin operation. What it does not need is any scope beyond the `user_impersonation` the
Azure CLI already holds on the BAP admin API.

`--elevate` re-reads the tenant afterwards and re-evaluates, so a pass means the role was observed in
the environment's security roles — not merely that a call returned 200. Verified by revoking the
role and letting the check grant it back: 27 seconds, unattended.

### Why not Microsoft's documented self-elevation

[The documented route](https://learn.microsoft.com/power-platform/admin/manage-high-privileged-admin-roles#self-elevate-to-the-system-administrator-role)
is a single POST:

```
POST https://api.powerplatform.com/usermanagement/environments/{environmentId}/user/applyAdminRole?api-version=2022-03-01-preview
```

It elevates **the calling user**, so it needs a *user* token carrying the delegated scope
`https://api.powerplatform.com/UserManagement.Users.Apply`, and the Azure CLI's token carries only
`EnvironmentManagement.Environments.Read`, `CopilotStudio.Copilots.Test` and
`PowerPages.Websites.{Read,Write}`.

**That is not a consent problem, and this is the correction worth carrying forward.** An earlier
reading of this preflight recorded the remedy as "consent to the scope once with
`az login --scope …`". It cannot work. Admin consent was granted — a `Principal`-scoped
`oauth2PermissionGrant` from the Azure CLI's service principal to the Power Platform API, created
successfully as Global Administrator — and the token request still fails:

```
AADSTS65002: Consent between first party application '04b07795-…' and first party resource
'8578e004-…' must be configured via preauthorization — applications owned and operated by Microsoft
must get approval from the API owner before requesting tokens for that API.
```

Consent between two Microsoft first-party applications is the API owner's to give, not a tenant
admin's. No sign-in, interactive or otherwise, adds that scope to an Azure CLI token. (The `az`
attempt reports `AADSTS50078`, a stale-MFA error, which *masks* this — `azd`, sharing the same
client id, surfaces the real one. An operator who trusted the first message would re-authenticate
forever.) The grant and the service principal created for that experiment were both removed.

There is no self-elevation action on the BAP admin API either: `applyAdminRole` and `addAdminRole`
both 404 across every supported API version.

### What `--elevate` deliberately will not do

It refuses to elevate unless the environment's identity checks out first. Elevating into a personal
Developer environment a maker was silently routed into would grant the role somewhere the demo never
runs — and that environment is capped at 10 requests/minute against the Default environment's 100
(see `docs/preflight/copilot-studio-payg-meter.md`). A wrong-environment verdict therefore reports
"wrong environment — do not elevate here" and offers no elevation. The identity check is only
meaningful if it can be told what the maker actually sees, which is what `--environment` is for; an
identifier the tenant does not have is reported by name rather than silently falling back to the
Default environment.

It also tears the bootstrap down in a `finally`, so a run that dies mid-way does not leave a standing
System Administrator service principal — with a live client secret — in the tenant. Deleting the app
registration is only half of that: Dataverse keeps the application user, still enabled and still a
System Administrator, with no credential left to use it, so teardown disables the user too.

### Timing quirks that look like failures

Two waits are built in, because both refusals are indistinguishable from real faults except that
they stop happening:

- `addAppUser` answers **`500 InternalServerError`** while the just-created service principal
  propagates. Retried on 5xx only; a 4xx is an answer, not a delay.
- The client secret is refused by the token endpoint for the first tens of seconds after
  `az ad app credential reset`.

The original manual walk-through never saw either, because minutes of hand-driven steps passed
between them.

## Scope

Verified: the Default environment's identity, its Dataverse instance state, the build account's
actual security roles, that the Dataverse-side self-assignment is refused, and that the bootstrap
elevation grants the role end to end from a revoked state. **Not** verified here: Dataverse search
itself (#3 — now enabled and its index proven synced, recorded separately in
[docs/preflight/dataverse-search.md](dataverse-search.md)), DLP connectors (#5), and the Copilot
Studio meter (#6, recorded separately and already passing).
