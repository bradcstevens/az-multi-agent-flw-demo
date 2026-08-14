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
| The seam | `orchestration_manager._handle_plan_reviews` | The approved branch submits the draft and pushes the card. The rejected branch does not. |
| The bridge | `GET`/`POST /api/v4/escalation/ticket` | What the MCP container calls. |
| The tool | `src/mcp_server/services/escalation_service.py` | `draft_service_ticket`, on the `escalation` domain. One tool. |
| The card | `src/App/src/components/escalation/SimulatedTicketCard.tsx` | Every row, and the `SimulatedBadge`. |

## The approval is the confirmation, and it is not instructed

The acceptance criterion is that the plan-approval step *is* the ticket confirmation — one
confirmation, not two. A system message saying *do not ask again* is a thing a model can improvise
past on the turn that matters, so the confirmation is taken at the seam instead.
`_handle_plan_reviews` already intercepts every approval before it reaches the framework.
`_raise_confirmed_ticket` runs in the **approved** branch, submits whatever draft the session holds
and pushes the card. The rejected branch calls nothing: a rejected plan is an unraised ticket, which
is the entire point of routing this to the **Deliberate lane** in the first place.

That is #21's move at a different seam, and for the same reason. It happens on every approved plan
whether or not the model remembers anything.

### The approval comes before the draft, so the submission is taken twice

Issue #50, found by a browser: the card never appeared. The plan review is presented **before** the
plan runs, and the plan whose last step is *"draft a simulated service-incident ticket"* has not
drafted one yet — so `_raise_confirmed_ticket` at the approval seam finds nothing, correctly says
nothing, and the associate reads a ticket in the prose with no card beside it.

So `run_orchestration` calls the same seam again when an **approved** run finishes, once the draft
exists. Both calls are the same single confirmation: nothing further is presented, the associate is
asked nothing, and the two ways this could have become a second confirmation are closed —
`TicketStore.submit` is idempotent, so a re-submission returns the ticket rather than reissuing the
number, and the manager remembers which ticket it has already put on the surface, so one approval
raises one card. A run with no plan review never reaches the call, which matters because the
EscalationAgent is in the pool on **every** turn: a ticket raised at the end of an unapproved Fast-lane
turn is the unconfirmed submission the gate exists to prevent. A rejected plan cancels the run
before it.

Every unit test around the seam passed throughout, because each handed it a store that already held
a draft. A fake that supplies what the collaborator cannot yet have is the #47 lesson one layer in.

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

The card renders in `PlanPanelRight`, which is the surface that survives the 640px **Phone
breakpoint** — the associate's screen is a phone, and a ticket they cannot see is a ticket they did
not confirm.

The slice clears on transparency's `conversationStarted` through `extraReducers` rather than
declaring a boundary action of its own. That boundary is already dispatched from two places, and a
second action is a second place to forget one of them. It deliberately ignores `requestStarted`: a
raised ticket stays raised when a new question is asked, which is the presenter alerts' lifetime and
for the same reason — asking a question does not unraise a ticket.

## What is not proven here

- **The live turn does not call `draft_service_ticket` — measured, 2026-08-14, issue #62.** The
  **Demo validator**'s escalation beat approved a plan against `rg-macae-flw-v1` and let it run to
  completion; `GET /api/v4/escalation/ticket` then answered `{"drafted": false}`. This was always
  *instructed*, not measured; the browser measured it, and the instruction is not being followed.
  With no draft, the deterministic half has nothing to raise, so the **Simulated ticket** exists on
  that deployment only in the model's prose.
- **The submission-at-completion seam has never been observed live**, for the same reason. An
  approved run submits when it finishes (issue #50); every proof of that is a unit test.
- **A failed submit is silent.** If the write fails the plan is still approved and no card is
  pushed, but the model's own words on that turn are outside this code's reach and may still say a
  ticket was raised.
- **The Cosmos round-trip is asserted against a fake store**, as the rest of the memory container's
  tests are.
