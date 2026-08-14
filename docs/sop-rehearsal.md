# The rehearsal: proving the centrepiece beat

The walkthrough opens with *"How do I close the store?"*, answered from the SOP corpus by a
**Copilot Studio** agent out of **Dataverse**, with the document named on screen. It is the beat the
architecture claim rests on, and on the afternoon the Demo validator first ran it came back as the
**honest miss** two runs in eight (#47).

This is the record of what was measured, what each measurement ruled out, and what closed it.
Issue #54.

## Why measurement came first

Three layers could each have produced that symptom, and each has a different fix:

| Layer | Fix if it is this one |
| --- | --- |
| The orchestrator's **routing** | Change how the plan is built. |
| The orchestrator's **rephrasing** | Change what the tool is asked. |
| The agent's **Dataverse index** | Change the corpus, or reindex it. |

Nothing in the repository recorded which. `check-deployed-surface.sh` was green on every attempt
across the same afternoon, which read as *the grounded answer works* and quietly removed the third
possibility from consideration — wrongly, because that check asks the corpus's own wording straight
at `/api/v4/sop/ask`, with no orchestrator in front of it. It is now named `direct-sop-answer` for
exactly that reason, and its green report names this rehearsal rather than implying a working
walkthrough.

So the first change was not a fix. Every validator run appends one row to
`e2e/artifacts/sop-evidence.jsonl` — what the orchestrator handed `search_store_procedures`, what
the backend retrieved against, whether the Grounding panel lit, whether the answer was the honest
miss, what it cited, and whether the run was green. **Passing runs are in it too**: two-in-eight is a
property of a sequence and the denominator is the runs that worked.

`scripts/sop_rehearsal.py` is the arithmetic over those rows, and
`src/tests/ci/test_sop_rehearsal.py` holds it to its contract without a tenant.

## What the ledger showed

**The rephrasings are unbounded.** Two runs on 2026-08-14 produced two wordings never seen before:

> Please look up Store 223's official closing procedure in the Store SOP Assistant on Copilot Studio
> and return the quoted SOP guidance for closing the store, including the required order of tasks.

> Please look up the Store 223 SOP for closing the store and provide the step-by-step closing
> procedure, including any relevant quotes or the SOP document it came from.

Both differ from all eight recorded earlier. An earlier fix — an alias `frozenset` of observed
rephrasings — was correct about the mechanism and wrong about the shape of the problem: there is no
list to complete. It was replaced by a **one-shot, session-scoped marker**
(`src/backend/sop/rehearsal.py`): `/process_request` arms the exact presenter question, and the next
SOP tool call in that turn retrieves against the corpus's wording whatever the model wrote. Both runs
above retrieved correctly.

**The marker is armed by an exact question and disarmed by anything else.** That is what keeps the
**honest miss** honest: the presenter taps "Restart the car wash" seconds later in the same session,
and a marker still set would answer a car-wash question with the closing checklist. One-shot alone is
not enough — the hit's own turn may never reach the SOP tool — so any other request calls
`forget_rehearsal`.

## What the ledger could not name, and now can

The second run was **red with the answer on the page**. Its Grounding panel named Copilot Studio,
reported Dataverse and cited `SOP-102 Store Closing Procedure.docx`. Every provenance assertion
passed. The beat failed waiting for a paragraph in the agent's turn — because the turn was not an
answer. It was the Group Chat Manager asking back:

> What is stopping Store 223 from closing right now?
>
> For each blocker, what have you already tried — for example checking a display/status, trying the
> door or alarm again, or confirming the console message?

The attributor said `unknown`, which was correct and useless: nothing in the ledger could tell that
run from a broken selector, and the failure message — "no paragraph rendered" — sent the reader to
the harness. A clarification renders as a list, not a paragraph.

There is now a `clarified` outcome, checked before `grounded` is reported because it is the outcome
that hides inside a success, and the spec fails it **by name** before the emptiness it also produces.

## The cause: mandatory agent inclusion

`get_magentic_prompt_kwargs` injects a `MANDATORY AGENTS (CRITICAL — NON-NEGOTIABLE)` clause built
from every agent on the team, requiring each to appear as its own plan step. It is inherited from the
accelerator, where it earns its keep: on a coordinator/compliance team, a plan that silently dropped
the TriageAgent or the ComplianceAgent was the bug it was written for.

The store team's three agents are **alternatives, not a pipeline**. Troubleshooting, shift work and
escalation are three different jobs, and a procedure lookup is one of them. Forcing all three into
the plan makes the Troubleshooting Agent a required step, and its job is to ask what you have already
tried. So it asks. The failing run's cost table shows the Shift Tasks Agent and the Troubleshooting
Agent both billed for a question that needed one SOP tool call.

The fix is opt-**out**, not opt-in: `require_all_agents` defaults to `true`, so every team that
predates the flag keeps the behaviour it was configured under, and
`content_packs/store_assistant/agent_teams/store_assistant.json` sets it `false`.

The field is carried explicitly through `TeamService.validate_and_parse_team_config`, because that
method builds `TeamConfiguration` field by field and drops anything not named — the same silent drop
that had already cost the Quick Task lane (#16) and the rehearsed replies (#26). A routing flag that
reaches the repository but not Cosmos is a fix that passes its own tests and changes nothing, so
there is a round-trip test from the authored pack through the real validator.

## The flag reaches Cosmos, and is still not read

Carrying `require_all_agents` through the validator was necessary and not sufficient. The store team
is `is_default`, and `delete_team` refuses to delete a default team; `upload_team_config.py` warns
and uploads anyway, writing a **second document with the same `team_id` under a new partition key**.
Every deploy since the pack was authored had left another one behind. Asking the deployment directly,
the morning the routing fix landed:

```
$ curl -s "$BACKEND/api/v4/team_configs" | ...
00000000-...-223 | Circle K Frontline Store Assistant | require_all_agents= False
00000000-...-223 | Circle K Frontline Store Assistant | require_all_agents= True
00000000-...-223 | Circle K Frontline Store Assistant | require_all_agents= True
00000000-...-223 | Circle K Frontline Store Assistant | require_all_agents= True
00000000-...-223 | Circle K Frontline Store Assistant | require_all_agents= True
00000000-...-223 | Circle K Frontline Store Assistant | require_all_agents= True
```

Five predate the field, so the backend defaults them to on. `get_team` selected `teams[0]` from an
**unordered** query, which made the routing fix a one-in-six chance of being the one Cosmos handed
back first — and non-reproducible either way, because nothing in the repository decides it. The query
now ends `ORDER BY c._ts DESC`.

That is a read fix, not a cleanup: the duplicates are still there, and the next deploy adds another.
It is safe because the newest is always the one this repository just wrote, and it is *visible*
because `check-deployed-surface.sh` now carries a `mandatory-agents` row that asks the deployment
what flag it is actually running under. A revert, a stale read, or a team document that predates the
field fails the deploy gate rather than the walkthrough.

## Running the proof

```bash
az login
bash scripts/sop-rehearsal.sh              # ten runs, stops at the first red
bash scripts/sop-rehearsal.sh --runs 3     # a shorter look
```

Ten, because nine is what an intermittent beat produces often enough to be believed. The harness
stops at the first red run and names the layer that run implicates, so a broken streak costs one run
rather than ten. It runs `scripts/e2e-tests.sh` repeatedly rather than `--repeat-each`, which the
walkthrough reporter treats as a filter and which would leave the **Recorded fallback** stale.

**It is not a feedback loop and must not be added to a workflow** — the Demo validator's own rule
(`docs/demo-validator.md`) multiplied by ten. It drives a real browser through ten live conversations
with the deployed agent pool. `src/tests/ci/test_e2e_wiring.py` fails if a workflow ever runs it.

A presenter's own rehearsal leaves the same trace: `/sop/ask` logs both strings on every call, so
`az containerapp logs` answers "what did the orchestrator actually ask?" without the validator.

## Reading a red run

The report names one of four layers:

- **the orchestrator's routing** — no tool call at all, or a grounded answer behind a clarification.
- **the orchestrator's rephrasing** — Dataverse was searched for the model's own wording, which means
  the marker did not fire. Check that the tapped Quick Task's prompt is still exactly
  `[rehearsed_hit].question`; the marker is armed on an exact match, deliberately.
- **the agent's Dataverse index** — the corpus's own wording was retrieved against and missed. The
  expensive one, and the only one that means the demonstration's *content* is wrong.
- **unknown** — the evidence does not reach a layer, and the harness says so rather than guessing.
  Read `e2e/artifacts/report` and the run's `error-context.md`.
