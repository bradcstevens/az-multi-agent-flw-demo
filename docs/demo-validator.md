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
as #47's mock-at-the-wrong-seam, one layer in.

**Beats 3 and 4 are two conversations, so the memory does not cross them.** The escalation Quick Task
starts a new session; the troubleshooting record is the memory of *one* conversation
(`docs/troubleshooting-memory.md`); and the plan page's chat box submits clarifications only, so
there is no way to continue the previous conversation with a new request. The ticket therefore reads
`steps_attempted: not reported` on the walkthrough as authored. The spec asserts the total claim —
every recorded step is carried, and a conversation with no record says exactly `not reported` — so a
ticket that *invented* steps fails as loudly as one that dropped them. Closing the gap is a change to
the surface, not to the validator, and is #61.



Only `data-testid`s that the **currently deployed image** carries. Adding an attribute to the
frontend makes the deployed target red until the next roll, which turns "the beat is broken" and
"the image is old" into the same red — the exact confusion #48 exists to remove. The agent's prose is
therefore located through `.content .panelContent` and the authored "AI Agent" tag rather than a
testid of its own; `data-testid="agent-message"` on `StreamingAgentMessage` is worth adding the next
time images are rebuilt.

Page objects live in `e2e/pages/` and describe the surface, not the walkthrough, so the headed
**Stage driver** (#51) can reuse them without a second description of the beats. They do carry
`expect`, but only as *waits* — "the surface has arrived" — never as a claim the walkthrough makes.
Every claim on the issue's acceptance criteria is in a spec.

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

**The retrieval sometimes misses on a question the corpus rehearses.** The hop completes — the panel
names Copilot Studio and Dataverse — and the answer is the **honest miss**: *"Searched Dataverse and
found no matching procedure."* Two runs in eight ended this way while
`check-deployed-surface.sh`'s `grounded-answer` check, which asks the backend directly, passed every
time. The difference is the question: the check asks the corpus's own words, and the orchestrator
hands the SOP tool whatever the model rephrased them into.

The spec checks for the honest miss **before** it checks the citation, and fails with a message
saying which of the two happened. Asserting only on the citation reports a miss as an empty string,
which reads like a broken selector and sends the reader to the wrong place.

`retries: 0` stands. A retry would turn an intermittently-working demonstration into a green run,
and the presenter would find out in the room. The intermittency is the finding, not the noise — it
is #54.
