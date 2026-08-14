# The Routing probe

Issue #54's residual, made measurable. `scripts/routing_probe.py`, behind
`bash scripts/measure-routing.sh`, drives the centrepiece Fast-lane turn — *"How do I close the
store?"* — against a running deployment over plain HTTP and the transparency WebSocket, with **no
browser**, N times, and reports which agents took part and at what rate.

It is not a feedback loop and must not be added to a workflow. It holds N live conversations with
the deployed agent pool and spends Copilot Credits and Foundry tokens on every sample, for the
Demo validator's reason multiplied by N. Its pure half — the grading, the report and the drain's
end condition — is unit-tested by `src/tests/ci/test_routing_probe.py` in the CI-tooling loop, so
what *can* be asserted without a tenant is.

```bash
az login
bash scripts/measure-routing.sh                # 12 turns, one at a time, about 25 minutes
bash scripts/measure-routing.sh --samples 3    # a quick read
```

Exit codes: `0` every observed turn was clean, `1` at least one was not, `2` nothing was observed at
all — which is a state to fix, not a rate to measure.

## Why it exists

AC3 of #54 — the beat passing the Demo validator ten consecutive times — was unmet for seven
iterations, and the residual was known: the `Troubleshooting Agent` taking part in a question with
nothing broken in it. Seven prompt clauses were forked on `minimal_plan` chasing it. Each cost a
twenty-minute deploy, each reduced the rate, and none removed it, because **the only instrument
that could see the fault was a browser suite that stops at the first red run.** A rate cannot be
measured one run at a time.

`bf7792a7` is the precedent and the argument: the honest miss was chased through the orchestrator
for six iterations and found in one afternoon by asking the *agent* directly, sixty-nine times.
This is the same move one layer up — ask the *backend* directly, many times, with nothing rendering
in between.

## What one sample does

A fresh principal and a fresh session per sample, which is this probe's equivalent of the fresh
Direct Line conversation `check-sop-agent.sh` samples in: the workflow cache, the active
orchestration task and the session's rehearsal marker are all per-user.

1. `POST /api/v4/select_team` — the Store Assistant team, read out of
   `content_packs/store_assistant/agent_teams/store_assistant.json`.
2. Connect the WebSocket **before** the request. `send_status_update_async` addresses a socket by
   *user*, and the `{process_id}` path segment is only a key in a second map — so the probe closes
   the connect window ADR-021 narrowed for the browser entirely, rather than racing it.
3. `POST /api/v4/process_request` with the rehearsed quick task, `lane: fast`.
4. Drain every frame until the turn is over, and grade what arrived.

**The WebSocket is the only server-side observation of a turn.** `GET /api/v4/plan` returns what the
*browser* posted back through `/api/v4/agent_message`; a headless probe polling it watches
`in_progress` and an empty message list forever. That is worth knowing before building any other
instrument against this backend.

## What it grades, and why the vocabulary is not new

The four outcomes are `e2e/evidence.ts`'s and `scripts/sop_rehearsal.py`'s — `grounded`,
`honest-miss`, `no-tool-call`, `clarified` — plus `not-observed` for a sample whose socket carried
nothing. A fifth name for the same four things is how two instruments end up disagreeing about a
run they both saw.

One grading rule decides every count in the report, the lesson `sop_agent.py` and then
`deployed_surface.py` each paid for once. Every fault of a turn is reported rather than the first,
because they send a reader to different layers: a turn that asked a question back *and* billed the
troubleshooter is one fault's cause beside its effect, and a turn that asked back with only the
procedure agent billed is a different bug in a different place.

**Billed is not spoken, and the report separates them.** An unneeded agent the manager invoked and
an unneeded agent that reached the presenter's screen implicate different halves of the same layer.
The browser only ever saw the second, because the first is invisible on the surface.

The denominator is **turns observed**, not requests sent: a replica restarting under the probe is
not evidence about the routing, and dividing by it reports a rate partly about the probe's own luck.
And as everywhere else in this repository, the green row says what it is *not* evidence of — the
smallest per-turn fault that many samples is likelier than not to catch.

## Two things the probe had to get right about itself

Both were measured, and both would have produced a confident report of the deployment's own fault.

**It is serial, and that is not a throughput decision.** `_push_source_used` — the Grounding panel's
own frame — resolves its recipient server-side, and until this probe existed that resolution was
`sole_user()`: *the* connected user, when there is exactly one. The probe's first run took two
samples at once and reported `no-tool-call` on **2 of 2** against a deployment that answers the same
question from the corpus on nearly every serial one. `collect` now takes one turn at a time, closes
each socket with a real WebSocket close frame rather than slamming the TCP connection, and waits
`BETWEEN_SAMPLES_SECONDS` for the backend to unregister the last one — because a close the backend
has not noticed is still a second registered user, and therefore a false fault on the *next* sample.

**Quiet counts only after the meter has fired.** There is no `final_result_message` on the Fast
lane: a complete rehearsed turn pushes several hundred streaming chunks, one `source_used` and one
`token_usage` per executor, and nothing that says *done*. So the turn ends on quiet — and the quiet
window has to be generous, because the manager is a reasoning model that streams nothing while it
decides who speaks next, and **that gap is where the residual lives**. A probe that settled in eight
seconds would cut the recording immediately before the troubleshooter's turn and report a clean rate
for the fault it was built to measure. It cost a sample before it was fixed: one 12-sample run
graded a turn `no-tool-call` on the strength of a single frame — the header the backend streams
before an agent's content — followed by more than thirty seconds of thought.

## What it found

Against build `8f0b77c7`, twelve serial samples:

```
   10  grounded
    2  no-tool-call
  FAIL  Troubleshooting Agent took part in 2 of 12 turns, on a question with nothing broken in
        it, and spoke on 2 of them
```

The residual reproduces **without a browser, in about two minutes a sample**, which is what seven
iterations of guessing did not have.

The two `no-tool-call` samples were the probe's own, and finding out cost one deliberate experiment
rather than one deploy — which is the whole argument for the instrument. A **positive control**: one
sample taken with a single idle bystander socket registered alongside it.

```
  "outcome": "no-tool-call",
  "agents_billed": ["Shift Tasks Agent"],
  "citations": [],
  "answer": "Here's the Store 223 closing procedure from **SOP-102 Store Closing Procedure**:
             1. At 60 minutes before close, begin the coffee bar shutdown ..."
```

The retrieval worked and the panel went dark. That is a **stage hazard, not a probe artefact**: a
presenter's second tab, a colleague's screen, or a reconnect the backend has not noticed closing yet
is enough to darken the demonstration's centrepiece panel on a turn that retrieved and cited
`SOP-102`, for a reason nothing on the screen explains. So `_push_source_used` now asks the sharper
question first — `sole_turn()`, the one user with a request *in flight*, which was already being
asked one module away for the troubleshooting tools — and falls back to `sole_user()`. Both refuse
to guess between two, so the recipient is still resolved server-side and is still never a UUID a
model copied; they differ only in what they count, and **a connection is not a question**.

## Evidence

Every run appends one line per sample to `e2e/artifacts/routing-evidence.jsonl` — the graded facts,
not the frames: the outcome, the fault, which agents were billed and which spoke, the wording that
actually reached the SOP tool, the citations, and the first 600 characters of the answer. Appended
rather than replaced, because the rate is a property of a *series* of runs and a file holding only
the last one cannot show a fix taking effect.

## What it cannot see

It observes frames **pushed**, not a surface **rendered**. A frame that arrives and renders wrong is
invisible here, and the Demo validator remains the proof of the beat. This instrument only points it
at a layer.

It also cannot run beside a real browser on the same deployment: with the presenter's socket
registered too, the fallback resolution is ambiguous and frames can be misattributed. Run it against
a deployment nobody is watching.
