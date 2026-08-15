"""What Chat deletion is allowed to take, and what it reports (#75, ADR-026).

The pure half of the operation: no Cosmos, no route. Everything here is a rule
a reviewer can check by reading it, which is the point — the IO half can only
be trusted to sweep a partition, and *which* partition it may sweep is decided
here.
"""

import pytest

from chat import deletion
from chat.deletion import (
    ChatDeletion,
    ChatsDeletion,
    DeletionOutcome,
    SETTLED_STATUSES,
    STILL_RUNNING_DETAIL,
    is_running,
)

# The very enum the rule was built from, reached through the module that built
# it. Importing `common.models.messages` here instead would hand this file
# whatever the shared interpreter happens to hold — earlier suites replace that
# module with a bare `Mock()`, and a `Mock` status is not a status.
PlanStatus = deletion.PlanStatus


class TestWhichChatsAreRunning:
    """A running Chat may not be deleted (ADR-026), so this decides which."""

    @pytest.mark.parametrize(
        "status",
        [PlanStatus.completed, PlanStatus.failed, PlanStatus.canceled],
    )
    def test_a_settled_chat_is_not_running(self, status):
        # The three states a conversation stops in. A failed or canceled chat
        # is exactly the rehearsal debris #74 put on screen and this ticket
        # exists to clear.
        assert is_running(status) is False

    @pytest.mark.parametrize(
        "status",
        [PlanStatus.created, PlanStatus.approved, PlanStatus.in_progress],
    )
    def test_an_unfinished_chat_is_running(self, status):
        # Not only `in_progress`: a plan the orchestrator has been handed and
        # has not started is as live as one it is halfway through, and deleting
        # the partition underneath it destroys a conversation in flight.
        assert is_running(status) is True

    def test_a_status_nobody_here_knows_is_running(self):
        # Fail-closed, the Identity boundary gate's discipline: *cannot tell*
        # is not *safe to delete*. A status added to the backend later reaches
        # this rule as a word it does not know, and refusing an irreversible
        # delete is the cheap side of that mistake.
        assert is_running("archived") is True

    def test_a_chat_reporting_no_status_at_all_is_running(self):
        assert is_running(None) is True
        assert is_running("") is True
        assert is_running("   ") is True

    def test_the_plain_wire_value_reads_the_same_as_the_enum(self):
        # A Plan comes back off the wire as a string; `PlanStatus` is a
        # `str` Enum whose hash is the member's, so a set of members does not
        # contain the value. Both sides of that are read here.
        assert is_running(PlanStatus.completed.value) is False
        assert is_running("in_progress") is True

    def test_the_settled_states_are_the_three_a_conversation_stops_in(self):
        # Named here as plain strings so the rule is legible without following
        # the enum: everything else, present or added later, is running.
        assert SETTLED_STATUSES == {"completed", "failed", "canceled"}


class TestWhatTheDeletionReports:
    """The route reports what happened, so the outcome has to carry it."""

    def test_a_sweep_that_took_everything_reports_deleted(self):
        swept = ChatDeletion.swept(deleted=7, failed=0)

        assert swept.outcome is DeletionOutcome.deleted
        assert swept.deleted == 7

    def test_a_sweep_that_left_documents_behind_does_not_report_success(self):
        # `delete_plan_by_plan_id` returns `True` even when it deleted nothing,
        # which is the shape ADR-026 refuses to route. A chat half-deleted is
        # a chat still in Cosmos, and the associate must not be told it is gone.
        swept = ChatDeletion.swept(deleted=4, failed=3)

        assert swept.outcome is DeletionOutcome.incomplete
        assert swept.deleted == 4
        assert swept.failed == 3

    def test_a_chat_that_is_not_this_users_is_no_chat_at_all(self):
        missing = ChatDeletion(DeletionOutcome.no_such_chat)

        assert missing.deleted == 0
        assert missing.failed == 0

    def test_the_refusal_says_why_rather_than_only_that(self):
        assert "running" in STILL_RUNNING_DETAIL.lower()


class TestWhatDeletingEveryChatReports:
    """The list-level control's accounting (#76).

    One chat's delete answers with an HTTP status; a sweep of the whole list
    cannot, because its chats do not all end the same way. The accounting is
    therefore the result rather than a decoration on it, and this is the rule
    that produces it — pure, so a reviewer can check the arithmetic without a
    store.
    """

    def test_nothing_to_delete_is_a_result_and_not_an_error(self):
        # A presenter who clears the list twice is not making a mistake the
        # second time.
        tallied = ChatsDeletion.tally([])

        assert tallied.deleted == ()
        assert tallied.kept_running == 0
        assert tallied.failed == 0
        assert tallied.documents_deleted == 0
        assert tallied.status == "deleted"

    def test_every_chat_that_went_is_named_rather_than_counted(self):
        # The panel prunes the rows the store says went, and navigates away
        # from the open chat only if it is one of them. A number cannot say
        # which, so the sessions come back and the count is derived from them.
        tallied = ChatsDeletion.tally(
            [
                ("session-1", ChatDeletion.swept(deleted=4, failed=0)),
                ("session-2", ChatDeletion.swept(deleted=3, failed=0)),
            ]
        )

        assert tallied.deleted == ("session-1", "session-2")
        assert tallied.documents_deleted == 7
        assert tallied.status == "deleted"

    def test_a_running_chat_is_kept_and_counted_as_kept(self):
        # ADR-026's noted cost, at list scale: refusing the whole operation
        # because one chat is running makes the control useless at exactly the
        # moment it is wanted, and omitting the chat silently is the surface
        # saying something that is not so.
        tallied = ChatsDeletion.tally(
            [
                ("session-1", ChatDeletion.swept(deleted=4, failed=0)),
                ("session-2", ChatDeletion(DeletionOutcome.still_running)),
            ]
        )

        assert tallied.deleted == ("session-1",)
        assert tallied.kept_running == 1
        assert tallied.failed == 0
        assert tallied.status == "deleted"

    def test_a_chat_that_only_partly_went_is_a_failure_and_not_a_deletion(self):
        # It is still in Cosmos, so the panel may not drop its row and the
        # outcome may not count it. The documents that did go are still
        # counted: they are gone whatever the row says.
        tallied = ChatsDeletion.tally(
            [
                ("session-1", ChatDeletion.swept(deleted=4, failed=0)),
                ("session-2", ChatDeletion.swept(deleted=2, failed=3)),
            ]
        )

        assert tallied.deleted == ("session-1",)
        assert tallied.failed == 1
        assert tallied.documents_deleted == 6
        assert tallied.status == "incomplete"

    @pytest.mark.parametrize(
        "outcome",
        [DeletionOutcome.no_such_chat, DeletionOutcome.not_yours],
    )
    def test_a_chat_this_sweep_may_not_take_is_a_failure(self, outcome):
        # These are enumerated from the user's own plans, so neither should
        # happen — a session holding somebody else's record is the one way it
        # can. It is not deleted and it is not running, and the third bucket is
        # where a result nobody predicted has to land rather than vanish.
        tallied = ChatsDeletion.tally([("session-1", ChatDeletion(outcome))])

        assert tallied.deleted == ()
        assert tallied.kept_running == 0
        assert tallied.failed == 1
        assert tallied.status == "incomplete"

    def test_every_chat_lands_in_exactly_one_bucket(self):
        # Total, deliberately. An outcome added to `DeletionOutcome` later
        # would otherwise be dropped on the floor and the surface would report
        # a shorter list than it swept.
        results = [
            (f"session-{i}", ChatDeletion(outcome))
            for i, outcome in enumerate(DeletionOutcome)
        ]

        tallied = ChatsDeletion.tally(results)

        assert (
            len(tallied.deleted) + tallied.kept_running + tallied.failed
            == len(results)
        )
