"""The Identity boundary gate's keyword fast path (issue #14, ADR-014).

The fast path is a pure function over plain data, so it needs no mocks at all.
Its hard requirement is the one that matters on stage: it must never refuse a
store-level question. Missing a personal one is survivable — the similarity
tier is behind it — but a false positive refuses a legitimate store question,
which ADR-014 names as worse than a miss.
"""

import pytest

from guardrail.corpus import (
    IMPROVISED_PARAPHRASES,
    NEGATIVE_CONTROLS,
    POSITIVE_PROBES,
)
from guardrail.keywords import matches_personal_keyword


class TestTheHardRequirement:
    @pytest.mark.parametrize("control", NEGATIVE_CONTROLS)
    def test_no_store_level_control_trips_the_fast_path(self, control):
        """0/10 false positives, the half of R5's criterion the fast path owns.

        Five of the controls are phrased in the first person and two brush
        against personal vocabulary ("night shift", "the rota") on purpose, so
        this is not a formality.
        """
        assert matches_personal_keyword(control) is False


class TestTheObviousCases:
    def test_it_catches_most_of_the_personal_probes(self):
        """The fast path exists for the obvious cases, not for all of them.

        Deliberately not asserted at 10/10: a list tuned until it swept the
        corpus would be fitted to the corpus, which is the failure mode
        ADR-015 rejected for the anchors. The similarity tier carries the rest.
        """
        caught = [probe for probe in POSITIVE_PROBES if matches_personal_keyword(probe)]

        assert len(caught) >= 7


class TestWhatTheFastPathDeliberatelyMisses:
    """The precondition that makes the improvised paraphrases evidence.

    Measured on the deployment, the fast path catches all ten positive probes,
    so the Guardrail corpus never reaches the similarity tier *through the
    gate*. The held-out paraphrases are the corpus's replacement for that, and
    they only mean anything if the fast path provably cannot claim them — so
    the miss is asserted here rather than assumed there.
    """

    @pytest.mark.parametrize("paraphrase", IMPROVISED_PARAPHRASES)
    def test_an_improvised_paraphrase_reaches_the_similarity_tier(self, paraphrase):
        assert matches_personal_keyword(paraphrase) is False
