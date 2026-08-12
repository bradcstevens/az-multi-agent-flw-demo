# Preflight — Copilot Studio data policy and network egress

**Verdict: all three required connectors are unblocked, and every required host is reachable.
One item is short of a full confirmation — the Direct Line WebSocket upgrade, which cannot be
completed until an agent is published; see below.** Verified 2026-08-12 against tenant
`0f87abfb-0840-4199-96b7-1882c01a998b` (`MngEnvMCAP786696.onmicrosoft.com`) and the Default
environment `Default-0f87abfb-0840-4199-96b7-1882c01a998b` ("Contoso (default)").

Re-run with `scripts/preflight/check-copilot-studio-dlp.sh`. Exit 0 clear, 1 blocked or
unreachable, 2 undetermined. **Today it exits 2, and that is the expected result** — nothing is
blocked, but the WebSocket row cannot be confirmed until an agent is published and a Direct Line
secret exists, and the check refuses to report an unproven path as clear.

## Why this had to be checked before the build

Agent data-policy exemption was withdrawn in early 2025 (message centre MC973179), so a blocked
connector has **no exemption route** — the policy itself has to change. Publishing fails outright
when no non-blocked channel remains, and Copilot Studio enforces data policies in real time, so a
block surfaces as a failed publish rather than as a warning during authoring.

"DLP" is the connectors' legacy name; Microsoft now calls the feature a **data policy**, and that
is the term used here and in `scripts/preflight/copilot_studio_preflight.py`.

## Finding 1 — the three connectors

Read from `https://api.bap.microsoft.com/providers/PowerPlatform.Governance/v2/policies` as
`brad.stevens@MngEnvMCAP786696.onmicrosoft.com`, whose only directory role is **Global
Administrator** (confirmed via `/me/transitiveMemberOf/microsoft.graph.directoryRole`).

| Capability the demo needs | Connector name in the Power Platform admin center | Finding |
| --- | --- | --- |
| Direct Line channels | `Direct Line channels in Copilot Studio` | **Unblocked** |
| Chat without Entra ID authentication | `Chat without Microsoft Entra ID authentication in Copilot Studio` | **Unblocked** |
| Document-based knowledge sources | `Knowledge source with documents in Copilot Studio` | **Unblocked** |

All three are unblocked for the same reason: **the tenant has no data policies at all.** Three
independent endpoints agree, each returning `{"value":[]}` with HTTP 200 — the v2 policies
endpoint, the v1 policies endpoint, and the legacy `scopes/admin/apiPolicies` endpoint.

That an empty list is a real finding rather than an unprivileged read is corroborated by the
same token reaching `scopes/admin/environments`, which returns the Default environment. A caller
without tenant admin scope does not see it. The check records the distinction itself: with no
policies it reports *"no data policy governs this environment"*, and with policies that permit
the connector it reports *"none of the N governing data policies block it"* — a reader can tell
the check looked.

**No policy owner or remediation path is needed, because nothing is blocked.** The second
acceptance criterion is satisfied vacuously, and deliberately so: recording a speculative owner
for a policy that does not exist would be fiction. Should a policy appear, the check names the
offending policy in its output and prints the remediation — a Power Platform administrator moves
the connector out of the Blocked group; an environment admin cannot edit a tenant-scoped policy.

### What the check catches that reading the admin center would not

- **The default data group.** Connectors introduced after 2019 — Direct Line channels and
  chat without Entra ID authentication among them — are not named in older policies and fall
  into the policy's default group. A tenant whose default group is Blocked blocks them without
  ever listing them. The check resolves the default group rather than treating "not listed" as
  "allowed".
- **A data-group split.** Unblocked is necessary but not sufficient: within one policy the
  connectors have to share a data group, because data cannot be shared across groups. All three
  unblocked but split across Business and Non-business still stops the agent, and reads as a
  clean pass if you only look for the word "Blocked".

## Finding 2 — network egress from the demo machine

Probed 2026-08-12 from the build machine. Required hosts come from the Copilot Studio
required-services table; each wildcard row is dialled at a concrete host the wildcard covers.

| Domain | Protocol | Required | Result |
| --- | --- | --- | --- |
| `*.directline.botframework.com` | HTTPS | Yes | **OK** — `405 Method Not Allowed` from the Direct Line service |
| `*.directline.botframework.com` | **WS** | Yes | **Unconfirmed** — the service answered, but see below |
| `*.powerva.microsoft.com` | HTTPS | Yes | **OK** — `200` |
| `*.analysis.windows.net` | HTTPS | Yes | **OK** — `404` |
| `bot-framework.azureedge.net` | HTTPS | Yes | **OK** — `400` from Azure Storage/CDN |
| `cci-prod-botdesigner.azureedge.net` | HTTPS | Yes | **OK** — `421` |
| `token.botframework.com` | HTTPS | No¹ | **OK** — `302` to `dev.botframework.com` |
| `cdn.botframework.com` | HTTPS | No² | **OK** — `200`, webchat bundle served |
| `pipe.aria.microsoft.com` | HTTPS | No³ | Unreachable — TLS closed without a handshake |
| `pa-guided.azureedge.net` | HTTPS | No³ | Unreachable — does not resolve in DNS |

¹ Bot Framework OAuth redirect, needed only for manual authentication. This demo publishes with
no authentication, so it is not on the demo path.
² Only if Web Chat is loaded from the CDN rather than bundled with the frontend. Recorded because
issue #18 has not yet settled which.
³ Client-side telemetry and in-product guidance. Microsoft marks both as recommendations, not
requirements. `pa-guided.azureedge.net` has no DNS record at all, which is consistent with the
`azureedge.net` CDN retirement rather than with anything about this tenant, and neither host is
on the demo's path. Nothing to remediate.

### The WebSocket result, in full

This is the finding the acceptance criterion singles out, because a proxy that permits HTTPS to a
host and silently drops its WebSocket upgrade is invisible until the chat transcript stops
arriving on stage. A real `Upgrade: websocket` / `Sec-WebSocket-Version: 13` handshake was sent
to `unitedstates.directline.botframework.com` and answered with:

```
HTTP/1.1 403 Forbidden
Content-Type: application/json; charset=utf-8
Access-Control-Allow-Origin: *
Access-Control-Expose-Headers: Retry-After
ARR-Disable-Session-Affinity: true

{"error":{"code":"BadArgument","message":"Missing token or secret"}}
```

That body is Direct Line's own error contract, so the request **reached the Direct Line service**
rather than a proxy: an interception answers with its own page or resets the connection, and this
did neither. It was refused for the expected reason — no bot exists yet, so there is no secret or
conversation token to present.

What it does **not** show is that the upgrade itself would be allowed. A plain `GET` to the same
path, carrying no `Upgrade` header at all, is answered with the byte-identical 403. The service
rejects on the missing secret before it looks at the upgrade, so this reply is evidence about the
HTTPS path and nothing more. That is precisely why the row reads **Unconfirmed** rather than OK,
and why the check exits 2 rather than 0 while it does.

Confirming it needs a real `101 Switching Protocols`, which needs a Direct Line secret, which
needs the SOP agent published — #17 and #18. Pass one to `--direct-line-secret` and the check
starts a conversation, dials the `streamUrl` the service returns, and accepts the row only on a
complete RFC 6455 handshake: status 101, `Upgrade: websocket`, `Connection: Upgrade`, and a
`Sec-WebSocket-Accept` derived from the key it generated. A bare 101 is not enough, because
anything can write that status line. Until then the check records the reply body on every error
response, so the evidence survives into the output rather than living only in this document.

## How the check avoids reporting a false pass

A preflight that says "clear" when it is not is worse than no preflight, so the ways this one
could have lied are handled explicitly rather than left to the happy path:

- **An under-privileged read.** A caller without tenant administrative scope is served an empty
  policy list rather than a denial. Before trusting an empty list the check confirms the same
  token sees the target environment through `scopes/admin/environments`, and returns
  *undetermined* (exit 2) if it does not.
- **An unrecognised policy scope.** Power Platform has added scope shapes before. A policy whose
  scope this check does not recognise is treated as governing, not skipped.
- **A policy summary without its classifications.** If a governing policy carries neither the
  connector nor a default group — or was returned without its `connectorGroups` at all, which the
  list endpoint can do — the verdict is *indeterminate* and the check exits 2, rather than reading
  the silence as "not blocked". An empty group list is an answer and is treated as one; a missing
  key is not.
- **The `policyDefinition` envelope.** The v2 list endpoint wraps each policy; left wrapped, every
  field the classifier reads is missing and a blocking policy would read as a clean pass.
- **A run that checks nothing.** `--egress-only --skip-egress` is refused, as is a saved payload
  that is not a policy list.
- **A truncated reply.** The probe reads a reply split across TCP segments to completion, so
  Direct Line's error contract is recorded rather than its first character.
- **An unproven WebSocket.** A required row that was reached but not confirmed exits 2, not 0.
  Unconfirmed is neither a pass nor a failure and is reported as neither.
- **A source that failed rather than answered.** A missing or unparseable `--policies-file`, or an
  HTTP error reaching the policy endpoint, exits 2. Letting a traceback exit 1 would have a reader
  act on a "blocked" finding that was never made.

## Loose ends

- The verdict is a **point-in-time** read of a tenant with zero policies. That is the state most
  likely to change without anyone telling the build: one new tenant-wide policy with a Blocked
  default group blocks all three at once. Re-run the check before the demo freeze.
- **The WebSocket row is Unconfirmed, not OK.** Close it with `--direct-line-secret` once #17
  publishes the agent, before the demo freeze.
- The connector-name match is by display name, normalised, and has never been exercised against a
  real policy payload because this tenant has none. Policy entries keep whatever name they were
  written with, so a renamed connector would be matched by nobody and fall through to the default
  group. As a hedge the check prints every Blocked group verbatim, so a reader can catch what the
  matcher missed; the first tenant that actually has a policy should confirm the names resolve and
  add the `shared_*` ids if they do not.
