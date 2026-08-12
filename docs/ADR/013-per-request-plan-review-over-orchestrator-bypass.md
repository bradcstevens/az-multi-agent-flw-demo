# ADR-013: Vary Plan review per request instead of building an orchestrator bypass

## Status

Accepted

## Date

2026-08-12

## Issue

#11 (spec #1)

## Context

The accelerator's core loop is: request → generate plan → user approves plan → agents execute →
consolidated answer. That is right for "onboard Jessica Smith." It is wrong for a store
associate asking "how do I close the store?" — a frontline worker on a shift should not approve
an execution plan to get a procedure, and the round trip is slow. Heavier stock scenarios are
documented at **10–15 minutes**, which is fatal on stage.

Hence the **Fast lane** / **Deliberate lane** split. The question this ADR settles is how the
Fast lane is built.

The superseded requirements document specified: "Fast lane bypasses `MagenticBuilder` and calls
the agent directly through the existing `agent_factory`." **This is not implementable as
written.** There is **no single-agent invocation path** in the accelerator. `agent_factory`
produces the agent pool a **Workflow** is built from; it is not an invocable entry point, and
the request endpoint into the orchestration builder is the only door
([correction 2](../superseded-requirements-corrections.md#2-the-fast-lane-cannot-bypass-the-orchestrator)).

Meanwhile **Plan review** — the approval gate the builder is configured with — is **hardcoded**
as the literal `enable_plan_review=True` at `orchestration_manager.py:193`, with
`test_orchestration_manager.py:350` asserting that literal
([correction 1](../superseded-requirements-corrections.md#1-the-plan-review-flag-is-hardcoded-not-configurable)).

## Decision

**Make Plan review a per-request value and keep the orchestration builder for both lanes.** The
Fast lane is the same path with the approval gate off, not a second path.

Four things follow and are part of this decision, not separate work:

1. **Both the literal and the test asserting it change.** The test is parametrised over both
   values rather than deleted.
2. **The Workflow cache is fixed in the same change.** Workflows are cached by **user
   identifier alone**, and the team-initialisation endpoint **eagerly builds a Workflow before
   any task is submitted**. Without a fix, the first request after a page load reuses that
   Workflow and silently ignores the per-request lane. The fix: record the Plan review value on
   the Workflow at build time and include it in **both** the cache-invalidation predicate and
   the full-rebuild predicate. (See also the confirmed finding in `CONTEXT.md` that `_team_id`
   is never assigned, which makes every request a Full workflow rebuild today.)
3. **Measure the resulting Fast-lane latency before building anything more.** Only build a
   genuine bypass route if the measured number misses the sub-10-second target. **Do not
   pre-emptively build the bypass** — the bypass this ADR declines is the one the superseded
   document described, and the measurement is what would reopen the question.
4. **Lane selection stays a separate component from the Identity boundary gate, deliberately.**
   They have opposite failure modes: the gate **fails closed**, the lane router **fails open to
   the Deliberate lane**. Merging them would force one failure mode onto both.

Lane is **declared as metadata on the Quick Task definition**, with a **keyword fallback** for
free-typed input. The starting-task model upstream carries only identifier, name, prompt,
creation timestamp, creator and logo — **no lane field** — so the schema extends on both the
backend model and the frontend type. **The lane taken is surfaced in the UI as a feature**, not
hidden as an implementation detail.

**Agent attribution survives Plan review being off** — it derives from the executor identifier
on output events, not from the plan. But **the plan object will be null**, so the endpoint that
returns the plan returns null and the Agent Team panel would be empty in the Fast lane.
**Populate that panel from the Workflow's agent roster instead of from the plan.**

## Considered Options

- **A genuine orchestrator bypass, as the superseded document specified.** Rejected because the
  path it names does not exist; building one means inventing a second invocation route through
  the framework, with its own event stream, attribution and error handling, on a demo clock.
- **Run every request through plan approval.** Rejected: it is the mismatch this whole design
  exists to remove.
- **One component that both classifies personal intent and selects the lane.** Rejected on
  failure modes, as above.

## Consequences

- **Positive:** One code path, one event stream, one set of tests. The Deliberate lane's
  approval step stops being ceremony and becomes *"here is the ticket I'm about to raise for
  you — approve it?"*, which is the strongest beat in the demo.
- **Negative:** The Fast lane still pays for orchestration setup, so the sub-10-second target is
  a measurement, not a guarantee. The Workflow cache fix is now on the critical path for the
  lane feature — the two ship together or neither works.
- **Testing:** Lane behaviour is tested through the in-process FastAPI client: a task carrying a
  declared lane reaches the orchestration call with the matching Plan review value, free text
  falls back to keywords, and an unparseable lane **falls open to Deliberate**. Deleting the
  line in the reuse test that hand-sets `_team_id` on the mock Workflow converts an existing
  passing test into a regression test for the cache fix.

## References

- [Corrections 1 and 2](../superseded-requirements-corrections.md)
- `CONTEXT.md` — *Workflow*, *Workflow cache*, *Full workflow rebuild*, *Plan review*, and the
  confirmed finding that the Workflow is not tagged with a team identifier
- [ADR-014: The identity boundary gate is deterministic code, not a prompt](./014-deterministic-identity-boundary-gate.md)
