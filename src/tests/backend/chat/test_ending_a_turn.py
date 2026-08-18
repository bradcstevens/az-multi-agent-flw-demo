"""**Ending a turn** — one primitive, one declaration (#120, ADR-031).

Three properties are the whole of it, and each is a failure this repository has
already reasoned about:

* **It is session-scoped.** The registry it reads is keyed by ``user_id``, and
  the request path already cancels across sessions on that key. One associate,
  one tab, one live turn is true in rehearsal, which is exactly why leaving one
  Chat and settling another would surface once, in front of an audience.
* **It never overwrites a Settled status.** A Chat that reached ``completed``
  or ``failed`` a moment earlier keeps saying so. Replacing a status that lied
  in one direction with one that lies in the other is not a fix.
* **It is never a verdict on a plan.** Ending is not rejecting. #108 gave
  ``approved: false`` the meaning *"send it back"*, so an end-of-turn that
  reached the approval path would file a revision request nobody wrote.

The store and the turn registry are stood in for at the primitive's own seam —
what is exercised here is the rule, which is the half a reviewer can check by
reading it.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from chat import deletion
from chat.turn import EndedTurn, TurnOutcome, end_turn

PlanStatus = deletion.PlanStatus


def _plan(status=PlanStatus.in_progress, session_id="sess-1"):
    """A Plan record, stood in for by the fields the primitive reads."""
    return SimpleNamespace(
        id="plan-1",
        plan_id="plan-1",
        session_id=session_id,
        overall_status=status,
    )


def _store(plan=None):
    store = MagicMock()
    store.get_plan_by_session = AsyncMock(return_value=plan)
    store.update_plan = AsyncMock()
    store.delete_plan_by_plan_id = AsyncMock(return_value=True)
    return store


async def _in_flight():
    """A turn that is genuinely running, and notices being cancelled."""

    async def _turn():
        await asyncio.sleep(60)

    return asyncio.create_task(_turn())


def _registry(turn=None):
    orchestration = MagicMock()
    orchestration.active_turn = MagicMock(return_value=turn)
    orchestration.release_active_turn = MagicMock()
    orchestration.set_approval_result = MagicMock()
    return orchestration


class TestEndingATurnInFlight:
    @pytest.mark.asyncio
    async def test_the_orchestration_is_cancelled_and_the_record_says_canceled(self):
        """What already happens, named (ADR-031 §1).

        The turn is destroyed today whether or not anybody writes it down: the
        socket closes, the orchestration computes against a connection that is
        gone and every frame is dropped. The write is not new behaviour, it is
        the surface stopping denying the loss.
        """
        task = await _in_flight()
        store = _store(_plan())
        orchestration = _registry(SimpleNamespace(session_id="sess-1", task=task))

        result = await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=orchestration,
        )

        assert task.cancelled() or task.cancelling()
        written = store.update_plan.await_args.args[0]
        assert written.overall_status == PlanStatus.canceled
        assert result == EndedTurn(outcome=TurnOutcome.ended, cancelled=True)

    @pytest.mark.asyncio
    async def test_the_slot_is_given_up_so_the_next_turn_starts_clean(self):
        task = await _in_flight()
        turn = SimpleNamespace(session_id="sess-1", task=task)
        orchestration = _registry(turn)

        await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=_store(_plan()),
            orchestration=orchestration,
        )

        orchestration.release_active_turn.assert_called_once_with("user-1", task)


class TestOneChatsTurnIsNotAnothers:
    """ADR-031 §6, and the reason it is a decision rather than an oversight."""

    @pytest.mark.asyncio
    async def test_a_turn_running_for_another_chat_keeps_running(self):
        task = await _in_flight()
        orchestration = _registry(SimpleNamespace(session_id="sess-2", task=task))

        await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=_store(_plan()),
            orchestration=orchestration,
        )

        assert not task.cancelled() and not task.cancelling()
        orchestration.release_active_turn.assert_not_called()
        task.cancel()

    @pytest.mark.asyncio
    async def test_only_the_named_chats_record_is_read_and_written(self):
        # The associate left `sess-1`. Nothing about `sess-2` — the Chat whose
        # turn is still computing — may be read, and nothing about it may be
        # written: `sess-2` is the conversation that would otherwise be
        # relabelled by leaving a different one.
        task = await _in_flight()
        store = _store(_plan(session_id="sess-1"))
        orchestration = _registry(SimpleNamespace(session_id="sess-2", task=task))

        await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=orchestration,
        )

        store.get_plan_by_session.assert_awaited_once_with("sess-1", plan_id=None)
        assert store.update_plan.await_args.args[0].session_id == "sess-1"
        task.cancel()


class TestTheRecordSettledIsTheCancelledTurnsOwn:
    """Which Plan, when the session holds more than one.

    A Chat holds more than one Plan (#71) and a new turn in the same session
    mints another, so "the session's latest" is the cancelled turn's record
    only while no newer turn has started. ``process_request`` writes the new
    Plan *before* it replaces the registry entry, so there is a window in which
    the registry still names the old turn and the latest plan is already the
    new one — and settling "the latest" there would cancel one turn and label a
    different one, leaving a turn about to run against a record that says it
    was canceled.
    """

    @pytest.mark.asyncio
    async def test_the_turn_names_the_plan_it_was_answering(self):
        task = await _in_flight()
        store = _store(_plan())
        orchestration = _registry(
            SimpleNamespace(session_id="sess-1", task=task, plan_id="plan-old")
        )

        await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=orchestration,
        )

        store.get_plan_by_session.assert_awaited_once_with("sess-1", plan_id="plan-old")

    @pytest.mark.asyncio
    async def test_an_abandoned_turn_still_settles_the_sessions_latest(self):
        # The fallback, and why the plan id cannot simply be required: a turn
        # whose task is gone leaves no registry entry to read one from, and
        # that stuck row is exactly what #122 has to be able to clear.
        store = _store(_plan())

        await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=_registry(),
        )

        store.get_plan_by_session.assert_awaited_once_with("sess-1", plan_id=None)


class TestAStoreThatCannotBeRead:
    """An outage may not become a destroyed turn (ADR-031, ADR-026).

    The record is read **before** anything is cancelled, and that order is the
    whole of this class. Cancel-then-read means a Cosmos failure kills the
    orchestration and then fails to write the status that would let anyone
    clear the row — an **Abandoned turn** manufactured by the primitive whose
    entire purpose is to end them. Read first, and a store that cannot answer
    leaves the turn exactly as it found it.
    """

    @pytest.mark.asyncio
    async def test_a_turn_is_not_cancelled_on_a_record_nobody_could_read(self):
        task = await _in_flight()
        store = _store()
        store.get_plan_by_session = AsyncMock(
            side_effect=RuntimeError("Cosmos is unavailable")
        )
        orchestration = _registry(SimpleNamespace(session_id="sess-1", task=task))

        with pytest.raises(RuntimeError):
            await end_turn(
                user_id="user-1",
                session_id="sess-1",
                memory_store=store,
                orchestration=orchestration,
            )

        assert not task.cancelled() and not task.cancelling()
        orchestration.release_active_turn.assert_not_called()
        task.cancel()

    @pytest.mark.asyncio
    async def test_a_chat_that_is_not_there_cancels_nothing(self):
        # No Plan record for this session and this user means there is no Chat
        # here to end a turn of. Reaching into the registry anyway would let a
        # session id somebody guessed reach a task — and the registry answers by
        # `user_id`, so the only turn it could reach is the caller's own,
        # running for a Chat they did not name.
        task = await _in_flight()
        orchestration = _registry(SimpleNamespace(session_id="sess-1", task=task))

        result = await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=_store(None),
            orchestration=orchestration,
        )

        assert result == EndedTurn(outcome=TurnOutcome.no_such_chat, cancelled=False)
        assert not task.cancelled() and not task.cancelling()
        task.cancel()


class TestASettledChatKeepsItsStatus:
    """A record corrected into being wrong is worse than one left alone."""

    @pytest.mark.parametrize(
        "settled",
        [PlanStatus.completed, PlanStatus.failed, PlanStatus.canceled],
    )
    @pytest.mark.asyncio
    async def test_a_turn_that_finished_first_is_left_exactly_as_it_is(
        self, settled
    ):
        store = _store(_plan(status=settled))

        result = await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=_registry(),
        )

        store.update_plan.assert_not_awaited()
        assert result.outcome is TurnOutcome.already_settled

    @pytest.mark.asyncio
    async def test_a_settled_record_still_ends_the_turn_it_finds_computing(self):
        # Keeping the status and ending the turn are separate answers. The
        # record already tells the truth, so nothing is written — but a task
        # still computing for this Chat is a turn the associate asked to end,
        # and leaving it running against a socket they have left is the
        # **Abandoned turn** by another name.
        task = await _in_flight()
        store = _store(_plan(status=PlanStatus.completed))
        orchestration = _registry(SimpleNamespace(session_id="sess-1", task=task))

        result = await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=orchestration,
        )

        assert task.cancelled() or task.cancelling()
        store.update_plan.assert_not_awaited()
        assert result == EndedTurn(
            outcome=TurnOutcome.already_settled, cancelled=True
        )

    @pytest.mark.asyncio
    async def test_a_status_nobody_recognises_is_a_turn_to_end(self):
        # The same fail-closed reading **Chat deletion** takes (ADR-026): a
        # status this repository does not know, and a record reporting none at
        # all, are both a chat something may still be happening to. Here that
        # cuts the other way and gives the same answer — such a Chat is
        # deletable by no route, so ending its turn is the only door it has.
        store = _store(_plan(status="whatever_comes_next"))

        result = await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=_registry(),
        )

        assert store.update_plan.await_args.args[0].overall_status == (
            PlanStatus.canceled
        )
        assert result.outcome is TurnOutcome.ended


class TestAnAbandonedTurn:
    """The row #122 has to be able to clear (ADR-031, **Abandoned turn**)."""

    @pytest.mark.asyncio
    async def test_a_chat_stuck_at_in_progress_settles_with_nothing_to_cancel(
        self,
    ):
        # The client is long gone and the task with it — a browser back or a
        # closed tab, which ADR-031 §3 deliberately leaves as a named gap. The
        # Plan record is still at `in_progress` and no exposed route will take
        # it. This is the door.
        store = _store(_plan())

        result = await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=_registry(),
        )

        assert result == EndedTurn(outcome=TurnOutcome.ended, cancelled=False)
        assert store.update_plan.await_args.args[0].overall_status == (
            PlanStatus.canceled
        )

    @pytest.mark.asyncio
    async def test_a_session_with_no_plan_record_is_no_chat_at_all(self):
        store = _store(None)

        result = await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=_registry(),
        )

        store.update_plan.assert_not_awaited()
        assert result.outcome is TurnOutcome.no_such_chat


class TestEndingIsNeverAVerdict:
    """ADR-031 §2. Navigating away is not an opinion about a plan."""

    @pytest.mark.asyncio
    async def test_a_reviewable_plan_awaiting_approval_is_cancelled_not_rejected(
        self,
    ):
        # #108 gave `approved: false` the meaning *"send it back"*. An
        # end-of-turn that reached the approval registry would file a revision
        # request nobody wrote, and the associate would come back to a plan
        # being redone on feedback that does not exist.
        task = await _in_flight()
        store = _store(_plan(status=PlanStatus.approved))
        orchestration = _registry(SimpleNamespace(session_id="sess-1", task=task))
        orchestration.approvals = {"m-1": None}

        result = await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=orchestration,
        )

        orchestration.set_approval_result.assert_not_called()
        assert result.outcome is TurnOutcome.ended

    @pytest.mark.asyncio
    async def test_the_plan_record_is_never_deleted(self):
        # `delete_plan_by_plan_id` is what the old navigation path reached
        # through the rejection route, and it took the conversation out of the
        # history entirely. The Plan record *is* the conversation (ADR-028).
        store = _store(_plan())

        await end_turn(
            user_id="user-1",
            session_id="sess-1",
            memory_store=store,
            orchestration=_registry(),
        )

        store.delete_plan_by_plan_id.assert_not_awaited()


class TestATurnDoesNotCancelItself:
    @pytest.mark.asyncio
    async def test_ending_from_inside_the_turn_writes_the_record(self):
        """The seam #123 calls this through.

        A **Clarification** that expires ends its own turn, from inside the
        orchestration task. Cancelling that task here would raise into this
        coroutine at its next await, so the write below would never happen and
        the Chat would stay at `in_progress` — the exact state the primitive
        exists to leave.
        """
        store = _store(_plan())
        ended = {}

        async def _turn():
            ended["result"] = await end_turn(
                user_id="user-1",
                session_id="sess-1",
                memory_store=store,
                orchestration=orchestration,
            )

        task = asyncio.create_task(_turn())
        orchestration = _registry(SimpleNamespace(session_id="sess-1", task=task))
        await task

        assert ended["result"] == EndedTurn(outcome=TurnOutcome.ended, cancelled=False)
        assert store.update_plan.await_args.args[0].overall_status == (
            PlanStatus.canceled
        )
