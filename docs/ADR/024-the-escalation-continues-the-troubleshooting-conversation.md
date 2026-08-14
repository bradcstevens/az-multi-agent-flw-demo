# ADR-024: The escalation continues the troubleshooting conversation

## Status

Accepted

## Date

2026-08-14

## Issue

#61 (spec #1)

## Context

The demonstration's strongest single claim is that the assistant remembers what you tried and does
not make you repeat it. Beat 3 collects three **Attempted steps** through the clarification seam;
beat 4 escalates, and the **Simulated ticket** the approval raises is supposed to carry them.

It cannot. `TaskService.createPlan` mints a fresh `session_id` on every tap, the **Troubleshooting
record** is keyed by session, and `draft_service_ticket` reads the record for whichever session the
turn in flight belongs to. So beat 4 reads an empty record and `format_attempted` returns
`not reported` — the beat that exists to prove the memory proves its absence.

The frontend's behaviour is not an oversight. The comment above it argues for itself:

> A session is one conversation — one **Simulated ticket**, one **Lane** taken, one troubleshooting
> record — so the tab cannot simply re-use the session it signed in on.

That reasoning is right and this decision does not overturn it. What was wrong is a hidden premise:
that a conversation ends when the presenter returns to the home screen. Beats 3 and 4 *are* one
conversation — an associate describing a fault, trying things, and then asking for help with the
same fault. The surface split them because the only route back to the Quick Tasks is **New task**,
which starts a new one by construction.

Two facts found while deciding this reshaped it, and both are the opposite of what the issue
assumed:

- **The Lane is a property of the request, not the session.** `select_lane(input_task.lane, …)`
  runs per request, and a lane change inside a live session is already handled — `plan_review_mismatch`
  forces the workflow rebuild. So the escalation keeps its **Deliberate lane**, its own plan and its
  own approval gate while sharing the session. The obvious objection to continuing the conversation
  does not hold.
- **No backend change is required.** `InputTask.session_id` is a required field the client already
  sends; server-side minting is only a fallback for an empty one. `note_turn(user_id,
  input_task.session_id)` notes whatever the request carried, and `_ticket_stores()` resolves the
  draft against exactly that. Carrying beat 3's session on beat 4's request makes the existing code
  read a populated record.

## Decision

**The escalation is a new task submitted into the troubleshooting conversation's session**, reached
by a **Follow-on task** card rendered inside that conversation.

Four parts, each load-bearing:

- **The follow-on is authored on the Quick Task, not in the surface.** `StartingTask` gains a
  `follow_on` pointer; the troubleshooting task names the escalation task. The prompt and the
  declared Lane stay in `content_packs/`, resolved the way **Rehearsed replies** already resolve —
  by matching the plan's own `initial_goal` — so this repository does not keep the list twice and
  the affordance survives a reload.
- **A task named as a follow-on is not a home card.** The roster still declares six; the home grid
  renders five. Tapping the escalation cold would start a fresh session with an empty record and
  produce the very `not reported` ticket this decision removes, and *"a Quick Task is a claim about
  what will happen when somebody taps it"* cannot survive a claim that depends on where you tapped.
  The rule is derived from the pointer that already exists, so there is no second flag to keep in
  sync.
- **The card is ungated.** It renders whenever the plan declares a follow-on. The gate already
  exists where the audience can watch it fire — the agent's offer to raise a ticket is driven by
  `escalation_due` — and a second copy in the UI would have to ride a flag this subsystem writes
  best-effort by design. That gate fails *closed*, mid-beat, with no recovery. Tapping early is
  honest: the ticket carries the steps that were actually tapped, fewer rather than false.
- **It sits in the conversation, above the chat box and below the chips slot.** Not in
  `PlanPanelRight`: below the **Stacking breakpoint** the rail stacks *beneath* the conversation, so
  on the associate's phone the action that ends the beat would be a full scroll away. Not in the
  chips slot either — clarifications arrive and clear repeatedly through beat 3, and a card sharing
  that slot would blink in and out between chip taps.

The card carries no new copy. It shows the authored Quick Task name — *"I can't fix it"* — exactly
as the other five do, which is also why it does not read as the assistant offering to give up: it
is the associate's own words, like every card on this surface.

**The presenter stops clicking New task between beats 3 and 4.** That click is the defect.

## Considered Options

- **Move step-reporting into the escalation turn**, merging beats 3 and 4. Rejected on two counts.
  It collides head-on with #62, which measured this happening live and named it the defect —
  *"a presenter cannot improvise answers to a diagnostic interview on stage."* And it shrinks the
  claim from *"everything I told it three minutes ago is already in this ticket"* to context
  carried within a single turn, which is a materially weaker thing to demonstrate.
- **Key the Troubleshooting record by shift rather than by session.** Genuinely attractive: it would
  close the gap between `docs/troubleshooting-memory.md`, titled *"The memory of one shift"*, and
  the glossary's *"one session's attempted steps"*. Rejected because it buys cross-conversation
  memory by weakening the invariant the memory exists to protect. The record's requirement runs one
  way — *"it may never claim a step was attempted that was not"* — and widening the key is precisely
  how the coffee brewer's steps reach the car wash's ticket. It also costs a Cosmos partition change
  and equipment scoping to be safe again. Joining the sessions gets the same result with the
  invariant untouched.
- **The plan's chat box submits a new task when no clarification is pending.** Would fix a real
  latent bug in passing — `PlanPage.tsx:326` posts a clarification with `request_id: ''` when none
  is pending, and toasts *"Please enter a clarification"* regardless. Rejected here because it puts
  a keyboard back into beat 4, which #26 spent real effort removing, and because free text falls to
  the **Lane keyword fallback**: the beat's Deliberate routing would rest on keyword matching
  instead of authored metadata. The bug is raised separately.
- **A "Continue this conversation" control beside New task.** Honest, but it makes the session model
  visible to an audience that should not have to think about it, and it adds a step to the runbook
  where this decision removes one.
- **Leave the escalation on the home screen as well.** Rejected: the runbook already carries a line
  for *"the ticket has no attempted steps"*, which is the tell that the failure is expected rather
  than fixed. A second entry point keeps it one mis-tap away.

## Consequences

- **Positive:** No backend change. `InputTask.session_id`, `note_turn` and `_ticket_stores` already
  compose to read a populated record the moment the request carries the right session.
- **Positive:** The **Troubleshooting record** stays session-keyed, so it can still never carry
  another fault's steps onto this ticket.
- **Positive:** Both beats survive as distinct claims — a Fast-lane memory beat and a Deliberate-lane
  approval beat — and the walkthrough loses a click rather than gaining one.
- **Negative:** `QuickTasks.test.tsx` asserts the grid renders *every* task and that badges match
  *every* lane. Both become "every task the home screen offers." The count of six moves from the
  grid to the roster, where `test_store_pack.py` already asserts it.
- **Negative:** The escalation can no longer be started cold. An associate who already knows they
  cannot fix something describes the fault first. That is the honest path anyway — a ticket raised
  before anything was tried is a ticket reading `not reported` — but it is a real reduction in what
  the surface offers.
- **This does not, on its own, make the beat work.** #62 measured that no ticket is ever drafted:
  `GET /api/v4/escalation/ticket` answered `{"drafted": false}` on a completed approved turn. #61
  populates the record the draft will read; #62 makes the draft happen. Neither alone is
  sufficient, and this decision is the reason #62's fix is sufficient when it lands — a
  deterministic draft against an unjoined session would still say `not reported`.
- **Risk accepted:** Someone will notice the escalation card is ungated and add an `escalation_due`
  flag to make it appear "properly". This record is the countermeasure. The gate is in the
  conversation on purpose.

## References

- [ADR-013: Vary Plan review per request instead of building an orchestrator bypass](./013-per-request-plan-review-over-orchestrator-bypass.md)
- [ADR-022: Completed tasks are hidden, never deleted](./022-completed-tasks-are-hidden-never-deleted.md)
- [docs/troubleshooting-memory.md](../troubleshooting-memory.md) — the record, the clarification seam and `escalation_due`
- [docs/escalation-ticket.md](../escalation-ticket.md) — `steps_attempted` runs one way, in three places
- [docs/quick-tasks.md](../quick-tasks.md) — the six tasks, and why a prompt is never restated
- `CONTEXT.md` — **Follow-on task**, **Troubleshooting record**, **Quick Task**, **Stacking breakpoint**
