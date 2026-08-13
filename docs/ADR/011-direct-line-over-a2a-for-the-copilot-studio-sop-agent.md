# ADR-011: Reach the Copilot Studio SOP agent over Direct Line, not A2A

## Status

Accepted

## Date

2026-08-12

## Issue

#11 (spec #1)

## Context

The **SOP agent** is the one low-code agent in this build and the entire cross-platform proof:
a Foundry orchestrator calling a Copilot Studio agent. Something has to carry that call.

The superseded requirements document chose **Direct Line API 3.0** and justified it by ruling
out the alternative: "**A2A (agent-to-agent) — PREVIEW.** Violates the GA-only constraint. Not
used."

**That justification is now false. A2A reached general availability in April 2026.** The
GA-only constraint no longer excludes it, so the choice has to be re-made on its merits rather
than inherited.

Re-made, it comes out the same way, for reasons the document never gave:

- **Direct Line 3.0 is the path Copilot Studio itself publishes to.** Publishing an agent
  produces a Direct Line token endpoint; roughly thirty lines of Python drives a conversation
  from there. It is the channel, not an integration layer bolted beside it.
- **Direct Line carries the citation data the grounding panel needs.** Citations arrive
  structurally in the activity's entities collection. R6's claim — that the answer came from
  the Copilot Studio side, with named source documents — is a property of this transport.
- **The orchestrator already has a socket for exactly this shape.** Wrapped as an MCP service,
  the Copilot Studio agent becomes a tool like any other, with no change to the orchestration
  layer. A2A would introduce a second, parallel notion of "calling another agent" alongside
  the one the accelerator already has.
- **The remaining options are dead ends.** Connected Agents (classic Agents API) is deprecated
  and unavailable in the new Foundry Agent Service, and there is no documented path to publish
  a Copilot Studio agent as an MCP server.

## Decision

**The orchestrator reaches the Copilot Studio SOP agent over the Direct Line API, wrapped as an
MCP service** (`src/mcp_server/services/`, registered under its own domain).

**A2A is not used** — but the recorded reason is fit, not availability. Do not repeat "A2A is
Preview" in any walkthrough, write-up or ticket; it is factually wrong and invites a correction
from the audience at the worst moment.

Client-side rules that fall out of the transport and are binding on the implementation:

- **Resolve the Direct Line endpoint from the regional channel settings service at runtime.
  Never hardcode the default Direct Line hostname.** This contradicts a snippet in the public
  web-security documentation but matches Microsoft's own working sample.
  **Amended by #18:** this environment serves *no* regional channel settings — the endpoint
  `PvaGetDirectLineEndpoint` returns is a legacy gateway that 404s on every settings path, and
  the `<envid>.environment.api.powerplatform.com` host is NXDOMAIN. The second source is the
  **`aud`/`iss` claim of the token the environment itself issued**, which is still the service
  telling us rather than us assembling a hostname. Neither answering is a failure, not a
  fallback to the default host. See [the client record](../copilot-studio/direct-line-client.md).
- **Tokens live 3600 seconds**, not the 30 minutes the superseded document states
  ([correction 8](../superseded-requirements-corrections.md#8-direct-line-tokens-expire-in-3600-seconds)).
  **Amended by #18:** a Copilot Studio Direct Line token is also **conversation-scoped** — it
  carries a `conv` claim, so reusing one for a second conversation rejoins the first and replays
  its transcript. The 3600 seconds bound one conversation's token, not a cache; fetch a token per
  conversation.
- **Parse citations structurally** from the entities collection where the entity type is the
  schema.org `Message` type, reading position, name and abstract. **Amended by #17:**
  `abstract` is the *filename*, identical to `name`; the snippet is a truncation of
  `appearance.text`. The markdown reference-style
  form in the activity text is a parallel representation, not the source of truth. **Expect the
  citation URL to be absent** for Dataverse-uploaded documents — render name plus snippet and
  do not make a link a requirement.
- **Filter incoming activities to the bot role** — Direct Line replaces the sender identifier
  with a server-generated value — and **de-duplicate by activity identifier**. Trigger the
  greeting with an explicit conversation-start event.
- **Failure behaviour is one fast retry, then a fixed failure message.** Never fall back to
  model knowledge, and do not keep a local copy of the SOP corpus as a safety net: a hidden
  fallback would make the cross-platform claim untestable and, if it fired on stage,
  unfalsifiable.
- **Publish propagation is slow and asymmetric.** New content reaches only new conversations;
  existing conversations end after 30 minutes idle; otherwise allow up to an hour, and up to
  two hours for secured-access changes. **Start a fresh conversation after every publish, and
  freeze the agent at least two hours before the demo.**

## Considered Options

- **A2A, now that it is GA.** Rejected on fit: it adds a second agent-calling mechanism beside
  the accelerator's existing tool path, and the citation and grounding-panel work would have to
  be redone against a different payload shape. Reconsider for a build that is not on a demo
  clock.
- **Copilot Studio published as an MCP server.** Rejected: no Microsoft Learn documentation
  exists for it. Do not plan on it.
- **Connected Agents (classic Agents API).** Rejected: deprecated, and not available in the new
  Foundry Agent Service.

## Consequences

- **Positive:** One contained new service, on a GA transport, inside the architecture the
  accelerator already has. The cross-platform claim is demonstrated by a real network call
  between two platforms.
- **Negative:** Glue code we own — token lifecycle, conversation lifecycle, activity filtering,
  de-duplication and citation parsing all become our bugs. This is the highest integration risk
  in the build, which is why it is scheduled early rather than late.
- **Testing:** No outbound-HTTP double library exists in the repo. The client is tested by
  subclassing the existing base API service and patching its request method, driven from canned
  Direct Line payloads.

## References

- [Correction 7](../superseded-requirements-corrections.md#7-a2a-is-ga-not-preview)
- [ADR-012: Ground the SOP agent on Dataverse Documents only](./012-grounding-option-a-dataverse-documents-only.md)
