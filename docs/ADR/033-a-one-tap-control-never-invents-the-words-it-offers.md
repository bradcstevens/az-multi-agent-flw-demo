# ADR-033: A one-tap control never invents the words it offers

## Status

Accepted

## Date

2026-08-16

## Issue

#91 (map #81, spec 1)

## Context

`BRIEF.md` asks for *"suggested button responses within a chat thread. This allows the user to
quickly submit a response back to the agent in the chat thread, instead of typing it out and
pressing enter."*

#91 put that as a binary — **authored or generated**. Both halves of the binary were already wrong.

**There is a third source, and it is already published.** Spec 3's decision 15
([#100](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/100)) says the suggestions on
a sent-back plan are *"derived from the plan in front of the associate, never generated."* **Derived**
is neither authored nor generated: nobody wrote those strings against a beat, and no model produced
them. Pure code computes them from a structured record, which makes them checkable like authored
content and universal like generated content.

**The brief's phrase is already banned.** `CONTEXT.md` closes the **Rehearsed reply** entry with
`_Avoid_: suggested reply, quick reply`.

**And the brief is already built, three times over.**

| Control | Source | Act | Endpoint |
| --- | --- | --- | --- |
| **Rehearsed reply** chips | authored on the **Quick Task** | *answers* a pending **Clarification** | `POST /v4/user_clarification`, against a `request_id` |
| **Follow-on task** card | authored, `StartingTask.follow_on` | *starts the next turn* | `POST /v4/process_request`, against a `session_id` |
| Send-back suggestions (spec 3, undelivered) | **derived** from the **Plan record** | *revises* a **Reviewable plan** | the revise path |

The **Follow-on task** is the one the brief is describing. `CONTEXT.md`: a Quick Task another Quick
Task leads to, *"rendered **inside** the conversation it follows rather than on the home grid"*,
sitting *"above the chat box and below the **Rehearsed reply** chips' slot"*, and tapping it
*"submits the authored prompt and the authored **Lane** with the current plan's `session_id`, which
needs no backend change."* That is a one-tap button inside a chat thread that submits a turn
without typing. Its only limit is **arity**: `follow_on` is a single pointer with one user —
`task-223-troubleshooting` names `task-223-escalation` — filtered out of the home grid by
`src/App/src/components/content/HomeInput.tsx:335-345`, frontend-only, derived from the pointer with
no flag anywhere.

Four facts found while grilling shape what follows.

1. **The resolution is already turn-scoped.** `followOnTaskFor(planTeam, planData?.plan?.initial_goal)`
   (`src/App/src/pages/ChatPage.tsx:209`) resolves against the *current* plan, and
   `submitTurnIntoSession` mints a new plan every turn. The mechanism is already a chain; a list
   makes it a graph.
2. **A typed turn leaves that graph permanently.** `taskForGoal` matches `initial_goal` against
   `starting_tasks[].prompt` by normalised string, so a typed goal resolves to nothing.
   `CONTEXT.md` records this for the chips — *"a goal matching no prompt resolves to none, exactly
   as an edit gives up the declared **Lane**"* — where it governed one card and three chips.
3. **The card does not know clarifications exist.** `RehearsedReplies.tsx:38` gates on
   `selectHasPendingClarification`; `FollowOnTask` has no gate of its own, and `handleFollowOnTask`
   (`ChatPage.tsx:498`) calls `submitTurnIntoSession` unconditionally — no `turnModeFor`, no
   clarification read. `task-223-troubleshooting` is the single task carrying **both** a `follow_on`
   and `rehearsed_replies`, so the two controls are live on screen together.
4. **Three of the four asserted properties are beat-specific.** `src/tests/ci/test_store_pack.py`
   requires each reply to record an **Attempted step**, the set to reach `ESCALATION_AFTER`, and
   each to be anchored in a runbook. None of the three is meaningful for a shift-swap question, and
   the third would forbid `task-223-honest-miss` — the prompt that is deliberately unanswerable.

## Decision

**A one-tap control never invents the words it offers.** They are authored against a beat or derived
from a record in front of the associate, and either way they are checked **before the demo** rather
than judged at run time.

Nine things follow, and they are part of this decision rather than separate work.

1. **Generation is refused outright.** A generated chip cannot satisfy any property in
   `test_store_pack.py`, because there is nothing to assert against until the model has already
   spoken on stage. It could record an **Attempted step** nobody tried — which the **Simulated
   ticket** then prints — or trip the **Identity boundary gate** mid-beat. This is ADR-014's
   reasoning at a second seam: a deterministic control beats a model's judgement wherever the
   failure is visible to the room.

2. **The general ask is the Follow-on task generalised, not the chips generalised.** The chips
   *answer a question the agent asked*; the brief's general case *is the next turn*, which is what
   the card already does. `StartingTask.follow_on` becomes a **list**.

3. **A suggestion is still a Quick Task**, so it inherits the declared **Lane**, `parse_lane`, and
   the assertion that its prompt reaches its declared lane **through the Lane keyword fallback
   too**. No second authoring format is introduced.

4. **"A task named as a follow-on is not a home card" is replaced by a declaration of context
   dependence.** That rule — recorded in `CONTEXT.md` and in
   [ADR-024](./024-the-escalation-continues-the-troubleshooting-conversation.md), which is
   superseded and is not edited — is only correct while there is exactly one follow-on. Its
   justification was never really about being a follow-on: *"a Quick Task is a claim about what will
   happen when somebody taps it, and that claim may not depend on where it was tapped"*, and the
   escalation is off the grid because it **reads a record the conversation wrote**. Generalising the
   pointer breaks the coincidence — a task naming three suggestions would strike three cards from
   the home grid, silently, and the home grid is the walkthrough's spine. So the task declares
   context dependence, the grid derives from **that**, and the cold-tap invariant gets stronger by
   being asserted directly instead of as a side effect. This is the second flag `CONTEXT.md`
   deliberately refused; it is reintroduced here in the open, because the pointer and the
   declaration now answer different questions.

5. **A suggestion is an edge in a graph** rooted at the Quick Task that produced the current turn.
   Typing leaves the graph and a tap re-enters it, so *what is on screen stays a pure function of
   what was authored* — checkable in CI with no runtime judgement.

6. **A suggested turn hides while a Clarification is pending.** One control at a time: the card
   yields the slot to the chips, the tap answers, the chips go and the card returns. *"A pending
   clarification wins"* becomes one rule with one implementation instead of two behaviours in
   adjacent components.

7. **What a tap submits follows from 5 and 6 rather than being decided separately.** A suggested
   turn always submits a **new turn** through `ChatPage.submitTurnIntoSession`; a **Rehearsed reply**
   always submits an **answer**. Neither is ever tappable at a moment when the other is what is
   wanted, so source, visibility and payload cannot disagree.

8. **Two tiers of check.** Tier 1, on every suggestion: every named id **resolves** to a task in the
   roster; the graph is **acyclic**; the home grid and the edge set are asserted **independently**;
   no prompt trips `matches_personal_keyword`; every edge on the walkthrough's path is **quoted in
   `docs/presenter-runbook.md`**; and the frontend asserts a suggestion is not rendered while a
   clarification is pending. Tier 2 — the attempted-step, `ESCALATION_AFTER` and runbook-anchoring
   properties — stays scoped to **Rehearsed reply**, unwidened.

9. **No new term, and the ban survives.** **Rehearsed reply** and **Follow-on task** remain two
   controls with different sources, gates, payloads and moments; a noun spanning them would name a
   category the code never instantiates. The shared invariant is a rule, in the glossary's own idiom
   alongside *"Only a clarification is a question"* and *"Label the invented things, and only
   those."* `_Avoid_: suggested reply, quick reply` **stays**, now for a better reason than the one
   originally recorded: after this decision the phrase is **ambiguous between two controls**.

## Considered Options

- **Generate the suggestions with the model already deployed.** Rejected on decision 1. It is the
  cheap implementation and the reason this ADR exists — the next reader will suggest it again.
- **Generalise the chips instead of the card.** Rejected on decision 2. A chip that answers a
  Clarification has no meaning where no question was asked, and routing an authored *next-turn
  prompt* into `/v4/user_clarification` would run *"I have tried everything and I can't fix it"*
  through `parse_attempted_steps` and write nonsense into the **Troubleshooting record**.
- **Keep the derived home-card rule and add a floor assertion on the grid.** Rejected on decision 4:
  it leaves authoring a chip as a way to delete a walkthrough beat.
- **A lighter suggestion that is not a Quick Task** — prompt and lane, no roster entry, no card.
  The honest runner-up: it cleanly separates *what the presenter taps to run a beat* from *what the
  associate is offered mid-conversation*. Rejected for duplication — every Quick Task invariant
  would have to be restated, and a suggestion repeating a Quick Task's prompt gives two authored
  copies that drift.
- **Suggestions sticky to the conversation**, surviving a typed turn. Rejected on decision 5: it
  offers the opening task's list three turns after it stopped fitting, and *a suggestion that no
  longer fits is worse than no suggestion*.
- **Re-resolve suggestions by fuzzy-matching typed text back onto the roster.** Rejected: a fuzzy
  matcher is wrong sometimes, and being wrong means a chip on screen that does not fit what was just
  said — generation's unverifiability arriving by a side door.
- **Hold every suggestion to all four asserted properties.** Rejected on decision 8: it would
  forbid `task-223-honest-miss`, which is the demo's evidence that the assistant does not bluff.
- **Badge every authored chip with the Simulated label.** Rejected — see decision below on the
  badge, and `CONTEXT.md`'s **Simulated label**, sharpened in this change to *claims, not controls*.
  A chip claims nothing; the instant it is tapped the words are the associate's own. Badging it
  would also put "Simulated" immediately upstream of a **real** Foundry answer, which the same entry
  warns *"gives away the demo's strongest evidence."* Where authored words do become a claim about
  the world — the attempted-steps field of `TKT-001` — the **Simulated ticket** already wears the
  badge.
- **Coin a superordinate term** (*Offered turn*, or similar) over both controls. Rejected on
  decision 9.

## Consequences

- **Positive.** The feature the brief asks for is mostly a **widening**, not a build: one model
  field goes from a pointer to a list, and the lane invariants, the render slot and the submit seam
  are all already there. The invariant generalises — the badge question and the check tiers were
  decided by applying it rather than by adding rules.
- **Negative — the typing cliff.** Under decision 5, an associate who types once loses every
  suggestion for the rest of the conversation. That is the honest consequence of refusing
  generation, and it is worth stating plainly to whoever writes spec 1: on a rehearsed walkthrough
  it is invisible, and for an associate on a shared device it is exactly when they would most want a
  chip back.
- **Negative — the graph costs three assertions a single pointer never did**, and decision 4 costs
  a flag that has to be kept honest. Both are in tier 1 of decision 8.
- **Negative — a nonsensical edge is authorable and no property catches it.** *"How do I close the
  store?"* → *"How do I restart the car wash?"* passes every check in tier 1. Only a person reading
  it catches that, which is why decision 8 makes `docs/presenter-runbook.md` quote every rehearsed
  edge: the runbook is where that judgement is recorded, and
  `src/tests/ci/test_presenter_runbook.py` is what holds it to the pack.
- **A live defect is named, not fixed here.** Fact 3 — tapping the escalation card while the
  orchestration waits on a clarification answer strands the turn that asked — exists on `main`
  today. Decision 6 is its repair, and it belongs to spec 1's implementation, not to this ADR.
- **`CONTEXT.md`'s Quick Task counts were stale and are corrected in this change.** The **Follow-on
  task** entry said *"the roster still declares six and the grid renders five"* — true when ADR-024
  was written, false since the seventh task. The pack declares **7**
  (`test_given_the_roster_when_read_then_there_are_seven_quick_tasks`) and the grid renders **6**
  (`src/App/src/components/content/QuickTasks.test.tsx`, whose own comments are stale the same way).
- **Spec 3 is corrected.** #100's decision 15 reads *"authored suggestions"* in one clause and
  *"derived from the plan"* in the next. This ADR makes those distinct sources, so the published
  spec is amended to say **derived**.
- **Testing.** Nothing here is implemented by this ADR. Tier 1 lands in the CI-tooling loop
  (`src/tests/ci/test_store_pack.py`, `test_presenter_runbook.py`) and the Frontend tests loop
  (`src/App/src`); tier 2 is unchanged. Decision 6 is a frontend seam and is asserted where
  `troubleshooting.spec.ts` already asserts the chips going hidden after a tap.

## References

- [ADR-014: The identity boundary gate is deterministic code, not a prompt](./014-deterministic-identity-boundary-gate.md)
- [ADR-024: The escalation continues the troubleshooting conversation](./024-the-escalation-continues-the-troubleshooting-conversation.md)
  — superseded by 027; its *"a task named as a follow-on is not a home card"* is replaced by
  decision 4 and its body is left unedited
- [ADR-027: Resume continues the session](./027-resume-continues-the-session.md)
- [ADR-028: A reviewable plan is earned by a transaction, not by a question](./028-a-reviewable-plan-is-earned-by-a-transaction.md)
- [ADR-034: The Identity boundary gate covers the clarification seam](./034-the-identity-boundary-gate-covers-the-clarification-seam.md)
- `CONTEXT.md` — **Quick Task**, **Follow-on task**, **Rehearsed reply**, **Clarification**,
  **Attempted step**, **Lane**, **Lane keyword fallback**, **Identity boundary gate**,
  **Simulated label**
- [docs/quick-tasks.md](../quick-tasks.md) — the tasks, and why a prompt is never restated
- [#100](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/100) — spec 3, whose
  decision 15 authors the derived half of this invariant for the sent-back plan
