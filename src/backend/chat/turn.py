"""**Ending a turn** — the one primitive, and the one declaration (#120).

ADR-031: leaving a Chat ends its turn. So does deleting a running Chat, and so
does a **Clarification** that expires. Three triggers, one act — and it is one
function because four copies of a cancellation flow is exactly what this
repository has just finished pulling apart.

What it does is small and the three properties around it are the point:

* **Session-scoped.** The turn registry is keyed by ``user_id``, and the
  request path deliberately cancels across sessions on that key — the Workflow
  is cached per user, so a second turn replaces the first rather than running
  beside it. Ending a turn is the opposite case: the associate named *one*
  Chat, and a turn belonging to another one is left alone. One associate, one
  tab, one live turn is true in rehearsal, which is exactly why the failure
  would surface once, in front of an audience (ADR-031 §6).

* **It never overwrites a Settled status.** ``is_running`` — the same
  fail-closed predicate **Chat deletion** refuses on (ADR-026) — decides, so
  the two operations cannot come to different conclusions about the same
  record. A turn that finished a moment before the associate left keeps saying
  ``Completed``: replacing a status that lied in one direction with one that
  lies in the other is not a fix.

* **It is never a verdict on a plan.** Nothing here reaches ``/plan_approval``
  or the approval registry, including for a **Reviewable plan** awaiting one.
  Ending is not rejecting, and #108 made ``approved: false`` mean *"send it
  back"* — an end-of-turn that kept posting it would file a revision request
  nobody wrote. A cancelled task raises out of its own ``wait_for_approval``,
  which is how the waiting review learns the turn is over.

The collaborators are handed in rather than reached for: the route passes the
store it already built for this user, and the orchestration passes the registry
it already holds. That keeps this module free of the database and the workflow
cache, and keeps the rule readable on its own.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from chat.deletion import is_running
from common.models.messages import PlanStatus

logger = logging.getLogger(__name__)


class TurnOutcome(str, Enum):
    """What ending a turn found to do."""

    #: The Chat's turn was ended: `canceled` is on the Plan record, and any
    #: orchestration still computing for it has been cancelled.
    ended = "ended"
    #: The Chat had already reached a **Settled status**. Left exactly as it
    #: was — this is the one outcome that writes nothing on purpose.
    already_settled = "already_settled"
    #: No Plan record for that session belongs to this user. There is no turn
    #: here to end and nothing to say about one.
    no_such_chat = "no_such_chat"


@dataclass(frozen=True)
class EndedTurn:
    """The result of asking for a Chat's turn to end.

    ``cancelled`` is reported separately from the outcome because the two
    answer different questions, and both callers ask. An **Abandoned turn**
    settles with nothing to cancel — the client left long ago and the task is
    gone — and that is an ``ended`` turn all the same; it is the row #122 has
    to be able to clear.
    """

    outcome: TurnOutcome
    cancelled: bool = False


async def end_turn(
    *,
    user_id: str,
    session_id: str,
    memory_store: Any,
    orchestration: Any,
) -> EndedTurn:
    """End one Chat's turn: cancel what is computing, write what happened.

    Args:
        user_id: the associate whose Chat this is.
        session_id: the **Chat** whose turn is ending. Nothing outside this
            session is cancelled, read or written.
        memory_store: the store, already scoped to ``user_id``.
        orchestration: the turn registry — anything answering ``active_turn``
            and ``release_active_turn``.
    """
    cancelled = _cancel_the_turn_in_flight(user_id, session_id, orchestration)

    plan = await memory_store.get_plan_by_session(session_id)
    if plan is None:
        logger.info(
            "No Plan record for session '%s' — no turn to end", session_id
        )
        return EndedTurn(outcome=TurnOutcome.no_such_chat, cancelled=cancelled)

    if not is_running(getattr(plan, "overall_status", None)):
        logger.info(
            "Chat '%s' already reached '%s' — leaving it alone",
            session_id,
            getattr(plan, "overall_status", None),
        )
        return EndedTurn(outcome=TurnOutcome.already_settled, cancelled=cancelled)

    plan.overall_status = PlanStatus.canceled
    await memory_store.update_plan(plan)
    return EndedTurn(outcome=TurnOutcome.ended, cancelled=cancelled)


def _cancel_the_turn_in_flight(
    user_id: str, session_id: str, orchestration: Any
) -> bool:
    """Cancel this Chat's orchestration, and only this Chat's.

    A turn belonging to another **Chat** is left running: that is ADR-031 §6,
    and it is the whole reason the registry records a session at all.
    """
    turn: Optional[Any] = orchestration.active_turn(user_id)
    if turn is None:
        return False

    if getattr(turn, "session_id", None) != session_id:
        logger.info(
            "User '%s' has a turn in flight for chat '%s', not '%s' — leaving "
            "it running",
            user_id,
            getattr(turn, "session_id", None),
            session_id,
        )
        return False

    task = turn.task
    if task is asyncio.current_task():
        # A turn ending itself — a **Clarification** that expired inside the
        # orchestration (#123). Cancelling here would raise into the caller at
        # its next await, so the write below would never happen and the Chat
        # would stay stuck at `in_progress`, which is the state this primitive
        # exists to leave. The turn is already ending; the record is what it
        # came for.
        return False

    task.cancel()
    orchestration.release_active_turn(user_id, task)
    return True
