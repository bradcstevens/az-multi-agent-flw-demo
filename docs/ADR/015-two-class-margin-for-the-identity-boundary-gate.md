# ADR-015: Score the identity boundary gate's similarity tier as a two-class margin

## Status

Accepted

## Date

2026-08-12

## Issue

#13 (spec #1)

## Context

[ADR-014](./014-deterministic-identity-boundary-gate.md) settled that the **Identity boundary
gate** is deterministic code with a keyword fast path plus an **embedding-similarity tier**, and
that the **Guardrail corpus** measures the threshold against the real embedding deployment before
the number is chosen. It did not say what the similarity tier compares against.

The obvious reading — embed the request, take its similarity to the nearest **personal-intent
anchor**, refuse above a threshold — was built first and scored against the corpus on
`text-embedding-3-small` in the deployed environment. **It does not separate the corpus at any
threshold.** The measured scores:

| | score | probe |
| --- | --- | --- |
| highest negative control | 0.5530 | "When is the next grocery delivery due at Store 223?" |
| | 0.4394 | "Which cleaning checklist runs on the night shift?" |
| lowest positive probe | 0.3606 | "Has the manager approved the holiday request submitted last week?" |
| | 0.3912 | "Total the overtime on the timecard for badge 4417." |

The failure is not noise and not a bad corpus. It is **shared surface form**. "When is the next
grocery delivery due?" is a sentence-for-sentence match on the shape of "When is my next shift?",
and the embedding rewards that shape. Meanwhile the genuinely personal probes that carry no
first-person pronoun — the ones the similarity tier exists to catch, because a keyword fast path
never will — are the *furthest* from the anchors. The two failure modes point in opposite
directions, so no threshold sits between them.

Raising the low positives by adding anchors that paraphrase them would fix the numbers and destroy
the test: the anchors would become near-copies of the probes, and the corpus would measure how well
the anchors were fitted to it rather than whether the tier generalises to the paraphrase the
presenter improvises live.

## Decision

**Score the similarity tier as a two-class margin**: the nearest **personal-intent anchor**'s
cosine similarity *minus* the nearest **store-scope anchor**'s. `STORE_SCOPE_ANCHORS`
(`src/backend/guardrail/corpus.py`) is added as the counterweight, and
`personal_intent_margin` (`src/backend/guardrail/similarity.py`) is the score the threshold
compares against.

Subtracting the store side cancels exactly what broke the one-class score. "When is the next
grocery delivery due at Store 223?" is close to a personal anchor (0.5529) *and* closer still to a
store anchor (0.8104), so its margin is −0.2575. "Has the manager approved the holiday request
submitted last week?" is far from both, but nearer the personal side, so its margin is +0.0721.
Shape cancels; intent survives.

Measured on the same deployment, the corpus then separates cleanly:

- every positive probe scores a **positive** margin, from +0.0720 to +0.4221
- every negative control scores a **negative** margin, from −0.2403 to −0.6230
- the perfect band — 10/10 refused, 0/10 falsely refused — runs from **−0.23 to +0.07**

**The recorded threshold is −0.08**, the band's midpoint at the sweep's own resolution, which puts
0.16 of margin either side. It is deliberately **below zero**: zero would separate this corpus, but
it sits 0.07 from the nearest probe and 0.24 from the nearest control, so an improvised paraphrase
has three times more room to fall the wrong way. A negative threshold is the fail-closed half of
ADR-014 expressed as a number — a request the deployment finds genuinely ambiguous is refused.

## Considered Options

- **Nearest personal anchor only.** Rejected on measurement, not on taste: it does not separate the
  corpus at any threshold, and the sweep that proves it is in the repository.
- **Add anchors that paraphrase the low-scoring probes.** Rejected: it fits the anchors to the
  corpus, so the corpus stops being evidence about anything else. ADR-014 keeps the corpus as the
  acceptance test precisely so it can disagree with the implementation.
- **Drop the awkward probes or soften the controls.** Rejected for the same reason, and worse: the
  pronoun-free probes and the store questions that sound personal are the *only* parts of the corpus
  that exercise the similarity tier at all.
- **A trained classifier over embeddings.** Rejected: needs training data this demo does not have,
  and replaces a threshold anyone can read off a printed sweep with weights nobody can.

## Consequences

- **Positive:** The tier now discriminates on intent rather than sentence shape, which is what
  survives an improvised paraphrase — the live test the audience will run.
- **Positive:** Both anchor sets are plain data and both comparisons are pure functions, so ADR-014's
  "no mocks at all" property is preserved and the sweep is re-runnable on demand.
- **Negative:** The gate embeds against two anchor sets instead of one. The anchors are embedded
  once at startup, not per request, so the per-request cost is unchanged — one embedding call.
- **Negative:** Scores are now margins in roughly ±0.6, not similarities in 0–1, so the threshold
  is not comparable to a cosine value and the sweep band straddles zero. Anyone reading the number
  cold will mis-read it unless it is labelled; hence this ADR.
- **Dependency:** The threshold is measured against `text-embedding-3-small` on the deployed
  environment. Changing the embedding deployment invalidates it, and the integration suite must be
  re-run — the recorded value is asserted to sit inside the measured perfect band, so drift fails
  loudly rather than quietly.

## References

- [ADR-014: The identity boundary gate is deterministic code, not a prompt](./014-deterministic-identity-boundary-gate.md)
- `src/backend/guardrail/corpus.py` — the Guardrail corpus and both anchor sets
- `src/backend/guardrail/similarity.py` — `personal_intent_margin`, `sweep`, `choose_threshold`
- `src/tests/backend/guardrail/test_guardrail_corpus.py` — the live suite that produced the numbers
