# ADR-047: A turn nobody is running is settled at startup, and nowhere else

## Status

Accepted

## Date

2026-08-18

## Issue

#159 (parent #155 — *Every chat claims to be running, so no chat can ever be deleted*)

## Context

[ADR-043](./043-the-server-settles-the-turn-it-ended.md) had the server settle the turn it ended, so
a turn that starts from now on reaches a **Settled status** whatever the browser does. It changed
nothing about the turns that ended before it, and
[ADR-031](./031-leaving-a-chat-ends-its-turn.md) had already named that debt in advance:

> **Negative — the existing backlog.** Chats already stuck at `in_progress` stay stuck until
> decision 5's control reaches them; nothing here retroactively settles them.

Decision 5's control — **Ending a turn** offered from the delete door — reaches a stuck Chat only if
somebody opens that Chat's overflow menu and taps it. The five rows in #155's screenshot are on the
machine that runs the demonstration, and they are the residue of turns whose process is long gone.
No exposed route clears them without a person clicking each one.

**The signal is not a timeout and not a guess.** A turn runs inside an `asyncio.Task` held in memory
by the process serving it — `run_orchestration_task` in `src/backend/api/router.py`, registered in a
process-local dictionary. When that process is gone, so is the turn: every frame it would have sent
goes nowhere, the socket it would have sent them on is closed, and no later event can settle it. So a
**Plan record** that a *starting* process finds at an unsettled status describes a turn that no
longer exists anywhere. Saying so is reporting what happened, which is the discipline
[ADR-023](./023-progress-narration-claims-only-what-a-signal-reports.md) holds everywhere else on
this surface — not inferring it from elapsed time, which is what a sweeper would do.

**That reasoning is narrower than it looks, and the narrowness is the decision.** It is about a
process's own *inheritance* — records that outlived the process serving them. It does **not**
license the general inference *"no task in flight here means no task in flight anywhere"*. With a
second replica, another instance may be mid-turn on a Chat this one knows nothing about, and settling
it would stamp a terminal status onto a live answer's record, in front of an audience — the one
direction of error ADR-043 exists to prevent, and the one that makes a running Chat deletable with
it.

**So the replica count had to be established rather than assumed, and it was.**
`infra/environments/macae-flw-v1.env` names `AZURE_ENV_DEPLOYMENT_FLAVOR=bicep`, and
`infra/bicep/main.bicep` pins all three Container Apps to `minReplicas: 1, maxReplicas: 1`. That is
not merely today's configuration: `docs/preflight/deployed-environment.md` carries a `single-replica`
check, and `scripts/preflight/deployed_environment.py::_single_replica_check` fails the preflight the
moment any app scales past one — a check that predates this ticket, because orchestrations are held
in a process-local dictionary and checkpoint storage is in memory, so a second replica was already
non-deterministic mid-demonstration.

**One replica is not one process, during a rollout, and that is the limit of this decision.** Those
scale settings are per *revision*. Azure Container Apps brings a new revision to ready while the old
one is still serving, so for the length of a deploy two processes share the store — and the new one's
reconciliation can reach a turn the old one is still computing. Weighed rather than waved away, in
three parts:

- **The turn is already lost.** The old revision is terminated moments later and its
  `asyncio.Task` goes with it, so `canceled` is the label that turn was going to end up with in any
  case — at the *next* deploy, having claimed to run in between.
- **What the window actually costs is a mislabel, not an answer.** If the old revision finishes
  inside it, the associate still receives the answer over the socket and the transcript rows are
  still written; what cannot happen is the correction, because the settle-write never overwrites a
  Settled status (ADR-043 §6). The record says `canceled` for a turn that completed, and the Chat is
  deletable while its answer is still arriving.
- **The window is a deploy.** Merging to `main` deploys (ADR-020) and that takes about twenty
  minutes; a deployment landing mid-turn is already a hazard this repository accepts, and one
  landing mid-*demonstration* is a much larger problem than a status.

That cost is bought deliberately, because the alternative is that the backlog is never cleared
without a person clicking each row. Closing it properly needs a **durable turn ownership** record — a
lease, or a Plan naming the instance computing it — which is the same signal a second steady-state
replica would require, and it is a decision about every turn rather than a detail of this pass.

## Decision

**A starting process settles the turns it inherited, through the settle-write, and nothing else
settles a turn it did not observe end.**

Six things follow, and they are part of this decision rather than separate work.

1. **The moment is startup, and startup is the whole of the argument.** The reconciliation runs
   inside the FastAPI lifespan's startup half (`settle_inherited_turns` in `src/backend/app.py`),
   before the application serves. Not a background sweeper, not a route, not a timer: every other
   moment would have to decide *whether* a turn is still running, and this one knows.

2. **It goes through the settle-write.** `settle_turn` (#157) is already the one route to a Settled
   status, and it already anticipated this caller by name. So the reconciliation inherits, rather
   than re-states, every rule on that write: owner-scoped, conditional on the `_etag` it read, and
   never overwriting a Settled status a Plan already reached. **A Chat that already settled is
   untouched.**

3. **It settles a Chat, not a Plan it happened to see.** The write is session-scoped and carries no
   `plan_id`. A Chat's state is its latest **Plan record**'s (#71), which is the document
   **Chat deletion** reads; binding this pass to a document it observed a moment earlier would come
   back `superseded` and leave the row exactly as stuck as it found it.

4. **The status is `canceled`.** The turn was *ended* — by the process going away — and nothing
   observed it fail. It is the word **Ending a turn** writes, for the same reason, and it names what
   already happened rather than adding a meaning.

5. **The deletion guard does not move.** `SETTLED_STATUSES` keeps its three members and `is_running`
   stays total and fail-closed, exactly as [ADR-026](./026-chats-are-deleted-not-hidden.md) and
   ADR-031 §5 have it. More Chats become deletable because more turns actually ended, which is the
   only way this repository has ever agreed to make one deletable.

6. **A reconciliation that could not run does not stop the application starting, and says which it
   was.** A store that cannot answer leaves a demonstration booting with its backlog uncleared —
   the state it is in today — and refusing to serve would turn a stale row into an outage. The pass
   logs what it examined and what it settled, so *"nothing was stuck"* and *"the pass never ran"* are
   never the same line.

**The fail-closed direction is deliberately the other way here, and that is worth stating.** Chat
deletion fails closed by treating an unrecognised status as *running*, because the cheap side of that
mistake is a refusal the associate can read. This pass treats an unrecognised status as *stuck*, and
the two agree rather than conflict: both are the same predicate, `is_running`, and a record no
process is serving is one this pass may settle whatever it says. The conservative direction for
*scope* is unchanged — a row it cannot name is left alone and counted, never guessed at.

## Considered Options

- **A background sweeper with an age threshold** — settle anything at `in_progress` for more than N
  minutes. Rejected: it is precisely the guess ADR-031 §3 declined for socket drops, one layer down.
  A long **Deliberate lane** turn and an abandoned one look identical to a clock, and the failure it
  buys is a live answer's record stamped terminal mid-demonstration.
- **Settle on WebSocket disconnect.** Rejected on ADR-031 §3's own ground, restated: a dropped
  socket is not an abandonment, and conference wifi would end live turns.
- **A route an operator calls to clear the backlog.** Not rejected on merit — it is strictly weaker.
  It needs somebody to know the backlog exists, to be authenticated, and to be at a keyboard;
  merging to `main` deploys ([ADR-020](./020-deploy-main-on-every-commit.md)), so startup is a moment
  that arrives on its own. It also has to answer *is this Chat running* without startup's evidence.
- **Bind each settle-write to the Plan row the pass observed** (`plan_id`). Rejected on decision 3.
  It reads as the more precise choice and is the less correct one: the settle-write's own read
  decides which Plan is a Chat's latest, and disagreeing with it settles nothing.
- **Filter the unsettled Plans in the Cosmos query.** Rejected. Cosmos omits from a predicate any
  document missing the field it names, so a `WHERE` clause on `overall_status` silently drops the
  Plans that carry no status at all — exactly the records `is_running` calls running. It is the same
  trap [#165](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/165) documents for
  `ORDER BY`, in the one place where the consequence is a backlog that reports itself clear. The rule
  stays whole in `chat/reconcile.py` and the store hands it rows.
- **Widen the rule to "no task in flight here means none anywhere"** and reconcile continuously.
  Rejected on the replica argument above. If the deployed environment ever runs more than one
  replica, this decision does **not** widen with it — it narrows to nothing, and the reconciliation
  needs a different signal (a lease, or a turn record naming the instance that owns it) before it may
  run at all.

## Consequences

- **Positive.** ADR-031's named debt is paid without loosening anything ADR-026 or ADR-043 decided,
  and the backlog clears itself on the next deploy rather than waiting for somebody to notice five
  rows and click each one.
- **Positive.** ADR-031's *known gap* — browser back and a closed tab, which are still not detected
  as they happen — stops being permanent. A turn abandoned that way still loses its answer, but its
  record stops claiming to be working at the next restart.
- **Negative — one cross-partition read at every start.** `plan_states` reads a four-field projection
  of every Plan document in the container, for every owner. At demonstration scale that is small and
  it happens once per process; at a scale this repository does not have, it would need a continuation
  token and a reason.
- **Negative — the read is the one on this interface that is not owner-scoped.** That is what the
  pass needs and it is a new shape here, so it is declared on `DatabaseBase` with the reason attached
  rather than left as an unexplained omission in `CosmosDBClient`.
- **A dependency on a preflight check, stated.** `single-replica` is now load-bearing for
  correctness, not only for determinism. `docs/preflight/deployed-environment.md` records that.
- **Negative — the rollout window.** A Container Apps revision swap runs two processes against one
  store for the length of a deploy, so a turn in flight on the outgoing revision can be settled by
  the incoming one's pass. Bounded to a mislabel rather than a lost answer, and weighed in *Context*
  above; closing it needs durable turn ownership and is not this decision.
- **Negative — the pass holds the process short of ready, and so is bounded.**
  `RECONCILIATION_TIMEOUT_SECONDS` in `src/backend/app.py`. It has to finish before the application
  serves — a pass still running while requests arrive could settle a turn that started after it read
  — but an unbounded wait would turn the one operation explicitly allowed to fail into a restart
  loop.
- **Negative — a second *process*, not only a second replica, is the thing to watch.** The argument
  is about processes sharing a store, so a backend started on a laptop against the demonstration's
  own Cosmos would settle turns the deployed instance is running. That is not a new hazard — a
  laptop pointed at that store can already delete every Chat in it — and it is not guarded here,
  because the only guard available is configuration that could silently switch the pass off in the
  one environment that needs it. Named so the next reader does not have to rediscover it.
- **Testing.** The seam that decides which records to settle is pure and asserted without a store
  (`src/tests/backend/chat/test_reconcile.py`), the cross-user read is asserted against a stood-in
  container, and the wiring — that a starting process asks, that it reports, and that a failure
  leaves the application serving — is asserted in `src/tests/backend/test_app.py`.
- **Merge order, not design.** #165 repairs the latest-Plan ordering that the settle-write reads
  through. This pass runs **once** against the real backlog, so it should reach `main` after that
  repair; nothing written here changes when it does.

## References

- [ADR-020: Merging to `main` deploys](./020-deploy-main-on-every-commit.md)
- [ADR-023: The loading screen claims only what a signal reports](./023-progress-narration-claims-only-what-a-signal-reports.md)
- [ADR-026: Chats are deleted, not hidden](./026-chats-are-deleted-not-hidden.md)
- [ADR-031: Leaving a Chat ends its turn, and says so](./031-leaving-a-chat-ends-its-turn.md)
- [ADR-043: The server settles the turn it ended](./043-the-server-settles-the-turn-it-ended.md)
- `docs/preflight/deployed-environment.md` — the `single-replica` check this decision leans on
- `CONTEXT.md` — **Startup reconciliation**, **Abandoned turn**, **Settled status**,
  **Ending a turn**, **Chat deletion**, **Plan record**
- [#155](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/155) — the backlog this pays
  off; [#165](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/165) — the ordering the
  settle-write reads through
