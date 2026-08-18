"""**Startup reconciliation** — the seam that decides which records to settle
(#159, ADR-047).

Asserted here rather than against Cosmos, because the whole of the decision is
readable from the rows: a **Plan record** a starting process finds at an
unsettled status describes a turn whose ``asyncio.Task`` died with the process
that held it, and the rule for which of those to settle is arithmetic over four
fields.

Three properties are the point, and each is a way this could do harm:

* **It is fail-closed in the same direction everything else here is.** ``is_running``
  decides, so a status this repository does not recognise is stuck rather than
  settled — the same predicate **Chat deletion** refuses on.
* **It settles a Chat, never a Plan it happened to see.** A Chat's state is its
  latest Plan's, so the settle-write is asked once per Chat and session-scoped,
  which is what `settle_turn` anticipated for this caller.
* **It reports what it did.** A backlog that cleared and a reconciliation that
  never ran are different facts, and an operator reads them off the same line.
"""

import pytest

from chat.reconcile import (Backlog, Reconciliation, StuckTurn, reconcile_turns,
                            stuck_turns)
from chat.settle import SettleOutcome, TurnSettled

# Sourced the way the module under test sources it. Six suites in this tree
# install a `Mock` over `common.models.messages` permanently, and a status read
# from there would be a `Mock` whose `.value` is not a string — which
# `is_running` correctly, and uselessly, calls running.
from chat.deletion import PlanStatus


def _plan(status=PlanStatus.in_progress, session_id="sess-1", user_id="user-1",
          plan_id="plan-1"):
    """A Plan record, as the cross-user read projects it."""
    row = {"id": plan_id, "session_id": session_id, "user_id": user_id}
    if status is not None:
        row["overall_status"] = getattr(status, "value", status)
    return row


class TestWhichRecordsAreStuck:
    """The seam. Pure, and asserted without a store of any kind."""

    def test_a_plan_still_claiming_to_run_is_stuck(self):
        found = stuck_turns([_plan(PlanStatus.in_progress)])

        assert found.stuck == (StuckTurn(user_id="user-1", session_id="sess-1"),)
        assert found.examined == 1

    @pytest.mark.parametrize(
        "status",
        [PlanStatus.completed, PlanStatus.failed, PlanStatus.canceled],
    )
    def test_a_chat_that_already_settled_is_untouched(self, status):
        # The three members of the **Settled status** set, and the reason the
        # set does not move for this ticket: more Chats become deletable only
        # by more turns actually ending.
        found = stuck_turns([_plan(status)])

        assert found.stuck == ()
        assert found.examined == 1

    @pytest.mark.parametrize(
        "status", [PlanStatus.approved, PlanStatus.created, "sleeping", None]
    )
    def test_anything_that_is_not_a_settled_status_is_stuck(self, status):
        # Fail-closed in the direction that *settles*, which is the safe one
        # here and the opposite of the delete's: a status nobody recognises
        # describes a turn no process is running either.
        found = stuck_turns([_plan(status)])

        assert found.stuck == (StuckTurn(user_id="user-1", session_id="sess-1"),)

    def test_a_chat_with_two_stuck_plans_is_settled_once(self):
        # A Chat's state is its latest Plan's (#71), and the settle-write is
        # session-scoped. Asking twice would settle the same document and then
        # report `already_settled` against the second ask, which reads to an
        # operator as a backlog half-cleared.
        found = stuck_turns([_plan(plan_id="plan-1"), _plan(plan_id="plan-2")])

        assert found.stuck == (StuckTurn(user_id="user-1", session_id="sess-1"),)
        assert found.examined == 2

    def test_two_associates_stuck_in_one_session_are_two_turns(self):
        # The settle-write's `user_id` predicate is the whole of its
        # authorization, so the owner is part of what names a turn. Collapsing
        # these would settle one associate's record under the other's identity.
        found = stuck_turns(
            [_plan(user_id="user-1"), _plan(user_id="user-2")]
        )

        assert found.stuck == (
            StuckTurn(user_id="user-1", session_id="sess-1"),
            StuckTurn(user_id="user-2", session_id="sess-1"),
        )

    def test_a_plan_naming_no_session_is_left_alone_and_counted(self):
        # No settle-write can reach it: the read it targets is scoped by
        # session *and* owner. Left stuck rather than guessed at, and reported
        # so the number an operator reads is not quietly short.
        found = stuck_turns([_plan(session_id=None), _plan(user_id=None)])

        assert found.stuck == ()
        assert found.unnameable == 2
        assert found.examined == 2

    def test_nothing_stuck_is_still_a_reconciliation_that_ran(self):
        found = stuck_turns([])

        assert found == Backlog()
        assert found.examined == 0


class _Store:
    """An owner-scoped store, stood in for at the settle-write's own seam."""

    def __init__(self, outcome=SettleOutcome.settled, raises=None):
        self.outcome = outcome
        self.raises = raises
        self.asked = []

    async def settle_turn(self, session_id, status, plan_id=None):
        self.asked.append((session_id, status, plan_id))
        if self.raises is not None:
            raise self.raises
        return TurnSettled(self.outcome, status=getattr(status, "value", status))


class _Stores:
    """``store_for`` — one store per owner, remembering who was asked for."""

    def __init__(self, **by_user):
        self.by_user = by_user
        self.requested = []

    async def __call__(self, user_id):
        self.requested.append(user_id)
        return self.by_user.setdefault(user_id, _Store())


class TestReconcilingTheBacklog:
    """The pass, driven through a store that is stood in for."""

    @pytest.mark.asyncio
    async def test_a_stuck_chat_is_settled_through_the_settle_write(self):
        stores = _Stores()

        result = await reconcile_turns([_plan()], stores)

        assert result.settled == ("sess-1",)
        assert stores.by_user["user-1"].asked == [
            ("sess-1", PlanStatus.canceled, None)
        ]

    @pytest.mark.asyncio
    async def test_the_write_names_no_plan(self):
        # Session-scoped, and deliberately: this pass has no turn of its own,
        # and a Chat's state is whichever Plan the settle-write's own read
        # calls latest. Binding to a document seen a moment earlier would
        # refuse as `superseded` and leave the row stuck.
        stores = _Stores()

        await reconcile_turns([_plan(plan_id="plan-7")], stores)

        _session, _status, named = stores.by_user["user-1"].asked[0]
        assert named is None

    @pytest.mark.asyncio
    async def test_the_write_goes_through_a_store_scoped_to_the_owner(self):
        # The settle-write's `user_id` predicate is the whole of its
        # authorization. A pass that reached for one unscoped store would be
        # writing verdicts onto conversations it cannot see.
        stores = _Stores()

        await reconcile_turns(
            [_plan(user_id="user-1", session_id="sess-1"),
             _plan(user_id="user-2", session_id="sess-2")],
            stores,
        )

        assert stores.requested == ["user-1", "user-2"]
        assert stores.by_user["user-1"].asked == [
            ("sess-1", PlanStatus.canceled, None)
        ]
        assert stores.by_user["user-2"].asked == [
            ("sess-2", PlanStatus.canceled, None)
        ]

    @pytest.mark.asyncio
    async def test_a_settled_chat_is_never_asked_to_settle_again(self):
        stores = _Stores()

        result = await reconcile_turns([_plan(PlanStatus.completed)], stores)

        assert result.settled == ()
        assert stores.requested == []

    @pytest.mark.asyncio
    async def test_a_chat_that_settled_under_the_pass_is_not_a_failure(self):
        # The record now says the turn ended, which is the fact this pass
        # exists to make true. Reporting it as a failure would put a false
        # alarm in a startup log.
        stores = _Stores(**{"user-1": _Store(SettleOutcome.already_settled)})

        result = await reconcile_turns([_plan()], stores)

        assert result.already_settled == 1
        assert result.failed == 0
        assert result.settled == ()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "outcome",
        [
            SettleOutcome.refused,
            SettleOutcome.lost_race,
            SettleOutcome.no_such_chat,
            SettleOutcome.superseded,
        ],
    )
    async def test_a_write_that_did_not_land_is_reported_as_not_settled(
        self, outcome
    ):
        stores = _Stores(**{"user-1": _Store(outcome)})

        result = await reconcile_turns([_plan()], stores)

        assert result.failed == 1
        assert result.settled == ()

    @pytest.mark.asyncio
    async def test_one_chat_the_store_could_not_settle_does_not_end_the_pass(
        self,
    ):
        # The backlog is a list of independent rows. Abandoning the rest of it
        # because one raised would leave a cleared backlog looking like a
        # broken one — and the next start would face the same list.
        stores = _Stores(
            **{
                "user-1": _Store(raises=RuntimeError("cosmos is having a day")),
                "user-2": _Store(),
            }
        )

        result = await reconcile_turns(
            [_plan(user_id="user-1", session_id="sess-1"),
             _plan(user_id="user-2", session_id="sess-2")],
            stores,
        )

        assert result.failed == 1
        assert result.settled == ("sess-2",)

    @pytest.mark.asyncio
    async def test_the_pass_reports_what_it_examined_even_when_nothing_moved(
        self,
    ):
        # A cleared backlog and a reconciliation that never ran are different
        # facts, and this line is where an operator tells them apart.
        result = await reconcile_turns([_plan(PlanStatus.completed)], _Stores())

        assert result.backlog.examined == 1
        assert "examined 1 plan(s)" in result.summary
        assert "settled 0 as canceled" in result.summary

    @pytest.mark.asyncio
    async def test_the_summary_names_the_status_the_pass_writes(self):
        # `canceled`, not `failed`: the turn was ended by the process going
        # away, and nothing observed it fail. The same word **Ending a turn**
        # writes, for the same reason.
        result = await reconcile_turns([_plan()], _Stores())

        assert result.settled == ("sess-1",)
        assert "settled 1 as canceled" in result.summary
        assert isinstance(result, Reconciliation)
