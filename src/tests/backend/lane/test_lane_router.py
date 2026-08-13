"""Lane selection: declared metadata first, keywords second, Deliberate always
as the floor (issue #16, ADR-013).
"""

import pytest

from lane.lane import Lane
from lane.router import select_lane


class TestADeclaredLane:
    """A Quick Task declares its lane, so nothing is inferred from its prompt."""

    def test_a_task_declaring_the_fast_lane_gets_it(self):
        assert select_lane("fast", "Raise a ticket for the coffee machine") is Lane.FAST

    def test_a_task_declaring_the_deliberate_lane_gets_it(self):
        """The declaration outranks the keywords, in the direction that matters.

        The description here is a textbook Fast lane SOP lookup, so if this
        returns Fast the declaration is decorative and the escalation Quick
        Task (#22) could be routed by its wording instead of by its metadata.
        """
        assert select_lane("deliberate", "How do I close the store?") is Lane.DELIBERATE


class TestFreeTypedInput:
    def test_a_procedure_question_falls_back_to_the_keyword_fast_path(self):
        assert select_lane(None, "How do I close the store?") is Lane.FAST

    def test_an_escalation_falls_back_to_the_deliberate_lane(self):
        assert select_lane(None, "I can't fix it, please escalate this") is Lane.DELIBERATE

    def test_input_matching_nothing_falls_open_to_the_deliberate_lane(self):
        assert select_lane(None, "hello") is Lane.DELIBERATE


class TestAnUnparseableLane:
    @pytest.mark.parametrize("declared", ["quick", "", "   ", 7, object()])
    def test_it_fails_open_to_the_deliberate_lane(self, declared):
        """Not consulted against the keywords, deliberately.

        A declared-but-unreadable lane means the metadata is corrupt. Guessing
        from the wording of a request whose metadata cannot be trusted is
        exactly how a router failure becomes a policy failure — so a corrupt
        declaration goes straight to the lane that keeps the approval gate,
        even when the wording is a plain Fast lane lookup.
        """
        assert select_lane(declared, "How do I close the store?") is Lane.DELIBERATE
