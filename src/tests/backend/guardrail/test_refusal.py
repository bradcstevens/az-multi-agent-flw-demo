"""The refusal the Identity boundary gate returns (issue #14, ADR-014).

The refusal is a **fixed string**, so the properties worth asserting are the
ones the acceptance criteria actually name: that it explains store scoping and
the absence of individual identity, that it deflects somewhere useful, that it
does not over-apologise, and that it does not read as an error. Asserting the
whole string back would be a tautology — it would only prove the constant is
itself — so each test below checks one named property instead.
"""

from guardrail.refusal import (
    IDENTITY_BOUNDARY_REFUSAL,
    POLICY_BLOCK_CODE,
    POLICY_BLOCK_KIND,
    policy_block_detail,
)


class TestTheRefusalString:
    def test_it_explains_that_the_assistant_is_scoped_to_the_store(self):
        assert "Store 223" in IDENTITY_BOUNDARY_REFUSAL

    def test_it_says_it_has_no_individual_identity_to_work_from(self):
        lowered = IDENTITY_BOUNDARY_REFUSAL.lower()

        assert "shared" in lowered
        assert "who is asking" in lowered

    def test_it_deflects_to_a_manager_and_an_hr_number(self):
        lowered = IDENTITY_BOUNDARY_REFUSAL.lower()

        assert "manager" in lowered
        assert "hr" in lowered
        assert any(character.isdigit() for character in IDENTITY_BOUNDARY_REFUSAL)

    def test_it_does_not_over_apologise(self):
        """A governed refusal is a policy, not a regret."""
        lowered = IDENTITY_BOUNDARY_REFUSAL.lower()

        for grovel in ("sorry", "apolog", "unfortunately", "i'm afraid"):
            assert grovel not in lowered

    def test_it_does_not_read_as_an_error(self):
        """The audience must not mistake the centerpiece for a bug."""
        lowered = IDENTITY_BOUNDARY_REFUSAL.lower()

        for failure_word in ("error", "failed", "failure", "invalid", "denied",
                             "unable", "try again", "something went wrong"):
            assert failure_word not in lowered

    def test_it_offers_a_way_forward(self):
        """The boundary is a door, not a wall — #27 hangs its sign-in here."""
        assert "ask me" in IDENTITY_BOUNDARY_REFUSAL.lower()


class TestThePolicyBlockDetail:
    def test_it_is_labelled_as_a_policy_block(self):
        """The UI renders a policy block distinctly from a retrieval miss, and
        it can only do that if the wire tells the two apart."""
        detail = policy_block_detail()

        assert detail["kind"] == POLICY_BLOCK_KIND == "policy_block"
        assert detail["code"] == POLICY_BLOCK_CODE == "identity_boundary"

    def test_it_carries_the_refusal_as_its_message(self):
        assert policy_block_detail()["message"] == IDENTITY_BOUNDARY_REFUSAL

    def test_it_is_a_fresh_dictionary_each_time(self):
        """A caller adding telemetry to one response must not edit them all."""
        first = policy_block_detail()
        first["message"] = "tampered"

        assert policy_block_detail()["message"] == IDENTITY_BOUNDARY_REFUSAL
