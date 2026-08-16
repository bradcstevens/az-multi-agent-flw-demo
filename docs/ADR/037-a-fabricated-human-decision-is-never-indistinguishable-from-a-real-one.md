# ADR-037: A fabricated human decision is never indistinguishable from a real one

## Status

Accepted — the boundary on
[ADR-036](./036-the-simulated-badge-comes-off-and-the-disclosure-stays-in-the-words.md), binding on
spec 4

## Date

2026-08-16

## Issue

#92 (spec #2), binding on spec 4

## Context

ADR-036 removes every **Simulated** badge from the surface. That decision governs invented
*content*: a store's name, a ticket number, a PTO figure, a rehearsed reminder. Spec 4 introduces
something this build has not had before, and the two are not the same kind of thing.

`BRIEF.md` asks for *"some kind of interaction that will simulate another user, in this case, a
manager of the store where the user is working… showcasing some kind of response back from the
manager, such as approved or any other comments, to make it seem more real and human-like"*, plus
peer associates who approve or deny a swap themselves.

What that renders is a **named person**, a **quoted sentence**, and a **decision presented as having
been made**:

> **Marcus Delgado** · Store Manager — **Approved**
> *"Fine by me, thanks for sorting the cover."*

Every disclosure ADR-036 removed sat on something invented about a store or about a record. This is a
fabricated **human act attributed to a named individual**. The honest answer to *"did that happen?"*
is not *these figures were authored* but *a person you can name did a thing they never did, and said
words they never said*. It is also the beat the brief most wants to feel real, which is precisely
the beat most likely to be believed.

Two facts make this decidable now rather than later.

**The flag already exists.** #85's `planApprovalModel.ts` defines an `Assignee` carrying a closed
`relation` (`associate` | `peer` | `manager`), a `simulated` field, and `waitsOn` ordering. It lives
on `prototype/85-plan-approval` and is unmerged. Under a *"nothing marks it"* reading, `simulated`
would arrive on the wire and render nothing — a flag nobody wired up, which is worse than no flag,
because the next reader assumes it is doing something.

**The disclosure that covers the swap today does not follow it.** The runbook's beat 8 has the
Workforce agent *describe* the swap — offering it, the other associate accepting, the shift lead
approving — quoting `WF-401`, with the library's `SIMULATED` string attached to the answer. That
disclosure attaches to a **description of a procedure**. Spec 4 turns the same swap into an **enacted
transaction**, and the string does not travel with it: nothing in `workforce_library.py` is in the
path when a plan step is marked approved by a manager.

So the surface is about to gain its most believable invented thing at the same moment it loses its
labelling convention, and the two changes are in the same spec group.

## Decision

**A fabricated human decision is never presented as indistinguishable from a real one.**

This is a rule, not a treatment. Spec 4 chooses how it is met; this ADR fixes what it must meet.

- **It is not a badge.** ADR-036 deleted `SimulatedBadge` and the `SIMULATED_LABEL` constant, and
  this rule does not reintroduce them under another name. The distinction is carried by *how the
  persona is presented* — the manager and the peer associates are rendered as demo personas, not as
  actors in a system of record.
- **`Assignee.simulated` is kept, and something must render from it.** A field that drives nothing is
  deleted, not retained; retaining it is the commitment that the treatment reads it. This also makes
  the rule checkable in a pure module rather than asserted about pixels, which is the shape #85
  already chose for `planApprovalModel.ts`.
- **The rule is about the *decision*, not the person.** A named peer appearing in a list of
  colleagues is set dressing and needs nothing, on ADR-036's reasoning. The moment that person is
  shown **approving, denying or replying**, the rule binds.

## Considered Options

- **Nothing at all — let spec 4 inherit ADR-036 whole.** The most consistent option, and rejected on
  its worst case: a fabricated approval by a named manager is the one artefact where an audience
  member could reasonably leave the room believing a human being made a decision. That is a
  different failure from believing a ticket number was real, and it is the one that would embarrass
  a customer conversation rather than merely disappoint it.
- **Make the personas obviously fictional by name** — an unmistakably invented manager. Rejected as
  the load-bearing mechanism: it degrades the beat the brief is trying to strengthen, and "obviously
  fictional" is a judgement about the audience rather than a property of the surface. It is
  available to spec 4 as a *supporting* choice; it is not the rule.
- **Reintroduce the badge for this case only.** Rejected. It reverses ADR-036 within a spec of
  writing it, and it re-creates the over-labelling failure ADR-036 identified as soon as several
  approval steps appear on one plan.
- **Defer the question to spec 4 entirely.** Rejected because #92 asks for it and a deferred question
  is one nobody owns. The rule is cheap to state now and expensive to retrofit after the approval
  surface is built.

## Consequences

- **Positive:** Spec 4 gets a constraint before it has an implementation, which is the cheapest
  moment to have one. `Assignee.simulated` becomes a requirement rather than a leftover.
- **Positive:** The rule survives ADR-036's deletion of the labelling convention, so `CONTEXT.md`'s
  entry is a rewrite rather than a removal, and the discipline stays reachable without finding this
  file.
- **Negative:** It constrains the beat the brief most wants unconstrained. Whatever spec 4 chooses
  will be *some* concession to visible artifice in the moment designed to feel least artificial.
- **Negative:** The line between *a peer in a list* and *a peer approving* has to be drawn in the
  implementation, and it is a real boundary with a real edge case — a peer shown as **waiting** to
  approve is neither, and spec 4 has to say which side it falls on.
- **Negative:** This is a rule with no test behind it until spec 4 builds one, unlike ADR-036's
  consequences, which are visible as red assertions the moment the change lands.
- **Risk accepted:** a rule stated one spec ahead of its implementation can be forgotten. The
  mitigation is that `Assignee.simulated` is retained *on the strength of this rule*, so the field is
  a standing question to whoever wires the approval surface: what does this render?

## References

- [ADR-036: The Simulated badge comes off, and the disclosure stays in the words](./036-the-simulated-badge-comes-off-and-the-disclosure-stays-in-the-words.md) — the reversal this bounds
- [ADR-017: The Workforce agent answers HR process, and never an individual's record](./017-workforce-agent-answers-process-never-record.md) — the per-answer disclosure that covers the swap as a *description* and not as a *transaction*
- [ADR-028: A reviewable plan is earned by a transaction](./028-a-reviewable-plan-is-earned-by-a-transaction.md) — why a shift swap earns a plan at all
- #85 — `planApprovalModel.ts`, the `Assignee` union and `waitsOn`, on `prototype/85-plan-approval`
- `CONTEXT.md` — **Disclosure in words**
