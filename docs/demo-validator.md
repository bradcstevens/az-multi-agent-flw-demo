# The Demo validator

Issue #47, decided in [ADR-016](ADR/016-typescript-playwright-for-the-demo-validator.md). A
`@playwright/test` suite in `e2e/`, behind `bash scripts/e2e-tests.sh`, that drives the walkthrough
through a real browser and asserts what the demonstration *claims*.

It is the only thing in this repository that observes a deployment through the surface a customer
will see. Every other declared loop runs against fakes — which is how a deployment 42 commits behind
stayed green for weeks, and how all four out-of-band signals came to be dropped in the browser while
223 frontend tests passed. See *Confirmed findings* in `CONTEXT.md` for both.

## Running it

```bash
bash scripts/e2e-tests.sh                 # the deployed surface (default)
bash scripts/e2e-tests.sh --target local  # a local `npm run dev` on :3001
bash scripts/e2e-tests.sh --stage         # the Stage driver: headed and paced (#51)
bash scripts/e2e-tests.sh -- --headed     # anything after `--` goes to Playwright
```

The script bootstraps its own toolchain — `npm ci` and `npx playwright install chromium` on first
use, a no-op afterwards — so it runs from a clean checkout with nothing but `node` and `az` on
`PATH`. For the deployed target it resolves the frontend's FQDN with `az containerapp show`, reading
the resource group and app name out of `scripts/preflight/deployed_surface.py` rather than carrying
a second copy. `E2E_BASE_URL` overrides the lookup and skips the `az` call.

## Why TypeScript, in a repository whose loops are Python

ADR-016. The suite's real user is a **presenter who does not know agent orchestration** and who will
be alone in the room. The trace viewer, the HTML report and the video are the reason for the choice;
they are what turns "the demonstration is broken" into something a non-engineer can act on, and the
video is the demonstration's own last-resort fallback (#51). A Python Playwright suite would match
the repository's convention and hand the presenter a stack trace.

## Video, trace and report on every run — including passing ones

`playwright.config.ts` sets `video`, `trace` and `screenshot` to `'on'`, not `'on-first-retry'` or
`'retain-on-failure'`. The recording is not a debugging aid here; it is the artefact #51 turns into
the fallback, and a fallback produced only by failing runs is a fallback of failures. Artefacts land
under `e2e/artifacts/` (`runs/` for videos and traces, `report/` for the HTML report), which is
gitignored.

A run in which **every beat passed** additionally leaves `e2e/artifacts/walkthrough/` — the beats in
order, with a self-contained player beside them. That is the **Recorded fallback**, and it is what
the presenter is handed; see [docs/stage-driver.md](stage-driver.md).

`retries: 0` and `workers: 1`, deliberately. A retried beat is a beat that flaked, and a flaky
demonstration is the thing this suite exists to find. One worker because the walkthrough is one
conversation against one deployment.

## The expectation is read out of the repository

`e2e/authored.ts` reads what the suite expects from the same files that produce it:

| Expectation | Read from |
| --- | --- |
| The assistant's name | `src/App/src/config/storeSurface.ts` |
| The rehearsed question, its Quick Task and its document identifier | `content/sop/corpus.toml`, `[rehearsed_hit]` |
| The Quick Tasks and their prompts | `content_packs/store_assistant/agent_teams/store_assistant.json` |

This is [ADR-019](ADR/019-rebrand-the-sop-corpus-to-circle-k.md)'s lesson one layer out, and the same rule
`scripts/preflight/deployed_surface.py` follows: **a check carrying its own copy of the expectation
passes a rebrand it never saw.** The corpus reader is section-scoped by hand rather than a TOML
library, because `question` appears under both `[rehearsed_hit]` and `[honest_miss]` and a flat
last-key-wins parse would silently assert the wrong beat.

## What it asserts, and what it refuses to

The cross-platform beat is asserted on the **deterministic transparency signals** — the platform the
**Grounding panel** names (`Copilot Studio`), the route it reports (`Dataverse`), and the citation's
document identifier (`SOP-102`) — and never on the wording of anything a model wrote. Model prose is
asserted only to have **arrived and to be non-empty**, which is a real assertion: an empty answer and
a paraphrased one look identical to a suite that greps for a sentence, and only one of them is a
failure.

Each run also attaches `sop-tool-query.json` to its Playwright artifact. It records both the query
the Foundry orchestrator actually gave `search_store_procedures` and the query the backend used for
the SOP corpus. A difference between the two is evidence of an orchestrator rephrasing; it is
captured rather than guessed, and the closing-store alias in `_retrieval_query` makes the rehearsed
hit retrieve against its authored corpus wording **when it recognises the rephrasing verbatim**.

What is graded is that the retrieval query is **one of those two** — the corpus wording or the
orchestrator's own — because `_retrieval_query` is an *input alias, not an answer fallback*, and a
third value would mean the backend retrieved against something nobody asked for. What is
deliberately **not** graded is that the alias fired. The orchestrator writes the tool call; its
wording is model prose, and the rule above applies to it exactly as it applies to the answer. An
earlier revision required the corpus wording and reported a run where the platform, the route and
`SOP-102` all landed as a failed beat, because the orchestrator had phrased the call a sixth way —
the alias list is a determinism aid, not a grammar the model agreed to. A missing Grounding panel
remains a routing failure: no tool query exists because the orchestrator did not call the tool.

The suite also asserts the Grounding panel is **empty before the question is asked**. Without it, a
panel left lit by a previous conversation satisfies every other assertion in the spec.

## The troubleshooting and escalation beats

Issue #50. The two hardest beats, and together the demonstration's strongest single claim: that the
assistant remembers what you tried and does not make you repeat it.

**Beat 3 — the clarification and the rehearsed replies.** The fault is asserted to provoke a
`user_clarification_request`, the chips are asserted to carry the pack's own authored labels, and the
tap is asserted to *record* — `GET /api/v4/troubleshooting/attempted` gains a step. A tap that
records nothing looks exactly like a tap that worked, right up to the moment the runbook walks the
associate through the step they already tried. The chips are then asserted to be **gone**: they are
one-tap answers carrying a `request_id`, and a chip offered after its question was answered submits
an answer to a question nobody is waiting for.

**Beat 4 — the approval is the ticket.** The Lane is read back from server-side session state, never
off the badge; the badge is the browser's recollection of what the router said, and a surface
rendering `Deliberate` over a request the router sent down the Fast lane is exactly the failure it
cannot see. Then the approval, the ticket, and two claims about things that must **not** happen — no
second `plan_approval_request`, no `user_clarification_request` between the approval and the card.
The rejected branch gets its own spec, because it is where the requirement fails silently: nothing on
the wire, no card, and no submitted ticket in the container.

Nothing is asserted about anything a model wrote. The ticket's number is a sha256 of the session
against the prefix `ticket.py` defines, its rows are the template's, and its `Simulated` labelling is
a property of the card.

### Both halves are graded on the wire

`e2e/wire.ts` records every frame the page received (`page.on('websocket')`). The absence claims —
*asked only while a question is pending*, *one confirmation not two*, *never asked twice* — are
claims that something did not happen, and a locator that is not on screen is equally a surface that
has not rendered yet. Counting frames between two marks distinguishes them, and a failure names what
the socket **did** carry instead of reporting a 30-second timeout.

### What these two beats found

**The chips outlived their question.** `clarificationMessage` was set by the incoming request and
cleared only by `resetChat` on a new plan, so after answering — by chip or by typing — the rehearsed
replies stayed on screen offering one-tap answers to a resolved `request_id`. Fixed at
`PlanChat`, the single seam both answers pass through, with `PlanPage` putting the question back if
the submit failed. Every panel test passed throughout, because each fed the component the state it
expected rather than the state a conversation produces.

**The ticket was never raised, because the draft did not exist yet.** The confirmation seam ran
inside `_handle_plan_reviews` — at plan-review time, which is *before* the plan runs, and the plan
whose last step is *"draft a simulated service-incident ticket"* has not drafted one. `TicketStore.read`
is deliberately non-total, so the seam found nothing, said nothing, and the card never appeared. The
approved run now submits again when it finishes; it is the same single confirmation, the rejected
plan never reaches it, and a Fast-lane turn nobody approved never reaches it either. Every unit test
around that seam passed, because each handed it a store that already held a draft — the same lesson
as #47's mock-at-the-wrong-seam, one layer in. **That fix has never been observed live**, for the
reason immediately below: no draft has ever existed to submit.

**The escalation never drafts the ticket at all — #62, and the beat is red on it.** An approved
escalation turn ran to completion against `rg-macae-flw-v1` — `final_result_message` on the wire,
2810 characters of answer — and `GET /api/v4/escalation/ticket` answered `{"drafted": false}`. The
**EscalationAgent** never called `draft_service_ticket`. `docs/escalation-ticket.md` had already
named the risk out loud: that a live turn calls the drafting tool is *instructed, not measured*. It
is now measured, and it is not happening, so the Simulated ticket exists only in the model's prose
and no submission seam anywhere can raise it. The same run showed the shape of the drift: after the
approval the plan asks twice in one pause — the `list_attempted_steps` tool-approval, rendered as
*"The agent needs clarification."*, and a `request_user_clarification` — and the Troubleshooting
Agent then improvises diagnostics until the turn ends in advice rather than an escalation. The
walkthrough answers up to four questions and grades the ticket; it fails naming what the socket
carried instead. That red is the product's, not the validator's, and it is the finding: the
demonstration's fourth beat does not currently work.

**Beats 3 and 4 are two conversations, so the memory does not cross them.** The escalation Quick Task
starts a new session; the troubleshooting record is the memory of *one* conversation
(`docs/troubleshooting-memory.md`); and the plan page's chat box submits clarifications only, so
there is no way to continue the previous conversation with a new request. The ticket therefore reads
`steps_attempted: not reported` on the walkthrough as authored. The spec asserts the total claim —
every recorded step is carried, and a conversation with no record says exactly `not reported` — so a
ticket that *invented* steps fails as loudly as one that dropped them. Closing the gap is a change to
the surface, not to the validator, and is #61.

## Selectors

Only `data-testid`s that the **currently deployed image** carries. Adding an attribute to the
frontend makes the deployed target red until the next roll, which turns "the beat is broken" and
"the image is old" into the same red — the exact confusion #48 exists to remove. The agent's prose is
therefore located through `.content .panelContent` and the authored "AI Agent" tag rather than a
testid of its own; `data-testid="agent-message"` on `StreamingAgentMessage` is worth adding the next
time images are rebuilt.

`.home-input-quick-tasks` is what the Quick Task tap is aimed at, and the rule above is why it is a
layout class rather than a testid of its own. A Quick Task is tapped by the card title the store
pack authors, and an accessible-name lookup matches by **substring**: every title is inside the
question it asks — "Close the store" inside *"How do I close the store?"* — which is what the task
rail calls every plan the walkthrough has ever raised. A page-wide lookup is therefore unambiguous
only on a store nobody has ever asked anything, and this one went red on a strict-mode violation
against twenty completed tasks while the demonstration itself was working. **A loop that rots by
being run is the one failure mode a loop must not have.** A `data-testid` was the first fix and was
withdrawn: it made the beat depend on an image built the same morning, and on a deployment two
integration branches were rolling minutes apart it went red for a reason that had nothing to do
with the walkthrough. The class has named the region since #26, it is plain CSS in this repository
rather than a Griffel hash, and `test_e2e_wiring.py` reads it out of `HomeInput.tsx` and out of
`StoreSurface.ts` and fails if they drift.

Page objects live in `e2e/pages/` and describe the surface, not the walkthrough, so the headed
**Stage driver** (#51) reuses them without a second description of the beats — it is a second
`projects` entry over these same specs, chosen with `--stage`. See
[docs/stage-driver.md](stage-driver.md). They do carry `expect`, but only as *waits* — "the surface
has arrived" — never as a claim the walkthrough makes. Every claim on the issue's acceptance
criteria is in a spec.

## The seam that stays runnable in CI

The browser suite needs a deployment, so it is declared as a loop and wired into **no workflow**.
What runs in CI is `src/tests/ci/test_e2e_wiring.py`, which reads the harness off disk as text and
asserts the wiring the suite's usefulness depends on: that the script exists and is executable, that
artefacts are unconditional, that the walkthrough is never retried, that there is exactly one
`testDir`, that the target parameter selects between the two surfaces, that the expectation is read
from the repository — including the ticket prefix and the lane's name, out of the backend modules
that define them — that both hard beats have a spec, that their absence claims are graded on the
wire, that the lane and the troubleshooting record are read server-side, and that the accelerator's
suite is gone. It is the same shape as `test_frontend_ci_wiring.py`, and like it, it strips comments
before scanning — a rule named only in prose otherwise satisfies the check.

## Known non-determinism

Two kinds, both real, both observed on this deployment on 2026-08-13 and both worth the presenter
knowing about (#53).

**The orchestrator does not always call the SOP tool.** Observed alternatives for *"How do I close
the store?"*: the **Group Chat Manager** answering from context, and the **Shift Tasks Agent**
answering with the **Troubleshooting Agent** then asking a clarification. With no tool call there is
no `source_used`, the Grounding panel is honestly empty, and this suite is honestly red.

**The retrieval previously missed on a question the corpus rehearses.** The hop completed — the panel
named Copilot Studio and Dataverse — and the answer was the **honest miss**: *"Searched Dataverse and
found no matching procedure."* Two runs in eight ended this way while
`check-deployed-surface.sh`'s `grounded-answer` check, which asks the backend directly, passed every
time. The difference was the question: the check asked the corpus's own words, and the orchestrator
handed the SOP tool whatever the model rephrased them into. The validator now records both values;
the alias normalises the rephrasings it recognises, and what the spec *grades* is the honest miss
itself, which is the symptom. Grading the retrieved wording instead was tried and withdrawn — the
orchestrator promptly produced a seventh phrasing and the beat went red on a run that named Copilot
Studio, reported Dataverse and cited SOP-102. The ten-run rehearsal is the proof that the fix has
reached the deployment; do not replace it with a direct SOP probe.

The spec checks for the honest miss **before** it checks the citation, and fails with a message
saying which of the two happened. Asserting only on the citation reports a miss as an empty string,
which reads like a broken selector and sends the reader to the wrong place.

`retries: 0` stands. A retry would turn an intermittently-working demonstration into a green run,
and the presenter would find out in the room. The intermittency is the finding, not the noise — it
is #54.

The recording this produces is the bottom rung of the presenter's fallback ladder — see
[presenter-runbook.md](presenter-runbook.md), which is where the findings above become
instructions for the person in the room.
