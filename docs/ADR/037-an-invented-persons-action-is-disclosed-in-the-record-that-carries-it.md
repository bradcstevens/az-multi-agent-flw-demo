# ADR-037: An invented person's action is disclosed in the record that carries it

## Status

Accepted — sits on
[ADR-036](./036-a-record-carries-its-own-provenance.md) and binds spec 4

## Date

2026-08-16

## Issue

#92 (map #81, spec 2), binding on spec 4

## Context

[ADR-036](./036-a-record-carries-its-own-provenance.md) decides that the surface asserts nothing
about itself and that a record carries its own provenance. Its decision 10 already binds spec 4 and
names the floor: *an invented person's action always discloses its provenance in the record.* This
ADR exists because that clause is doing more work than one clause in a list can carry, and because
spec 4 is the first thing to build on ADR-036 that was not on screen when it was written.

Three things make it worth its own record.

### The claim is a different kind of claim

Every other invented thing ADR-036 governs is a fact about a **store or a record**: a store number,
a ticket id, a PTO figure, a rehearsed reminder. `BRIEF.md` asks spec 4 for something else — *"some
kind of interaction that will simulate another user, in this case, a manager… showcasing some kind
of response back from the manager, such as approved or any other comments, to make it seem more
real and human-like"* — plus peer associates who approve or deny.

What that renders is a **named person**, a **quoted sentence**, and a **decision presented as
having been made**:

> **Marcus Delgado** · Store Manager — **Approved**
> *"Fine by me, thanks for sorting the cover."*

The honest answer to *"did that happen?"* is not *these figures were authored* but *a person you can
name made a decision about this associate's working life, and said words they never said*. It is
also the beat the brief most wants to feel real, which is exactly the beat most likely to be
believed — and the one place where being wrong is a claim about a human being rather than about a
system.

### The disclosure that covers the swap today does not follow it

`docs/presenter-runbook.md`'s beat 8 has the **Workforce agent** *describe* a swap — offering it,
the other associate accepting, the shift lead approving — quoting `WF-401`, with
`workforce_library.py:22`'s `SIMULATED` string attached to the answer and the agent's system message
ordering it to be said. That disclosure attaches to a **description of a procedure**.

Spec 4 turns the same swap into an **enacted transaction**, and nothing in `workforce_library.py` is
in the path when a plan step is marked approved by a manager. The one disclosure that covers this
subject matter today does not travel with it, and ADR-036's own line — *record-borne disclosure
stays* — is silent about a record that does not exist yet.

### The Recorded fallback has no presenter

ADR-036 moves the enumeration into `docs/presenter-runbook.md` as the **Simulation register**. That
is the right place for it and it is CI-pinnable, which is the whole argument. But
`docs/stage-driver.md` writes one **silent `.webm` per beat** as the **Recorded fallback**, and
nobody speaks over a video. A register discharges the disclosure duty only when a presenter is in
the room.

This is not a defect in ADR-036 — it is the strongest argument *for* it. Record-borne disclosure is
in the video frame and in any transcript pasted afterwards, where a spoken sentence is not. But it
means the register cannot be the *only* thing standing between a fabricated approval and an audience,
and spec 4 is the first beat where that gap has consequences.

## Decision

**An invented person's action is disclosed in the record that carries it, and never only in the
runbook.**

- **The disclosure is a Provenance line on the record**, meeting ADR-036's behavioural floor: *a
  reader who does not know this repository's rules can tell, from the line alone, that the content
  was not produced by a connected system.* It names the system that was not consulted, on the
  **Grounding panel**'s mirror-image pattern — the approval was not routed to a workforce management
  system, and the line says so.
- **It is not a badge**, and this ADR does not reintroduce one under another name. `SimulatedBadge`
  and `SIMULATED_LABEL` are deleted by ADR-036 and stay deleted.
- **`Assignee.simulated` (#85) is the flag that drives it.** The field was designed when `simulated`
  meant *render a badge*; ADR-036 leaves it with a new consumer rather than no consumer, and this
  ADR is what obliges spec 4 to wire it. A field that drives nothing is deleted, not retained.
- **The rule binds at the decision, not at the person.** A named peer appearing in a list of
  colleagues is set dressing and needs nothing, on ADR-036's reasoning. The moment that person is
  shown **approving, denying or replying**, the rule binds.
- **Spec 4 cannot decide otherwise without superseding this ADR and ADR-036 together.** Spec 4
  chooses the wording and the treatment; it does not choose whether there is one.

## Considered Options

- **Leave it to ADR-036's decision 10.** The clause is already there, and this ADR would be
  redundant. Rejected on where the clause has to be found: decision 10 of eleven, inside an ADR
  about badges, is not where somebody building a shift-swap approval surface will look. The
  practical test is whether the rule is reachable from the work it governs, and one line in a list
  is not.
- **Rely on the Simulation register alone.** The register is CI-pinned and enumerates every invented
  thing, which is more than the badge ever did. Rejected because of the **Recorded fallback**: a
  register is read by a presenter, and the fallback has none. It is also the wrong shape for this
  case — the register tells the *presenter* what is invented; a Provenance line tells the *audience*,
  at the moment they are looking at the thing.
- **Make the personas obviously fictional by name.** Available to spec 4 as a supporting choice and
  rejected as the mechanism: it degrades the beat the brief is trying to strengthen, and "obviously
  fictional" is a judgement about the audience rather than a property of the record.
- **Reintroduce a badge for this one case.** Rejected. It reverses ADR-036 within a spec of writing
  it, and re-creates the over-labelling failure as soon as a plan carries several approval steps.

## Consequences

- **Positive:** Spec 4 gets its constraint before it has an implementation, which is the cheapest
  moment to have one, and `Assignee.simulated` becomes a requirement rather than a leftover.
- **Positive:** The disclosure survives into the **Recorded fallback** and into a screenshot, which
  is the one property the badge never had and the register cannot supply.
- **Negative:** It constrains the beat the brief most wants unconstrained. Whatever spec 4 writes is
  some concession to visible artifice in the moment designed to feel least artificial.
- **Negative:** The boundary between *a peer in a list* and *a peer approving* has to be drawn in the
  implementation, and it has a real edge: a peer shown as **waiting** to approve is neither, and spec
  4 must say which side it falls on.
- **Negative:** Unlike ADR-036, this rule has no guard until spec 4 builds one. ADR-036's drift-away
  guard — every Provenance line constant in source appears in the register — is the shape that will
  eventually cover it, and it covers this rule only once the constant exists.
- **Risk accepted:** a rule stated one spec ahead of its implementation can be forgotten. The
  mitigation is that `Assignee.simulated` is retained on the strength of it, so the field stands as a
  question to whoever wires the approval surface: what does this render?

## References

- [ADR-036: A record carries its own provenance, and the surface says nothing about itself](./036-a-record-carries-its-own-provenance.md) — the rule this sits on; see its decisions 5, 6 and 10
- [ADR-017: The Workforce agent answers HR process, and never an individual's record](./017-workforce-agent-answers-process-never-record.md) — the per-answer disclosure that covers the swap as a *description* and not as a *transaction*
- [ADR-028: A reviewable plan is earned by a transaction](./028-a-reviewable-plan-is-earned-by-a-transaction.md) — why a shift swap earns a plan at all
- [docs/stage-driver.md](../stage-driver.md) — the **Recorded fallback**, which has no presenter
- #85 — `planApprovalModel.ts`, the `Assignee` union and `waitsOn`, on `prototype/85-plan-approval`
- `CONTEXT.md` — **Provenance line**, **Simulation register**
