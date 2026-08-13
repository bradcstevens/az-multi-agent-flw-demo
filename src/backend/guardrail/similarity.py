"""The Identity boundary gate's similarity tier, as pure functions.

ADR-014 keeps the threshold comparison free of collaborators so it can be
tested with no mocks at all. Nothing in this module performs I/O: embeddings
arrive already computed, from `backend.guardrail.embeddings` in production and
from the Guardrail corpus harness when the threshold is being tuned.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Cosine of the angle between two embedding vectors.

    A zero vector has no direction, so it scores 0.0 rather than raising: the
    gate must never fall over on a degenerate embedding, and 0.0 keeps it
    below any threshold the sweep would choose.
    """
    if len(left) != len(right):
        raise ValueError(
            f"embedding dimensions differ: {len(left)} != {len(right)}"
        )

    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))

    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    return dot / (left_norm * right_norm)


def max_similarity(
    probe: Sequence[float], anchors: Sequence[Sequence[float]]
) -> float:
    """The probe's similarity to its nearest anchor.

    The gate refuses on the *nearest* anchor rather than the mean, because a
    paraphrase of one personal question should not be diluted by the nine
    anchors it has nothing to do with. An empty anchor set scores 0.0.
    """
    if not anchors:
        return 0.0
    return max(cosine_similarity(probe, anchor) for anchor in anchors)


def personal_intent_margin(
    probe: Optional[Sequence[float]],
    personal_anchors: Sequence[Sequence[float]],
    store_anchors: Sequence[Sequence[float]],
) -> Optional[float]:
    """How much more personal than store-level a request looks.

    The nearest personal anchor's similarity minus the nearest store-scope
    anchor's. Measured against the Guardrail corpus (issue #13), similarity to
    the personal anchors *alone* does not separate the corpus at any
    threshold: a store question phrased like a personal one — "When is the
    next grocery delivery due at Store 223?" against "When is my next shift?"
    — scores 0.55, above four probes that genuinely are personal. Subtracting
    the store-side similarity cancels the shared surface form and leaves the
    intent, which does separate.

    An unembeddable probe has no margin at all, and `refuses` turns that None
    into a refusal rather than an admission.
    """
    if probe is None:
        return None
    return max_similarity(probe, personal_anchors) - max_similarity(
        probe, store_anchors
    )


def refuses(score: Optional[float], threshold: float) -> bool:
    """Whether a similarity score trips the Identity boundary gate.

    Fail-closed in both directions ADR-014 names: a score exactly on the
    threshold refuses, and a probe that could not be scored at all — an
    embedding call that raised or timed out, handed here as None — refuses
    too. The gate is modelled on the content-safety check, not on the
    neighbouring team-scope evaluation that fails open.
    """
    if score is None:
        return True
    return score >= threshold


# The Identity boundary gate's similarity threshold, **measured** against the
# Guardrail corpus rather than guessed (issue #13, ADR-014, ADR-015). A
# request is refused when its two-class margin reaches this value.
#
# It is *negative* by design. Zero would already separate the corpus — every
# personal probe scored a positive margin and every store control a negative
# one — but zero sits only 0.07 from the nearest probe and 0.24 from the
# nearest control. The measured perfect band runs from -0.23 to +0.07, and its
# midpoint puts 0.16 of margin either side, so an improvised paraphrase has
# room to drift in both directions. Being below zero is the fail-closed half
# of that: a request the deployment finds genuinely ambiguous is refused.
#
# Re-derive it by running the integration suite in src/tests/backend/guardrail,
# which prints the sweep, the perfect band and the chosen value.
IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD = -0.08

# The band the sweep walks. Scores are two-class margins, not raw cosine
# similarities, so the band straddles zero: a request nearer a store anchor
# than a personal one scores negative. Measured margins over the Guardrail
# corpus run from -0.62 to +0.42, so +/-0.50 brackets everything interesting
# without spending rows on margins no English sentence pair reaches.
SWEEP_FLOOR = -0.50
SWEEP_CEILING = 0.50
SWEEP_STEP = 0.01


@dataclass(frozen=True)
class SweepRow:
    """One threshold's verdict over the whole Guardrail corpus."""

    threshold: float
    refused: int
    positives: int
    false_positives: int
    negatives: int

    @property
    def perfect(self) -> bool:
        """Every positive refused and no negative control refused.

        This is R5's numeric criterion — 10/10 and 0/10 — expressed once so
        the harness and the acceptance test read it the same way.
        """
        return self.refused == self.positives and self.false_positives == 0


def default_thresholds() -> List[float]:
    """The sweep's default band, 0.30 to 0.90 in hundredths."""
    steps = int(round((SWEEP_CEILING - SWEEP_FLOOR) / SWEEP_STEP)) + 1
    return [round(SWEEP_FLOOR + index * SWEEP_STEP, 4) for index in range(steps)]


def sweep(
    positive_scores: Sequence[Optional[float]],
    negative_scores: Sequence[Optional[float]],
    thresholds: Optional[Sequence[float]] = None,
) -> List[SweepRow]:
    """Score the corpus at every candidate threshold, ascending.

    Unscoreable probes (None) are refused, the same fail-closed rule the gate
    itself applies — so a negative control that could not be embedded shows up
    as a false positive rather than quietly vanishing from the numbers.
    """
    candidates = sorted(
        default_thresholds() if thresholds is None else thresholds
    )
    return [
        SweepRow(
            threshold=threshold,
            refused=sum(1 for score in positive_scores if refuses(score, threshold)),
            positives=len(positive_scores),
            false_positives=sum(
                1 for score in negative_scores if refuses(score, threshold)
            ),
            negatives=len(negative_scores),
        )
        for threshold in candidates
    ]


def choose_threshold(
    positive_scores: Sequence[Optional[float]],
    negative_scores: Sequence[Optional[float]],
) -> Optional[float]:
    """The most defensible threshold for a scored corpus, or None.

    The widest separating band's midpoint: it refuses every positive probe and
    admits every negative control with the largest margin either side, which
    is what survives a paraphrase improvised on stage. None means the corpus
    does not separate at any threshold, and no number should be invented for
    it.

    A None positive is refused everywhere and so constrains nothing; a None
    negative is a false positive everywhere and so makes the corpus
    inseparable.
    """
    if any(score is None for score in negative_scores):
        return None

    scoreable_positives = [score for score in positive_scores if score is not None]
    if not scoreable_positives or not negative_scores:
        return None

    lowest_positive = min(scoreable_positives)
    highest_negative = max(negative_scores)
    if highest_negative >= lowest_positive:
        return None

    midpoint = (highest_negative + lowest_positive) / 2
    rounded = round(midpoint, 4)
    if highest_negative < rounded <= lowest_positive:
        return rounded
    return midpoint


def format_sweep(rows: Sequence[SweepRow]) -> str:
    """The sweep as a table a threshold can be read off by eye."""
    lines = [
        "threshold  refused    false positives",
        "---------  ---------  ---------------",
    ]
    for row in rows:
        marker = "  PERFECT" if row.perfect else ""
        lines.append(
            f"{row.threshold:>9.3f}  "
            f"{row.refused}/{row.positives:<7}  "
            f"{row.false_positives}/{row.negatives}{marker}"
        )
    return "\n".join(lines)
