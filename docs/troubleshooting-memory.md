# The memory of one shift

Issue #21. An associate reporting *the coffee machine is down* is asked what they have already
tried, and the assistant **never walks them through the same failed step twice**.

The rule this iteration is built to is the one #23 through #25 were built to — *a surface may say
nothing, but it may not say something that is not so* — applied to **memory**. A record that says
nothing was tried offers the whole runbook and costs the associate one repeated line. A record that
says a step was tried when it was not means that step is silently skipped, and the equipment stays
broken. Every decision below runs one way for that reason.

## What is where

| Piece | Where | What it is |
| --- | --- | --- |
| Attempted step | `troubleshooting/steps.py` | Pure. Reads discrete steps out of what an associate typed, decides when two wordings are one step. |
| Troubleshooting record | `common/models/messages.py`, `troubleshooting/store.py` | One `DataType` member and one model in the schemaless memory container. No migration. |
| Current turn | `troubleshooting/turn.py` | Process-local note of which session a user's request in flight belongs to. |
| The bridge | `GET`/`POST /api/v4/troubleshooting/attempted` | What the MCP container calls. |
| The tools | `src/mcp_server/services/troubleshooting_service.py` | `list_attempted_steps`, `record_attempted_steps`, on the `troubleshooting` domain. |

## The record is written where the answer arrives, not where a model remembers to write it

Framework checkpoint state is in-memory and must not be relied on, so the acceptance criterion is
that attempted steps are persisted **explicitly**. The seam where an associate actually reports what
they tried is `OrchestrationManager._handle_tool_approvals` — the manager already intercepts the
clarification answer there, before approving the tool, to hand it to the tool body. Persisting at
that seam means the record is written on **every** clarification turn, whether or not the agent
remembers to call anything.

The same seam carries the record back. `_remember_attempted_steps` appends the note to the answer it
stores, and the tool body returns exactly what was stored — so an agent cannot proceed from a
clarification without having been told what it must not repeat. Fetching it would have been a tool
call the model could skip.

Both halves swallow failure. The record is the memory of one shift; the answer is the associate's.
An unreachable container costs a repeated step, and raising there would cost the turn.

## The session is resolved server-side

Nothing on the wire between the MCP container and the backend names a session or a user. Neither
tool takes one and neither route reads one.

`ask_user`'s pattern has a model copying a `SESSION_USER_ID` line out of its instructions. A mis-copy
there costs a clarification prompt. A mis-copy here writes one associate's attempted steps onto
another associate's fault, or reads back steps nobody on this shift tried and skips a real runbook
branch. So the request path leaves a note (`note_turn`) and the bridge resolves it (`sole_turn`),
which is the rule `connection_config.sole_user()` already records: **exactly one, or nothing, never
a choice between two.**

That is the third of the three constraints issue #21 names as acceptable for a single-presenter demo
and unacceptable for production. It is stated out loud rather than engineered around. The other two
are the framework's: at most one clarification call per turn, and a 300-second wait.

**A note expires.** `TURN_TTL_SECONDS` is 900 seconds — comfortably longer than the 300-second
clarification wait a single turn can contain, and bounded, because without an expiry one stray second
user reaching the process would leave two notes standing forever and `sole_turn` refusing for the
rest of that process's life.

## Two wordings, one step

`already_attempted` matches on the content words two steps share, stemmed and order-insensitive,
because a runbook says *Power cycle the brewer at the wall switch* and an associate says *turned it
off and on again*.

Its requirement runs **one way only**, like the lane keyword fallback's and the guardrail keyword
fast path's. It may miss — the associate says so again and the record grows, costing one wasted line
— but it may never claim a step was attempted that was not. Hence:

- **Containment on a single shared word is refused.** *Check the drip tray* and *checked the water
  line* share only *check*.
- **A denial records nothing.** *Nothing yet* is an answer to the question, not a step.
- **A substituted answer records nothing.** When the clarification path times out it substitutes its
  own words; those are the backend's, not the associate's.
- **An empty step is never recorded.** It would compare equal to every runbook step and skip the
  whole runbook.

## Why the troubleshooting agent may hold a knowledge base *and* a toolbox

`ShiftTasksAgent` holds `search_store_procedures` and deliberately has no Foundry knowledge base at
all: an agent holding two sources that both answer *the same question* chooses between them turn by
turn, and the branch it does not take is the cross-platform hop the demonstration rests on.

That reasoning does not reach here. `list_attempted_steps` and `record_attempted_steps` ground
nothing. They answer *what has this associate already tried*, which the runbook knowledge base cannot
answer and which cannot answer an equipment question. There is no branch to take, so there is nothing
for the agent to choose between. `src/tests/ci/test_store_pack.py` asserts both readings — one holder
for each tool, and only the SOP tool's holder stripped of its knowledge base.

## Escalation is a property of the record

`escalation_due` is the predicate: three or more distinct attempted steps and the shift is unlikely
to fix this. Below that, an offer to raise a ticket reads as the assistant giving up after one try,
which is the opposite of the beat. The note the agent reads carries the instruction to offer a
service ticket only once the record is over that line, so the offer is triggered by what actually
happened rather than by a model's mood.

#22 picks the record up from there: `TKT-001`'s `steps_attempted` field is the `attempted` list, in
the associate's own words, never re-typed.

## The MCP container still has no Cosmos access

No connection configuration, no credentials, no dependency. It reaches the record over HTTP through
the `BackendClient` seam, which gained a `get_json` for the read half — a GET because the request
carries nothing at all. `test_troubleshooting_service.py` asserts that against the module's **imports**
and the container's `pyproject.toml`, not against its prose, which names Cosmos on every second line.

## Not verified live

- Nothing here has run against a deployment. The `troubleshooting` domain server is asserted to be
  mounted by reading `Domain`, not by connecting to it.
- Whether a real `gpt-5.4` turn actually calls `list_attempted_steps` first is instructed, not
  measured. The deterministic half — the record written and returned at the clarification seam —
  is what does not depend on that.
- The step matcher has been driven against written examples, not against what an associate types on
  a phone mid-shift.
