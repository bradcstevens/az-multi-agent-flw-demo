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

## Selectors

Only `data-testid`s that the **currently deployed image** carries. Adding an attribute to the
frontend makes the deployed target red until the next roll, which turns "the beat is broken" and
"the image is old" into the same red — the exact confusion #48 exists to remove. The agent's prose is
therefore located through `.content .panelContent` and the authored "AI Agent" tag rather than a
testid of its own; `data-testid="agent-message"` on `StreamingAgentMessage` is worth adding the next
time images are rebuilt.

`data-testid="quick-tasks"` is the one attribute added *and* rolled in the same act, because the
alternative was worse. A Quick Task is tapped by the card title the store pack authors, and an
accessible-name lookup matches by **substring**: every title is inside the question it asks — "Close
the store" inside *"How do I close the store?"* — which is what the task rail calls every plan the
walkthrough has ever raised. A page-wide lookup is therefore unambiguous only on a store nobody has
ever asked anything, and this one went red on a strict-mode violation against twenty completed
tasks while the demonstration itself was working. **A loop that rots by being run is worse than a
loop that is red until the next roll.** The tap is aimed at the region; the region is named on both
sides; `test_e2e_wiring.py` reads the name out of `HomeInput.tsx` and out of `StoreSurface.ts` and
fails if they drift.

Page objects live in `e2e/pages/` and hold no assertions, so the headed **Stage driver** (#51) can
reuse them without a second description of the walkthrough.

## The seam that stays runnable in CI

The browser suite needs a deployment, so it is declared as a loop and wired into **no workflow**.
What runs in CI is `src/tests/ci/test_e2e_wiring.py`, which reads the harness off disk as text and
asserts the wiring the suite's usefulness depends on: that the script exists and is executable, that
artefacts are unconditional, that there is exactly one `testDir`, that the target parameter selects
between the two surfaces, that the expectation is read from the repository, that page objects carry
no assertions, and that the accelerator's suite is gone. It is the same shape as
`test_frontend_ci_wiring.py`, and like it, it strips comments before scanning — a rule named only in
prose otherwise satisfies the check.

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

The recording this produces is the bottom rung of the presenter's fallback ladder — see
[presenter-runbook.md](presenter-runbook.md), which is where the findings above become
instructions for the person in the room.
