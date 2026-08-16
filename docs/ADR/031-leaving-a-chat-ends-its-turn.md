# ADR-031: Leaving a Chat ends its turn, and says so

## Status

Accepted

## Date

2026-08-16

## Issue

#89 (map #81, spec 1)

## Context

`BRIEF.md` asks for one thing here: *"they are prompted with a confirmation of plan cancelation.
There shouldn't have been any plans included in this conversation yet… we need to remove the
confirmation."* The complaint is exact and it is right. The dialog is
`PlanCancellationDialog.tsx`, driven from `ChatPage`, gated on `usePlanCancellationAlert.tsx:24`:

```js
return planData?.plan?.overall_status === PlanStatus.IN_PROGRESS;
```

[ADR-028](./028-a-reviewable-plan-is-earned-by-a-transaction.md) already named that predicate as the
defect — it is true of every conversation — and expected this ticket to repair it with the **Lane**
it recorded onto the **Plan record**. Reading the path end to end says the predicate is the smallest
thing wrong here.

**The dialog is wrong in both directions.** With no approval frame — every **Fast lane** chat, and
every **Deliberate lane** chat before the plan arrives, which is precisely the case the brief
describes — confirming calls **no backend at all**: `handleConfirmCancellation` guards the call on
`planApprovalRequest?.id`, so it navigates and drops the socket while the dialog claims *"the plan
process will be stopped and the plan will be cancelled."* It stops nothing. With an approval frame,
confirming POSTs `/v4/plan_approval` with `approved: false`, and `plan_service.py:164-173` reaches
`delete_plan_by_plan_id` — the Plan document is **deleted outright**. Not `canceled`, not `failed`.
The conversation leaves the history, and the dialog says nothing about it.

So the only thing in this repository that can remove an unsettled **Chat** is a navigation gesture,
while the control actually named *"Delete chat"* refuses to.

**Nothing on the server persists a turn.** `_process_event_stream` performs no Cosmos writes in any
branch; neither do the response callbacks. The transcript exists only because the browser echoes
each frame back through `POST /v4/agent_message`, and `plan_service.py:196-210` — reached from the
client's `FINAL_RESULT_MESSAGE` handler — is the **only** writer of `overall_status = completed`.

**Therefore leaving a chat does not orphan a turn. It destroys it, silently.** The socket closes,
the orchestration keeps computing against a connection that is gone, every frame is dropped, no
transcript row is written, and `overall_status` stays at the `in_progress` set at creation
(`router.py:463`) **forever**. Nothing cancels the task until that user's *next* request, and that
cancellation is keyed by `user_id` rather than by session and writes no status either. Reopen the
chat under [ADR-027](./027-resume-continues-the-session.md) and you get an empty conversation that
looks like it is still running.

**And that chat can never be deleted.** `deletion.py:151-163` fails closed —
`is_running` is true of anything outside `SETTLED_STATUSES` — and both the per-row delete and
**Delete every chat** apply it identically, the first answering *"This chat is still running, so it
cannot be deleted yet."* Since nothing writes a terminal status to an abandoned turn, those rows are
unclearable by **any** exposed route, permanently, on the machine that runs the demonstration.

**`PlanStatus.canceled` has never been reachable.** No code anywhere in `src/backend` writes it. Yet
it sits in `SETTLED_STATUSES` (`deletion.py:41`), in its frontend mirror (`chatDeletion.ts`) and in
`chatStateLabel` as `'Canceled'`. Three places permit or render a state the system cannot produce.

## Decision

**Leaving a Chat ends its turn, and says so. Nothing else about leaving is a decision the associate
is asked to make.**

Six things follow, and they are part of this decision rather than separate work.

1. **Leaving a Chat cancels its in-flight turn and writes `canceled` onto the Plan record.** This
   makes `PlanStatus.canceled` producible for the first time. It is not new behaviour dressed as a
   fix: the turn is already lost, so the write only *names what already happens*, which is the
   discipline [ADR-023](./023-progress-narration-claims-only-what-a-signal-reports.md) and
   **Not reported vs measured** hold everywhere else on this surface.

2. **A Reviewable plan awaiting approval is treated identically — cancelled, never rejected.**
   `/v4/plan_approval` is not called on navigation at all. Navigating away is not a verdict on a
   plan, and ADR-028 §5 measured why it need not be one: `_raise_confirmed_ticket` has exactly one
   call site, `orchestration_manager.py:953`, inside the approved branch, so leaving commits
   nothing. This also severs a coupling before it bites —
   [#108](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/108) is open to give
   `approved: false` the new meaning *"sends it back instead of destroying it"*, and a New chat tap
   that kept POSTing it would silently file a revision request nobody wrote.

3. **Every control that leaves a Chat sends the cancel, and a socket drop does not.** **New chat**,
   selecting another chat row (`ChatPanelLeft`'s `handleChatSelect`) and the logo
   (`handleLogoClick`) are one act with one declaration, and the never-called
   `NewChatService.handleNewChatFromChat` is unified with it or deleted. The trigger is the
   associate's stated intent, never a transport event: a dropped socket is not an abandonment, and
   cancelling on one would kill a live turn on conference wifi, mid-demonstration. Browser back and
   a closed tab therefore remain **a known gap**, named rather than closed by a guess.

4. **No confirmation survives.** `PlanCancellationDialog.tsx`, `usePlanCancellationAlert.tsx`, the
   `showCancellationDialog` and `cancellingPlan` Redux state and both strings all go. A confirmation
   must guard against a loss; the expensive loss is structurally impossible (decision 2) and the
   cheap one is removed by decision 1. What remains would be a modal between the presenter and their
   next question, on stage, every time.

5. **The way out of `in_progress` is to end the turn, never to loosen the guard.**
   [ADR-026](./026-chats-are-deleted-not-hidden.md) stays fail-closed exactly as written, and
   `SETTLED_STATUSES` keeps its three members. Where the delete refuses a running Chat, it offers to
   end it and then delete — the same primitive as decision 1, requiring no heuristic about
   abandonment because the associate is explicitly asking. This is what turns ADR-026's *"A running
   Chat cannot be deleted, so the surface must explain when it keeps one"* into a door rather than a
   sentence.

6. **The cancel is session-scoped, and it never overwrites a terminal status.** The active-task
   registry records which session its task belongs to, so leaving one Chat cannot cancel or
   mislabel another; today `active_tasks` is keyed by `user_id` alone and `process_request` already
   cancels across sessions on that key. And a turn that finished a moment before the associate left
   keeps saying `Completed` — replacing a status that lied in one direction with one that lies in
   the other is not a fix.

**This decision declines ADR-028's gift, deliberately.** ADR-028 recorded the **Lane** onto the Plan
record expecting #89 to gate the dialog on it. With no dialog there is nothing to gate, and the
truthful signal for *"is there a turn to end"* is that a turn is in flight — not which lane it took.
The Lane on the Plan record keeps its other reasons (the `LaneBadge` on a plan, a conversation that
carries what it was); it is simply not what fixes this. Recorded here so a future reader does not
read ADR-028's expectation as an unmet obligation.

## Considered Options

- **Remove the confirmation and nothing else**, as `BRIEF.md` literally asks. Rejected: it grants
  the ask by deleting the warning while keeping the damage, and leaves every New chat tap producing
  a permanently undeletable row.
- **Keep a confirmation with honest words** — *"This will end the answer in progress."* Rejected on
  decision 4, but it is the closest alternative and the one to revisit if the surface should never
  end work without asking. It fails on the same ground the dialog does: **Progress narration**
  already tells the associate a turn is running, so the modal restates the screen.
- **Navigating away stays a rejection**, POSTing `approved: false` without the delete. Rejected on
  decision 2: it puts words in the associate's mouth, and #108 is about to make those words mean
  something else.
- **Cancel on socket disconnect**, which would also cover browser back and a closed tab. Rejected on
  decision 3. It buys the two gestures a client cannot intercept at the price of misreading a
  network blip as an abandonment, on a surface whose socket lifecycle already needed
  [ADR-021](./021-connect-the-socket-before-navigation.md).
- **Move persistence server-side** so an orphaned turn's answer survives and resume shows it. Not
  rejected — it is the right fix in the large, and it is a different decision. It re-lets the whole
  transcript contract, which today runs through the browser's echo, and it does not remove the need
  for an answer to *this* question in the meantime.
- **Relax `canDeleteChat` so an `in_progress` Chat can be deleted.** Rejected on decision 5.
  ADR-026's guard is deliberately fail-closed and `src/tests/ci/test_chat_deletion_contract.py` pins
  both halves of it across the language boundary.
- **Keep the cancel user-scoped**, reusing the registry as it is. Rejected on decision 6: one
  associate, one tab, one live turn is true today, which is exactly why the failure would never
  appear in rehearsal and would surface once, mislabelling a conversation in front of an audience.

## Consequences

- **Positive.** The brief's ask is granted, and granted *safely* rather than obediently: the modal
  goes because nothing is lost, not in spite of it. A dead enum member becomes reachable, and the
  two places that already handle `canceled` stop describing a state the system cannot produce.
- **Positive.** The surface stops holding two contradictory rules about removing an unsettled Chat —
  one control refusing it by name while another does it silently as a side effect of navigating.
- **The demolition is unusually cheap, and that is a finding rather than luck.** Nothing asserts the
  dialog: *"Confirm Plan Cancellation"* has zero matches across `src/App/src`, `src/tests`, `e2e/`
  and `docs/`. Its copy was never tested and never documented, which is part of why it survived
  saying something untrue for this long.
- **Negative — a net-new endpoint.** No session-scoped route can say *"end this Chat's turn"*
  today; the only existing mechanisms are the destructive `/v4/plan_approval` rejection and the
  implicit per-user cancel inside `process_request`. Decisions 1, 3 and 6 require a real one.
- **Negative — the existing backlog.** Chats already stuck at `in_progress` stay stuck until
  decision 5's control reaches them; nothing here retroactively settles them.
- **A known gap, named.** Browser back and a closed tab still abandon a turn, and decision 3
  deliberately declines to close them by guessing. Decision 5 is what makes the result recoverable
  rather than permanent.
- **Out of scope, and left where it belongs.** `delete_plan_by_plan_id` keeps its one remaining
  caller — the genuine plan rejection — and removing it stays #108's, along with
  `src/tests/backend/services/test_plan_service.py::test_handle_plan_approval_rejection`, which
  asserts that delete today. This ADR only stops *navigation* from reaching it.
- **Testing.** The frontend loop gains the cases the dialog never had: that leaving a Chat with a
  turn in flight settles it, that leaving a completed Chat does not overwrite its status, and that
  leaving one Chat does not settle another. `test_chat_deletion_contract.py` keeps `SETTLED_STATUSES`
  agreeing across the boundary, now with a status that something can actually write.

## References

- [ADR-013: Vary Plan review per request instead of building an orchestrator bypass](./013-per-request-plan-review-over-orchestrator-bypass.md)
- [ADR-021: Connect the WebSocket on the `createPlan` response, not on the plan page](./021-connect-the-socket-before-navigation.md)
- [ADR-023: The loading screen claims only what a signal reports](./023-progress-narration-claims-only-what-a-signal-reports.md)
- [ADR-025: Chat is the unit of the surface](./025-chat-is-the-unit-of-the-surface.md)
- [ADR-026: Chats are deleted, not hidden](./026-chats-are-deleted-not-hidden.md)
- [ADR-027: Resume continues the session](./027-resume-continues-the-session.md)
- [ADR-028: A reviewable plan is earned by a transaction, not by a question](./028-a-reviewable-plan-is-earned-by-a-transaction.md)
- `CONTEXT.md` — **Abandoned turn**, **Settled status**, **Leaving a Chat**, **Chat**,
  **Chat deletion**, **Plan record**, **Reviewable plan**
- [#108](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/108) — what rejecting a plan
  should do. Not settled here; this ADR only stops navigation from reaching that path.
