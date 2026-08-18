"""The Reviewable plan's revision lineage.

The pure half of #108: a send-back is not a deletion, it is the next revision,
and the feedback that asked for it travels with it so the associate can check
they were understood.
"""

import pytest
from orchestration.plan_revision import PlanRevision


class TestPlanRevision:
    """What a Reviewable plan carries about the verdicts already given on it."""

    def test_a_plan_nobody_has_sent_back_is_revision_one(self):
        first = PlanRevision()

        assert first.number == 1
        assert first.feedback == ()
        assert first.latest_feedback is None

    def test_sending_a_plan_back_asks_for_the_next_revision(self):
        second = PlanRevision().sent_back("Ask Marcus instead.")

        assert second.number == 2
        assert second.feedback == ("Ask Marcus instead.",)
        assert second.latest_feedback == "Ask Marcus instead."

    def test_every_send_back_keeps_what_the_associate_said(self):
        third = PlanRevision().sent_back("Ask Marcus instead.").sent_back("Ask Dana.")

        assert third.number == 3
        assert third.feedback == ("Ask Marcus instead.", "Ask Dana.")

    def test_the_feedback_is_recorded_the_way_it_was_written(self):
        assert PlanRevision().sent_back("  Ask Marcus instead.  ").feedback == (
            "Ask Marcus instead.",
        )

    def test_a_send_back_with_nothing_asked_is_not_a_verdict(self):
        with pytest.raises(ValueError, match="feedback"):
            PlanRevision().sent_back("   ")

    def test_a_plan_record_reads_back_the_lineage_it_stored(self):
        stored = PlanRevision.restored(revision=3, feedback=["Ask Marcus instead."])

        assert stored == PlanRevision(number=3, feedback=("Ask Marcus instead.",))
        assert PlanRevision.restored(revision=None, feedback=None) == PlanRevision()
