# ADR-036: The Simulated badge comes off, and the disclosure stays in the words

## Status

Accepted — amends the **Simulated label** rule in `CONTEXT.md`, which is renamed **Disclosure in
words**

## Date

2026-08-16

## Issue

#92 (spec #2)

## Context

`BRIEF.md` asks for a reversal, in one sentence: *"Remove all the 'simulated-badge' indicators to
make the demo feel more real. If the customer asks questions regarding these simulated-badge items,
the presenter will address them conversationally."*

`CONTEXT.md` has said the opposite since #25. **Simulated label** — *"the badge on anything whose
content was authored for the walkthrough rather than produced by a connected system… The converse
matters as much — a badge on a real Foundry answer, a real Copilot Studio hop or a measured token
count gives away the demo's strongest evidence. Label the invented things, and only those."*

That rule does not stand alone. **Not reported vs measured** (`—` means nobody told us, `0` means we
know it was nothing), [ADR-023](./023-progress-narration-claims-only-what-a-signal-reports.md)
(narration claims only what a signal reports), [ADR-017](./017-workforce-agent-answers-process-never-record.md)
(the **Workforce agent** is named for its function *"because the surface would otherwise claim an
integration that does not exist"*) and the **Workforce procedure library**, *"mocked, and it says so
on every answer"*, are one discipline written down in five places. Reversing any of it in silence
would leave four of the five standing and no record of why the fifth went.

### What is actually on screen

The badge is not in four places. It is in **six**, all unconditional, none driven by a flag on the
wire:

| Call site | Tooltip |
| --- | --- |
| `StoreIdentity.tsx:48` | *Store 223 is simulated for this demonstration.* |
| `StoreIdentity.tsx:54` (when signed in) | *This sign-in is simulated for this demonstration.* |
| `SimulatedTicketCard.tsx:38` | *This service ticket is simulated for this demonstration.* |
| `PersonalAnswerCard.tsx:43` | *This associate record is simulated for this demonstration.* |
| `PresenterAlertCard.tsx:43` | *This shift task is simulated for this demonstration.* |

Four further disclosures are **not** badges and would survive a `SimulatedBadge` deletion untouched:
the ticket card's *"No service desk receives this ticket and no engineer is dispatched."*;
`HomeInput`'s *"Simulated sign-in — no identity provider is involved."*; `PERSONAL_ANSWER_NOTE` in
`src/backend/associate/answer.py:49`, a backend default on every `PersonalAnswer`; and the workforce
library's `SIMULATED` string, appended to every tool answer in
`src/mcp_server/services/workforce_library.py:22`.

So "remove all the simulated-badge indicators" is a narrower instruction than it first reads. It
names the chrome, and the chrome is not where most of the disclosure lives.

### The argument that carried

The brief's complaint is aesthetic, but it lands inside the rule rather than against it.
`CONTEXT.md`'s own converse is that *a badge on a real thing gives away the demo's strongest
evidence* — and six badges in one viewport does exactly that **by proximity**. An audience reading
*Simulated* five times before the first answer arrives has been taught to read the whole surface as
a mock-up, and discounts the real Foundry hop, the real Copilot Studio hop and the measured token
count along with it. Over-labelling was already a failure under the rule as written; it was simply
never counted as one.

### What cuts the other way, and was accepted anyway

- **ADR-023 refused this trade in the opposite direction.** It considered badging the invented
  loading copy and rejected it, because *"a badge on the loading screen spends the demonstration's
  credibility to buy filler."* Removing a badge to buy realism is the same coin.
- **The presenter is not always there.** `docs/stage-driver.md` writes one silent `.webm` per beat as
  the **Recorded fallback**. Nobody speaks over a video, so *"the presenter will address them
  conversationally"* has no purchase on the artefact the walkthrough falls back to.
- **Spec 4 makes a new invented thing**, and a worse one — a named manager approving a shift swap.
  That is handled separately and deliberately, in
  [ADR-037](./037-a-fabricated-human-decision-is-never-indistinguishable-from-a-real-one.md).

## Decision

**The badge comes off every surface. Disclosure stays in the words, where it already exists.**

1. **All six `SimulatedBadge` call sites are removed**, and `SimulatedBadge.tsx` and the
   `SIMULATED_LABEL` constant in `models/storeSurface.ts` are **deleted rather than orphaned**. A
   component that is merely no longer rendered is one import away from returning, which is the
   reasoning `CONTEXT.md` already applies to the deleted team picker under **One assistant**.

2. **Three prose disclosures stay, unchanged**: `HomeInput`'s sign-in line, the ticket card's *"No
   service desk receives this ticket and no engineer is dispatched."*, and the workforce library's
   per-answer `SIMULATED` string. ADR-017 is therefore untouched — the Workforce agent still says on
   every answer that it is mocked, which is the half of ADR-017 that lives on the surface.

3. **`PERSONAL_ANSWER_NOTE` is deleted.** The associate record's pay and PTO figures carry no
   disclosure on screen. `src/backend/associate/records.py` states as a binding module rule that
   *"Everything shown from here carries the **Simulated label**, unconditionally — there is no
   unlabelled path"*; that docstring is rewritten, because the unlabelled path is now the only path.

4. **The Presenter alert carries nothing.** Its only disclosure was the badge. What remains is a card
   headed *Proactive alert*, arriving unbidden, naming a real `SOP-104`.

5. **The Token meter's `—` is the far edge of this reversal and is untouched.** It is not a
   simulation disclaimer; it is a rendering rule for missing data, and making it render `0` would be
   the surface stating a number nobody reported. That is a falsehood, not a removed disclaimer, and
   it is a different kind of thing from everything else in this ADR. **Not reported vs measured**
   stands exactly as written.

6. **The presenter runbook absorbs the two disclosures the screen gives up.** `docs/presenter-runbook.md`
   gains say-out-loud lines for the **Presenter alert** (the shift task is rehearsed) and for the
   **associate record** (the figures are authored), on the pattern beat 6 already uses for the
   sign-in — *"Say it out loud, unprompted. A stakeholder who works this out for themselves afterwards
   stops believing everything else you showed them."* Without this, *"addressed conversationally"* is
   an intention with nothing carrying it; the runbook is the only artefact a presenter reads.

This is the *decision*, not the change. Per #81 this ticket produces ADRs, and the removal itself is
spec 2's implementation work.

## Considered Options

- **Keep every badge; refuse the brief.** Rejected. It overrules the customer's own stated complaint,
  and the complaint is correct: the surface reads as a mock-up, and the rule's converse says that
  costs us the real evidence.
- **Sharpen the rule instead of reversing it** — badge only a claim that a system *outside this demo*
  acted (a ticket raised, an identity verified, a manager approved), and drop it from set dressing
  like the store's name. This was the recommendation put to the decision and it was **not** taken.
  Recorded because it is the option a future reader will think of: it keeps two or three badges, and
  the brief asked for none.
- **Consolidate to one standing disclosure** — no per-card badges, one "About this demo" affordance.
  Rejected: the disclosure stops being adjacent to the thing it disclaims, so a screenshot of the
  ticket carries nothing, and screenshots are how a demo travels after the room empties.
- **Drive the badge from a wire flag** so only some instances render. Rejected on the reasoning
  already recorded in `SimulatedTicketCard.tsx` and in **Simulated ticket** — *a flag that can be
  omitted is a fabricated record that looks real*. The choice is render it always or not at all.

## Consequences

- **Positive:** The surface stops teaching the audience to discount it. The strongest evidence in the
  room — a real Foundry answer, a real Copilot Studio hop, a measured token count — is no longer
  sharing a viewport with five *Simulated* chips.
- **Positive:** One component and one constant leave the codebase, and the six call sites stop being
  six places to disagree about how an invented thing announces itself.
- **Negative — stated plainly, because it is the price:** two surfaces end up disclosed **nowhere on
  screen**. The associate record shows a named person's pay and PTO with nothing marking it, and
  `HomeInput`'s surviving line covers the *sign-in*, one beat earlier, not the *figures*. The
  Presenter alert states a shift task is due with nothing marking it. Both now depend on a presenter
  saying so, and the **Recorded fallback** has no presenter at all.
- **Negative:** six vitest assertions go red by design — `SimulatedTicketCard.test.tsx:65,81`,
  `PersonalAnswerCard.test.tsx:43,57`, `PresenterAlertCard.test.tsx:38` and
  `StoreIdentity.test.tsx:50,68`. They are the guard for the rule being reversed, so they are deleted
  with it rather than weakened.
- **Negative:** `e2e/specs/escalation.spec.ts:107` asserts `ticketSimulatedBadge` is visible, and
  `ChatSurface.ts:149` is the locator behind it. The **Demo validator** runs against a live
  deployment, so this goes red on the first run after the change and must move in the same commit.
- **Negative:** `src/tests/ci/test_presenter_runbook.py::test_the_simulated_sign_in_is_said_out_loud`
  reads the sign-in string **out of `HomeInput.tsx`** and asserts the runbook quotes it. That
  coupling is why the sign-in line is the one prose disclosure that could not have been dropped
  quietly, and it now guards the strongest surviving disclosure. It stays.
- **Negative:** `docs/presenter-runbook.md` lines 137, 177 and 196 each describe a badge that will
  not render. All three become false the moment this ships, and standing rule 2 of #81 requires the
  runbook and the validator to move in the same change as the beat.
- **Neutral:** [ADR-033](./033-a-one-tap-control-never-invents-the-words-it-offers.md) **survives**.
  Its decision is about where a one-tap control's words come from, which this does not touch; only
  its corollary in `CONTEXT.md` — *"The badge labels claims, not controls"* — becomes moot and is
  removed, because there is no badge to place.
- **Neutral:** ADR-023 stands. It names `SimulatedBadge` as a rejected alternative, and a reader will
  find that it references a component that no longer exists; the reasoning it rejected the badge
  *for* is unaffected, and re-adding authored loading copy is still forbidden.
- **Risk accepted:** the failure this rule existed to prevent is now possible. A stakeholder who
  works out unaided that the ticket, the pay figures or the shift alert were authored stops believing
  the parts that were not. The mitigation is a presenter following a runbook, which is a weaker
  guarantee than a rendered string, and this ADR is the record that the weaker guarantee was chosen
  knowingly.

## References

- [ADR-017: The Workforce agent answers HR process, and never an individual's record](./017-workforce-agent-answers-process-never-record.md) — untouched; its per-answer disclosure survives
- [ADR-023: The loading screen claims only what a signal reports](./023-progress-narration-claims-only-what-a-signal-reports.md) — rejected the badge as a licence for fiction
- [ADR-033: A one-tap control never invents the words it offers](./033-a-one-tap-control-never-invents-the-words-it-offers.md) — survives; its badge corollary does not
- [ADR-037: A fabricated human decision is never indistinguishable from a real one](./037-a-fabricated-human-decision-is-never-indistinguishable-from-a-real-one.md) — what spec 4 inherits
- [docs/stage-driver.md](../stage-driver.md) — the **Recorded fallback**, which has no presenter
- [docs/presenter-runbook.md](../presenter-runbook.md)
- `CONTEXT.md` — **Disclosure in words** (formerly **Simulated label**), **Not reported vs measured**, **Simulated ticket**, **Presenter alert**, **Workforce procedure library**
