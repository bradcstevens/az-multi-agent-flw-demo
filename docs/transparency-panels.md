# The transparency panels

Issue #24. #23 put three signals on the socket; this is what the audience sees when they arrive,
and the first frontend tests in the repository.

The panels inherit #23's rule and apply it to pixels: **a surface may say nothing, but it may not
say something that is not so.** In a table of numbers that rule has a precise form, and it is the
single most important decision here:

| Rendered | Means | Where |
| --- | --- | --- |
| `—` | **Not reported.** Nobody told us. | The Copilot Studio row's tokens, an unassigned model |
| `0` | **Measured.** We know it was nothing. | The identity boundary gate's refusal |

If an unreported cost also rendered `0`, the guardrail row — the one that proves a refused request
adds nothing — would prove nothing at all, because it would look exactly like an agent whose cost
never arrived.

## The layers

| Layer | File | What it owns |
| --- | --- | --- |
| Contract | `src/App/src/models/transparency.ts` | The three payloads, and total parsers that return `null` rather than a half-filled object |
| Meter | `src/App/src/models/meter.ts` | The whole of the meter's arithmetic, pure |
| Roster | `src/App/src/models/roster.ts` | Executor id → model deployment, and the agents to list |
| Chord | `src/App/src/models/presenterChord.ts` | Which keystroke is the hidden control |
| State | `src/App/src/store/slices/transparencySlice.ts` | Parsing at the reducer, so the contract is testable without a socket |
| Subscription | `src/App/src/hooks/useTransparencySignals.tsx` | Three `webSocketService.on` handlers |
| Panels | `src/App/src/components/transparency/` | Grounding, Token meter, Agent Team, Presenter alert, and the rail that hosts them |

Parsing happens **at the reducer** rather than in the subscription. It puts the whole
backend-payload-to-panel contract behind a plain function call — no store provider, no rendered
page, no socket — and it means an unreadable payload is dropped in exactly one place.

## Grounding panel

Leads with the **platform**, not the document. The claim R6 exists to make is that *this one answer
left Foundry*, so the headline is `Copilot Studio` and the route reads
`Foundry orchestrator → Copilot Studio → Dataverse`. **Dataverse**, never SharePoint: that is where
the SOP corpus actually lives (ADR-012), and naming SharePoint would describe an architecture this
demo deliberately does not have.

Three states, and the differences between them are the point:

- **cited** — the route, and the documents that came back.
- **uncited** — the route, and an explicit "found no matching procedure". That is the rehearsed
  out-of-corpus probe. The backend deliberately still emits for it (#23), and rendering it as an
  empty panel would delete the honest miss.
- **no signal** — the panel describes itself and asserts nothing. It does **not** say the answer
  came from Foundry. Nobody told it that: `source_used` is emitted for a successful hop, and its
  absence is also what a swallowed push looks like.

A **Policy block** never reaches this panel. A refusal is not a retrieval miss — it is a refused
request, rendered where the question was asked (`HomeInput`), and ADR-014 exists to keep the two
apart.

## Token meter

One row per agent, in the order each first spent, with **tokens and estimated Copilot Credits side
by side**. Each row fills only its own column, because the point being made is that the two billing
models are *not* uniform:

| Row | Billing | Tokens | Credits |
| --- | --- | --- | --- |
| A Foundry agent | `tokens` | accumulated | `—` |
| The Copilot Studio SOP agent | `credits` | `—` | 2 per answer |
| The identity boundary gate | `refused` | `0` | `0` |

**2 Copilot Credits** is Microsoft's published rate for a *generative answer*
([Billing rates and management](https://learn.microsoft.com/microsoft-copilot-studio/requirements-messages-management);
a classic answer is 1). The SOP agent answers with `GenerativeAIRecognizer` over its uploaded
Dataverse documents, so every answer it gives is a generative answer. It is one constant, labelled
**Est.** on screen, because the rate is Microsoft's to change.

The Copilot Studio row's tokens are `—` and never `0`: Direct Line reports no token count at all,
so a zero there would be the panel inventing a measurement.

The guardrail row's zeros **are** measurements. The gate is deterministic code before the lane
router and before orchestration (ADR-014), so when it refuses, no agent runs and no answer is
generated. (Its own embedding-similarity tier is a model call — a small one, not an agent, and not
on this table. The row's tooltip says which zero this is.) The refusal reaches the meter from
`HomeInput`, where the 403 is caught, because it is an HTTP response rather than a socket signal.

The **model** column is the per-agent assignment from the workflow roster's `deployment_name`,
which is how "cheap models on cheap work" becomes checkable rather than asserted. An agent the
roster does not name renders `—`.

## Agent Team panel

Populated from the **workflow roster** (`planData.team.agents`), not from the plan. With Plan review
off there is no plan object at all (ADR-013), and the panel previously read
`planApprovalRequest.team` — behind an early return that rendered the entire right-hand panel as
"No plan available". On the Fast lane, which is most of the walkthrough, the audience saw no agents
and no panels. The early return is gone, and "Plan is being generated…" is now shown only when a
plan is actually coming; a Fast-lane request says "No plan to review on this request."

## Presenter alert

Rendered as visibly a different object from a reply: `role="alert"`, its own icon, a "Proactive
alert" badge, and a title where a reply carries an agent name. An alert answers no question, because
nobody asked one — an alert mistaken for an answer is worse than no alert.

The chord is **Ctrl + Alt + Shift + A**, matched on `event.code` rather than `event.key`: with Alt
held, several keyboard layouts compose a different character, and a chord that only works on US
English is a chord that fails on the borrowed laptop. Three modifiers, so it cannot be produced by
typing a question, and `metaKey` must be up so it never fires under an operating-system combination.

It is a **global** listener, which is the one place this codebase departs from its own inline
`onKeyDown` convention — the chord has to work while focus is anywhere, including nowhere, and an
inline handler would mean clicking the right box first, on stage, mid-sentence. It POSTs an **empty
body**: the words are the server's and so is the recipient, so there is nothing for the browser to
choose. A failure is logged and swallowed on this side; the backend still reports one honestly (404
with nobody connected, 502 when the socket refused it), but an unhandled rejection thrown into the
page during a demo is a worse answer than a beat that did not land.

## The rail is on both surfaces

`TransparencyRail` reads the slice directly rather than taking props, so it can be dropped onto any
surface the walkthrough visits — and it has to be. The refusal happens on the home surface and the
answers happen on the plan surface, while the meter's running total spans both. A rail only on the
plan page would mean the guardrail's zero was never seen beside a row that cost something.

## The first frontend tests

vitest, React Testing Library and jsdom were fully configured in the accelerator baseline, with **no
test file and no workflow**. There are now 75 tests, and the wiring that runs them:

- `npm run test:run` — `vitest run`, never a bare `vitest`, which watches.
- `bash scripts/frontend-tests.sh` — the feedback loop, declared in `AGENTS.md`.
- `.github/workflows/frontend-tests.yml` — separate from `test.yml`, which is triggered on Python
  paths; widening those would run the backend suite for a CSS edit.
- `src/tests/ci/test_frontend_ci_wiring.py` — fails if any of the above is quietly disconnected.

The suite that matters most is `transparencySlice.test.ts`: every payload in it is what
`send_status_update_async` actually puts on the wire, so it fails if the backend's payloads and the
frontend's reading of them ever drift apart.

## Not verified live

- None of this has rendered against a real socket. Every assertion is against the payload shape
  recorded in #23, and #23's own assertions stopped at what the backend sent.
- Whether an executor id on `token_usage` matches a roster agent's `name` exactly. `modelsByExecutor`
  answers to three spellings of each name; if the live stream uses a fourth, the model column empties
  to `—` rather than showing something wrong.
- The estimated credit rate is Microsoft's published rate, not a measured bill.
