"""The Identity boundary gate's keyword fast path (issue #14, ADR-014).

The fast path is a pure function over plain data, so it needs no mocks at all.
Its hard requirement is the one that matters on stage: it must never refuse a
store-level question. Missing a personal one is survivable — the similarity
tier is behind it — but a false positive refuses a legitimate store question,
which ADR-014 names as worse than a miss.
"""

import pytest

from guardrail.corpus import NEGATIVE_CONTROLS, POSITIVE_PROBES
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
