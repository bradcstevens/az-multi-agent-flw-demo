# ADR-034: The Identity boundary gate covers the clarification seam

## Status

Accepted

## Date

2026-08-16

## Issue

#91 (map #81, spec 1)

## Context

[ADR-014](./014-deterministic-identity-boundary-gate.md) made the **Identity boundary gate**
deterministic code rather than a prompt, precisely because a prompt-level defence cannot be pinned
by a test. [ADR-015](./015-two-class-margin-for-the-identity-boundary-gate.md) tuned its similarity
tier. [ADR-017](./017-workforce-agent-answers-process-never-record.md) is the prompt-level half —
the **Workforce agent** answers HR process and never an individual's record.

Grilling #91 established that the deterministic half **is not present on the clarification seam.**

`identity_boundary_gate` is imported once in `src/backend/api/router.py` (line 24) and called once
(line 347), inside `process_request`:

```python
if session_state is not None and input_task.session_id:      # 343
    identity = await session_state.resolve_identity(input_task.session_id)
else:
    identity = ANONYMOUS
verdict = await identity_boundary_gate().evaluate(           # 347
    input_task.description, identity
)
if verdict.refused:
    raise HTTPException(status_code=403, detail=policy_block_detail())
```

The call sits above every branch — a cold home-grid tap and a turn carrying an existing
`session_id` are gated identically, and `session_id` only decides which identity the gate evaluates
against. There is no bypass on that path.

The clarification handler (`router.py:1094` onward) **never calls it.** So anything submitted as an
answer to a **Clarification** reaches the orchestration ungated:

> *"actually, while you're there, how much PTO do I have?"*

typed into the box while `TroubleshootingAgent` waits on *"what have you tried?"* goes straight
through. This is not specific to the **Rehearsed reply** chips — a **typed** answer is equally
ungated, and always has been.

`src/tests/ci/test_store_pack.py`'s
`test_given_the_rehearsed_replies_when_read_then_none_of_them_trips_the_gate` asserts
`not matches_personal_keyword(reply)` over the three authored strings. It reads like a duplicate of
a runtime check. It is not: it is **standing in for one that does not exist**, and it covers only
what was authored.

[ADR-033](./033-a-one-tap-control-never-invents-the-words-it-offers.md) is what forces the decision.
It makes suggested turns **Quick Tasks** posting to `/v4/process_request` — where the gate *is* —
while the chips one slot above post to `/v4/user_clarification` — where it is not. The same
authored-string assertion would then mean *"the gate will refuse this on stage"* for one control and
*"nothing will notice"* for the control directly above it.

The complication is what a refusal lands in. Per
[#87](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/87), an unanswered
clarification times out at **300 seconds**, is auto-approved with the synthetic answer *"No response
received from user (timeout)."*, and the workflow resumes — and `_remember_attempted_steps` runs on
that placeholder. A naive 403 on the answer is fail-**closed** into a path that fails **open**: the
orchestration keeps waiting and then resumes on a lie.

## Decision

**`/v4/user_clarification` evaluates the Identity boundary gate, and a refusal leaves the question
still askable.**

1. **The gate runs on the answer**, against the identity resolved for that plan's session, as
   `process_request` already does.

2. **A refusal returns the Policy block**, rendered as `CONTEXT.md`'s **Policy block** already is —
   distinctly from an error, because it is a boundary being drawn rather than something breaking.

3. **The clarification stays pending and the message box stays open.** The refusal is not a verdict
   on the turn; it is a refusal of *those words*. `turnModeFor` therefore still reports
   `'clarification'`, the placeholder still invites an answer, and the associate answers again.
   This is what keeps the refusal out of #87's timeout: nothing is consumed, so nothing resumes on
   the synthetic answer.

4. **The fourth asserted property becomes one sentence that is true everywhere.** *"None may trip
   the **Identity boundary gate**"* now describes a runtime check on both seams, which is what lets
   ADR-033's tier 1 state it once for every one-tap control rather than twice with two meanings.

5. **A typed answer is covered for the first time.** This is the larger half of the decision, and
   the reason it is not merely a consequence of ADR-033: the associate types on this surface far
   more often than the presenter taps, and the authored strings were the only thing anybody was
   checking.

## Considered Options

- **Leave the hole and document the split.** Cheapest; changes no code. Rejected because it leaves
  a typed clarification answer permanently ungated and leaves the two adjacent controls asserting
  the same property with two different meanings.
- **Gate it plainly with a 403 and let the existing timeout handle the consequence.** Honest about
  the boundary, dishonest about what happens next: the orchestration waits 300 seconds and resumes
  on *"No response received from user (timeout)."*, having been told the tool succeeded — after
  which, per #87, the manager asks the question again. Rejected on decision 3.
- **Defer it to its own ticket, outside #91.** The disciplined option, and it was put explicitly.
  Rejected because ADR-033 is what makes the split load-bearing, so the two decisions are only
  reviewable together — but the *implementation* still lands in the request path rather than on the
  chat surface, which is why this is a separate ADR and not a decision inside ADR-033.

## Consequences

- **Positive.** ADR-014's deterministic gate covers both routes an associate's words can take into
  the orchestration. The boundary the walkthrough's beat 5 draws in front of the room is no longer
  reachable around.
- **Negative — this is a request-path change, not a chat-surface one.** It touches
  `src/backend/api/router.py` and the clarification response contract, so it lands in a different
  part of spec 1 than the chips do and carries the deploy cost of ADR-020 like any backend change.
- **Negative — a new refusal state on a seam that had none.** The clarification path currently has
  exactly two outcomes: answered, or timed out. This adds *refused and still pending*, which the
  frontend must render without closing the box — and `CONTEXT.md` already records that *answering
  one settles it, by name, against the `request_id`*, so the refusal must be careful to settle
  **nothing**.
- **The gate's corpus is the acceptance test.** `src/backend/guardrail/` and the **Guardrail
  corpus**'s `POSITIVE_PROBES` and `NEGATIVE_CONTROLS` already measure this gate, and that suite is
  `-m integration` and deselected from unattended runs. Extending the gate to a second seam does
  not change what the corpus measures, but the seam itself needs assertions in the backend loop —
  a refused clarification answer leaves the request pending, and does not consume it.
- **#87 is unblocked in one respect and untouched in another.** The timeout still fails open on the
  synthetic answer; this decision only ensures a refusal does not *become* a timeout.

## References

- [ADR-014: The identity boundary gate is deterministic code, not a prompt](./014-deterministic-identity-boundary-gate.md)
- [ADR-015: Score the identity boundary gate's similarity tier as a two-class margin](./015-two-class-margin-for-the-identity-boundary-gate.md)
- [ADR-017: The Workforce agent answers HR process, and never an individual's record](./017-workforce-agent-answers-process-never-record.md)
- [ADR-033: A one-tap control never invents the words it offers](./033-a-one-tap-control-never-invents-the-words-it-offers.md)
- `CONTEXT.md` — **Identity boundary gate**, **Policy block**, **Clarification**, **Rehearsed
  reply**, **Mocked unlock**
- [#87](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/87) — the 300-second
  clarification timeout, its synthetic answer, and why a refusal must not land in it
