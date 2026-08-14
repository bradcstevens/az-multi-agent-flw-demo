# ADR-021: Connect the WebSocket on the `createPlan` response, not on the plan page

## Status

Accepted

## Date

2026-08-14

## Issue

#63 (spec #1)

## Context

The browser opens its WebSocket after the orchestration it is meant to observe has already started
talking.

`usePlanWebSocket` is mounted only by `PlanPage` and is gated on `planId`, so
`webSocketService.connect(planId)` cannot run until the HTTP `createPlan` round-trip has resolved,
`HomeInput` has called `navigate` to `/plan/:id`, and the plan page has mounted and rendered. The
backend does not wait: `process_request` schedules `run_orchestration_task` as a detached
`asyncio.create_task` **before** it returns the HTTP response. Everything emitted in the window
between that schedule and the browser's connect is pushed at a socket that does not exist, and
`send_status_update_async` drops it.

The code already knows this happens. `connection_config.py` carries a comment demoting the
"No active WebSocket" log to DEBUG precisely because it fires once per streaming token before the
frontend connects. The drop was treated as noise; it is a hole.

The **Fast lane** is most of the walkthrough and it is the fast one, so the frames most likely to
land in that window are the ones the demonstration most depends on: the first agent's
`agent_message_streaming` header — the **only** signal in the system that names *which* specialist
took the question — and, on a short answer, `source_used` and `token_usage` too.

`CONTEXT.md` already records what this class of failure costs, under *"Every transparency signal
was dropped in the browser, and 223 frontend tests were green"* (2026-08-13, #47). There the frames
arrived and were misshaped by a double-wrap in `WebSocketService.handleMessage`; the total parsers
correctly returned `null` and every panel stayed dark in silence. This is the same outcome reached
by a different road — the frames never arrive at all — and it is equally invisible, equally green,
and equally capable of taking the demonstration's evidence off the screen without saying so.

It also blocks work that was about to be built on top of it. The **Progress narration** (ADR-023)
keys a phase on `agent_message_streaming`; over the current connect ordering that phase would
silently never advance.

## Decision

**The connect is initiated on the `createPlan` response, before `navigate`, rather than on the plan
page after it mounts.**

The plan id exists at that moment — it is in the response body — which is the only thing the
connect ever needed. The plan page keeps its own connect for the case that has no `createPlan`
response to hang off: a direct load or reload of `/plan/:id`. Connecting twice for one plan is
guarded against; connecting late is not.

The window is **narrowed, not closed**. A frame can still be emitted between the backend scheduling
the task and the browser receiving the HTTP response. The "No active WebSocket" path therefore
stays reachable and stays logged: a drop that still happens must remain visible to whoever reads
the logs, and this ADR does not claim to have eliminated one.

The regression test asserts the ordering through `WebSocketService` **with raw wire text**, not
hand-fed payloads. #47's finding is explicit about why: *"Four tests agreeing with each other about
a shape the service does not produce is not four tests."* A test that mocks the service cannot see
this bug, and four such tests already existed while the panels were dark.

## Considered Options

- **Leave it and accept the loss.** Rejected. It is a silent, intermittent removal of exactly the
  evidence the demonstration is built to show, on the lane the demonstration mostly runs on. The
  same class of defect has already cost this project one live failure and eight validator runs to
  characterise.
- **Buffer or replay server-side** — hold frames until a socket for that `process_id` appears, then
  flush. Genuinely more robust, and the right answer for a product. Rejected here as too large for
  the surface it protects: it adds per-session buffering, an eviction policy, and a new class of
  bug (a replayed `source_used` lighting the Grounding panel for a question already superseded)
  to fix an ordering problem that a client-side move fixes outright.
- **Connect on home-page mount, before any request.** Rejected: the socket route is keyed by
  `process_id`, so there is nothing to connect *to* until a plan exists. It would mean inventing an
  identifier before the backend has one, which is the sort of thing that ends with the frontend and
  the backend disagreeing about who a session belongs to.
- **Move the connect but keep mocking it in tests.** Rejected explicitly. The fix and the test that
  proves it are one decision; the mocked version of this test is the one that already passed while
  the bug shipped.

## Consequences

- **Positive:** The signals the transparency panels exist to render stop being lost on the fastest
  and most-used lane. The **Grounding panel**, the **Token meter** and the **Progress narration**
  all benefit from the same change.
- **Positive:** `src/App/src/store/WebSocketService.test.ts` — named in the #47 finding as *the
  missing seam* — gains a second reason to exist and a second raw-wire case.
- **Negative:** Connection lifecycle now has two entry points, the `createPlan` response and the
  plan page's own mount. Double-connect and leak-on-abandon are new failure modes and are covered
  by acceptance criteria rather than by construction.
- **Negative:** A reader encountering `connect()` in a submit handler will reasonably think it is
  misplaced and move it back to the hook. That is the specific regression this ADR exists to
  prevent; the code should point here.
- **Risk accepted:** The window is narrowed, not eliminated. A sufficiently fast orchestration can
  still emit before the HTTP response reaches the browser. If that proves to happen in practice, it
  is measured and recorded as a **Confirmed finding** first, and buffering is reconsidered on
  evidence rather than on suspicion.

## References

- [ADR-013: Vary Plan review per request instead of building an orchestrator bypass](./013-per-request-plan-review-over-orchestrator-bypass.md)
- [ADR-023: The loading screen claims only what a signal reports](./023-progress-narration-claims-only-what-a-signal-reports.md)
- [docs/transparency-signals.md](../transparency-signals.md) — the three signals this delivery path carries
- [docs/transparency-panels.md](../transparency-panels.md) — the panels that go dark when it fails
- `CONTEXT.md` — **Progress narration**, and the #47 confirmed finding
