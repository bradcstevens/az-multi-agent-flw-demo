# ADR-028: A reviewable plan is earned by a transaction, not by a question

## Status

Accepted

## Date

2026-08-16

## Issue

#83 (map #81, spec 3)

## Context

`BRIEF.md` asks the demo to be *"more strategic on what things would require plans versus what
things are just chat threads that might pull information from one or more other agents"*, and names
ticket creation and shift swapping as the plan-worthy ones.

Two facts made that ask impossible to answer as written.

**The word "plan" already names two different objects.** A `Plan` row is created for *every*
request at `src/backend/api/router.py:456`, forty-six lines before the **Lane router** picks a lane
at `src/backend/api/router.py:502`. The plan the associate *approves* is a different object — the
`plan_approval_request` frame — and it exists only on the **Deliberate lane**. #78 already had to
make the "Plan Overview" heading conditional on that frame rather than on a plan existing, and the
reason is written into `src/App/src/components/content/PlanPanelRight.tsx:79-84`.

**The row is load-bearing for something that has nothing to do with approval.** The chat list *is*
the plan list: `ChatPanelLeft.tsx:88` fetches `GET /v4/plans`, which is `get_all_plans_by_team_id`,
returning every status deliberately (#74). There is no separate chat query. The row also carries
`streaming_message` and the clarification fields.

So the brief's *"no plans should be made at this point"* is ambiguous between an object that cannot
be removed without deleting the chat history and an object that is already absent on six of the
seven **Quick Tasks**. And [ADR-013](./013-per-request-plan-review-over-orchestrator-bypass.md) had
already answered the mechanism question once: **Plan review** is a per-request value derived from
the request's **Lane**.

## Decision

**A request earns a Reviewable plan when it commits something on the associate's behalf. A question
does not, however many specialists answer it.**

Nine things follow, and they are part of this decision rather than separate work.

1. **The Lane router remains the mechanism.** ADR-013 is not superseded. The brief's *"if a plan is
   created by a planner agent"* reads as though the planner should decide, and it must not: a model
   deciding whether to gate itself is unrehearsable and untestable, and #54 spent seven iterations
   making one routing residual deterministic. The declared lane, the keyword fallback and the
   fail-open default stand as ADR-013 wrote them.

2. **The Lane grows in reach: the lane taken is recorded on the Plan record.** Today it is written
   only into **Session state** (`src/backend/api/router.py:513`), so no surface holding a `Plan` can
   tell whether that conversation was ever reviewable. This is the whole of the growth — the enum
   keeps two values and keeps deciding exactly one thing.

3. **The Quick Task allocation.** Nothing that answers a question changes lane. The one change is
   that **`task-223-shift-swap` is repurposed from the shift-swap process question into the
   shift-swap transaction, and declares `deliberate`.** Ticket creation
   (`task-223-escalation`) was already the one deliberate task and stays as it is.

4. **"No plans should be made at this point" means no Reviewable plan.** The Plan record is still
   created for every request. Suppressing it on the Fast lane is not a small change; it is the chat
   history, against [ADR-025](./025-chat-is-the-unit-of-the-surface.md) and
   [ADR-026](./026-chats-are-deleted-not-hidden.md). The defect the brief is pointing at is that
   `usePlanCancellationAlert.tsx:24` reads `overall_status === IN_PROGRESS`, which is true of every
   conversation; decision 2 gives that predicate the field it has been missing.

5. **The Lane keyword fallback's one-way requirement survives, and the Fast vocabulary widens
   instead.** The asymmetry is now measured, not assumed: `_raise_confirmed_ticket` has exactly one
   call site — `orchestration_manager.py:953`, inside the approved branch of `_handle_plan_reviews`
   — so a transaction that lands on the Fast lane commits **nothing, silently**, while a question
   that lands on the Deliberate lane costs one visible approval step. Because `keyword_lane` matches
   the Deliberate vocabulary **first and outright**, adding Fast terms can never steal a
   transaction; the safety property is structural, not a matter of list length. The brief's
   complaint about ceremony on stray questions is therefore answerable without touching the
   direction that fails silently.

6. **The swap transaction does not discover peers; the associate names their partner.** The brief
   asks the agent to *"identify other store associates… and [guide] them through selecting the
   person they want to swap shifts with"*. That is record access about third parties, it would
   supersede [ADR-017](./017-workforce-agent-answers-process-never-record.md), and there is no data
   behind it: nothing in this repository enumerates an associate other than the signed-in one.
   `WF-401` already answers the other way — *"pick the associate you have already agreed it with"* —
   which is also what happens in a store. What the brief actually wants from this beat is the
   multi-party **approval**, and that needs no roster.

7. **The brief's "chat thread that pulls information from one or more other agents" is the Fast
   lane**, which is already the full orchestration with the gate off (ADR-013). No third mechanism
   is introduced. **The conversation must name the specialist answering**, which the Fast lane does
   not do today — the Agent Team panel and the cost table carry it, the thread does not. Agent
   configuration, prompt inspection and MCP visibility remain #99's.

8. **A ticket-status inquiry is Fast lane, inside the conversation that raised the ticket.** It is a
   lookup; nothing is committed. `TicketStore.read` is *"this conversation's ticket, or nothing"*, so
   the inquiry stays where [ADR-024](./024-the-escalation-continues-the-troubleshooting-conversation.md)
   and [ADR-027](./027-resume-continues-the-session.md) already put the escalation. Making it work
   from a fresh chat would need a lookup by ticket number, and nothing here asks for one.

9. **The glossary pins the two objects.** **Plan record** is the row; **Reviewable plan** is what the
   associate approves. The unqualified word "plan" is not used of either.

## Considered Options

- **A planner agent decides which plans are worth reviewing.** Rejected on decision 1. The demo's
  most expensive beat cannot depend on a judgement no test can pin.
- **Grow the Lane into a third value, or into a richer declaration carrying its approvers.**
  Rejected for now. The brief itself assigns humans to *steps* — *"everything in the plan, as well
  as any agents or humans assigned"* — so widening a two-value enum that five test files pin would
  pre-empt a question #85 is about to answer with a prototype. `MStep` carries `agent` and `action`
  and nothing else, which is where that answer will have to land.
- **Stop creating the `Plan` row on the Fast lane**, as the brief's wording suggests. Rejected on
  decision 4: that query is the chat history.
- **Real peer discovery, superseding ADR-017.** Rejected on decision 6. It buys a list of invented
  colleagues and costs the boundary that beat 5 and beat 8 exist together to draw.
- **Flip the keyword fallback's default to Fast**, so stray typed questions skip the ceremony.
  Rejected on decision 5: it trades a visible annoyance for a transaction that vanishes without a
  signal, on stage.

## Consequences

- **Positive.** The allocation now follows one sentence a presenter can say out loud, and it
  generalises: the ticket-status inquiry was decided by applying it rather than by adding a rule.
  ADR-013, ADR-017 and the Identity boundary gate all survive intact.
- **Negative — repurposing the shift-swap task is not free.** Beat 8 of `docs/presenter-runbook.md`
  is *"Swap a shift — the fourth specialist"*, and its prompt and name are asserted verbatim by
  `src/tests/ci/test_presenter_runbook.py`. `e2e/specs/workforce.spec.ts` asserts that task's lane is
  `'fast'`. Both change with the task, in the same commit, per the standing rule that a spec moving a
  beat moves the runbook and the validator with it. The beat keeps its subject — the Workforce agent
  is still the fourth specialist — but it now *follows* `WF-401` rather than reciting it.
- **Negative — a guardrail control is left describing a phrase nobody says.** `guardrail/corpus.py:99`
  holds *"How do I swap a shift with another associate?"* as a **negative control**, which ADR-017
  chose deliberately as *"the hardest control in the set"*. Repurposing the task does not delete the
  control, but it does mean the live beat is no longer the phrase the corpus validates.
- **The new prompt must be written against the gate.** `PERSONAL_SCOPE_TERMS` contains `my shift`,
  `my shifts` and `my schedule`, and the Identity boundary gate **fails closed** before any agent
  runs. A natural transaction phrasing is refused outright unless the associate is signed in. Beat 8
  follows the sign-in beat, so the walkthrough is safe; a tap out of order is not.
- **Unblocks two tickets.** #85 (what a Reviewable plan looks like, including how a step assigned to
  a person is represented) and #89 (the cancellation dialog, which decision 2 finally gives a
  truthful predicate). Whether the peer and the manager carry a **Simulated label** is #92's, under
  the standing rule that a truthfulness reversal needs an ADR of its own.
- **Testing.** The lane suites in `src/tests/backend/lane/` keep their meaning unchanged; decision 5
  adds Fast terms only, which cannot alter a Deliberate outcome. Decision 2 is asserted where the
  lane is written — the value recorded on the `Plan` record must equal the lane the request took.

## References

- [ADR-013: Vary Plan review per request instead of building an orchestrator bypass](./013-per-request-plan-review-over-orchestrator-bypass.md)
- [ADR-017: The Workforce agent answers HR process, and never an individual's record](./017-workforce-agent-answers-process-never-record.md)
- [ADR-025: Chat is the unit of the surface](./025-chat-is-the-unit-of-the-surface.md)
- [ADR-026: Chats are deleted, not hidden](./026-chats-are-deleted-not-hidden.md)
- `CONTEXT.md` — **Plan record**, **Reviewable plan**, **Plan review**, **Lane**, **Lane keyword
  fallback**, **Fast lane**, **Deliberate lane**
- [#84](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/84) and
  [#98](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/98) — what rejecting a plan
  does today, and the `revise(feedback)` call this repository declines to make. Not settled here.
