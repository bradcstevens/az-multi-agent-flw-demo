# ADR-012: Ground the SOP agent on Dataverse Documents only — Option B is deleted, not deferred

## Status

Accepted

## Date

2026-08-12

## Issue

#11 (spec #1)

## Context

The **SOP corpus** has to be reachable by the Copilot Studio SOP agent from an **anonymous**
session: the demo front end is a shared store device with no individual sign-in, which is the
premise the whole identity story rests on.

**Copilot Studio's SharePoint knowledge source requires an authenticated user context.**
Microsoft Learn is explicit that generative answers over SharePoint are made *on behalf of the
user chatting with the agent*, and that selecting "No authentication" means the agent will not
retrieve from SharePoint **at all**. Not degraded — nothing.

The superseded requirements document offered three grounding options and recommended
"**build A, attempt B as a stretch**":

| Option | Mechanism | Auth |
| --- | --- | --- |
| **A** | Documents uploaded to the agent's knowledge, stored in **Dataverse** | None |
| **B** | SharePoint via a **store service account** ("Authenticate manually" against Entra) | Manual |
| **C** | Public website source | None |

Option B is architecturally faithful — Circle K's shared store account *is* a real account — and
that is what makes it tempting. But it is **partially unverified over Direct Line**, and the
time to verify it lands in phase 0, the same phase that already carries the two longest-lead
items in the build (Dataverse search enablement and quota tier confirmation).

The platform's refusal is worth saying out loud rather than engineering around: **the platform
itself will not serve tenant SharePoint content into an unidentified session.** That is the
guardrail thesis, validated by Microsoft engineering rather than asserted by us.

## Decision

**Grounding Option A only. Documents uploaded to Dataverse, no authentication.**

**Option B is deleted from the plan entirely, not deferred.** Keeping it as a stretch goal
would spend phase-0 time on a path that cannot work for an anonymous demo, and a half-attempted
B is worse than no B: it produces an agent configured for auth that silently returns nothing.

Consequences that follow and are binding:

- **Every reference to SharePoint as the SOP source becomes Dataverse** — including the
  grounding panel copy. The walkthrough says plainly that production grounds on SharePoint with
  an authenticated store identity, and that the demo grounds on Dataverse because the platform
  correctly refuses the anonymous case.
- **Publishing is pay-as-you-go, not licence-based.** An M365 Copilot licence does **not**
  entitle publishing to Direct Line here: the zero-rating is conditioned on the agent operating
  under an authenticated M365 Copilot user's identity, and a no-auth Direct Line session has no
  such identity
  ([correction 9](../superseded-requirements-corrections.md#9-an-m365-copilot-licence-alone-does-not-permit-publishing-to-direct-line)).
  Pay-as-you-go is also strictly better here: it avoids the prepaid overage kill switch that
  disables custom agents at 125% of a zero-capacity allocation, and it raises rate limits from
  10 requests/minute to 100.
- **Dataverse search must be enabled in the hosting environment.** It is required for
  Documents-based knowledge and is **not enabled by default in a Default environment**.
  Propagation takes 15 minutes minimum and a full sync can exceed an hour — **the longest
  lead-time item in the build; start it before anything else.**
- **Citation URLs will be absent** for Dataverse-uploaded documents. Render name plus snippet;
  do not make a link a requirement (see [ADR-011](./011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md)).
- **SOP files must be DOC/DOCX, PPT/PPTX or PDF, under 7 MB each, and unlabelled** — Copilot
  Studio silently excludes files marked Confidential or Highly Confidential.

## Considered Options

- **Option B, SharePoint via a store service account.** Rejected as above: unverified over
  Direct Line, phase-0 cost, and it is the option most likely to fail silently.
- **Option B as a stretch after A ships.** Rejected specifically. "Deferred" is how an
  unverified path stays on the board and keeps consuming attention; deleting it is the decision.
- **Option C, a public website source.** Rejected: requires publicly reachable content, which
  is unrealistic for store procedures.

## Consequences

- **Positive:** The grounding path is GA, anonymous-safe and reliable. The platform's own
  refusal becomes a demo beat rather than a blocker.
- **Negative:** The demo is not literally grounded on SharePoint, so the walkthrough must state
  the production/demo difference honestly. Dataverse file capacity is 3 GB shared tenant-wide.
- **Risk:** Three DLP connector categories must not be blocked — Direct Line channels, chat
  without Entra ID authentication, and document-based knowledge sources. There has been no
  exemption path since early 2025, and publishing fails outright if no non-blocked channel
  remains. Verify in phase 0.

## References

- [ADR-011: Reach the Copilot Studio SOP agent over Direct Line, not A2A](./011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md)
- [Corrections 9 and 10](../superseded-requirements-corrections.md)
