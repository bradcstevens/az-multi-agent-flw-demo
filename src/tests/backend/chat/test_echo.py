"""What the echo may be called, with no store behind it (#158, ADR-043 §7).

*One fact, one writer.* The browser's echo stopped deciding whether a turn
ended, and this file is the half of that a reviewer can check by reading: the
three ways recording an agent message can differ, and which of them a route is
allowed to answer with success.

The distinction the old code lost is the one asserted hardest here. A store that
refused a write and a **Plan record** that has gone are not the same event: the
first is a write this process believed it had made and had not, and the second
is ordinary — #108's rejection path deletes a Plan record outright, and the echo
is fire-and-forget, so it can arrive after the server settled the turn and the
associate deleted the Chat that settling made deletable. A broad `except`
answered both, and a clean write, with `{"status": "message recorded"}`.
"""

import pytest

from chat.echo import NOT_RECORDED_DETAIL, EchoOutcome, MessageEchoed


class TestWhatCountsAsRecorded:
    def test_a_clean_write_persisted(self):
        assert MessageEchoed(EchoOutcome.recorded).persisted is True

    @pytest.mark.parametrize(
        "outcome", [EchoOutcome.no_such_plan_record, EchoOutcome.refused]
    )
    def test_nothing_else_did(self, outcome):
        # `persisted` answers one question — did every write the echo asked for
        # land — and a **Plan record** that has gone means the streamed reply
        # did not.
        assert MessageEchoed(outcome).persisted is False


class TestWhatCountsAsAStoreFailure:
    def test_a_refusal_is_one(self):
        assert MessageEchoed(EchoOutcome.refused).store_failed is True

    def test_a_plan_record_that_has_gone_is_not(self):
        # The whole reason these are separate members. Answering a deleted Chat
        # with a 500 would report an outage every time somebody cleared their
        # history — and the route decides its status code off this property.
        assert MessageEchoed(EchoOutcome.no_such_plan_record).store_failed is False

    def test_a_clean_write_is_not(self):
        assert MessageEchoed(EchoOutcome.recorded).store_failed is False


class TestWhatTheRouteMaySay:
    """Never more than it did."""

    def test_a_clean_write_says_the_message_was_recorded(self):
        assert MessageEchoed(EchoOutcome.recorded).status == "message recorded"

    @pytest.mark.parametrize(
        "outcome", [EchoOutcome.no_such_plan_record, EchoOutcome.refused]
    )
    def test_no_other_outcome_says_that(self, outcome):
        # The exact sentence the route used to give unconditionally. If any
        # outcome but the clean one can produce it again, this ticket is undone
        # however the route is written.
        assert MessageEchoed(outcome).status != "message recorded"

    def test_a_plan_record_that_has_gone_names_what_did_not_land(self):
        assert MessageEchoed(EchoOutcome.no_such_plan_record).status == (
            "message recorded without its streaming message"
        )

    def test_a_refusal_says_the_message_was_not_recorded(self):
        # Total over the outcomes, including the one the route answers with an
        # error, so this property can never be the reason a failure is
        # described as a success.
        assert MessageEchoed(EchoOutcome.refused).status == "message not recorded"


def test_the_refusal_detail_says_what_did_not_happen():
    # The sentence the browser is given on a 500. Stated once, here, rather
    # than written a second time at the route.
    assert "did not reach the store" in NOT_RECORDED_DETAIL
