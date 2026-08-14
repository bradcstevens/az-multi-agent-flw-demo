# ADR-017: The Workforce agent answers HR process, and never an individual's record

## Status

Accepted

## Date

2026-08-13

## Issue

#1 (spec #1)

## Context

The demonstration gains a fourth Foundry participant, `WorkforceAgent`, so that the walkthrough
shows an HR-system interaction of the kind a store associate would otherwise take to a manager or a
Workday portal. Nothing in spec #1 asked for this; it is new scope, added 2026-08-13.

It lands directly on top of a settled decision, and the collision has to be resolved explicitly or
it will be resolved by accident. [ADR-014](./014-deterministic-identity-boundary-gate.md) makes the
**Identity boundary gate** deterministic code rather than a prompt, and
[the Mocked unlock](../mocked-unlock.md) records why the signed-in answer runs **no agent at all**:

> Deciding *which* number a phrasing wants would be a third classifier behind the gate's two, and a
> third classifier can report the wrong number — which, for a claim about somebody's pay, is the
> worst thing this system could say.

That reasoning is about **personal records**. It is not about HR *process*, which no agent
currently handles and which carries none of the same risk: nobody is harmed by an imperfectly
worded explanation of how to swap a shift, and everybody is harmed by a wrong PTO balance stated
confidently on stage.

There is a second constraint, and it is why the beat's wording is a design decision rather than
copy. The gate has a **Keyword fast path** — deterministic, inspectable, and containing `pto`,
`payroll`, `paycheck`, `health benefits`, `open enrollment`, `time off request`, `my shift`,
`my hours` and some forty more terms — and a **similarity tier**, which is a live model call scored
as a two-class margin ([ADR-015](./015-two-class-margin-for-the-identity-boundary-gate.md)). A
process question phrased near the personal probes can be refused **on stage**, by the second tier,
on the run that matters.

## Decision

**`WorkforceAgent` answers HR process questions only. Personal-record questions continue to be the
Identity boundary gate's business and continue to be answered without an agent, from the
Associate record.**

The boundary is drawn in the vocabulary, not in a prompt:

- The agent's tools are a mocked `workforce` MCP domain describing **procedures**. No tool returns
  an individual's balance, rate, hours or entitlement.
- `DOMAIN_ALLOWED_TOOLS["workforce"]` names those tools explicitly. This entry is load-bearing
  twice, as #21 and #22 both found: **a domain with no entry gets no filter**, which lets the
  shared `ask_user` tool reach the agent.
- The beat's question is **"How do I swap a shift with another associate?"** — chosen because it
  is recognisably an HR-system task, trips no keyword, and is semantically about a procedure
  between two people rather than about the asker's own data.
- The agent is named for its **function**, not for Workday. The surface has no Workday integration
  behind it, and this build's governing rule is that a surface may say nothing but may not say
  something that is not so.

## Considered Options

- **Route signed-in personal questions through `WorkforceAgent`.** Rejected. It is the thing
  ADR-014 and the Mocked unlock exist to prevent, it puts a language model in charge of stating an
  associate's pay, and it costs the beat its "the answer costs what the refusal cost" property.
- **Name it `WorkdayAgent`.** Rejected. It reads, on the agent roster and on every plan step, as an
  integration that does not exist. The association is better made out loud by the presenter — *"this
  is where Workday would sit"* — than claimed on screen by software that cannot back it up.
- **"How do I request time off for next Tuesday?" as the beat.** Rejected on gate risk: it is the
  most recognisably-Workday phrasing available and it sits closest to the corpus' positive probes,
  so the similarity tier may refuse it live. The gate fails closed, which on stage is the most
  convincing possible way to look broken.
- **Add no fourth agent.** Genuinely arguable — beats 1–4 already demonstrate orchestration across
  Foundry and Copilot Studio, and this was recommended against the deadline. Overruled deliberately:
  the fourth specialist makes the routing story legible to an audience that has not read the code.

## Consequences

- **Positive:** The demonstration shows four specialists being chosen between, and beat 5 keeps its
  refusal-then-unlock contrast intact and unweakened.
- **Positive:** No language model is ever the thing that states an associate's pay or leave balance.
- **Negative:** A fourth agent is a fourth chance to trip the **Silent agent skip** — an agent whose
  `deployment_name` is absent from the `SUPPORTED_MODELS` allowlist is dropped with a warning and
  the roster simply comes up short. The full roster must be verified after the change.
- **Negative:** The gate's similarity tier is not asserted against the new beat's wording by any
  existing corpus. The **Guardrail corpus** must gain the shift-swap question as a negative control,
  or the beat's safety is an assumption rather than a measurement.
- **Risk accepted:** This is net-new code shipped against a deadline, into a demonstration nothing
  had yet proven live. It is additive and sits behind a Quick Task, so it can be removed by removing
  one card if it misbehaves.

## References

- [ADR-014: The identity boundary gate is deterministic code, not a prompt](./014-deterministic-identity-boundary-gate.md)
- [ADR-015: Score the identity boundary gate's similarity tier as a two-class margin](./015-two-class-margin-for-the-identity-boundary-gate.md)
- [docs/mocked-unlock.md](../mocked-unlock.md) — why the personal answer runs no agent
- `src/backend/guardrail/keywords.py` — the Keyword fast path's terms
- `CONTEXT.md` — **Workforce agent**, **HR process question**, **Silent agent skip**
