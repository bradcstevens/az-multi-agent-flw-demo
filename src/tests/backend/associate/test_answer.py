"""The Personal answer as it reaches the browser (issue #27).

Beside ``escalation/payloads.py`` and for the recorded reason: the package that
decides what a claim may say owns the shape of the claim.
"""

import pytest

from associate.answer import (
    PERSONAL_ANSWER_KIND,
    PersonalAnswer,
    personal_answer_detail,
)
from associate.records import DEMO_ASSOCIATE, AssociateFact, AssociateRecord
from provenance import ASSOCIATE_RECORD_PROVENANCE


class TestBuildingTheAnswer:
    """One record in, one answer out."""

    def test_the_answer_names_the_associate_it_is_about(self):
        answer = PersonalAnswer.from_record(DEMO_ASSOCIATE)
        assert answer.display_name == DEMO_ASSOCIATE.display_name

    def test_the_answer_carries_every_fact_in_the_records_own_order(self):
        """The record is shown *whole*. Picking the field the question asked
        about would be a third classifier, and a third classifier can report
        the wrong number."""
        answer = PersonalAnswer.from_record(DEMO_ASSOCIATE)
        assert [(f.label, f.value) for f in answer.facts] == [
            (f.label, f.value) for f in DEMO_ASSOCIATE.facts
        ]

    def test_the_answer_carries_the_associates_role(self):
        answer = PersonalAnswer.from_record(DEMO_ASSOCIATE)
        assert answer.role == DEMO_ASSOCIATE.role

    def test_a_record_with_no_facts_still_answers(self):
        """It says who is signed in and lists nothing, which is true. An
        exception here would turn a thin record into a failed request."""
        answer = PersonalAnswer.from_record(AssociateRecord(display_name="Nobody"))
        assert answer.display_name == "Nobody"
        assert answer.facts == []


class TestTheAnswerCarriesItsProvenance:
    """A claim about a person's pay may not read as a system of record's."""

    def test_the_answer_names_the_payroll_system_that_was_not_queried(self):
        answer = PersonalAnswer.from_record(DEMO_ASSOCIATE)
        assert answer.provenance_line == ASSOCIATE_RECORD_PROVENANCE

    def test_there_is_no_provenance_flag_to_omit(self):
        """Every answer this system produces is from authored content — there
        is no other kind — so the framing is a property of the answer, not a
        field a caller could leave off."""
        payload = personal_answer_detail(DEMO_ASSOCIATE)
        assert "provenance_line" in payload

    def test_the_provenance_line_is_the_same_for_every_record(self):
        a = PersonalAnswer.from_record(DEMO_ASSOCIATE)
        b = PersonalAnswer.from_record(AssociateRecord(display_name="Nobody"))
        assert a.provenance_line == b.provenance_line


class TestTheWireShape:
    """What the request path actually returns."""

    def test_the_payload_names_itself(self):
        """The browser switches on this the way it switches on a policy
        block's ``kind`` — an answer that did not name itself would have to be
        recognised by the shape of its fields."""
        assert personal_answer_detail(DEMO_ASSOCIATE)["kind"] == PERSONAL_ANSWER_KIND

    def test_the_payload_is_a_kind_of_its_own(self):
        from guardrail.refusal import POLICY_BLOCK_KIND

        assert PERSONAL_ANSWER_KIND != POLICY_BLOCK_KIND

    def test_the_payload_is_plain_data(self):
        payload = personal_answer_detail(DEMO_ASSOCIATE)
        assert isinstance(payload, dict)
        assert all(isinstance(fact, dict) for fact in payload["facts"])

    def test_the_facts_travel_as_an_ordered_list_of_rows(self):
        """The order is the order the record was authored in. A map would make
        it an accident of how two languages iterate a dictionary."""
        payload = personal_answer_detail(DEMO_ASSOCIATE)
        assert isinstance(payload["facts"], list)
        assert payload["facts"][0] == {
            "label": DEMO_ASSOCIATE.facts[0].label,
            "value": DEMO_ASSOCIATE.facts[0].value,
        }

    def test_a_fresh_payload_each_call(self):
        """A caller that annotates one response must not quietly edit the one
        behind every other — the same rule ``policy_block_detail`` follows."""
        first = personal_answer_detail(DEMO_ASSOCIATE)
        first["facts"].append({"label": "x", "value": "y"})
        assert len(personal_answer_detail(DEMO_ASSOCIATE)["facts"]) == len(
            DEMO_ASSOCIATE.facts
        )


class TestTheAnswerNeverInventsAFact:
    """The one-way requirement, in the direction that matters."""

    @pytest.mark.parametrize("label,value", [("", "5 hours"), ("PTO", "")])
    def test_a_half_written_fact_is_dropped_rather_than_shown_blank(
        self, label, value
    ):
        """A blank value beside a label reads as *nothing owed*, which is a
        claim about somebody's pay that nobody authored."""
        record = AssociateRecord(
            display_name="Nobody", facts=(AssociateFact(label, value),)
        )
        assert PersonalAnswer.from_record(record).facts == []
