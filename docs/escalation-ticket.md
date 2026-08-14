# The ticket the approval raises

Issue #22. An associate who has tried three things and is still holding a broken coffee machine is
offered a service ticket, reads it, approves the plan — and that approval **is** the ticket being
raised. There is no second confirmation, and nothing they already said is asked for again.

The rule this iteration is built to is the one #23 through #25, #19 and #21 were built to — *a
surface may say nothing, but it may not say something that is not so* — applied to **a claim made on
the associate's behalf**. #21 applied it to memory, which is a claim made to the associate. A ticket
is a claim made to somebody outside the room, in the associate's name, about what happened on this
shift. The failure modes are not symmetric: a ticket that was never raised is a piece of equipment
that stays broken and an associate who can see nothing arrived. A ticket that was raised saying
something the associate did not say is a service desk acting on a fiction, and nobody in the store
finds out.

## What is where

| Piece | Where | What it is |
| --- | --- | --- |
| Ticket rules | `escalation/ticket.py` | Pure. `TKT-001`'s field order, the ticket number, what a confirmation may change, what may never be typed. |
| Service ticket | `common/models/messages.py`, `escalation/store.py` | One `DataType` member and one model in the schemaless memory container. No migration. |
| The wire shape | `escalation/payloads.py` | `TicketRaised` — the ordered rows the browser renders. |
| The seam | `orchestration_manager._handle_plan_reviews` | An approved escalation drafts from the session record, submits it and pushes the card. The rejected branch does none of those things. |
| What is a question | `orchestration/clarification.py` | Pure. Which of the framework's pauses is a **Clarification**, and what the agent is told on a turn that asks nothing. |
| The bridge | `GET`/`POST /api/v4/escalation/ticket` | What the MCP container calls. |
| The tool | `src/mcp_server/services/escalation_service.py` | `draft_service_ticket`, on the `escalation` domain. One tool. |
| The card | `src/App/src/components/escalation/SimulatedTicketCard.tsx` | Every row, and the `SimulatedBadge`. |

## The approval is the confirmation, and it is not instructed

The acceptance criterion is that the plan-approval step *is* the ticket confirmation — one
confirmation, not two. A system message saying *do not ask again* is a thing a model can improvise
past on the turn that matters, so the confirmation is taken at the seam instead.
`_handle_plan_reviews` already intercepts every approval before it reaches the framework. For an
authored escalation task, `_raise_confirmed_ticket` first drafts from the session's troubleshooting
record, then submits that stored ticket and pushes the card. The rejected branch calls nothing: a
rejected plan is an unraised ticket, which is the entire point of routing this to the **Deliberate
lane** in the first place.

That is #21's move at a different seam, and for the same reason. It happens on every approved plan
whether or not the model remembers anything.

## The approved escalation asks the associate nothing

Issue #62. A live approved escalation turn ran to completion — 2810 characters of answer — and
`GET /api/v4/escalation/ticket` said `{"drafted": false}`. The drafting is deterministic now, which
is the first half; the second half is what the turn did *instead*. It stopped twice in one pause and
then kept improvising diagnostics — *"Is the left-head display lit? … FILL, HEATING, or an error
code starting with E?"* — and ended in troubleshooting advice. A presenter cannot improvise answers
to a diagnostic interview on stage, and an associate who has already approved the ticket is being
asked about a fault the ticket has already recorded.

So the number of questions the approved escalation puts to the associate is **bounded, at zero**,
and the bound is taken at the clarification seam rather than asked for in a prompt. Two rules, both
in `orchestration/clarification.py` and its caller:

- **Only a `request_user_clarification` with words in it is a question.** The framework pauses on
  every approval-gated tool call. `_handle_tool_approvals` presented all of them, and one that
  carries no `questions` argument — the observed `list_attempted_steps` — reached the associate as
  the placeholder *"The agent needs clarification."* and held the turn for the full 300-second
  wait. Three things were wrong with that and only the first is cosmetic: a question with no words
  cannot be answered; a **Rehearsed reply** tapped into it is spent on a call that will not read it;
  and the answer was written into the troubleshooting record, which is the field `steps_attempted`
  is filled from — so a pause nobody was asked about could put words in the associate's mouth on a
  ticket. Any other gated call is now approved without the associate hearing of it, which is what
  `require_approval="never"` would have done.
- **A ticket-on-approval turn asks nothing at all.** Not a preference about pacing: on this task the
  ticket is drafted and submitted from the session's record at the approval seam, and nothing the
  associate could answer afterwards changes what it says — `steps_attempted` runs one way out of the
  record in the three places above, and every field nobody reported is written `not reported` rather
  than asked for. A question whose answer changes nothing the associate can see is worse than no
  question: it implies the ticket is waiting on it.

The agent is *told* the associate was not asked, rather than left with the tool body's *"No answer
was provided by the user"*, which reads as a failure worth retrying. What it is told invents no
answer on the associate's behalf — that is the one thing a ticket may never carry.

The bound is read off the running team's **authored** task, the same `ticket_on_approval` fact that
makes the approval raise the ticket, and carried to the seam by the turn. Reading it twice from two
places is how the two would come to disagree: a turn that raises the ticket deterministically *and*
interviews the associate about it.

## There is no submit tool

The second confirmation is not forbidden, it is **unreachable**. `EscalationService` exposes exactly
one tool and that tool drafts; there is no route the container can call that raises anything, and
`DOMAIN_ALLOWED_TOOLS["escalation"]` names one tool by name. A test asserts that no tool name, no
route path and no allowlist entry contains *submit*, *confirm* or *raise* — because the way this
requirement fails is not somebody arguing for a second confirmation, it is somebody adding a tool
that looks helpful.

The allowlist entry is load-bearing twice over, which is #21's finding applied again. A domain with
no entry gets **no filter**, which means the shared `ask_user` tool reaches the agent — and
`ask_user` *is* a second confirmation step, quite apart from the `SESSION_USER_ID` contract that no
longer exists. `EscalationAgent` keeps `user_responses: false` for the same reason.

## The attempted steps run one way

`steps_attempted` is filled from the troubleshooting record and can only be filled from there. Three
places enforce it and none of them is prose:

- `draft_service_ticket` **has no such parameter**. A model cannot pass it.
- The `POST` route **discards** a supplied value before it reaches the ticket.
- `draft_fields` overwrites it from the record even on the correction path, where every other field
  merges over the previous draft.

The requirement is that the associate never re-types what they already told the assistant. Asking
the model not to is the version of this that works until the one turn it doesn't.

## What a confirmation may change, and what a correction may not blank

`submitted_fields` writes exactly three fields: the status, the ticket number and the timestamp. It
touches no content. A confirmation that could edit the ticket is a ticket the associate did not read
the version of.

`draft` **merges** over the previous draft rather than replacing it. An agent correcting one field —
the priority, say — sends that field; a replacing write would blank the other eighteen, and the
associate has already read the ticket and will not read it again. `draft` also refuses to touch an
already-submitted ticket, and `submit` is idempotent, because one turn can carry more than one plan
review.

## `TicketStore.read` is not total, and `TroubleshootingStore.read` is

This asymmetry is deliberate and it is the one thing here most likely to be "tidied up".

`TroubleshootingStore.read` returns an empty record when there is nothing stored, because its caller
asks *what has this associate tried* and **nothing** is a true answer.

`TicketStore.read` returns `None`. Its caller is the approval seam, which runs on **every** approved
plan on the Deliberate lane — including every approved plan that has nothing to do with a ticket. A
total read would hand that seam a blank ticket every single time and raise one, and the surface
would show a ticket for a plan that was never an escalation. Nothing recorded must stay
distinguishable from a record of nothing.

## The number is derived, not counted

`ticket_id_for` is a sha256 of the session, rendered `SIM-223-NNNN`. A counter is shared state that
a container restart resets, and a reissued number is two different faults wearing one identity at a
service desk. Deriving it means the same session asks twice and reads the same number back, and
`SIM-` says on the number itself what the badge says on the card.

## The badge is a property of the card

There is no `simulated` flag on the wire and the card does not read one. Every ticket this system
produces is simulated, so a flag would be a field that could be omitted, and an omitted flag is an
unbadged ticket that looks real. `SimulatedBadge` renders unconditionally — the same reasoning #25
used to decide *which* things carry it: label the invented things, and only those.

## Where it renders and when it clears

The card renders in `PlanPanelRight`, which is the surface that survives the **Stacking
breakpoint** — the associate's screen is a phone, and a ticket they cannot see is a ticket they did
not confirm.

The slice clears on transparency's `conversationStarted` through `extraReducers` rather than
declaring a boundary action of its own. That boundary is already dispatched from two places, and a
second action is a second place to forget one of them. It deliberately ignores `requestStarted`: a
raised ticket stays raised when a new question is asked, which is the presenter alerts' lifetime and
for the same reason — asking a question does not unraise a ticket.

## What is not proven here

- **The drafting no longer depends on a live turn, and that was measured.** It used to: the
  `EscalationAgent` was *instructed* to call `draft_service_ticket` before presenting a ticket, and
  a live `gpt-5.4` turn did not (#62) — an approved escalation that ran to completion left
  `{"drafted": false}`. The draft is taken at the approval seam now, from the session's record, and
  the agent is told not to call the tool at all.
- **Nothing here has run against a deployment since.** The seam, the bound and the join are asserted
  against fakes; `e2e/specs/escalation.spec.ts` asserts them through a browser and needs a
  deployment, `az login` and real Copilot Credits.
- **A failed submit is silent.** If the write fails the plan is still approved and no card is
  pushed, but the model's own words on that turn are outside this code's reach and may still say a
  ticket was raised.
- **The turn's prose is still the model's.** The bound stops the escalation *asking* the associate
  anything; it cannot stop an agent narrating a question it will never receive an answer to.
- **The Cosmos round-trip is asserted against a fake store**, as the rest of the memory container's
  tests are.
