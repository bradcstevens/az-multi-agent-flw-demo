# ADR-036: A record carries its own provenance, and the surface says nothing about itself

## Status

Accepted — retires `CONTEXT.md`'s **Simulated label**

## Date

2026-08-16

## Issue

#92 (map #81, spec 2)

## Context

`BRIEF.md`:

> Remove all the "simulated-badge" indicators to make the demo feel more real. If the customer asks
> questions regarding these simulated-badge items, the presenter will address them conversationally.

Against that, `CONTEXT.md`'s **Simulated label**:

> the badge on anything whose content was authored for the walkthrough rather than produced by a
> connected system … The converse matters as much — a badge on a real Foundry answer, a real
> Copilot Studio hop or a measured token count gives away the demo's strongest evidence. Label the
> invented things, and only those.

That is a recorded rule, and #81's standing rule 1 is that a truthfulness reversal is superseded in
the open or left alone. It is also not an isolated rule: **Not reported vs measured**
(`—` means nobody told us, `0` means we know it was nothing), [ADR-023](./023-progress-narration-claims-only-what-a-signal-reports.md),
[ADR-017](./017-workforce-agent-answers-process-never-record.md) and the **Workforce procedure
library**'s per-answer disclaimer are the same discipline in five places.

### What the badge is actually for

The entry gives two reasons in two sentences and they are not the same reason. One is a **disclosure
duty** — nobody in the room should be misled — and a *person* can discharge that, which is what the
brief proposes. The other is **evidential contrast**: absence of a badge is what makes the Foundry
answer, the Copilot Studio hop and the measured token counts credible as real. *"The converse
matters as much"* is a sentence about evidence, not about disclosure, so contrast is the reason
actually written down, and no presenter can substitute for it — saying *"that part is simulated,
the rest is real"* out loud is exactly what a vendor with **no** real integration would also say.

That contrast is not folklore. `docs/presenter-runbook.md:287-289` states the rule to the audience:

> *"Is that a real ticket?"* No — it is marked *Simulated* on the card. Nothing here writes to a
> service desk. **Everything invented carries that badge, and nothing that is real does: the Copilot
> Studio hop, the token counts and the model assignments are not badged, because they are measured.**

**That passage is pinned by no test.** `src/tests/ci/test_presenter_runbook.py` holds nineteen
properties and none of them is this one.

### What is actually on the surface

Eight findings from the inventory, each of which moved the decision.

1. **There are five badge renders, not the four the issue names.** `StoreIdentity` renders two —
   `<SimulatedBadge what="Store 223" />` (`StoreIdentity.tsx:47`) and, after the mocked sign-in,
   `<SimulatedBadge what="This sign-in" />` (`:53`) — alongside `SimulatedTicketCard.tsx:41`,
   `PersonalAnswerCard.tsx:47` and `PresenterAlertCard.tsx:41`. All five resolve to one component,
   `components/branding/SimulatedBadge.tsx`, over one constant, `SIMULATED_LABEL = 'Simulated'`
   (`models/storeSurface.ts:41`).

2. **Every one is unconditional, deliberately.** `SimulatedTicketCard.tsx`: *"The badge is
   unconditional and carries no flag from the wire. Every ticket this assistant raises is
   simulated … so a flag would only ever be one omission away from an unbadged ticket."*

3. **The badge is the *quietest* disclosure on the surface, not the loudest.** In descending
   volume: `PERSONAL_ANSWER_NOTE` — a paragraph reading *"Simulated associate record, authored for
   this walkthrough. No identity provider signed you in and no payroll system was queried — the
   sign-in and these figures are both mocked."* (`associate/answer.py:49`, rendered unconditionally);
   the ticket card's JSX sentence *"No service desk receives this ticket and no engineer is
   dispatched."* (`SimulatedTicketCard.tsx:47`); `HomeInput`'s *"Simulated sign-in — no identity
   provider is involved."*; `SIM-223-0007`, rendered at `SimulatedTicketCard.tsx:34`; the workforce
   library's `SIMULATED` string appended to **every** procedure (`workforce_library.py:22`) and the
   `WorkforceAgent` system message ordering the model to say it. **Removing the chip alone would
   change nothing an audience perceives.**

4. **One badge is chrome, not a label.** `StoreIdentity`'s store badge is the only mark on screen
   100% of the time. It does not label a claim; it **frames the whole application**, including the
   real token meter beneath it — the converse failure achieved by placement rather than by
   mislabelling, and the likeliest thing the brief is reacting to.

5. **`SIMULATED_NOTICE` never reaches the browser.** `escalation/ticket.py:34` is used once, at
   `:223`, in a server-side text rendering. It is not in `FIELD_ORDER`, not in the wire payload, and
   not on the card. The card's similar sentence is a **separate hardcoded JSX literal**.

6. **The ticket id is disclosure that travels with the artefact.** `TICKET_ID_PREFIX = "SIM-223-"`
   (`ticket.py:28`) is pinned three times — `test_ticket.py:183`, `test_ticket_store.py:239`, and
   `e2e/authored.ts:213`, which reads the constant *out of the Python source* to build
   `ticketNumberPattern()` rather than duplicating the literal. It survives into a screenshot, which
   a badge in a recording does not.

7. **The badge was also an index.** `grep SimulatedBadge` was the repository's own enumeration of
   what it invented — one component, five call sites, complete by construction. Deleting it leaves
   **nothing in the repo that knows what the invented things are**, at the exact moment spec 4 is
   about to add two more and spec 2 one more.

8. **A worse honesty problem is already on screen and this change promotes it.**
   `ticket.py:21` still holds `SITE = "Brightpath Convenience Store 223"`, and the card renders
   every field in `ticket.fields` without filtering, so a **different company's name** is a row on
   the ticket. It is also in all four agent `system_message`s and seven content-pack documents,
   surviving [ADR-019](./019-rebrand-the-sop-corpus-to-circle-k.md). *Simulated* was at least a
   deliberate marker; *Brightpath* reads as *"they built this for someone else and swapped the
   logo"*, and once the badge is gone it is the loudest thing on the card telling the audience this
   is not real.

## Decision

**The surface asserts nothing about itself; a record carries its own provenance.**

The contrast the old rule protected is not abandoned, it is inverted and strengthened: **the real
things show receipts, and the invented ones have none.** The meter's measured counts, the model
assignments, the **Grounding panel**'s named sources and the Copilot Studio hop are evidence a
fabrication cannot produce. *Store 223* has no receipt. `SIM-223-0007` links to no service desk.
Absence of evidence is a better contrast than presence of a label, because it cannot be applied to
something that has not earned it.

Eleven things follow, and they are part of this decision rather than separate work.

1. **All five badge renders are removed.** `SimulatedBadge.tsx` and `SIMULATED_LABEL` are deleted,
   not left unused.

2. **Surface-authored prose goes with them.** The ticket card's JSX sentence and `HomeInput`'s
   *"Simulated sign-in — no identity provider is involved."* are the surface talking about itself in
   words a component author wrote, which is the same act as the badge in a different font.

3. **Record-borne disclosure stays.** `SIM-223-`, `SIMULATED_NOTICE`, and the workforce library's
   per-answer line together with its system-message clause. These are authored where the content is
   authored, they travel with the artefact into a screenshot or a transcript, and they are what let
   the presenter's conversational answer be **checked** rather than merely believed. **ADR-017 is
   therefore not amended.**

4. **The line between 2 and 3 is where the string is authored, not how loud it is.** Prose written
   in a component is the surface asserting something about itself. Prose written in the record is
   the record declaring its own origin. That is one rule rather than a list of judgements about
   cards, and it decides cases nobody has thought of yet.

5. **A record's provenance is stated as a Provenance line, which names the system that was not
   consulted.** The **Grounding panel** names the document that answered; a Provenance line is its
   mirror image — *"No payroll system was queried — these figures were authored for this
   walkthrough."* It states a checkable fact about the world instead of a confession about itself,
   and it reads as the surface being precise rather than apologetic.

6. **The floor on a Provenance line is behavioural, not lexical.** *A reader who does not know this
   repository's rules can tell, from the line alone, that the content was not produced by a
   connected system.* Vocabulary below that is free, and the words *simulated* and *mocked* are not
   required. The floor exists because there is a euphemism gradient — *"Authored for this
   demonstration"* → *"Demonstration content"* → *"Source: internal"* — and a line that looks like
   disclosure without disclosing is worse than no line, since it converts an omission into a claim
   of having told them. Spec 2 writes the final words; this ADR fixes the floor and one example.

7. **Two records carry one today**: the associate record (`PERSONAL_ANSWER_NOTE`, rewritten) and
   the rehearsed **Presenter alert**, which has no artefact-borne disclosure at all and would
   otherwise be the one invented thing on the surface with nothing — an unattributed operational
   alert that reads exactly as though a shift-task system pushed it.

8. **The token meter's `—` is categorically out of reach, now and later.** It does not disclose
   that something is invented; it refuses to state a number nobody reported. Removing it would
   replace an honest omission with a **fabricated measurement**, in the one panel the record
   repeatedly calls the demo's strongest evidence, and it would destroy **Not reported vs measured**
   — after which the guardrail row's real `0` and an unreported cost would look identical. Nothing
   in this decision reaches it.

9. **Disclosure moves into the presenter's script, which is the one artefact already held to
   string-for-string CI.** `docs/presenter-runbook.md` gains a **Simulation register** enumerating
   every invented thing, and its Q&A at lines 287-289 is rewritten in the same change — every clause
   of it becomes false the moment the badges go. The replacement answer is better than the one it
   replaces: *"No — look at the ticket number, `SIM-223-0007`."* This is what makes *"the presenter
   will address them conversationally"* a property of the repository rather than of somebody's
   memory: the presenter can only address *them* if somebody wrote down what *them* is.

10. **Spec 4 is bound, and an invented person's action has a named floor.** The rule covers the
    simulated manager — an approval is a record, and records carry provenance — but *"a person did
    this"* is the strongest claim this system will ever make, and it is qualitatively past a store
    number or a ticket id: it asserts that a human being made a decision about the associate's
    working life, after a realistic pause, in a human-sounding voice the brief asks to be *"more
    real and human-like"*. **An invented person's action always discloses its provenance in the
    record, and spec 4 cannot decide otherwise without superseding this ADR.** The manager may be
    named. `Assignee.simulated` (#85) drives the Provenance line and **never** a badge — the flag was
    designed when `simulated` meant *render a badge*, and this decision leaves it with a new
    consumer rather than no consumer.

11. **Two guards replace the seven deleted assertions.** Removing the badges deletes four frontend
    cases, `escalation.spec.ts:107`, and `test_the_simulated_sign_in_is_said_out_loud`. **Drift
    back** — the surface renders no simulation badge anywhere — is cheap and guards the exact mistake
    spec 4 is set up to make. **Drift away** — every Provenance line constant in source appears in
    the runbook's Simulation register — is the cost of decision 9 and must not be paid on faith: on
    the surface an unbadged card was visible to anyone looking, but an omission from a runbook is
    invisible until somebody asks on stage. The register guard is a **conversion** of
    `test_the_simulated_sign_in_is_said_out_loud`, which already reads a literal out of `HomeInput.tsx`
    and asserts it appears in the runbook; running that shape in reverse means a new invented thing
    carrying a Provenance line cannot ship without forcing a runbook edit. The browser check swaps
    from `ticketSimulatedBadge` to `ticketNumberPattern()`, which `e2e/authored.ts` already builds —
    asserting the disclosure that survived instead of the one that went.

**`CONTEXT.md`'s Simulated label is retired**, not amended. Its rule is reversed rather than
refined, and a glossary entry naming a component that no longer exists is a defect in the glossary:
the cheapest way for a future reader to reconcile *"Label the invented things, and only those"* with
an empty `grep` is to **put the badge back**. Its surviving half — the converse, which nothing here
reverses — is carried into **Provenance line**, and `_Avoid_: simulated badge, simulated label` stops
the deleted device walking back in under its old name.

**The Brightpath leak is decided here and shipped separately.** Removing the badges is what promotes
it from cosmetic to load-bearing, so the reasoning belongs to this ADR; the work — `SITE`, four
system messages, seven content-pack documents — is its own issue under spec 2, ordered **before**
the badge removal ships, so the surface is never in a state where the most conspicuous fake thing on
it is another company's name.

## Considered Options

- **Keep all five badges; change only the word or the volume.** The honest conservative option, and
  it is what the evidential-contrast argument alone would recommend. Rejected: it does not answer
  the brief at all, and finding 4 shows one of the five is doing active harm no rewording fixes.

- **Take the badge off the chrome, keep it on claims** — *Store 223* and the sign-in chip go,
  because a store number is the stage a demo is set on rather than an assertion about a connected
  system, and nobody badges *Contoso*. This was recommended and rejected. It is a real position and
  the next reader will propose it again: it concedes the brief's actual complaint at almost no cost,
  and it needs no register, no floor and no guard. It was overruled deliberately, because *almost no
  cost* also means almost no benefit — the ticket, the associate record and the alert are where the
  audience spends its attention, and leaving three of five badges is a demo that still wears
  *Simulated* wherever anyone is looking.

- **Strip every badge and replace them with one legend or About panel.** Rejected: it is the badge
  with an extra click, it is read by nobody on stage, and it re-creates the index problem in a place
  with no CI harness — where the runbook already has nineteen pinned properties.

- **Invert to positive marks: badge the *real* things** *live*, *measured*, *grounded*. Genuinely
  attractive, and it satisfies both halves of the issue's question 4. Rejected because it is already
  built and better: the meter's counts, the model assignments and the Grounding panel's sources
  **are** those marks, earned rather than asserted, and a *measured* chip beside a real number is a
  label competing with the evidence underneath it. Decision 5 keeps the inversion and drops the
  chip.

- **Replace `SIM-223-0007` with a plausible incident number.** Rejected, and the rejection is the
  sharpest line in this ADR. Deleting a badge is *withholding* a disclosure; minting `INC-0004821`
  is **manufacturing a forged artefact** — a different act, one the presenter then has to un-say
  when asked, and one that survives into every screenshot. There is no neutral third option: the id
  either announces itself or impersonates a real one.

- **Strip the workforce library's per-answer line and the system-message clause that requires it.**
  Rejected on decision 3. It would amend ADR-017 for no gain the audience perceives, it is the one
  disclosure that holds when the *model* is the thing that might overclaim, and **spec 5 is going to
  put agent system prompts on screen** — so the clause becomes audience-visible evidence of the
  discipline rather than a cost.

- **Remove the token meter's `—`.** Rejected categorically, and fenced off in decision 8 so the
  question is not reopened by someone reading only this ADR's title.

- **Leave `PERSONAL_ANSWER_NOTE` verbatim** on the grounds that it is record-authored and decision 4
  already saves it. Correct on the rule and rejected on the outcome: keeping a paragraph reading
  *"Simulated … mocked"* while deleting a small chip is a strange result for a brief about feeling
  real, and decision 5 keeps every bit of its honesty at half the length.

- **Delete the note entirely and give the associate record a `SIM-` marker like the ticket's.**
  Rejected: an employee id nobody in the audience can parse is disclosure in name only, and it fails
  decision 6's floor. A fabricated PTO balance attached to a named individual is the strongest claim
  this surface makes today and it earns a sentence.

- **Make the ticket real.** The most interesting option raised, and the only one that removes the
  badge *by removing the simulation*: persist the ticket to Cosmos, which this deployment already
  runs, and read it back — a real record in a real store, honestly unbadged. Rejected for scope
  rather than merit. It converts a badge decision into a feature, it does nothing for the associate
  record, the alert or spec 4's manager, and the ticket would still not reach a service desk, so
  `SIM-` would have to stay anyway. Worth revisiting if the ticket workflow in spec 4 needs a status
  lookup with somewhere to look.

- **Redefine "Simulated label" to mean the Provenance line**, keeping the term. Rejected: the term
  carries *label* and *badge* in its own name, which is the device being deleted, and a redefined
  term is how a retired idea returns.

## Consequences

- **Positive — the brief is answered in full, and more than it asked.** Every badge and every
  surface-authored confession goes. The demo stops wearing *Simulated* as permanent chrome, which is
  what *"feel more real"* was actually about.

- **Positive — the rule got sharper by being reversed.** *"Label the invented things"* was a list of
  cards. *"The surface asserts nothing about itself; a record carries its own provenance"* decides
  the presenter alert, spec 4's manager and cases nobody has proposed, without a new judgement each
  time. [ADR-033](./033-a-one-tap-control-never-invents-the-words-it-offers.md)'s *claims, not
  controls* is not superseded: its conclusion survives *a fortiori*, since a surface with no badges
  cannot badge a chip.

- **Negative — disclosure is now invisible when it fails.** This is the real price of decision 9 and
  it should be stated plainly. An unbadged card was visible to anybody in the room; an invented thing
  missing from the Simulation register is visible to nobody until it is asked about on stage.
  Decision 11's register guard narrows this to *an invented thing that carries no Provenance line at
  all* — which nothing can detect, because "invented" is not a property code can see.

- **Negative — the recording has no presenter.** `scripts/e2e-tests.sh --stage` leaves a **Recorded
  fallback** in `e2e/artifacts/walkthrough/` and `docs/presenter-runbook.md`'s own fallback ladder
  ends at *recording*. In that artefact nobody addresses anything conversationally, and after this
  change the only disclosure left in frame is what the records carry. That is exactly why decision 3
  keeps them and decision 5 puts them in the shot rather than in a tooltip.

- **Negative — seven assertions are deleted and two written.** Four frontend cases,
  `escalation.spec.ts:107` and `test_the_simulated_sign_in_is_said_out_loud` go; the last is
  converted rather than lost.

- **A live defect is promoted, not fixed here.** Finding 8's Brightpath leak. Its issue is ordered
  ahead of the badge removal under spec 2.

- **Testing.** Nothing here is implemented by this ADR. Decision 11's guards land in the Frontend
  tests loop (`src/App/src`) and the CI-tooling loop (`src/tests/ci/test_presenter_runbook.py`); the
  browser swap lands in `e2e/specs/escalation.spec.ts`. `src/tests/backend/escalation/` is untouched,
  because decision 3 changes nothing about the ticket id.

- **`CONTEXT.md` changes in this commit**: **Simulated label** is retired, and **Provenance line**
  and **Simulation register** are added.

## References

- [ADR-014: The identity boundary gate is deterministic code, not a prompt](./014-deterministic-identity-boundary-gate.md)
- [ADR-017: The Workforce agent answers HR process, and never an individual's record](./017-workforce-agent-answers-process-never-record.md)
  — not amended; its per-answer disclaimer is record-borne and survives under decision 3
- [ADR-019: Rebrand the SOP corpus to Circle K](./019-rebrand-the-sop-corpus-to-circle-k.md) —
  incompletely applied; finding 8
- [ADR-023: The loading screen claims only what a signal reports](./023-progress-narration-claims-only-what-a-signal-reports.md)
  — the same discipline at the loading seam; decision 8 is its reasoning, not a reversal of it
- [ADR-033: A one-tap control never invents the words it offers](./033-a-one-tap-control-never-invents-the-words-it-offers.md)
  — not superseded; its *claims, not controls* conclusion survives a surface with no badges
- `CONTEXT.md` — **Provenance line**, **Simulation register**, **Grounding panel**, **Not reported
  vs measured**, **Presenter alert**, **Simulated ticket**, **Workforce agent**
- `docs/presenter-runbook.md` — the Simulation register's home; lines 287-289 are rewritten
- [#81](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/81) — the map, whose standing
  rule 1 required this ADR rather than a quiet deletion
- [#85](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/85) — `Assignee.simulated`,
  whose consumer is redefined by decision 10
