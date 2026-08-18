"""The mocked associate record the sign-in unlocks (issue #27).

The gate refuses a personal question because a shared device cannot tell who is
asking. Sign-in answers that, and the answer has to come from *somewhere*: the
record here is what "answered from mocked data" means. It is authored demo
content and is labelled as such wherever it is shown.
"""

import pytest

from associate.records import (
    DEMO_ASSOCIATE,
    AssociateRecord,
    lookup_associate,
)


class TestTheDemoAssociate:
    """The one associate the mocked sign-in signs in as."""

    def test_the_demo_associate_has_a_display_name(self):
        assert DEMO_ASSOCIATE.display_name.strip()

    def test_the_demo_associate_has_an_authored_address_name(self):
        assert DEMO_ASSOCIATE.address_name == "Tanya"

    def test_the_demo_associate_is_the_one_the_boundary_probe_names(self):
        """The Quick Task says "My name is Tanya" — signing in as anybody else
        makes the beat a non sequitur on stage."""
        assert "tanya" in DEMO_ASSOCIATE.display_name.lower()

    def test_the_demo_associate_carries_facts_to_answer_with(self):
        assert DEMO_ASSOCIATE.facts, "a record with no facts answers nothing"


class TestLookingUpAnAssociate:
    """Resolving the record from the name held in Session state."""

    def test_the_demo_associates_own_name_resolves(self):
        assert lookup_associate(DEMO_ASSOCIATE.display_name) is DEMO_ASSOCIATE

    def test_a_first_name_alone_resolves(self):
        """The Session identity is a display name and the demo's is a full one,
        but a presenter improvising a sign-in may type only "Tanya"."""
        first_name = DEMO_ASSOCIATE.display_name.split()[0]
        assert lookup_associate(first_name) is DEMO_ASSOCIATE

    def test_the_name_is_matched_case_and_space_insensitively(self):
        assert lookup_associate("  tANYa  ") is DEMO_ASSOCIATE

    @pytest.mark.parametrize("name", [None, "", "   ", "Someone Else", 17])
    def test_an_unknown_or_unusable_name_resolves_to_no_record(self, name):
        """No record is the honest answer, and the request path falls through
        to the ordinary agents rather than inventing a balance."""
        assert lookup_associate(name) is None

    def test_a_substring_of_a_name_is_not_a_match(self):
        """"Tan" is not Tanya. A loose match would answer one associate's
        question out of another associate's record."""
        assert lookup_associate("Tan") is None


class TestTheRecordIsSimulated:
    """A record nobody could mistake for a real HR system's."""

    def test_a_record_is_immutable(self):
        """Shown on stage more than once; a caller that annotated it would
        change what the next tap says."""
        with pytest.raises(Exception):
            DEMO_ASSOCIATE.display_name = "Someone Else"  # type: ignore[misc]

    def test_every_fact_is_a_label_and_a_value(self):
        for fact in DEMO_ASSOCIATE.facts:
            assert fact.label.strip()
            assert fact.value.strip()

    def test_the_record_answers_the_question_the_boundary_probe_asks(self):
        """The probe asks about PTO. A record that never mentions it answers a
        question nobody asked."""
        labels = " ".join(fact.label.lower() for fact in DEMO_ASSOCIATE.facts)
        assert "pto" in labels or "time off" in labels

    def test_a_record_can_be_built_with_no_facts(self):
        """Total: the type does not require the demo's own content."""
        assert AssociateRecord(display_name="Nobody").facts == ()

    def test_a_record_can_omit_an_address_name(self):
        assert AssociateRecord(display_name="Nobody").address_name == ""
