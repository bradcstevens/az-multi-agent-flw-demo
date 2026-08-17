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

## Three scopes, and why the meter is not one of them

The panels do not all belong to the same span of time, and treating them as if they did is how a
surface ends up saying something that is not so:

| State | Scope | Cleared by |
| --- | --- | --- |
| `source` | **One answer** | `requestStarted` — HomeInput submission, Quick Task activation, and `ChatPage.handleOnchatSubmit` |
| `alerts` | **One conversation** | `conversationStarted` — the `planId` effect, and `resetPlanVariables` |
| `railPinned`, `railSourceUsed` | **One conversation** | `conversationStarted` — the presenter's **Pinned panel** choice and the rail's one automatic expansion reset together |
| `meter` | **The whole walkthrough** | nothing in the browser |

The Grounding panel is the one that matters. Only the SOP hop emits `source_used`; a troubleshooting
question answered inside Foundry emits nothing at all. So a panel that simply held its last value
would still be showing `Copilot Studio → Dataverse` beside an answer that never left Foundry —
crediting Copilot Studio on screen with an answer it did not give, which is the same lie as emitting
for a failed reply, told from the other end.

The meter is deliberately the exception. The refusal is recorded on the home surface and the costed
answers arrive on the chat surface, so a meter cleared at the conversation boundary would never show
the guardrail's zero beside a row that cost something — which is the entire comparison R7 exists to
make.

Both clearing points are dispatched from more than one place, because there is more than one way to
start each. A question is started by `HomeInput.handleSubmit`, its Quick Task
activation, **and** by `ChatPage.handleOnchatSubmit`, the clarification path — a
follow-up produces a new answer just as much as a first question does. A conversation is started by
the `planId` effect and not only by `resetPlanVariables`, which runs on the no-planId error path
alone: wiring the reset there and nowhere else would have left it firing almost never.

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

A citation the backend could not **name** is rendered, labelled `Unnamed document`, rather than
dropped. `citations_from_activity` emits `name: ""` when the appearance metadata carries none, and
discarding it empties the citation list — which the panel renders as the *uncited* state, printing
"found no matching procedure" about a document that did come back. That is the honest miss reported
for a miss that did not happen, and it is the miss branch's one way of lying. Only a citation with
neither a name nor a snippet is dropped: there is nothing there to render.

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

### The agent is named once

The column is headed `Agent`, so the cell does not say it again: the meter reads `Troubleshooting`,
`Shift Tasks`, `Escalation`, `Workforce`. That is the **Agent display name** rule — one base name
through `getAgentDisplayName`, two presentations — and it is deliberately *not* the Agent Team
panel's, which keeps the suffix because it names an agent inside a sentence. Until #70 the meter was
the only panel in the rail rendering `agent_name` raw off the wire, and the repeated noun is what
made the name too long to fit: `Troubleshoo` / `ting Agent`, in the panel whose whole job is to be
believed.

Two things are sized against that, and both are read out of the stylesheets by the frontend loop
rather than eyeballed. The **Agent** column holds the longest word in the store assistant roster:
`Troubleshooting` measures **96.4px** at the meter's size and weight, against the 73px that 30% of a
~257px table gave it, and it has 101.4px at 41%. The table is 257px and not the rail's 288 because
the panel inside the rail is a padded card with a border of its own. And the width came from
**Model**, **Calls** and two points of **Tokens**, which keeps the five-figure total #60 sized it
for and no more: a deployment name breaks at its own hyphens and costs a
line, while a token total may not break at all, so a column too narrow for a five-figure count sets
it across the estimated Copilot Credits.

Those pixel figures are measured in a browser, not derived, and that distinction is the whole of why
#70 took two attempts. The first sized the column from a per-character average of 6px — but
`Workforce` is 6.80px a character and `boundary` 7.04, so the average was an under-estimate wearing
the word "conservative", and the column came out six pixels short with the guard agreeing. The guard
now sums **measured per-character advances**, each rounded up, so what it predicts is never less
than what Chromium lays out; it over-states `Troubleshooting` by 3.4px, which is the direction a
check about fitting should be wrong in.

Two smaller consequences of the same arithmetic. `overflow-wrap: break-word` is scoped to the table
**body**, because the one heading that ever broke was `MODEL` set as `MO` / `DEL` — a label obeying
a rule written for data. And the headings are **sentence case**: uppercase costs about a fifth of a
label's width, and it is what makes all five fit their columns rather than run into one another.
`Calls` still overflows by 9.3px, because holding every heading, every figure and a 96.4px name at
once needs about 6px more than the table has — the headings have always overflowed, and there is
less of it now than before.

The guardrail row is the exception. Its name is a constant in `models/meter.ts` rather than anything
that arrived over a wire, and it is rendered as written — the **Identity boundary gate**, not a
title-cased paraphrase of it.

## Agent Team panel

Populated from the **workflow roster** (`planData.team.agents`), not from the plan. With Plan review
off there is no plan object at all (ADR-013), and the panel previously read
`planApprovalRequest.team` — behind an early return that rendered the entire right-hand panel as
"No plan available". On the Fast lane, which is most of the walkthrough, the audience saw no agents
and no panels. The early return is gone, and `PLAN_ARRIVING` — *"Plan is being generated…"*, owned
by `models/progressNarration.ts` since #64 along with every other string shown while a request is in
flight — is now rendered only when a plan is actually coming.

### Plan vocabulary only where there is a plan to review

That fix left the rail heading a **Plan Overview** section on every request and choosing, underneath
it, between `PLAN_ARRIVING` and a sentence saying there was nothing there — a section whose only
content was the statement that it was empty. #78 removes the second case and the section along with
it.

The rule cannot be *"only if a plan is actually being created"*, because a `Plan` is constructed
before the **Lane router** has run and every request therefore has one. What varies is whether a
plan is put to the associate **for approval**, and that has a real signal already: the
`plan_approval_request` frame, ADR-023's *Done* phase. No new events. So `PlanPanelRight` renders
the section when — and only when — it holds a `planApprovalRequest`, and `PLAN_ARRIVING` is what the
section says between the frame arriving and its steps doing so.

The catch is the heading. It is part of the **Heading outline** (#57, WCAG 1.3.1), so removing it
makes the outline *conditional* — which is an improvement rather than a regression, because a
screen-reader user currently skims to a heading and finds nothing behind it. `headingOutline.test.tsx`
therefore asserts the chat surface's outline **twice**, once per lane, rather than losing the case it
used to cover: the Fast lane's outline has no `Plan Overview` in it, the Deliberate lane's does, and
neither skips a level.

### It states availability, never participation

The panel is on screen for the whole loading window — `PlanPanelRight` renders *outside*
`ChatPage`'s `loading || !planData` branch — and `planData` is `null` for all of it. Sourced only
from the plan fetch, it therefore rendered its honest empty state, **"No agent roster loaded for
this conversation."**, two inches from a spinner reading *"Initializing AI agents…"*. One of those
was wrong and it was not the panel — and the spinner no longer says it, because #64 deleted the
four authored stages outright. What that position shows now is the **Progress narration**, which
names one agent at a time as each speaks, and nothing at all before any of them has (ADR-023).

Nothing was missing. The **store assistant roster** is in Redux from `HomePage`'s mount, so
`selectedTeam` is the panel's second source and `selectTeamAgentCount` — exported and unused since
the slice was written — is the count. Resolution order is in `models/agentAvailability.ts`: this
conversation's own roster, then the plan's flat list of names, then the roster this tab is holding,
then nothing. A historical plan opened from the chat list ran on its own team, and the team the tab
happens to hold is not a claim about it — which is why `selectedTeam` is a fallback and never a
replacement.

What it says is **availability**, and nothing stronger. `AVAILABILITY_NOTE` is on screen under the
names for the same reason the count says *available* rather than *identified*: on the
boundary-probe beat the **Identity boundary gate** refuses above the **Lane router** and the number
that participate is **zero**, which is exactly why the **Token meter** renders a measured `0` on
that row. "3 agents identified" over that beat contradicts the panel directly beneath it. Who
*did* answer is named one at a time, as each specialist speaks, by the **Progress narration**
(ADR-023) and in each reply's header.

The count is a real heading — `SUBSECTION_HEADING`, one level below the panel's own title — so the
roster is reachable by heading navigation like everything else on the rail (#57). The empty state
stays: a deployment with no store assistant is a real state and the panel is right to say so. It
just may not say it about a team the app is already holding.

### And it says it before a question is typed

#79 puts the panel on the **home surface**'s rail as well. Nothing new was needed: the roster is
`selectedTeam`, which this page already resolves in order to exist at all, and the count is
`selectTeamAgentCount`. There is no request of the panel's own and nothing on the socket. The home
surface passes no conversation roster — there is no conversation — which is why `team` and `plan`
are optional props rather than a `null` standing in for a question nobody asked.

It is rendered only where there **is** a roster, on #78's rule. `selectedTeam` is null for the whole
of the team fetch and again on a deployment with no store assistant, and the panel's empty state is
wrong twice over on this surface: it would sit beside the spinner reading *"Starting the store
assistant…"*, which is exactly the contradiction #65 removed one surface across, and it speaks of
*"this conversation"* when there is none. `HomeInput` already says the honest version of the second
case in the middle of the screen, and once is enough.

It is the honest neighbour of the loading copy #64 deleted. *"Initializing AI agents…"* was a
scripted stage with no signal behind it; **"3 specialists available"** is a fact about the roster,
stated where a presenter opening the demo used to have nothing to point at.

The home surface is also where it is hardest to get away with. The **Identity boundary gate**
refuses the boundary probe *there*, above the **Lane router**, so the meter's guardrail row is two
panels below the roster with a measured **zero** on it. Availability survives that beat unchanged —
three were available and none was asked — and the note says *"which of them take part"* rather than
*"which of them take this question"* for the same reason the count says *available*: before
anything is typed there is no *this question* to speak of, and a note that presumes one is the same
untruth as a participation claim, in the grammar instead of in the verb.

Availability is deliberately **not** a phase of the **Progress narration**. ADR-023's phases are
each an observed event and run from a question being sent to its answer arriving; availability is a
standing fact that is true before any of them and is not advanced past. `progressNarration.test.ts`
fails if a phase for it is ever added, or if any phase's words mention it.

## Presenter alert

Rendered as visibly a different object from a reply: `role="alert"`, its own icon, a "Proactive
alert" badge, and a title where a reply carries an agent name. An alert answers no question, because
nobody asked one — an alert mistaken for an answer is worse than no alert.

The chord is **Ctrl + Alt + Shift + A**, matched on `event.code` rather than `event.key`: with Alt
held, several keyboard layouts compose a different character, and a chord that only works on US
English is a chord that fails on the borrowed laptop. Three modifiers, so it cannot be produced by
typing a question, and `metaKey` must be up so it never fires under an operating-system combination.
**AltGraph** must be up for the mirror-image reason — on Windows and several European layouts AltGr
*is* Ctrl+Alt, so Shift+AltGr+A while typing a question would otherwise fire it mid-sentence — and
an **auto-repeat is not a press**, or holding the chord POSTs one alert per repeat interval and the
beat becomes a stack of identical cards.

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
answers happen on the chat surface, while the meter's running total spans both. A rail only on the
chat page would mean the guardrail's zero was never seen beside a row that cost something.

## The panels are headings

Each panel's title is a section heading rather than a styled span (#57), at the level
`models/headingOutline.ts` declares. The rail's whole job is to be **skimmed** — where the answer
came from, what it cost, who could have answered — and heading navigation is how that is done
without a mouse or a pair of eyes. A span makes the rail skimmable by layout only, which is to say
by sight only. See [The heading outline](store-surface.md#the-heading-outline).

## The first frontend tests

vitest, React Testing Library and jsdom were fully configured in the accelerator baseline, with **no
test file and no workflow**. There are now 88 tests, and the wiring that runs them:

- `npm run test:run` — `vitest run`, never a bare `vitest`, which watches.
- `bash scripts/frontend-tests.sh` — the feedback loop, declared in `AGENTS.md`.
- `.github/workflows/frontend-tests.yml` — separate from `test.yml`, which is triggered on Python
  paths; widening those would run the backend suite for a CSS edit.
- `src/tests/ci/test_frontend_ci_wiring.py` — fails if any of the above is quietly disconnected.

The suite that matters most is `transparencySlice.test.ts`: every payload in it is what
`send_status_update_async` actually puts on the wire.

But it hand-writes those payloads, so **it cannot notice a rename on the backend** — a field renamed
in `payloads.py` leaves all 88 vitest tests green and the panel silently dark. That seam is spanned
from the Python side, by `src/tests/ci/test_transparency_contract.py`, which **imports** the backend
dataclasses and asserts the browser's parsers read every field they carry, that the citation keys
`/sop/ask` builds are all read, and that the three `WebsocketMessageType` wire strings are identical
at both ends.

Three details make it an assertion rather than a formality. Comments are **stripped** before
scanning, or a field named only in prose would satisfy a check nothing satisfies in code. Each check
is scoped to **one parser's body**, because the payloads share field names — `agent_name` is read by
two — so a whole-file search reports a field as read after the parser that needs it stopped reading
it. And the citation keys are read back out of `router.py` rather than listed in the test, because a
list written down in a test is a list that agrees with itself forever.

It runs on both sides of the seam: `test.yml` triggers on Python paths, and names
`transparency.ts` and `enums.tsx` explicitly — just those two, since widening it to `src/App/**`
would run the backend suite for a CSS edit, which is why the two workflows are separate at all.
Mutation-checked: renaming `conversation_id` on `SourceUsed`, changing `SOURCE_USED`'s value,
renaming a citation key in the route, dropping `agent_name` from one parser while the other keeps
it, and defaulting a count with `|| 0` each turn it red.

## Not verified live

- None of this has rendered against a real socket. Every assertion is against the payload shape
  recorded in #23, and #23's own assertions stopped at what the backend sent.
- Whether an executor id on `token_usage` matches a roster agent's `name` exactly. `modelsByExecutor`
  answers to three spellings of each name; if the live stream uses a fourth, the model column empties
  to `—` rather than showing something wrong.
- The estimated credit rate is Microsoft's published rate, not a measured bill.
