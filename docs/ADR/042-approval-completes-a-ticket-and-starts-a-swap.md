# ADR-042: Approval completes a ticket and starts a swap

## Status

Accepted — decides the boundary
[ADR-037](./037-an-invented-persons-action-is-disclosed-in-the-record-that-carries-it.md) left to
spec 4

## Date

2026-08-16

## Issue

#114 (map #81, spec 4), building on #83, #85, #100, #105, #106 and #109

## Context

Map #81's first *Not yet specified* bullet for spec 4 asks whether the support-ticket workflow and
the shift swap are **one mechanism or two**. Spec 3 (#100) is published and stops at the moment a
plan is approved. Both workflows reach that moment, and neither #100 nor its tickets say what
happens after it. The two want different answers, and the difference is not a matter of degree.

Read out of the code before deciding anything.

**The support ticket has no human in it but the associate.**

- `TicketStatus` is a closed enum of exactly two states — `draft` and `submitted`. There is no
  *assigned*, *in progress* or *resolved*.
- `_raise_confirmed_ticket` has one call site, `_handle_plan_approval`, and is invoked
  **deterministically by backend code** at the approval seam. It is not a tool the model can call,
  and `CONTEXT.md` records why that is load-bearing: *"a submit tool the model can call is the second
  confirmation step the template says there is not"*, with `DOMAIN_ALLOWED_TOOLS["escalation"]`
  keeping the shared `ask_user` out of the path (#21).
- `EscalationAgent` is instructed to ask the associate nothing, and `asks_the_associate_nothing`
  auto-approves the clarification pause with a synthetic `NOT_ASKED`. **The ticket path never touches
  the human-in-the-loop seam at all.**
- The ticket already carries a record-borne disclosure, `SIMULATED_NOTICE`: *"No service desk
  receives it, no engineer is dispatched."*
- There is no ticket-status lookup path anywhere in `src/`. `TicketStore.read` exists only for
  draft/submit idempotency.

**The shift swap has no mechanism yet.** `task-223-shift-swap` declares `"lane": "fast"` and is
answered by the **Workforce agent** out of `workforce_library.py` as rehearsed text — `WF-401`, five
authored steps, a per-answer disclosure. No plan, no store, no state, no id. #109 turns it into the
**Deliberate lane** transaction; #106 makes a person-assigned step representable on the wire.

So the two are asymmetric at the root, and the asymmetry is structural rather than incidental:

| | Support ticket | Shift swap |
| --- | --- | --- |
| Humans involved | the associate, alone | the associate, a peer, a shift lead |
| What approval does | **completes** it | **starts** it |
| Can the outcome be *no*? | no — nothing can refuse it | yes, twice |
| Post-approval life | none, by design | the entire point |
| Which rule governs the disclosure | ADR-036 — an invented **record** | ADR-037 — an invented **person's action** |

ADR-037 binds spec 4 and leaves it exactly one edge: *"a peer shown as **waiting** to approve is
neither, and spec 4 must say which side it falls on."* It also fixes what spec 4 may not choose —
*"Spec 4 chooses the wording and the treatment; it does not choose whether there is one."*

## Decision

**Approval completes a ticket and starts a swap. They are two mechanisms sharing one shape.**

The **shape** is shared. #106's `Assignee` union, its closed `relation`, its `simulated` field and
`waitsOn` are one data model with one renderer and one contract test. Nothing is built twice and the
wire contract cannot drift.

The **runtime** is not shared, and the boundary is a property of the data rather than a judgement
call:

> **A step assigned to a person other than the associate is the only thing that creates
> post-approval waiting.**

The ticket has none, so it gains **no new runtime mechanism** — which is what holds the "there is no
submit tool" invariant closed without anybody having to remember it. The swap has two, and they are
the whole of spec 4.

Six things follow, and they are the decision as much as the sentence above is.

1. **A ticket's status never moves past `submitted`.** The two-state enum stays two. The status
   inquiry (#105) reads back the real persisted record — the `SIM-223-NNNN` number, the nineteen
   fields, the **Attempted steps** carried from the troubleshooting record — together with the
   `SIMULATED_NOTICE` it already carries. A progressing status would mean an invented person picked
   the ticket up, which is an invented person's *action* and would pull ADR-037 onto the one path
   this decision keeps clear. It would also be a claim no signal reports, which ADR-023 forbids and
   which the ticket model already refuses field by field by degrading to `not reported`.

2. **A person's verdict is authored; their words are generated.** The **outcome** — approved or
   declined — is authored metadata on the **Quick Task**, the way `ticket_on_approval` already is,
   so the beat is rehearsable and pinnable. What the person *says* is generated per run. This is
   ADR-038's split — *"tone is authored in the prompt and the addressee rides the turn"* — applied
   one spec later: the fact is authored, the voice rides the turn.

3. **The clarification seam is not the mechanism.** `request_user_clarification` times out at 300s,
   is auto-approved with the synthetic *"No response received from user (timeout)."*, and resumes
   (#87). Wiring a manager's approval to it would let a stalled demonstration **fabricate the
   manager's approval by timeout** — an invented person's action produced by nothing at all, in the
   beat ADR-037 identifies as the one most likely to be believed.

4. **The disclosure is a Provenance line on the record, in both places, and never in a component.**
   Once on the **plan record** at approval time, covering every simulated person in it at once, and
   again on **each verdict record** as it lands. The second is not a choice — ADR-037 requires a
   Provenance line on the record carrying the action. The first is this ADR's addition, and it earns
   its place by landing *before* the associate approves, which is the only moment a disclosure can
   change what they do. Both are authored **where the content is authored**: ADR-036 decision 4 puts
   the line at *where the string is authored, not how loud it is*, so a component-authored sentence
   is out even in prose — that is the act that deleted `HomeInput`'s *"Simulated sign-in"* line.
   Each meets ADR-036's behavioural floor and names the system that was not consulted: the approval
   was **not routed to a workforce management system**, and the line says so. Vocabulary below the
   floor is free; *simulated* and *mocked* are not required.

5. **Waiting is set dressing.** ADR-037's open edge is decided on the side its own wording implies —
   the rule binds *"the moment that person is shown approving, denying or replying"* — so a person
   who has not decided yet is shown plainly, with no treatment. The plan record's Provenance line
   has already disclosed what every person in that plan is, before any of them is asked, which is
   what makes the plain rendering honest rather than merely undecorated.

6. **A decline is expressible, specified, and not exercised.** A person step resolves to approved or
   declined; a decline stops the plan at that step, every step that `waitsOn` it never runs, and the
   conversation says which person declined and what did not happen. The walkthrough authors both
   people to approve. This is not optional completeness: #100's user story 6 already promises the
   associate *"they can say no"*, and a model that cannot represent a refusal would leave that story
   as the exact fault ADR-037 names about `Assignee.simulated` — a thing retained that drives
   nothing — except in prose, where no `grep` will ever find it.

**The pacing is the real generation, and nothing else.** Because the verdict's words are generated
per run, each one is a real, observable event taking real time, so the steps resolve in `waitsOn`
order while the **Progress narration** narrates something true. No artificial delay is introduced.
ADR-023 is satisfied by construction rather than by careful wording — which matters here because
ADR-036 decision 10 names *"after a realistic pause"* as part of what makes this claim strong, and a
fabricated pause would be a second invented thing wearing the first one's clothes.

**Every Provenance line constant this spec adds appears in the Simulation register.** ADR-036's
drift-away guard is not satisfied on faith: `docs/presenter-runbook.md` must gain these lines and
`src/tests/ci/test_presenter_runbook.py` must fail without them. The reason is the **Recorded
fallback** — one silent `.webm` per beat, and nobody speaks over a video.

## Considered Options

- **One mechanism — run the ticket through the swap's post-approval machinery with an empty set of
  person steps.** Elegant on paper, rejected on cost: the ticket's approval seam is deterministic
  backend code precisely so that no second confirmation exists, and giving that path a post-approval
  executor reopens the invariant #21 found to be load-bearing twice. It would also buy nothing — the
  ticket has no second human to wait for and, by its own notice, never will.
- **Two mechanisms, fully separate — give the swap its own step model.** Rejected: it duplicates
  #106's `Assignee`/`waitsOn` contract within weeks of its being pinned, and two shapes for *a step
  that reaches a person* is the drift its contract test exists to prevent.
- **Generate the verdict outcome as well as the words.** The only option in which the peer genuinely
  decides, and attractive for it. Rejected because the outcome is load-bearing for the
  demonstration: a beat where the named peer might decline on the customer run is unpresentable, and
  it can be neither rehearsed nor pinned. #106 already made this argument about *who* a plan
  reaches; it transfers to *what they decide* without stretching, and the generated words keep
  everything that made the option attractive.
- **Author the words too.** The safest option, rejected as unnecessary: ADR-038 and
  `e2e/specs/workforce.spec.ts` both establish that generated prose can be held by an invariant
  rather than by a string, so determinism was available without a canned line.
- **Disclose only on the verdict, not on the plan.** Compliant with ADR-037 on its own terms, and
  rejected because it discloses only after the associate has already approved. It also leaves
  decision 5 unsupported: without a plan-level line there is nothing that makes an undecorated
  *waiting* person honest rather than merely unlabelled.
- **An authored delay between verdicts, tuned for the stage.** Rejected: a narrated wait that is not
  happening is a **Progress narration** claiming what no signal reports, which is ADR-023's subject.
- **Defer the ticket half to a later spec.** Rejected — map #81 lists *"the support-ticket workflow
  and its status"* as spec 4's own content, and the honest answer to the status question turned out
  to cost nothing.

## Consequences

- **Positive:** The ticket half of spec 4 costs nothing to build. The record is already persisted
  and already complete, and the status beat is a read of real data alongside a notice that already
  exists.
- **Positive:** The "no submit tool" invariant stays closed by construction, because the boundary
  rule keeps the ticket path out of the executor rather than relying on anybody recalling #21.
- **Positive:** `Assignee.simulated` gets the consumer ADR-036 decision 10 and ADR-037 both promised
  it, so the standing question those left on the field is answered.
- **Positive:** ADR-023 holds without special care, because the only pacing is a real event.
- **Negative:** The verdicts are a foregone conclusion, and anyone reading the content pack can see
  the shift lead was always going to say yes. That is the price of a rehearsable centrepiece.
- **Negative:** The decline path is specified and unit-tested but never demonstrated, so it can rot
  in a way only a test will notice.
- **Negative:** The gap between verdicts is not tunable. If generation is fast, the two land close
  together and the `waitsOn` ordering reads as less deliberate than a presenter might want.
- **Negative:** Two Provenance lines on one plan is more disclosure than any single artefact carries
  today, and the over-labelling failure ADR-037 warns about in its options is a real risk if a plan
  later grows several approval steps. The mitigation is that the plan-level line covers *all* people
  in the plan at once and does not multiply.
- **Risk accepted:** a generated verdict is fabricated human speech, and no string assertion can
  guard its wording. The mitigation is ADR-038's — assert the invariant, not the wording, and let
  the runbook state the invariant.

## References

- [ADR-037: An invented person's action is disclosed in the record that carries it](./037-an-invented-persons-action-is-disclosed-in-the-record-that-carries-it.md) — the rule this builds on, and the *waiting* edge it left to spec 4
- [ADR-036: A record carries its own provenance, and the surface says nothing about itself](./036-a-record-carries-its-own-provenance.md) — decisions 4, 5, 6, 10 and 11: where a string is authored, the **Provenance line**, its behavioural floor, spec 4's binding, and the drift-away guard
- [ADR-038: The manager addresses the associate the session knows](./038-the-manager-addresses-the-associate-the-session-knows.md) — the authored-fact / generated-voice split this reuses
- [ADR-028: A reviewable plan is earned by a transaction](./028-a-reviewable-plan-is-earned-by-a-transaction.md) — why a swap earns a plan and a question does not
- [ADR-023: The loading screen claims only what a signal reports](./023-progress-narration-claims-only-what-a-signal-reports.md) — why the pacing must be a real event
- [ADR-017: The Workforce agent answers HR process, and never an individual's record](./017-workforce-agent-answers-process-never-record.md) — the disclosure that covers the swap as a *description*, not as a transaction
- [docs/stage-driver.md](../stage-driver.md) — the **Recorded fallback**, which has no presenter
- #100 — spec 3, published; its user story 6 is why a decline must be expressible
- #105, #106, #109 — the spec 3 tickets this builds on and must not contradict
- `CONTEXT.md` — **Provenance line**, **Simulation register**, **Simulated ticket**, **Deliberate lane**, **Progress narration**
