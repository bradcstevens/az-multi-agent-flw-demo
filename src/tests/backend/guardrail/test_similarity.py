"""The Identity boundary gate's similarity arithmetic, as pure functions.

ADR-014 requires the threshold comparison to be a pure function so it needs no
mocks at all. These tests use hand-written vectors with known-good cosine
values rather than recomputing the formula the implementation uses.
"""

import math

import pytest

from backend.guardrail.similarity import (
    cosine_similarity,
    max_similarity,
    personal_intent_margin,
    refuses,
)


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_scale_is_ignored(self):
        assert cosine_similarity([1.0, 0.0], [7.5, 0.0]) == pytest.approx(1.0)

    def test_known_forty_five_degree_pair(self):
        assert cosine_similarity([1.0, 0.0], [1.0, 1.0]) == pytest.approx(
            math.sqrt(2) / 2
        )

    def test_opposite_vectors_score_minus_one(self):
        assert cosine_similarity([1.0, 2.0], [-1.0, -2.0]) == pytest.approx(-1.0)

    def test_zero_vector_scores_zero_rather_than_dividing_by_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_mismatched_dimensions_are_rejected(self):
        with pytest.raises(ValueError):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])


class TestMaxSimilarity:
    """A probe is scored against the whole anchor set, nearest anchor wins."""

    anchors = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]

    def test_takes_the_nearest_anchor(self):
        assert max_similarity([1.0, 0.0], self.anchors) == pytest.approx(1.0)

    def test_a_probe_between_anchors_takes_the_closer_one(self):
        # 15 degrees off [1, 1] and 30 degrees off [1, 0]: the diagonal wins.
        probe = [math.cos(math.radians(30)), math.sin(math.radians(30))]
        assert max_similarity(probe, self.anchors) == pytest.approx(
            math.cos(math.radians(15))
        )

    def test_no_anchors_scores_zero(self):
        assert max_similarity([1.0, 0.0], []) == 0.0

    def test_a_probe_facing_away_from_every_anchor_scores_below_zero(self):
        assert max_similarity([-1.0, -1.0], [[1.0, 0.0], [0.0, 1.0]]) == pytest.approx(
            -math.sqrt(2) / 2
        )


class TestRefuses:
    """The threshold comparison, fail-closed on the boundary (ADR-014)."""

    def test_a_score_above_the_threshold_is_refused(self):
        assert refuses(0.81, 0.80) is True

    def test_a_score_below_the_threshold_is_admitted(self):
        assert refuses(0.79, 0.80) is False

    def test_a_score_exactly_on_the_threshold_is_refused(self):
        assert refuses(0.80, 0.80) is True

    def test_an_unscoreable_probe_is_refused(self):
        # The gate fails closed: no score means refuse, never admit.
        assert refuses(None, 0.80) is True


class TestPersonalIntentMargin:
    """Two-class scoring: nearest personal anchor minus nearest store anchor.

    Nearest-personal-anchor similarity alone does not separate the Guardrail
    corpus — a store question that shares surface form with a personal anchor
    ("When is the next grocery delivery due?" against "When is my next
    shift?") outscores a genuinely personal probe that shares none. The margin
    against a second, store-scope anchor set is what separates them.
    """

    personal = [[1.0, 0.0]]
    store = [[0.0, 1.0]]

    def test_a_probe_on_the_personal_anchor_scores_a_full_positive_margin(self):
        assert personal_intent_margin([1.0, 0.0], self.personal, self.store) == (
            pytest.approx(1.0)
        )

    def test_a_probe_on_the_store_anchor_scores_a_full_negative_margin(self):
        assert personal_intent_margin([0.0, 1.0], self.personal, self.store) == (
            pytest.approx(-1.0)
        )

    def test_a_probe_equidistant_from_both_scores_zero(self):
        assert personal_intent_margin([1.0, 1.0], self.personal, self.store) == (
            pytest.approx(0.0)
        )

    def test_with_no_store_anchors_it_degrades_to_plain_similarity(self):
        assert personal_intent_margin([1.0, 0.0], self.personal, []) == (
            pytest.approx(max_similarity([1.0, 0.0], self.personal))
        )

    def test_a_probe_near_both_is_pulled_towards_the_nearer_one(self):
        # Closer to the store anchor than the personal one: negative margin,
        # even though its personal similarity is far from zero.
        probe = [math.cos(math.radians(70)), math.sin(math.radians(70))]
        margin = personal_intent_margin(probe, self.personal, self.store)
        assert margin < 0
        assert max_similarity(probe, self.personal) > 0.3

    def test_an_unembeddable_probe_has_no_margin(self):
        assert personal_intent_margin(None, self.personal, self.store) is None
