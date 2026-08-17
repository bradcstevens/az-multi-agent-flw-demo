# ADR-043: The server settles the turn it ended

## Status

Accepted

## Date

2026-08-16

## Issue

#156 (parent #155) — the decision [ADR-031](./031-leaving-a-chat-ends-its-turn.md) deferred, narrowed
to status only.

## Context

Every **Chat** in the panel reads **In progress** for ever, so both deletion controls are dead: each
row's **Delete chat** refuses with *"This chat is still running, so it cannot be deleted yet."*, and
**Delete every chat** — labelled *"Delete all chats"* — is disabled outright, because `ChatPanelLeft`
gates it on `deletableChatsCount === 0` (`ChatPanelLeft.tsx:229`, `:365`) and nothing is deletable.
The rows in that state include turns that finished and answered correctly. The machine that runs the
demonstration cannot clear its own history.

**The guard is not the defect.** `is_running` (`src/backend/chat/deletion.py:155`) is fail-closed
exactly as [ADR-026](./026-chats-are-deleted-not-hidden.md) requires, and it is reporting faithfully.
The defect is upstream: nothing on the server ever tells the record that the turn ended.

Read end to end, the path is one fact travelling the wrong way:

- Every **Plan record** is born `in_progress` (`src/backend/api/router.py:464`).
- The **only** writer of a **Settled status** anywhere in the system is
  `PlanService.handle_agent_messages` (`src/backend/services/plan_service.py:206-210`), which sets
  `overall_status = completed` when the **browser** echoes `is_final: true` back through
  `POST /v4/agent_message`.
- That echo is sent from exactly one branch of one handler —
  `usePlanWebSocket.tsx:283`, `messageStatus === PlanStatus.COMPLETED`. The `error` branch
  (`:302`) and the any-other-terminal-status branch (`:320`) dispatch Redux-only actions and persist
  nothing. **`PlanStatus.failed` is therefore never written by anything, anywhere** — the same
  dead-enum finding ADR-031 made about `canceled`.
- The surviving happy path is fire-and-forget. `persistAgentMessage`'s `.catch()`
  (`usePlanWebSocket.tsx:94-98`) swallows the failure and refreshes the chat list anyway, so the
  panel is repainted from a record the write never reached.
- The backend swallows it a second time: `handle_agent_messages` wraps everything in a broad
  `except` and returns `False`, and `/v4/agent_message` logs that and returns
  `{"status": "message recorded"}` regardless (`router.py:1323-1344`). A write that did not happen is
  reported as one that did.
- Meanwhile the server **knows** the turn ended. `run_orchestration` sends
  `FINAL_RESULT_MESSAGE` with `status: "completed"` (`orchestration_manager.py:568`) and with
  `status: "error"` (`:592`), and performs no Cosmos write in either branch.

So a durable record is contingent on a socket, a tab and a fetch, and every one of them fails
routinely — a reload, a closed tab, a socket blip, a 500 or a redeploy mid-turn loses the status
silently.

ADR-031 saw this and put it down deliberately. Among its rejected options: *"**Move persistence
server-side** so an orphaned turn's answer survives and resume shows it. Not rejected — it is the
right fix in the large, and it is a different decision."* This is that decision arriving. Recorded
here rather than assumed, because an implementer who changed who writes a **Settled status** without
this record would be contradicting a live ADR by accident.

The seam a repair needs already exists: `_latest_plan(session_id)`
(`src/backend/common/database/cosmosdb.py:681`) returns the latest Plan's `overall_status`, `id` and
`_etag` — which is precisely a conditional, never-clobbering settle-write.

## Decision

**The terminal status of a turn is written by the server that ended the turn**, because the server is
the only party that knows the turn ended and is still there when it does. The browser's echo is no
longer what makes that fact durable.

Take it narrowly. This is **not** the whole transcript moving server-side; the browser keeps echoing
agent messages and the streaming message, which nothing else persists. It is one fact changing hands.

Seven things follow, and they are part of this decision rather than separate work.

1. **The signal is the orchestration's own terminal branch, never a heuristic.**
   `FINAL_RESULT_MESSAGE` is already sent with `completed` and with `error`; this is the same event,
   written down rather than only broadcast. Nothing new is being observed, inferred or timed out, so
   the record claims only what a signal reports
   ([ADR-023](./023-progress-narration-claims-only-what-a-signal-reports.md)).

2. **The write happens whether or not anyone is listening.** It is not conditional on a live socket,
   an open tab, or a client that came back. That is the entire point: the durability of *"this turn
   ended"* stops being a function of who was watching when it did.

3. **`failed` becomes producible for the first time.** The failure branch settles `failed`, so an
   orchestration that fell over leaves a record saying it fell over instead of one claiming to still
   be working. `failed` already sits in `SETTLED_STATUSES`, in its frontend mirror
   (`src/App/src/models/chatDeletion.ts`) and in `chatStateLabel` as `Failed`: three places permitting
   or rendering a state the system could not produce, which is exactly the shape ADR-031 found in
   `canceled`.

4. **The wire's vocabulary is not the record's, and the mapping is made here.** The orchestration
   broadcasts `status: "error"`; the record carries `PlanStatus.failed`. `error` is not a fourth
   member of the settled set and must not become one — the wire word maps onto the existing status,
   and no new status is coined by this decision or by the tickets under it.

5. **ADR-026's guard does not move.** The way out of `in_progress` is to end the turn, never to
   loosen the guard. **Settled status** keeps its three members — `completed`, `failed`, `canceled` —
   the rule stays total and fail-closed (any other answer, including none, means running), and the
   two copies of it stay in agreement across the language boundary via
   `src/tests/ci/test_chat_deletion_contract.py`. This decision makes more Chats deletable by making
   more turns *end*, and by no other route.

6. **A Settled status is never overwritten.** A later write of a different terminal status leaves the
   first alone. This is ADR-031 decision 6's rule generalised from *leaving* to *every* writer: a
   record corrected into being wrong is worse than one left alone. It follows that the write is
   conditional on what was read — `_latest_plan`'s `_etag` — rather than read-then-clobber, so a
   concurrent settle cannot silently lose to a stale read, and that the first true answer is the one
   that stands.

7. **One fact, one writer.** Once the server settles its own turns, the browser's `is_final` echo is a
   second opinion on a question already answered, and two writers of one fact is how they come to
   disagree. The echo keeps the transcript and loses the status decision; the route stops answering
   success for a write that did not land. That narrowing is #158, and it is part of this decision
   rather than a later tidy-up.

### How this sequences against #120, #121 and #122

Those three end a turn the associate **left**. This ends the turn that **ended by itself**. Both
write through decision 6's rule, against the same document, through the same conditional write — so
they are one mechanism with two triggers, not two mechanisms that happen to touch one field.

- **#120** builds the end-of-turn primitive: cancel this session's in-flight orchestration and write
  `canceled`. Session-scoped, never a verdict on a plan, never overwriting a **Settled status**.
- **#121** wires **Leaving a Chat** to it and deletes the confirmation dialog.
- **#122** turns deletion's refusal into a door — end the turn, then delete it.

**#122 must land after #157**, the ticket that implements this ADR. Its door is aimed squarely at the
rows in #155's report, and those rows are the ones that **completed**: today they claim `in_progress`
only because the echo never landed. Ending them writes `canceled`, and decision 6 cannot save them,
because it protects a status that *was written* and there is none. The result would be replacing a
status that lies in one direction with one that lies in the other — which ADR-031 decision 6 forbids
by name. Once #157 has landed, a completed turn already carries `completed`, and the same door's write
is refused rather than accepted. The ordering is a correctness constraint, not a preference.

#120 and #121 carry no such hazard and may land in any order relative to this: they fire on an
explicit gesture against a turn that is genuinely in flight.

## Considered Options

- **Loosen `canDeleteChat`, or add `in_progress` to the settled-status set,** so the stuck rows can be
  deleted. Rejected on decision 5, and it is the option this ADR exists to refuse: it makes the symptom
  go away by making the guard lie, and it would let a delete take a Chat with a live turn still writing
  into its partition. ADR-026's guard is deliberately fail-closed and
  `src/tests/ci/test_chat_deletion_contract.py` pins both halves of it across the language boundary.
- **Keep the browser as the writer, and make it reliable** — retries, a `sendBeacon` on unload, an
  idempotent replay on reconnect. Rejected. It is more machinery in the party that is *definitionally*
  absent in the cases that fail: a closed tab, a crashed browser, a walk-away. Every retry lengthens the
  window in which the record is wrong, none of them covers a turn nobody was watching at all, and the
  result is a durability guarantee whose weakest link is a client this repository does not control.
- **Have the WebSocket send path write the status** as a side effect of broadcasting
  `FINAL_RESULT_MESSAGE`. Rejected on decision 2 in reverse: the send path can only run for a connection
  that exists, so persistence would still be a function of who was listening — the same defect one layer
  down.
- **Move the whole transcript server-side now**, so an orphaned turn's answer survives and **Resume**
  shows it. Deferred again, deliberately and with the same reasoning ADR-031 used: it re-lets the entire
  transcript contract, and it is not required to make a finished turn deletable. What is different this
  time is that the status half is no longer waiting on it. Still the right fix in the large.
- **Infer that a turn ended from the absence of a running task, or from the record's age.** Rejected as
  a general rule — it settles a live turn whenever the inference is wrong, and a timeout picks an
  arbitrary number that a slow answer will eventually cross on stage. #159 takes the one form of this
  that is a report rather than a guess: a turn's `asyncio.Task` is held in memory by the process serving
  it, so a process that has just started cannot be running any turn it inherited, and settling those is
  saying what already happened. That reasoning does not extend past a starting process's own
  inheritance — see the gap below.
- **Let the last terminal write win.** Rejected on decision 6. The failing cases are exactly the ones
  where the later writer knows less: a late echo, a delete-door cancel against a Chat that finished
  minutes ago, an end-of-turn primitive firing on a session whose orchestration already returned.
- **Broadcast a "settle me" frame the browser must acknowledge** before the server writes. Rejected: it
  is the current design with an extra round trip, and it keeps the client on the critical path of a fact
  the client does not own.

## Consequences

- **Positive.** A finished turn is deletable, so ADR-026's controls do what their labels say and the
  demonstration machine can clear its own history. The fix arrives through the guard rather than around
  it.
- **Positive.** A second dead enum member becomes reachable, and the three places that already render
  `failed` stop describing a state the system cannot produce.
- **Positive.** The record stops depending on the browser's `is_final` plumbing, which parses that flag
  out of a frame arriving in three shapes — including a regex over a stringified Python repr. That
  parser deciding whether a Chat is deletable for ever is #155 stated in one line.
- **Negative — the existing backlog is not cleared by this decision.** Rows already stuck stay stuck
  until #159's startup reconciliation reaches them. This decision stops new ones being created; it is
  not retroactive.
- **A known gap, unchanged: abandonment is still not detected as it happens.** Browser back and a closed
  tab still abandon a turn, and ADR-031 decision 3 still declines to close them by guessing, because
  cancelling on a dropped socket would kill a live turn on conference wifi. What changes is that the
  turn now settles when the *orchestration* ends rather than when the client reports it, so the window
  in which a row lies is the turn's remaining runtime rather than for ever.
- **A known gap, named: a process killed mid-turn writes nothing.** A redeploy, a crash or an OOM kill
  ends the turn without reaching either terminal branch. The turn's task is process-local, so no later
  event can settle it, and only #159's reconciliation clears it — on the *next* start, not at the moment
  of death.
- **A known gap, named: more than one replica breaks the inference #159 rests on.** The reconciliation's
  reasoning is process-local. It does **not** license *"no task in flight here means no task in flight
  anywhere"*: with a second replica, another instance may be mid-turn on a Chat this one knows nothing
  about, and settling it would stamp a terminal status onto a live answer — the one direction of error
  this decision exists to prevent. Today the inference holds for `macae-flw-v1` **because of a pin, not
  as a property of the system**: that environment sets `AZURE_ENV_DEPLOYMENT_FLAVOR=bicep`
  (`infra/environments/macae-flw-v1.env`) and `infra/bicep/main.bicep` fixes the backend container app
  at `minReplicas: 1, maxReplicas: 1`. The `avm` and `avm-waf` flavours set
  `maxReplicas: enableScalability ? 3 : 1` (`infra/avm/main.bicep:1078`), and `enableScalability`
  defaults to true for `avm-waf` (`infra/main.bicep:221`) — so a WAF deployment of this repository
  invalidates it. Establish the replica count before widening the rule, write the answer down where the
  next reader will find it, and if it is more than one, leave the rows stuck: the conservative direction
  is the one that does not settle a turn somebody is still running.
- **A known gap, named: the status is not the answer.** A settle-write records that the turn ended, not
  what it said. A turn whose client was gone still leaves no transcript row, so the answer is lost —
  now lost with an accurate label instead of an indefinite claim to be working. Recovering the answer is
  the transcript decision this one declines.
- **Out of scope, and left where it belongs.** `delete_plan_by_plan_id` still deletes a Plan document
  outright on plan rejection; that path is #108's and is untouched here.
- **Testing.** The guarantee is asserted with nothing echoing back — a completed turn reaches
  `completed` and a raising orchestration reaches `failed` with the browser absent entirely — and a
  settle-write against an already-settled Chat is asserted to leave it alone for every terminal status.
  `test_chat_deletion_contract.py` keeps `SETTLED_STATUSES` agreeing across the boundary, now with two
  statuses something can actually write.

## References

- [ADR-023: The loading screen claims only what a signal reports](./023-progress-narration-claims-only-what-a-signal-reports.md)
- [ADR-025: Chat is the unit of the surface](./025-chat-is-the-unit-of-the-surface.md)
- [ADR-026: Chats are deleted, not hidden](./026-chats-are-deleted-not-hidden.md)
- [ADR-027: Resume continues the session](./027-resume-continues-the-session.md)
- [ADR-031: Leaving a Chat ends its turn, and says so](./031-leaving-a-chat-ends-its-turn.md) — the
  decision this one was deferred from, and the source of the never-overwrite rule generalised in
  decision 6
- `CONTEXT.md` — **Settled status**, **Abandoned turn**, **Plan record**, **Chat deletion**,
  **Leaving a Chat**
- [#155](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/155) — the diagnosis
- [#157](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/157) — the settle-write and the
  wiring to both terminal branches
- [#158](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/158) — the browser stops
  deciding whether a turn ended
- [#159](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/159) — the existing backlog, and
  the replica question above
- [#120](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/120),
  [#121](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/121) and
  [#122](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/122) — ADR-031's half, and why
  #122 lands after #157
- [#108](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/108) — what rejecting a plan
  should do. Untouched here.
