"""The settle-write's rules, with no store behind them (#157, ADR-043).

*The server settles the turn it ended*, and this file is the half of that a
reviewer can check by reading: what may be written onto a **Plan record**, and
what a caller is allowed to call a fact that landed. The Cosmos half can only be
trusted to write one field conditionally; *which* field values it may write, and
which of its outcomes mean the record now says the turn ended, are decided here.
"""

import pytest

from chat import deletion
from chat.settle import (
    SettleOutcome,
    TurnSettled,
    settled_status,
)

# The enum reached through the module that built the rule, for the reason
# `test_deletion.py` states: earlier suites in this interpreter replace
# `common.models.messages` with a bare `Mock()`, and a `Mock` status is not a
# status.
PlanStatus = deletion.PlanStatus


class TestWhatMaySettleATurn:
    """Only a **Settled status** settles a turn."""

    @pytest.mark.parametrize(
        "status",
        [PlanStatus.completed, PlanStatus.failed, PlanStatus.canceled],
    )
    def test_each_settled_status_may_be_written(self, status):
        assert settled_status(status) == status.value

    @pytest.mark.parametrize("status", ["completed", "failed", "canceled"])
    def test_the_wire_value_is_the_same_request_as_the_member(self, status):
        # A caller holding the enum and one holding what it serialises to are
        # asking for the same write. `PlanStatus` is a `str` Enum whose hash is
        # the member's, so this is not automatic and is asserted rather than
        # assumed — the same trap `SETTLED_STATUSES` is built out of plain
        # strings to avoid.
        assert settled_status(status) == status

    @pytest.mark.parametrize(
        "status",
        [PlanStatus.in_progress, PlanStatus.approved, PlanStatus.created],
    )
    def test_an_unfinished_status_is_refused(self, status):
        # A settle-write that could write `in_progress` would be a way of
        # *un*-ending a turn — the never-overwrite rule read backwards.
        with pytest.raises(ValueError):
            settled_status(status)

    def test_the_orchestrations_wire_word_is_not_a_settled_status(self):
        # ADR-043 decision 4: the wire's vocabulary is not the record's. The
        # orchestration broadcasts `status: "error"`; the record carries
        # `failed`. Letting `error` through here is how a fourth terminal
        # status gets coined by accident — and `SETTLED_STATUSES` would not
        # recognise it, so the chat it settled would still read as running.
        with pytest.raises(ValueError):
            settled_status("error")

    @pytest.mark.parametrize("status", [None, "", "   ", 7, object()])
    def test_a_status_that_is_not_one_at_all_is_refused(self, status):
        with pytest.raises(ValueError):
            settled_status(status)

    def test_the_refusal_names_what_a_turn_may_settle_at(self):
        # The caller is a programmer, and this is a programming error rather
        # than a store outcome: the message has to say what would have worked.
        with pytest.raises(ValueError) as refusal:
            settled_status(PlanStatus.in_progress)

        for member in ("completed", "failed", "canceled"):
            assert member in str(refusal.value)

    def test_the_set_is_chat_deletions_own(self):
        # One set, not two. A settled status that could be written but not
        # deleted — or deleted but not written — is the two halves of ADR-026's
        # guard disagreeing about what "ended" means.
        for member in deletion.SETTLED_STATUSES:
            assert settled_status(member) == member


class TestWhatASettleWriteReports:
    """Which outcomes mean the record now says the turn ended."""

    def test_a_write_that_landed_is_persisted(self):
        assert TurnSettled(SettleOutcome.settled, status="completed").persisted

    def test_a_chat_that_had_already_settled_is_persisted(self):
        # The never-overwrite rule's other half. A late echo, a delete-door
        # cancel and #120's end-of-turn primitive all converge on one document,
        # and arriving second is the ordinary case: the fact this operation
        # exists to make durable is durable either way, so refusing to overwrite
        # is not a failure to report.
        assert TurnSettled(SettleOutcome.already_settled, status="failed").persisted

    @pytest.mark.parametrize(
        "outcome",
        [
            SettleOutcome.no_such_chat,
            SettleOutcome.superseded,
            SettleOutcome.lost_race,
            SettleOutcome.refused,
        ],
    )
    def test_everything_else_is_not(self, outcome):
        # The defect ADR-043 names in the browser's plumbing is a store write
        # reported as success by the layer above it. Every outcome that is not
        # a settled record has to be readable as one, or the caller logs a turn
        # that ended over a record that does not say so.
        assert TurnSettled(outcome).persisted is False

    def test_the_result_carries_the_status_the_record_holds(self):
        # Not the status that was *asked for*: a caller that lost to another
        # writer should be able to log which answer stood.
        assert TurnSettled(
            SettleOutcome.already_settled, status="canceled"
        ).status == "canceled"

    def test_a_result_says_nothing_about_a_record_it_never_read(self):
        assert TurnSettled(SettleOutcome.no_such_chat).status is None

    def test_a_turn_whose_chat_moved_on_is_not_a_settled_record(self):
        # The successor's Plan is at the top of the session and is *running*.
        # Reporting this as persisted would be the finished turn claiming the
        # live one's record as its own.
        settled = TurnSettled(SettleOutcome.superseded, status="in_progress")
        assert settled.persisted is False
