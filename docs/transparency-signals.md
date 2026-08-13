# The three transparency signals

Issue #23. Three new `WebsocketMessageType` members ride the socket the client already has open:
`source_used`, `token_usage` and `presenter_alert`. They were built in one pass because they share
one emission path and one frontend subscription, and because each is a claim made to an audience
watching the screen — which is the only thing they have in common that matters.

The rule they are all built to is the same rule the Direct Line client's deadline is built to: **a
surface may say nothing, but it may not say something that is not so.** A panel that goes dark is a
missing feature. A panel that lights up for an answer that did not happen is a lie told to a
customer in a room.

| Signal | Emitted from | Builder | Surface |
| --- | --- | --- | --- |
| `source_used` | `POST /api/v4/sop/ask`, after the Direct Line reply | `transparency/source.py` | Grounding panel (R6) |
| `token_usage` | the `executor_completed` branch of `_process_event_stream` | `transparency/tokens.py` | Token meter (R7) |
| `presenter_alert` | `POST /api/v4/presenter/alert` (hidden) | `transparency/alert.py` | Presenter alert (R8) |

The payloads are dataclasses in `src/backend/transparency/payloads.py`, not in
`models/messages.py`. That is partly ownership — the package that decides what a signal may claim
owns the shape of the claim — and partly survival: `test_orchestration_manager.py` replaces
`sys.modules['models.messages']` with a `Mock` at import time, so a payload defined there is a
`Mock` attribute in every test collected after it.

## Source used

`source_used(reply)` reads the `/sop/ask` reply dict and returns a `SourceUsed` or `None`.

It carries `platform` and not only `source`. "Dataverse" alone does not distinguish the
cross-platform hop from any other retrieval, and the claim R6 exists to make is that *this one
answer left Foundry*.

**A failed reply emits nothing.** When the Direct Line client gives up it returns
`DIRECT_LINE_FAILURE` with `failed=True` — the backend's own fixed wording, chosen in #18 precisely
so that a timed-out generation cannot wear the agent's voice. Lighting the Grounding panel for it
would undo that in the other direction: crediting Copilot Studio, on screen, with an answer it never
gave.

**A successful answer with no citations does emit.** That is the rehearsed out-of-corpus probe —
the honest miss. The agent ran, the hop happened, and nothing came back. The panel showing the route
with an empty citation list is the beat, not a bug, and suppressing it would delete the
demonstration.

The two are different facts and the code keeps them different. `failed` decides; the citation count
does not.

## Token usage

Net-new. The MACAE baseline emits no token telemetry at all, so `transparency/tokens.py` is the
whole of the meter's supply.

The counts are read by **duck typing**. `agent_framework` is stubbed in the backend test suite, so a
reader written against `isinstance` would be testing the stub rather than the framework. The shape
read is the framework's own: a content whose `type` is `"usage"` carrying a `usage_details` mapping
keyed `input_token_count` / `output_token_count` / `total_token_count`. The older OpenAI vocabulary
(`prompt_tokens`, `completion_tokens`) is accepted too, because some clients still report it.

Usage can sit in three places on one completion payload, and `_candidates()` returns **the first
that has a number**:

1. the item's own `contents`, where a `"usage"` content sits on a `ChatMessage`;
2. an `AgentExecutorResponse`'s wrapped `agent_response` — what an `AgentExecutor` actually sends,
   and where the framework accumulates usage having *stripped it out of* the message contents when
   streaming;
3. the item itself, which is where an `AgentResponse` carries it.

Reading all three double-counts the same cost. A meter that doubles is as wrong as one that reports
nothing, and this one gets quoted at a customer.

**No usage reported means no event.** Not a zero. A zero on the meter reads as *this agent was
free*, which is a claim, and it collides head-on with R7's guardrail column — a refused request adds
nothing to the meter — where **nothing has to be the only thing that looks like nothing**. If a
guardrail refusal and an unreported cost both render `0`, the row that proves the guardrail is free
proves nothing.

The absence is logged at debug rather than passed over in silence:

```
[TOKENS] <executor_id> completed with no usage reported
```

That line exists because of something **not verified live**: upstream,
`StandardMagenticManager._complete()` returns `response.messages[-1]` and drops
`AgentResponse.usage_details` on the way, so the orchestrator's own cost may never reach the event
stream at all. The emission branch treats the manager like any other executor; whether the framework
gives it anything to emit is a question the first real run answers, and the log line is how it
answers.

Attribution is by **executor identifier**, formatted through the same
`format_agent_display_name` the streaming header already uses. That is the attribution that survives
Plan review being off: on the Fast lane there is no plan object to read an agent name out of, and a
meter that emptied whenever the demo took its fast path would be empty for most of the walkthrough.

## Presenter alert

`POST /api/v4/presenter/alert`, registered with `include_in_schema=False`.

Hidden, because the audience is looking at the same screen: the beat only works if the control is
invisible and unguessable. There is **no wall-clock timer** anywhere on this path — the alert has to
land while the presenter is talking about it, and a timer lands it whenever the timer says so, which
on stage is an interruption rather than a demonstration.

Hidden is not authenticated, so the route is built so that being found costs little:

- **The words are the server's.** The body names one of a rehearsed roster in
  `transparency/alert.py`; there is no parameter that accepts prose. An unrecognised name is the
  default alert rather than an error, because a mistyped chord on stage should still produce the
  beat.
- **The recipient is the server's.** See below.

The worst an uninvited caller achieves is a rehearsed shift-task alert appearing early.

Unlike the Grounding panel's push, this route **reports failure**. `404` when nobody is connected,
`502` when the socket refused the write. The presenter pressed a key; being told nothing happened is
the difference between a bug and a chord that missed.

## Resolving the recipient

Both out-of-band pushes have the same problem: nothing asked for them, so there is no request-scoped
user to answer to. `/sop/ask` is called by the MCP container, which has no user at all.

`ConnectionConfig.sole_user()` returns the connected user when there is **exactly one**, and `None`
otherwise. It never picks between two.

It is deliberately **not** the caller-supplied `user_id` that `ask_user` takes. That path has an LLM
copying a UUID out of context, and a mis-copy there costs a clarification prompt; a mis-copy here
darkens the demo's centrepiece panel, or pushes one associate's provenance onto another's screen
through a bridge reachable without credentials. Both routes read the connection registry and nothing
else — and both have a test that fails if a `user_id` is ever plumbed back in.

`send_status_update_async` now returns whether it reached a socket. Every pre-existing caller
ignores the answer, which is right for them: a lost streaming chunk is not worth a branch. The alert
route is the one caller that needs it.

## Tests

- `src/tests/backend/transparency/` — the three builders as the pure functions they are.
- `src/tests/backend/orchestration/test_orchestration_manager.py` — the emission, driven from the
  existing `_make_event` factory and `_async_iter` helper, asserting on the recorded
  `send_status_update_async` calls.
- `src/tests/backend/api/test_router.py` — both routes through the shared `TestClient`.
- `src/tests/backend/orchestration/test_connection_config.py` — `sole_user()` and the delivery
  report.

Mutation-checked: emitting for a failed reply, suppressing an uncited answer, removing the emission,
returning a zero instead of `None`, reading every candidate level, `sole_user()` guessing between
two connections, either route trusting a caller-supplied `user_id`, `presenter_alert` accepting
prose, the alert route ignoring the delivery report, and `send_status_update_async` always claiming
delivery — each turns specific tests red.

## Not verified live

- Whether the framework reports the **orchestrator's** own usage (see above).
- Whether participant executors' `executor_completed` data arrive as messages or as
  `AgentExecutorResponse`s in the pinned version. The extractor handles both, but only one of them
  has been seen.
- The rendering of any of this. #24 owns the panels, and every assertion here is on what the backend
  sent.
