# Presenter runbook

## If the closing-store beat misses

The first Quick Task should show **Copilot Studio → Dataverse** and cite
`SOP-102`. If the Grounding panel instead says no matching procedure, say:

> "That is an honest miss: the published procedure library did not return a
> match, so the assistant will not invent closing steps. On shift, the associate
> asks the shift lead rather than acting on an answer it cannot ground."

Do not describe a citation that did not arrive, and do not substitute procedure
steps from memory. The customer has just seen the system's safety boundary,
not a successful cross-platform answer.

If the Grounding panel stays empty, say:

> "The procedure tool was not invoked on this run, so the system is not making
> a cross-platform grounding claim."

Continue only if the remaining beat is independent. For the full walkthrough,
use the recording from a green validator run rather than retrying live in front
of the customer.

## Before a customer session

Run the Demo validator ten times against the deployed surface. Every run must
be green and its artifact must include `sop-tool-query.json`: the
`retrievalQuery` must be the corpus's closing-store question. Keep the video
and report from one green run as the recorded fallback. A direct SOP probe is
not a substitute because it does not exercise the Foundry orchestrator.
