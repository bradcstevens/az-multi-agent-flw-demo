# ADR-014: The identity boundary gate is deterministic code, not a prompt

## Status

Accepted

## Date

2026-08-12

## Issue

#11 (spec #1)

## Context

R5 — refusing personal, individual-identity questions from a shared store device — is the
**centerpiece** of this demo. It is the requirement the stalled architecture decision actually
turns on, and it is the one the audience will attack live.

The accelerator's nearest equivalent is the **team scope policy** in
`src/backend/orchestration/plan_review_helpers.py` (`get_magentic_prompt_kwargs()`), which
routes out-of-scope requests to a single manager step. It is **prompt-based**, and it **fails
open in two places**.

A prompt-based guardrail can be talked around live. That is precisely what will be attempted,
and a single successful jailbreak in front of the stakeholders costs more than the demo.

Two pre-orchestration hooks already exist upstream — a content-safety gate and the team-scope
evaluation — which establish both the insertion point and the surrounding shape. The
content-safety check is also the repo's one **fail-closed** precedent: it returns false on
exception.

## Decision

**The identity boundary gate is deterministic code in the request path, executed before the
lane router and before orchestration.** Not a system message, and not the accelerator's
prompt-based team-scope evaluation.

- **Hybrid classifier**: a keyword fast-path for the obvious cases, plus an
  **embedding-similarity tier** for paraphrases. The presenter will be asked to improvise a
  paraphrase live, which a keyword list alone cannot survive. This is why
  `text-embedding-3-small` is added to the model deployments and **must land in the first
  deployment** — the accelerator ships no embedding model at all, and adding one later is a
  second infrastructure round trip. It is deployed by the **vanilla** flavour only
  (`infra/bicep/main.bicep:226`); `infra/main.bicep` does not forward `embeddingModelName` to
  the AVM path, so **an AVM deployment has no embedding model and the similarity tier cannot
  run there.**
- **Fails closed.** If the embedding call errors or times out, the request is **refused**, not
  admitted. Model it on the content-safety check, **not** on the neighbouring team-scope gate,
  which fails open.
- **Identity-aware.** The same classifier is the mechanism behind R9: pre-sign-in it refuses;
  post-"sign-in" it admits and returns the mocked personal answer. **R9 is a parameter of this
  gate, not a second gate.**
- **On a match the request short-circuits**: no agent invoked, no plan generated, no tokens
  spent. This is what makes R7's claim that the guardrail costs nothing literally true and
  demonstrable — and the test asserts the **non-call**, because "no agent ran" is the actual
  requirement.
- **The refusal is a fixed, well-written string**: explains store scoping and the absence of
  individual identity, deflects to a manager or an HR number, does not over-apologise, does not
  read as an error.
- **The UI distinguishes a policy block from a retrieval miss.** They are different events and
  must look different; conflating them turns a governed refusal into an apparent bug.

**The guardrail corpus is the acceptance test and the tuning harness, and it runs against the
real embedding deployment.** R5's criterion is numeric — 10/10 on personal probes, 0/10 false
positives on store-level controls — and a mocked embedder would only prove plumbing. It carries
the `integration` marker the repo already declares and is deselected in CI. **It must exist
before the similarity threshold is chosen, not after.**

Keep the keyword fast-path and the threshold comparison as **pure functions**, so they need no
mocks at all.

## Considered Options

- **Extend the accelerator's team-scope prompt.** Rejected: prompt-based, fails open twice, and
  talk-around-able — the exact three properties the centerpiece cannot have.
- **Keyword list only.** Rejected: cannot survive an improvised paraphrase, which is the live
  test the audience will run.
- **Embedding similarity only.** Rejected: pays an embedding round trip on every request
  including the obvious ones, and has no behaviour to fall back on when the embedding call
  fails.
- **Fold the gate into the lane router.** Rejected — opposite failure modes; see
  [ADR-013](./013-per-request-plan-review-over-orchestrator-bypass.md).

## Consequences

- **Positive:** The refusal is reproducible and explainable — deterministic code with a test
  that proves no agent ran. The governance claim becomes demonstrable rather than asserted.
- **Negative:** A false positive refuses a legitimate store question, which is worse on stage
  than a miss. The threshold is therefore tuned against the corpus, and the corpus must contain
  the negative controls, not just the probes.
- **Dependency:** The embedding deployment is on the critical path for the centerpiece. It is
  available at quota Tier 0, so it cannot itself be the quota blocker.
- **Build order:** The gate is built **before any rebranding** — if the centerpiece is not
  convincing, the rest is decoration.

## References

- [ADR-013: Vary Plan review per request instead of building an orchestrator bypass](./013-per-request-plan-review-over-orchestrator-bypass.md)
- `src/backend/orchestration/plan_review_helpers.py` — the prompt-based gate this decision
  declines to build on
