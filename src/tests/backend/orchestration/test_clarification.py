"""What the clarification seam puts to the associate (issue #62).

The seam's own tests live beside the orchestration manager's, because that is
where the question reaches the wire. These are the decision alone: which of the
framework's pauses is a **Clarification** at all.
"""

import json
from types import SimpleNamespace

import pytest

from orchestration.clarification import (CLARIFICATION_TOOL, NOT_ASKED,
                                         clarification_questions)


def _call(name=CLARIFICATION_TOOL, arguments=None):
    """A pending function call, as the framework hands it over."""
    return SimpleNamespace(name=name, arguments=arguments)


class TestWhichPauseIsAQuestion:
    def test_a_clarification_carries_its_questions_through_unchanged(self):
        """The associate reads the agent's words, not a summary of them."""
        asked = "What is the display showing — FILL, HEATING or an error code?"

        assert (
            clarification_questions(
                _call(arguments=json.dumps({"questions": asked}))
            )
            == asked
        )

    def test_any_other_gated_tool_puts_no_question_to_anybody(self):
        """``list_attempted_steps`` reads the record. Its pause is the
        framework's, not the associate's."""
        assert clarification_questions(_call(name="list_attempted_steps")) is None

    def test_a_clarification_with_no_questions_is_not_a_question(self):
        """The seam used to substitute *"The agent needs clarification."* here.
        A question with no words cannot be answered, and the **Rehearsed
        reply** tapped into it is spent on a call that will not read it."""
        assert clarification_questions(_call(arguments="{}")) is None

    def test_a_blank_question_is_not_a_question_either(self):
        assert (
            clarification_questions(
                _call(arguments=json.dumps({"questions": "   "}))
            )
            is None
        )

    def test_questions_that_arrived_as_a_list_are_still_a_question(self):
        """A model that emits its numbered questions as a JSON array has still
        asked them. The rule runs one way — this may leave a pause unasked,
        which the agent is told about and can retry, but it may never swallow a
        question the associate was waiting to answer."""
        assert clarification_questions(
            _call(
                arguments=json.dumps(
                    {"questions": ["Is the display lit?", "Does it say FILL?"]}
                )
            )
        ) == "Is the display lit?\nDoes it say FILL?"

    def test_an_empty_list_of_questions_asks_nothing(self):
        assert (
            clarification_questions(_call(arguments=json.dumps({"questions": []})))
            is None
        )

    def test_arguments_already_parsed_by_the_framework_are_read_as_given(self):
        """``arguments`` is a JSON string on the wire, and the framework has
        been seen to hand over the parsed mapping instead."""
        assert (
            clarification_questions(_call(arguments={"questions": "What is lit?"}))
            == "What is lit?"
        )

    @pytest.mark.parametrize(
        "arguments", ["not json at all", None, json.dumps(["questions"]), 7]
    )
    def test_arguments_that_did_not_survive_the_model_ask_nothing(self, arguments):
        """The pause is still approved by the caller — the turn continues — but
        nothing is put to the associate that nothing will read the answer to."""
        assert clarification_questions(_call(arguments=arguments)) is None

    def test_a_function_call_the_framework_left_unnamed_asks_nothing(self):
        assert clarification_questions(SimpleNamespace()) is None


class TestTheToolNameIsTheRealOne:
    def test_the_name_matched_is_the_clarification_tool_s_own(self):
        """Read out of the real tool rather than agreed with itself.

        A renamed tool would leave this module matching nothing, and the
        failure is silent and one-way: every clarification would be approved
        without ever reaching the associate, and the troubleshooting beat would
        stop asking what has already been tried with every test green.
        """
        from tools.clarification_tool import request_user_clarification

        real_name = getattr(
            request_user_clarification, "name", None
        ) or getattr(request_user_clarification, "__name__", None)

        assert real_name == CLARIFICATION_TOOL


class TestWhatTheAgentIsToldInstead:
    def test_it_says_the_associate_was_not_asked(self):
        """It may not invent an answer on the associate's behalf: the ticket
        is a claim made to somebody outside the room, in their name."""
        assert "not asked" in NOT_ASKED

    def test_it_says_where_the_ticket_gets_its_fields_from(self):
        assert "stored record" in NOT_ASKED
        assert "not reported" in NOT_ASKED
