"""The shape of a Simulated ticket, and the rules TKT-001 states (issue #22).

Pure: no I/O, no container, no model. Everything here is a rule the ticket
template already writes down, moved to where it can be enforced rather than
instructed — because a ticket is the assistant making a claim on the
associate's behalf to somebody who is not in the room, and the rule the whole
build runs on is that a surface may say nothing but may not say something that
is not so.
"""

import os
import sys

import pytest

_backend_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
)
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from escalation.ticket import (  # noqa: E402
    CARRIED_FIELDS,
    FIELD_ORDER,
    NOT_REPORTED,
    SIMULATED_NOTICE,
    TicketStatus,
    draft_fields,
    render_ticket,
    submitted_fields,
    ticket_id_for,
)


class TestTheAttemptedStepsAreCarriedNotRetyped:
    """The whole reason the ticket is raised in this conversation."""

    def test_the_attempted_steps_come_from_the_record(self):
        fields = draft_fields({}, attempted=["Fitted a fresh paper filter"])

        assert "fresh paper filter" in fields["steps_attempted"]

    def test_a_caller_supplied_value_is_discarded_in_favour_of_the_record(self):
        """One-way, like the guardrail's keyword path and the step matcher.

        A model that re-typed the steps would produce a ticket that reads
        correct and is not the associate's account. The record is the only
        source there is, so the field is not one the caller can write.
        """
        fields = draft_fields(
            {"steps_attempted": "descaled the machine"},
            attempted=["Fitted a fresh paper filter"],
        )

        assert "descaled" not in fields["steps_attempted"]
        assert "fresh paper filter" in fields["steps_attempted"]

    def test_every_recorded_step_reaches_the_ticket(self):
        steps = [
            "Fitted a fresh paper filter",
            "Checked the grind on the marked notch",
            "Switched it off at the wall for a minute",
        ]

        fields = draft_fields({}, attempted=steps)

        for step in steps:
            assert step in fields["steps_attempted"]

    def test_an_empty_record_is_reported_not_invented(self):
        """The honest answer to "what did they try" is sometimes nothing."""
        assert draft_fields({}, attempted=[])["steps_attempted"] == NOT_REPORTED

    def test_the_carried_fields_are_named_and_the_steps_are_one(self):
        assert "steps_attempted" in CARRIED_FIELDS


class TestAFieldWithNoAnswer:
    def test_is_written_not_reported_rather_than_left_blank(self):
        """TKT-001: not left blank, not guessed, not turned into another
        question. A blank field on a service ticket reads as *nothing to
        report*, which is a claim nobody made."""
        fields = draft_fields({}, attempted=["a step"])

        assert fields["impact"] == NOT_REPORTED
        assert fields["notes"] == NOT_REPORTED

    def test_and_so_is_a_field_supplied_as_whitespace(self):
        fields = draft_fields({"symptom": "   "}, attempted=["a step"])

        assert fields["symptom"] == NOT_REPORTED

    def test_and_so_is_a_field_supplied_as_something_that_is_not_text(self):
        fields = draft_fields({"symptom": {"nested": "object"}}, attempted=["a"])

        assert fields["symptom"] == NOT_REPORTED


class TestTheTemplatesFields:
    def test_every_field_the_template_names_is_on_the_ticket(self):
        fields = draft_fields({}, attempted=[])

        assert set(fields) == set(FIELD_ORDER)

    def test_a_field_the_template_does_not_name_is_dropped(self):
        """A ticket carrying a field TKT-001 has no row for is a ticket whose
        shape the model chose. The template is the shape."""
        fields = draft_fields({"vendor_promised": "next day"}, attempted=[])

        assert "vendor_promised" not in fields

    def test_the_site_is_the_store_and_is_not_the_callers_to_set(self):
        """Store 223 is where this assistant runs. A ticket naming another
        site is a van sent to the wrong forecourt."""
        fields = draft_fields({"site_number": "999"}, attempted=[])

        assert fields["site_number"] == "223"
        assert "223" in fields["site"]


class TestTheAssetIsWhatBroke:
    def test_it_falls_back_to_the_equipment_the_record_already_names(self):
        """The turn that reports a step is rarely the turn that named the
        equipment — the record carries it precisely so the ticket need not
        ask again."""
        fields = draft_fields({}, attempted=["a step"], equipment="coffee brewer")

        assert fields["asset"] == "coffee brewer"

    def test_but_a_supplied_asset_is_the_more_specific_one_and_wins(self):
        fields = draft_fields(
            {"asset": "front counter coffee brewer, left head"},
            attempted=["a step"],
            equipment="coffee brewer",
        )

        assert fields["asset"] == "front counter coffee brewer, left head"


class TestPriority:
    @pytest.mark.parametrize("supplied", ["1", 2, "3", 4])
    def test_the_four_the_template_allows_are_kept(self, supplied):
        assert draft_fields({"priority": supplied}, attempted=[])["priority"] == str(
            supplied
        )

    @pytest.mark.parametrize("supplied", ["urgent", 0, 7, "as soon as possible"])
    def test_anything_else_is_not_reported_rather_than_coerced(self, supplied):
        """A priority the template has no row for would be read by a service
        desk as a service window that was never promised."""
        assert (
            draft_fields({"priority": supplied}, attempted=[])["priority"]
            == NOT_REPORTED
        )


class TestADraftIsNotATicketYet:
    def test_a_draft_says_it_is_a_draft(self):
        assert draft_fields({}, attempted=[])["status"] == TicketStatus.draft

    def test_and_carries_no_ticket_number(self):
        """TKT-001: the number is issued when the associate confirms. A number
        printed on a draft is a number the associate could quote to a service
        desk for a ticket that was never raised."""
        assert draft_fields({}, attempted=[])["ticket_id"] == NOT_REPORTED

    def test_nor_a_time_it_was_opened(self):
        assert draft_fields({}, attempted=[])["opened_at"] == NOT_REPORTED


class TestTheTicketNumber:
    def test_it_is_derived_from_the_session_not_from_a_counter(self):
        """A counter is shared state that a restart resets, and a reissued
        number is two different faults with one identity. Derived, so the same
        conversation's ticket keeps its number however often it is read."""
        assert ticket_id_for("s-1") == ticket_id_for("s-1")

    def test_two_sessions_do_not_share_one(self):
        assert ticket_id_for("s-1") != ticket_id_for("s-2")

    def test_it_says_simulated_in_the_number_itself(self):
        """The number travels further than the card it was rendered on."""
        assert ticket_id_for("s-1").startswith("SIM-223-")


class TestCorrectingADraft:
    def test_a_field_not_mentioned_again_keeps_what_it_said(self):
        corrected = draft_fields(
            {"priority": "1"},
            attempted=["a step"],
            previous={"symptom": "left head runs cold", "priority": "3"},
        )

        assert corrected["symptom"] == "left head runs cold"
        assert corrected["priority"] == "1"

    def test_but_the_attempted_steps_still_come_only_from_the_record(self):
        """Even here. A correction turn re-drafts against the draft it
        corrects, and if the previous ticket's ``steps_attempted`` survived
        that, the record would stop being the only source the moment anybody
        corrected anything."""
        corrected = draft_fields(
            {},
            attempted=["Fitted a fresh paper filter"],
            previous={"steps_attempted": "descaled the machine"},
        )

        assert corrected["steps_attempted"] == "Fitted a fresh paper filter"

    def test_and_a_previously_issued_number_does_not_survive_into_a_draft(self):
        corrected = draft_fields(
            {}, attempted=[], previous={"ticket_id": "SIM-223-0041",
                                        "status": TicketStatus.submitted}
        )

        assert corrected["ticket_id"] == NOT_REPORTED
        assert corrected["status"] == TicketStatus.draft


class TestConfirmationChangesOnlyWhatItConfirms:
    """"The associate sees exactly what will be submitted" — which, once the
    approval *is* the submission and there is no second screen, is a property
    of the confirmation and not of a preview."""

    @pytest.fixture
    def draft(self):
        return draft_fields(
            {
                "symptom": "left head runs cold and slow",
                "asset": "front counter coffee brewer, left head",
                "priority": "2",
                "category": "equipment",
                "impact": "one of two brew heads out of service",
            },
            attempted=["Fitted a fresh paper filter"],
        )

    def test_every_field_the_associate_read_survives_the_confirmation(self, draft):
        confirmed = submitted_fields(draft, session_id="s-1", opened_at="2026-08-13T14:12:00")

        for name in FIELD_ORDER:
            if name in ("ticket_id", "opened_at", "status"):
                continue
            assert confirmed[name] == draft[name], name

    def test_the_attempted_steps_in_particular_survive_it(self, draft):
        confirmed = submitted_fields(draft, session_id="s-1", opened_at="t")

        assert confirmed["steps_attempted"] == draft["steps_attempted"]

    def test_and_the_confirmation_is_what_issues_the_number(self, draft):
        confirmed = submitted_fields(draft, session_id="s-1", opened_at="t")

        assert confirmed["ticket_id"] == ticket_id_for("s-1")
        assert confirmed["status"] == TicketStatus.submitted
        assert confirmed["opened_at"] == "t"

    def test_it_does_not_mutate_the_draft_it_was_given(self, draft):
        """A draft mutated in place is a draft that can no longer be compared
        with what was submitted — which is the comparison this whole class is."""
        submitted_fields(draft, session_id="s-1", opened_at="t")

        assert draft["status"] == TicketStatus.draft
        assert draft["ticket_id"] == NOT_REPORTED


class TestRender:
    def test_it_lists_the_fields_in_the_order_the_template_states_them(self):
        rendered = render_ticket(draft_fields({}, attempted=["a step"]))
        positions = [rendered.index(f"{name}:") for name in FIELD_ORDER]

        assert positions == sorted(positions)

    def test_every_field_is_shown_so_the_associate_sees_what_will_be_submitted(self):
        rendered = render_ticket(draft_fields({}, attempted=["a step"]))

        for name in FIELD_ORDER:
            assert f"{name}:" in rendered

    def test_it_says_the_ticket_is_simulated(self):
        assert SIMULATED_NOTICE in render_ticket(draft_fields({}, attempted=[]))
