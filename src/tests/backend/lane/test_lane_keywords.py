"""The lane router's keyword fallback (issue #16, ADR-013).

Free-typed input carries no declared Lane, so the fallback is all there is.
Its hard requirement runs one way only, exactly like the guardrail's Keyword
fast path: it may **miss** a Fast lane request — the miss falls open to the
Deliberate lane, which costs an approval step and nothing else — but it may
**never** claim an escalation or a ticket for the Fast lane, because that would
raise a simulated ticket with no confirmation, and the approval step *is* the
confirmation (#22).

The phrasings below are the demo's own vocabulary — SOP lookup, troubleshooting
turn and task query on the Fast side, escalation and ticket creation on the
Deliberate side — not phrasings reverse-engineered from the term lists.
"""

import pytest

from lane.keywords import keyword_lane
from lane.lane import Lane

FAST_PHRASINGS = (
    "How do I close the store?",
    "How does swapping shifts work?",
    "What are the steps for the coffee machine cleaning procedure?",
    "What's the process for reporting a fuel spill?",
    "What is the process for reporting a fuel spill?",
    "Show me the SOP for a fuel spill",
    "The coffee machine is down",
    "The slush machine stopped working",
    "What tasks are due on this shift?",
    "What needs doing before the end of the shift?",
    "What's on the checklist tonight?",
)

DELIBERATE_PHRASINGS = (
    "I can't fix it, please escalate this",
    "Raise a ticket for the coffee machine",
    "Create a service ticket for the walk-in cooler",
    "I need someone to come out and repair the fridge",
    "Log this with maintenance for me",
    "Submit a request for a replacement part",
)


class TestTheHardRequirement:
    @pytest.mark.parametrize("phrasing", DELIBERATE_PHRASINGS)
    def test_no_escalation_is_claimed_for_the_fast_lane(self, phrasing):
        assert keyword_lane(phrasing) is Lane.DELIBERATE

    def test_an_escalation_wearing_fast_lane_phrasing_still_goes_deliberate(self):
        """The mixed case is the realistic one and the dangerous one.

        "How do I ... raise a ticket" carries both vocabularies. Deliberate has
        to win outright, or the fallback's one-way requirement is only true of
        sentences that happen not to overlap.
        """
        assert keyword_lane(
            "How do I escalate this to maintenance?"
        ) is Lane.DELIBERATE

    @pytest.mark.parametrize(
        "phrasing",
        [
            "The freezer is broken and I cant fix it",
            "The freezer is broken and I can't fix it",
            "The coffee machine is down, I cannot fix it",
            "The slush machine stopped working — I've tried everything",
        ],
    )
    def test_a_fault_report_that_gives_up_still_goes_deliberate(self, phrasing):
        """An associate reports the fault *and* asks for help in one sentence.

        This is the shape #21 hands to #22, and it carries Fast lane
        troubleshooting vocabulary ("is broken", "stopped working") alongside
        the give-up. Typed on a shared device mid-shift, the apostrophe is
        optional — "cant" has to be the same word as "can't", or the escalation
        that is missing one loses its approval step.
        """
        assert keyword_lane(phrasing) is Lane.DELIBERATE

    @pytest.mark.parametrize(
        "phrasing",
        [
            "Start the process for swapping my shift with Alex",
            "Please replace the faulty card reader",
            "The card reader is faulty; please replace it",
            "This needs doing: swap my Friday shift with Alex",
            "Please do what needs doing to swap my Friday shift with Alex",
        ],
    )
    def test_a_transaction_does_not_match_lookup_language(self, phrasing):
        assert keyword_lane(phrasing) is Lane.DELIBERATE


class TestTheObviousFastLaneCases:
    @pytest.mark.parametrize("phrasing", FAST_PHRASINGS)
    def test_a_procedure_troubleshooting_or_task_question_takes_the_fast_lane(
        self, phrasing
    ):
        assert keyword_lane(phrasing) is Lane.FAST


class TestTheDefault:
    @pytest.mark.parametrize("phrasing", ["", "   ", "hello", None, 7])
    def test_anything_unrecognised_falls_open_to_the_deliberate_lane(self, phrasing):
        """A router failure never becomes a policy failure on stage.

        Total as well as fail-open: the fallback is reached from a request
        handler, so a non-string must not raise there.
        """
        assert keyword_lane(phrasing) is Lane.DELIBERATE
