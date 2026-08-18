"""**Startup reconciliation** — a turn nobody is running is settled (#159).

ADR-047. #157 stopped new turns getting stuck at an unsettled status; it did
nothing for the ones already stuck, and ADR-031 named that debt in advance —
*"Chats already stuck at `in_progress` stay stuck… nothing here retroactively
settles them."* This module is what clears them, and the whole of its reasoning
is one observation about where a turn lives:

**A turn runs inside an ``asyncio.Task`` held in memory by the process serving
it.** When that process is gone, so is the turn — every frame it would have sent
goes nowhere, and no later event can settle it. So a **Plan record** a *starting*
process finds at an unsettled status describes a turn that no longer exists
anywhere, and settling it is reporting what happened rather than inferring it.
That is the same discipline **Not reported vs measured** holds everywhere else on
this surface: the write names what already happened.

**The scope is narrow on purpose, and the reason is worth reading before it is
widened.** The observation above is about a *process's own inheritance* — the
records that outlived the process that was serving them. It does **not** license
the general inference *"no task in flight here means no task in flight
anywhere"*: with a second replica, another instance may be mid-turn on a Chat
this one knows nothing about, and settling it would stamp a terminal status onto
a live answer's record in front of an audience — the one direction of error
ADR-043 exists to prevent. The deployed environment runs exactly one replica
(``infra/bicep/main.bicep`` pins every Container App to ``minReplicas: 1,
maxReplicas: 1``, and ``scripts/preflight/deployed_environment.py``'s
``single-replica`` check fails the preflight the moment that stops being true),
which is what makes *startup* a safe moment and nothing else one. If that answer
ever changes, this rule does not widen with it; the conservative direction is the
one that leaves a row stuck.

**One replica is not one process during a rollout**, and ADR-047's *Context*
weighs that rather than leaving it to be rediscovered. Container Apps scale
settings are per *revision*, and a revision swap brings the new process to ready
while the old one still serves — so a deploy is a window in which this pass can
reach a turn another process is computing. The cost is bounded to a mislabelled
status: the outgoing revision is terminated moments later and its turn dies with
it, and its own settle-write cannot correct the record because a Settled status
is never overwritten. Closing the window properly needs durable turn ownership —
a lease, or a Plan naming the instance computing it — which is the same signal a
second steady-state replica would need, and a decision about every turn rather
than a detail of this pass.

Three rules live here, and all three are the sort a reviewer checks by reading:

* **Fail-closed, in the same words as everywhere else.** ``is_running`` decides —
  the predicate **Chat deletion** refuses on and **Ending a turn** keeps a
  settled Chat by — so a status this repository does not recognise, and a record
  carrying no status at all, are both stuck. The **Settled status** set does not
  move for this ticket: more Chats become deletable only by more turns actually
  ending.
* **A Chat is settled, never a Plan that happened to be seen.** A Chat's state is
  its latest **Plan record**'s (#71), and the settle-write is asked once per
  Chat, session-scoped and with no ``plan_id`` — exactly the caller
  ``settle_turn`` anticipated. Naming a Plan here would settle a document that is
  no longer the one **Chat deletion** reads, which is the backlog silently not
  cleared.
* **It reports what it did.** A backlog that cleared and a reconciliation that
  never ran are different facts, and an operator has to be able to tell them
  apart from one line.

The store is handed in rather than reached for, on **Ending a turn**'s
precedent: the caller passes the rows it read and a way to reach an owner-scoped
store, which keeps the rule above readable without a database.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Mapping, Tuple

from chat.deletion import PlanStatus, is_running
from chat.settle import SettleOutcome

logger = logging.getLogger(__name__)

#: What a reconciled turn ends as. `canceled` rather than `failed`: the turn was
#: ended — by the process going away — and nothing observed it fail. It is the
#: same word **Ending a turn** writes, for the same reason, and it is taken from
#: `chat.deletion` along with `is_running` because that module is where the
#: **Settled status** vocabulary lives — the same reason `chat.settle` sources
#: the set itself from there rather than keeping a second copy.
RECONCILED_STATUS = PlanStatus.canceled


@dataclass(frozen=True)
class StuckTurn:
    """One Chat whose **Plan record** still claims to be running.

    Both fields name it: the settle-write reads the Chat's latest Plan through a
    query predicated on session *and* owner, and the owner predicate is the whole
    of its authorization.
    """

    user_id: str
    session_id: str


@dataclass(frozen=True)
class Backlog:
    """What a startup reconciliation found to do, decided from Plan rows alone.

    ``unnameable`` is counted rather than dropped. A Plan carrying no session or
    no owner cannot be reached by any settle-write — the read it targets is
    scoped by both — so it is left exactly as it is, and saying how many were
    left is the difference between a number an operator can trust and one that is
    quietly short.
    """

    examined: int = 0
    stuck: Tuple[StuckTurn, ...] = ()
    unnameable: int = 0


@dataclass(frozen=True)
class Reconciliation:
    """What a startup reconciliation examined, settled, and could not settle.

    ``settled`` names the sessions rather than counting them, on **Chat
    deletion**'s precedent: a count cannot say *which*, and the whole purpose of
    this pass is that an operator can look at the rows it claims to have cleared.

    ``already_settled`` is not a failure. Between the read and the write a Chat
    may have reached a **Settled status** by any other route, and the settle-write
    reporting so means the record now says the turn ended — which is the fact this
    pass exists to make true.

    ``failed`` is every outcome that is *not* that, and it is the one that must
    not be silent: a write this process believed it had made and had not is
    exactly the defect ADR-043 named in the browser's plumbing.
    """

    backlog: Backlog = field(default_factory=Backlog)
    settled: Tuple[str, ...] = ()
    already_settled: int = 0
    failed: int = 0

    @property
    def summary(self) -> str:
        """One line an operator reads to tell a cleared backlog from no backlog.

        It always says how many Plans were *examined*, so a pass that found
        nothing is still visibly a pass that ran — the reading a reconciliation
        that never ran must not be confusable with.
        """
        return (
            f"examined {self.backlog.examined} plan(s), "
            f"found {len(self.backlog.stuck)} chat(s) claiming to run, "
            f"settled {len(self.settled)} as {RECONCILED_STATUS.value}, "
            f"{self.already_settled} already settled, "
            f"{self.failed} not settled, "
            f"{self.backlog.unnameable} plan(s) naming no chat of anyone's"
        )


def stuck_turns(rows: Iterable[Mapping[str, Any]]) -> Backlog:
    """The Chats a starting process settles, decided from Plan rows.

    Deduplicated per Chat and in first-seen order, so the pass is deterministic
    and a Chat holding several stuck Plans is settled once. Order matters to
    nothing but the log, which is precisely why it should not be arbitrary.
    """
    examined = 0
    unnameable = 0
    stuck = []
    seen = set()

    for row in rows:
        examined += 1

        if not is_running(row.get("overall_status")):
            continue

        session_id = row.get("session_id")
        user_id = row.get("user_id")

        if not session_id or not user_id:
            unnameable += 1
            continue

        turn = StuckTurn(user_id=user_id, session_id=session_id)
        if turn in seen:
            continue

        seen.add(turn)
        stuck.append(turn)

    return Backlog(examined=examined, stuck=tuple(stuck), unnameable=unnameable)


async def reconcile_turns(
    rows: Iterable[Mapping[str, Any]],
    store_for: Callable[[str], Awaitable[Any]],
) -> Reconciliation:
    """Settle every Chat these rows say is running, and report what happened.

    ``store_for`` yields a store scoped to one owner, because that is what the
    settle-write's authorization is made of. The write is session-scoped and
    carries no ``plan_id``: this pass has no turn of its own and must not bind
    itself to a document that may no longer be the Chat's latest.

    A store that raises on one Chat does not stop the pass. The backlog is a
    list of independent rows and abandoning the rest of it because one failed
    would leave a cleared backlog looking like a broken one.
    """
    backlog = stuck_turns(rows)

    if backlog.unnameable:
        logger.warning(
            "Startup reconciliation left %s plan(s) alone: they name no "
            "session or no owner, so no settle-write can reach them",
            backlog.unnameable,
        )

    settled = []
    already_settled = 0
    failed = 0

    for turn in backlog.stuck:
        try:
            store = await store_for(turn.user_id)
            result = await store.settle_turn(turn.session_id, RECONCILED_STATUS)
        except Exception:
            failed += 1
            logger.error(
                "Startup reconciliation could not settle chat %s: the "
                "settle-write raised, so it still reads as running",
                turn.session_id,
                exc_info=True,
            )
            continue

        if result.outcome is SettleOutcome.settled:
            settled.append(turn.session_id)
        elif result.outcome is SettleOutcome.already_settled:
            already_settled += 1
        else:
            failed += 1
            logger.warning(
                "Startup reconciliation did not settle chat %s: %s. It still "
                "reads as running and cannot be deleted",
                turn.session_id,
                result.outcome.value,
            )

    return Reconciliation(
        backlog=backlog,
        settled=tuple(settled),
        already_settled=already_settled,
        failed=failed,
    )
