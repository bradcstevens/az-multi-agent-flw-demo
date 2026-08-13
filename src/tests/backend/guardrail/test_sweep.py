"""The Guardrail corpus's threshold sweep, as pure arithmetic.

The corpus is simultaneously R5's acceptance test and the tuning harness for
the Identity boundary gate's similarity threshold (ADR-014), so the sweep has
to be readable without a live embedding deployment. These tests hand it
already-scored probes.
"""

import pytest

from backend.guardrail.similarity import (
    IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD,
    choose_threshold,
    format_sweep,
    sweep,
)

# Cleanly separated: every positive scores above every negative.
SEPARATED_POSITIVES = [0.90, 0.85, 0.80]
SEPARATED_NEGATIVES = [0.50, 0.40, 0.30]


class TestSweep:
    def test_a_row_per_requested_threshold_in_ascending_order(self):
        rows = sweep(SEPARATED_POSITIVES, SEPARATED_NEGATIVES, [0.80, 0.40, 0.60])
        assert [row.threshold for row in rows] == [0.40, 0.60, 0.80]

    def test_counts_positives_refused_and_negatives_falsely_refused(self):
        (row,) = sweep(SEPARATED_POSITIVES, SEPARATED_NEGATIVES, [0.45])
        assert (row.refused, row.false_positives) == (3, 1)

    def test_a_threshold_below_every_score_refuses_everything(self):
        (row,) = sweep(SEPARATED_POSITIVES, SEPARATED_NEGATIVES, [0.10])
        assert (row.refused, row.false_positives) == (3, 3)

    def test_a_threshold_above_every_score_refuses_nothing(self):
        (row,) = sweep(SEPARATED_POSITIVES, SEPARATED_NEGATIVES, [0.99])
        assert (row.refused, row.false_positives) == (0, 0)

    def test_a_row_is_perfect_only_at_ten_out_of_ten_and_zero_false_positives(self):
        rows = {row.threshold: row for row in
                sweep(SEPARATED_POSITIVES, SEPARATED_NEGATIVES, [0.45, 0.80, 0.99])}
        assert rows[0.80].perfect is True
        assert rows[0.45].perfect is False
        assert rows[0.99].perfect is False

    def test_the_default_range_walks_the_plausible_margin_band(self):
        # Scores are two-class margins, so the band straddles zero: a request
        # can be nearer a store anchor than a personal one.
        rows = sweep(SEPARATED_POSITIVES, SEPARATED_NEGATIVES)
        assert rows[0].threshold == pytest.approx(-0.50)
        assert rows[-1].threshold == pytest.approx(0.50)
        assert len(rows) == 101

    def test_the_default_range_covers_the_measured_threshold(self):
        # A sweep that could not report the threshold the gate actually uses
        # would be unable to re-derive it.
        thresholds = [row.threshold for row in sweep([0.1], [-0.1])]
        assert min(thresholds) <= IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD
        assert IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD <= max(thresholds)

    def test_an_unscoreable_probe_counts_as_refused(self):
        # Fail-closed all the way through the harness: a positive that could
        # not be embedded is still refused, and a negative that could not be
        # embedded is a false positive the sweep must not hide.
        (row,) = sweep([None], [None], [0.80])
        assert (row.refused, row.false_positives) == (1, 1)


class TestChooseThreshold:
    def test_picks_the_midpoint_of_the_separating_band(self):
        assert choose_threshold(SEPARATED_POSITIVES, SEPARATED_NEGATIVES) == (
            pytest.approx(0.65)
        )

    def test_returns_none_when_no_threshold_separates_the_corpus(self):
        assert choose_threshold([0.40, 0.90], [0.30, 0.60]) is None

    def test_a_narrow_band_still_yields_a_threshold_that_separates(self):
        chosen = choose_threshold([0.7009], [0.7001])
        assert chosen is not None
        assert 0.7001 < chosen <= 0.7009

    def test_an_unscoreable_positive_does_not_prevent_a_choice(self):
        # A None positive is refused at every threshold, so it constrains
        # nothing; a None negative is a false positive at every threshold and
        # must therefore make the corpus inseparable.
        assert choose_threshold([None] + SEPARATED_POSITIVES, SEPARATED_NEGATIVES) == (
            pytest.approx(0.65)
        )
        assert choose_threshold(SEPARATED_POSITIVES, [None]) is None


class TestFormatSweep:
    def test_renders_a_row_per_threshold_with_both_counts(self):
        report = format_sweep(sweep(SEPARATED_POSITIVES, SEPARATED_NEGATIVES, [0.65]))
        assert "0.650" in report
        assert "3/3" in report
        assert "0/3" in report

    def test_marks_the_perfect_rows_so_a_threshold_can_be_read_off(self):
        report = format_sweep(
            sweep(SEPARATED_POSITIVES, SEPARATED_NEGATIVES, [0.45, 0.65])
        )
        perfect_rows = [line for line in report.splitlines() if line.endswith("PERFECT")]
        assert len(perfect_rows) == 1
        assert "0.650" in perfect_rows[0]
