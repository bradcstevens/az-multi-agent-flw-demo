# ADR-023: The loading screen claims only what a signal reports

## Status

Accepted

## Date

2026-08-14

## Issue

#64 (spec #1)

## Context

`commonComponents/components/LoadingMessage.tsx` exports four strings — *"Initializing AI
agents..."*, *"Generating plan scaffolds..."*, *"Optimizing task steps..."*, *"Applying finishing
touches..."* — and `PlanPage` rotates them on a bare 3000ms `setInterval` keyed to `loading`, a
boolean meaning *a GET is in flight*.

Nothing scaffolds. Nothing optimises. No backend event named any of those stages exists, because
**there is no phase state anywhere in the system**: the plan slice has `waitingForPlan`, one
undifferentiated boolean, and `StreamingPlanResponse` derives a second, local `isCreatingPlan` from
`!planSteps.length && !factsContent`. The rotation is a progress bar with no progress behind it,
inherited from the accelerator.

Six components narrate the same moment and none share a source: `HomeInput` (*"Creating a plan"*),
`StreamingPlanState` (*"Creating your plan..."*, *"Processing your plan and coordinating with AI
agents..."*), `StreamingPlanResponse` (*"Creating plan..."*), `PlanPanelRight` (*"Plan is being
generated..."*) and `PlanPage`'s rotation. This is the problem `storeSurface.ts` already solved
once for identity — *"the left panel's toolbar, the conversation's header, the browser tab and the
identity chip are four places to disagree about which assistant this is."*

They already do disagree, and the story runs **backwards**: `HomeInput` toasts *"Plan created —
Fast lane"*, then `PlanPage` mounts and says *"Loading plan data..."* over *"Initializing AI
agents..."*. The audience is told it finished, then told it is starting.

In an ordinary product this is cosmetic. Here it is not. Every other panel on this surface is built
on the rule that the screen asserts only what it knows — `—` means nobody told us and `0` means we
know it was nothing; the **Grounding panel** goes dark rather than credit a platform with an answer
it did not give; the **Lane badge** was rewritten because it claimed a latency nobody had measured.
A scripted progress bar three inches from the Token meter invites an audience to re-read the meter
as scripted too, and the meter is the strongest evidence in the room.

The obvious counter-argument is that a loading screen is atmosphere and nobody reads it as a claim.
That is true right up until someone does, and the person most likely to is the technical evaluator
in the second row.

## Decision

**The loading state enters a phase only when a real signal reports it. Where no signal has arrived,
it holds the last true statement rather than inventing the next one.** The four authored messages
and the `setInterval` that rotates them are deleted.

**And it stops.** Reaching the Done phase removes the in-flight indicator from the screen — a rule
worth stating separately because every other sentence here governs what the surface *says*, and
none of them governs it ever *finishing*. That gap was a shipped defect (#69): nothing
cleared `waitingForPlan` on the **Fast lane**, because the only signal that cleared it was
`plan_approval_request` and [ADR-013](./013-per-request-plan-review-over-orchestrator-bypass.md)
means that lane has no plan to approve. So the surface rendered *"Creating your plan..."* under the
answer, indefinitely, three inches from a rail reading *"No plan to review on this request."* A
narration that claims only what a signal reports and then never stops is still making a false
claim — that the request is in flight — and it makes it for the rest of the conversation.

#69 was fixed ahead of this machine, and its guard **survived** being rebased into it: it drives
raw wire text through `WebSocketService` into the real `PlanChat`, and asserts that no `progressbar`
remains. Asserted by role rather than by copy, because this ADR rewrote every one of those strings —
a guard pinned to the words is deleted along with the words, exactly when it is needed — and against
the whole conversation rather than one indicator, because the surface has two and a stand-in
rendering one can only agree with itself. It is now pointed at the phase slice, and `waitingForPlan`
is gone: nothing on the surface reads a second boolean about whether a request is in flight.

Every phase is an observable event:

| Phase | Signal |
| --- | --- |
| Sent | the `createPlan` POST is in flight |
| Routed | the `createPlan` response's `lane`, the same field `LaneBadge` reads |
| Connected | `connection_status` — plumbing, says nothing |
| Working | `agent_message_streaming`, which carries the **executor name** |
| Done | `plan_approval_request` or `final_result_message` |

There is deliberately **no "agents selected" phase**, because no such event exists anywhere in the
system. `OrchestrationManager.init_orchestration` and `AgentFactory.get_agents` build the workflow
in-process and emit nothing. The nearest real signal is an agent *producing output*, which is a
different and weaker claim, and it is the one the copy makes.

Three structural commitments follow:

- **One module owns every string** shown while a request is in flight, on the `storeSurface.ts`
  pattern. Six places to disagree becomes one place to be correct.
- **One Redux slice holds the phase, and it survives the navigation** from home to plan. Across two
  independent components "only advances" is a coincidence, not a property; monotonicity is the
  entire safety guarantee and it has to be enforceable in one place. It also carries the **plan the
  narration is about**, so that opening an earlier task from the left panel while a request is in
  flight does not leave *"Shift Tasks Agent is responding..."* over a conversation that finished
  last week.
- **The phase machine is asserted through `WebSocketService` with raw wire text.** A machine keyed
  to frames, tested against hand-fed payloads, is the exact configuration that let #47 ship.

The separate claim about *who is available* is not part of this machine and must not be conflated
with it — see **Available vs participating** in `CONTEXT.md`.

## Considered Options

- **Keep the rotation and rewrite the words** (the original request was *"collecting"* or *"calling
  agents"*). Rejected on inspection. "Collecting" has no object — nothing is retrieved at that
  point; retrieval happens inside an agent's turn — so it claims a stage that does not exist, which
  is the existing fiction restated in a new verb. "Calling agents" is *true* at
  `agent_message_streaming`, but at that moment the frame carries the executor's name, so the
  surface can say **which** specialist is responding for the same cost. Naming it is strictly more
  information and is unfakeable.
- **Two independent narrations, one per page.** Simpler and needs no new state. Rejected: it
  guarantees the backwards-running story that is already the defect. It would fix the words and
  keep the bug.
- **Keep authored copy but badge it `SimulatedBadge`.** Consistent with the **Simulated label**
  rule, and rejected on effect: a badge on the loading screen spends the demonstration's credibility
  to buy filler, and the label exists for content that could not otherwise be told apart from real.
- **Buffer a richer phase set server-side** so the browser can narrate more stages. Rejected as
  inventing events to justify copy — the stages would exist because the loading screen wanted them,
  which is the fiction with extra steps.

## Consequences

- **Positive:** The narration becomes evidence. "Troubleshooting Agent is responding..." arriving
  late and unevenly is a stronger demonstration of live orchestration than a smooth scripted
  sequence, because the unevenness is the proof.
- **Positive:** Six strings collapse to one module, so the surface can no longer contradict itself
  about what it is doing.
- **Negative:** The loading screen will sometimes say less than it does today, and on a very fast
  Fast lane request it may show only two phases. That is the honest amount.
- **Negative:** It depends on [ADR-021](./021-connect-the-socket-before-navigation.md). Over the
  previous connect ordering the later phases key off frames that are dropped, and the machine would
  stall silently — a worse failure than the fiction it replaces.
- **Negative:** `PlanPanelRight.test.tsx` and `docs/transparency-panels.md` both carried
  *"Plan is being generated..."* and moved with the change; it is `PLAN_ARRIVING` now, and both
  read it from the module. `docs/SampleQuestions.md` carried the elapsed-keyed copy and moved too.
- **Negative:** A reload of `/plan/:id` mid-request narrates **nothing** until the next
  `agent_message_streaming` frame, because no signal has reported anything to that browser. That is
  the honest amount, and it is what "holds the last true statement" costs when there is no last true
  statement.
- **Risk accepted:** Someone will later want to make the loading screen "nicer" and re-add authored
  copy. This ADR is the answer to that, and the rule itself is in `CONTEXT.md` as **Progress
  narration** so it is reachable without finding this file.

## References

- [ADR-013: Vary Plan review per request instead of building an orchestrator bypass](./013-per-request-plan-review-over-orchestrator-bypass.md) — why the Fast lane has no plan object
- [ADR-021: Connect the WebSocket on the `createPlan` response, not on the plan page](./021-connect-the-socket-before-navigation.md)
- [docs/transparency-panels.md](../transparency-panels.md)
- [docs/store-surface.md](../store-surface.md) — the `storeSurface.ts` single-source pattern
- `CONTEXT.md` — **Progress narration**, **Available vs participating**, **Not reported vs measured**
