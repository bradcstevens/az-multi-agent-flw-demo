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
list to complete. It was replaced by a **turn-scoped, session-scoped marker**
(`src/backend/sop/rehearsal.py`): `/process_request` arms the exact presenter question, and every
SOP tool call in that turn retrieves against the corpus's wording whatever the model wrote. Both runs
above retrieved correctly.

**The marker is armed by an exact question and disarmed by anything else.** That is what keeps the
**honest miss** honest: the presenter taps "Restart the car wash" seconds later in the same session,
and a marker still set would answer a car-wash question with the closing checklist. So any other
request calls `forget_rehearsal` — including one that arrives while the hit's own turn is still in
flight, and one that follows a turn which never reached the SOP tool at all.

### It was one-shot, and one-shot was a latent failure of the centrepiece

Reading the marker was a `pop` until 2026-08-14, which spent it on the **first**
`search_store_procedures` call of the turn. The Grounding panel is a claim about whichever SOP call
answered **last**, so a second lookup in the rehearsed turn retrieved against the raw rephrasing and
overwrote a correct retrieval with whatever that returned — the beat failing with nothing in the
panel to say which call it was showing. Only the Shift Tasks Agent holds the tool today, so it takes
one agent calling it twice; that is a routing accident away, not an architecture change away.

Consuming the marker was never what kept the honest miss honest — `forget_rehearsal` is. So the read
stopped consuming, and the marker's bound moved to **the end of the turn that armed it**, in
`run_orchestration_task`'s `finally`. Two things follow from putting the disarm there, and both were
found by review rather than by the tests:

- **Arming is now the last thing `/process_request` does**, immediately before the orchestration task
  is scheduled, while disarming stays the first. A request that failed earlier — Cosmos refusing the
  plan, the workflow refusing to build — would otherwise strand an armed marker for the full
  900-second TTL, and the next SOP question in that session, honest miss included, would come back as
  the closing checklist. Both failure directions are now the safe one.
- **The disarm is held to the turn's own token.** `/process_request` cancels the prior turn and gives
  it one event-loop iteration to unwind before arming — one iteration, not a guarantee. Without the
  token, a cleanup that took longer would clear the marker of the turn that cancelled it: the
  presenter asking the rehearsed question twice, and the beat working only the first time.

The 900-second TTL stays as the bound for a turn that never reached its `finally` at all.

**What the marker cannot tell apart, stated rather than engineered around.** `sole_turn()` resolves
the session from the one user with a request in flight, so a *direct* `/api/v4/sop/ask` call is
indistinguishable from the orchestrator's tool call and is canonicalised too if it lands inside a
rehearsed turn. One-shot narrowed that to the first such call, not to none of them — and for the case
#54 is actually about the turn-scoped bound is the *shorter* one, because a rehearsed turn that never
reached the SOP tool used to leave the marker standing until the session's next request. No check
probes `/sop/ask` with a question the corpus cannot answer: `check-deployed-surface.sh` asks the
corpus's own wording, and `check-sop-agent.sh`'s out-of-corpus probe goes through Direct Line.

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

## The residual: the troubleshooter interrogating a question with no fault in it

Turning the flag off did most of the work — six consecutive green runs, where the same beat had been
failing two in eight. Run 7 failed anyway, `clarified`, and the ledger has what it said:

> Which equipment is blocking closing right now: coffee brewer, hot food case, fuel dispensers,
> walk-in cooler, self-checkout, handhelds, or something else?

Nothing was blocking closing. Nothing was broken at all. `require_all_agents: false` lets the manager
plan one step; it does not stop it planning two, and on run 7 it put the Troubleshooting Agent in the
plan beside the Shift Tasks Agent. The lookup still worked — Copilot Studio, Dataverse, SOP-102 — and
the turn the presenter would have been standing in front of was the interrogation.

The instruction to hand procedures over was already in the troubleshooter's system message. It was
the **last line**, four paragraphs after *"Before you give steps, ask the associate what they have
already tried… list two or three likely things so they can answer quickly"* — which is precisely the
sentence that produced the equipment menu above. The model reached the interrogation first because
the interrogation came first.

So the fix is ordering, in prose: deciding whether anything is broken is now the agent's **first**
instruction, with the tools and the runbook search explicitly off the table when nothing is, and the
"what have you tried" rule is conditioned on a reported fault. `test_store_pack.py` pins the order
rather than the words, because appending the deferral back at the bottom is the exact regression and
would leave every other assertion in that file green.

That this was findable at all is the ledger's doing. A single red Playwright run says the beat is
flaky; the ledger says it is flaky at run 7 of 10, with the retrieval green and the clarification
verbatim, which names one agent's system message.

## The second residual: "one step per agent" is read as a template

Reordering the troubleshooter's instructions was not enough either — the next rehearsal failed at
run 1, same outcome, and the cost table is what said why:

| Agent | Model | Calls | Tokens |
| --- | --- | --- | --- |
| Store SOP Assistant | — | 1 | — |
| Shift Tasks Agent | gpt-5.4-mini | 1 | 3,888 |
| Troubleshooting Agent | gpt-5.4 | 1 | 6,911 |

The troubleshooter was still *in the plan*. Its system message is not what put it there, so no edit
to that message could have taken it out — and an agent handed a step by the manager does the step it
was handed, whatever its own instructions say about deferring.

`PLAN RULES` was the reason:

> Steps are HIGH-LEVEL task assignments — **one step per agent**.

That sentence means *at most* one step each. A manager reads it as a template: one step, per agent.
With the MANDATORY AGENTS clause removed there was nothing left saying a shorter plan was allowed, so
it kept producing the same three-step plan the clause used to compel.

So `minimal_plan` replaces the rule for a team that opts out, saying the thing that was never said:
include only the agents whose description names the job being asked for, a one-step plan is complete,
and do not add an agent because it might be tangentially relevant. The reason is stated in the prompt
too, because it is the part a manager cannot infer — an unneeded agent does not sit quietly; it does
its own job on a request that did not ask for it, and the user is answered by the wrong specialist.

`plans_minimally` is a separate pure function from `mandatory_participants` rather than an inline
`not required_agent_names`, because these two clauses failed **independently**: removing one left the
other doing its work, and a reader of either one alone would conclude the team plans minimally when
it does not.

## The third residual: the loop goes looking for someone unused

Minimal plans did not settle it either — six green, red at run 6, and the cost table again showed the
Troubleshooting Agent billed on a question with nothing broken in it. Which was the useful part: the
plan was not the thing still putting it there.

Magentic does not run a plan and stop. Each round it asks the **progress ledger** who should speak
next, and the inherited execution rule is:

> When selecting next_speaker, **prefer a work agent that has NOT yet been invoked.**

That rule is not scoped to the plan. So after the Shift Tasks Agent answered, the next round went
looking for an agent that had not spoken, and found the troubleshooter. This is why the two earlier
fixes each *reduced* the failure rate without removing it: they changed how the plan was built, and
this clause operates after the plan is built.

On a pipeline team the rule is exactly right — an agent that has not run yet is the one the plan is
waiting on. Under `minimal_plan` it is replaced by its opposite: select only an agent whose own
description covers what was asked, and do not select one because it has not been invoked yet.

The first attempt at that replacement said *"select only from the agents in the **approved** plan"*,
and it did not work either — because the rehearsed beat runs in the **Fast lane**, where
`enable_plan_review=False` and nothing is approved at all. A rule conditioned on an approved plan is
a rule the manager can read as not applying. The wording now names what the *user asked for*, which
exists in both lanes.

Underneath it, the COMPLETION CHECK was saying the same thing again in a different voice:

> If ANY plan-step agent has NOT been invoked and produced a substantive response, set
> is_request_satisfied to false and **select the next uninvoked agent as next_speaker**.

Two clauses, thirty lines apart, one telling the manager not to reach for an unused agent and the
other telling it to. Under `minimal_plan` the completion check now ends on what the user asked for
rather than on the roster.

Four clauses, one inherited assumption — *every agent on the team runs on every request* — expressed
in four places that fail independently. Each was found the same way: a red run, a cost table showing
the troubleshooter billed, and a search for what put it there. The order they were found in is the
order the ledger found them, which is the argument for the ledger.

The ledger now records **which agents were billed** for each run, because guessing between "the
troubleshooter must not run" and "the troubleshooter must not have the last word" is what cost three
of those deploys.

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

## The proof has to name the build it proved

Ten green runs against *which* build? Until this the rehearsal never said, and could not have: the
ledger row carried the commit the **harness** ran from, which is explicitly not the deployed build.

The Demo validator dates the deployment before a browser opens (#48, [ADR-018]) — but there are two
signposted ways past that gate, and both of them are right. `--target local` runs the same specs
against a `npm run dev`, which dates no deployment at all. And the gate's own failure message ends:

> To go anyway — knowing the beats are about another build — set `E2E_SKIP_BUILD_CHECK=1`.

Which is correct for the **Stage driver**: a refusal to start, mid-demonstration, over a one-commit
drift is the check doing more harm than the drift it found. It is a lie in a *rehearsal's* ledger.
A run under that flag appended a row indistinguishable from a verified one, and ten of them printed
**the beat is proved** — about a build nobody could name. That is this issue's own failure mode
wearing the harness's clothes: the proof and the thing being proved were about different questions.

So the gate now publishes what it verified — one `check-deployed-build.sh --json` read, whose payload
carries the commit *and* the rendered report, so the human text and the machine answer come from a
single `az` call and `format_report` is never given a second opinion in TypeScript. Every ledger row
records `deployedBuild` and `buildVerified`, and `provenance` refuses three streaks the arithmetic
used to accept:

| The streak | Why it is not a proof |
| --- | --- |
| A run that skipped the gate | Whatever those runs are about, it is not a build this rehearsal can name. |
| Ten runs against a local surface | They prove the harness. The claim is about the deployment. |
| Ten runs spanning two builds | `deploy-main.yml` runs on every push to `main`, so this is not hypothetical. Ten green runs across two builds is two rehearsals of five, and neither is the proof. |

A row from a harness older than the fields counts as none of these and as no proof either, which is
ADR-018's rule inherited: an unproved build is not a passing one.

The verdict prints the commit on the line that says the beat is proved, because the sentence was
never complete without it:

```
  ----  the rehearsed hit answered from the corpus 10 consecutive times
        against 03a80ef18183: the beat is proved
```

[ADR-018]: ADR/018-deployed-build-provenance-check.md

## The meter was read a frame too early

The first run that could name its build came back `clarified` — the hop worked, `SOP-102` was cited,
and then the surface asked the presenter three troubleshooting questions back. Its ledger row said
`agentsBilled: ["Store SOP Assistant"]`. Its own DOM snapshot, from the same run, showed a cost table
with three rows: `Store SOP Assistant`, `Shift Tasks Agent` at 4,032 tokens, `Troubleshooting Agent`
at 6,906.

That is the precise wrong answer. `agentsBilled` exists in the ledger to separate the residual above
— *the troubleshooter must not have the last word* — from the far cheaper *the troubleshooter must
not run at all*. Guessing between those two has already cost this repository three deploys. Read as
recorded, the next diagnosis would have gone to the orchestrator's routing to ask why an agent that
never ran had spoken.

The read was in the block that fires when the Grounding panel lights. That block is correct for
everything `source_used` carries, because the whole frame lands at once and renders in one pass. It
is wrong for the meter: the cost table fills from `token_usage`, **one frame per executor**, as each
agent finishes — all of it after the SOP tool has already answered. So the ledger systematically
recorded the agents billed *so far*, which on the runs that matter is the first one.

Reading it in `afterEach` reads it after the turn. It is guarded, because the ledger observes a run
and may not decide it: a page closed by a timeout is not a reason to turn a beat red, and
`recordRehearsal` has never been allowed to throw for the same reason. On the next live run the row
came back with two agents on a beat that had recorded one.

This is the fifth way the proof could have come back green, or red, about the wrong thing — and the
only one of the five that would have been read as evidence rather than as a passing streak.

## The sixth residual: three more places the roster is the plan

With the meter finally readable, the next question was whether the troubleshooter was still being
billed. Four clauses had already been rewritten for that, and each had *reduced* the failure rate
without removing it, because each was one expression of a single inherited assumption — **every agent
on the team runs on every request** — and the assumption is written down in more places than anybody
had counted.

Counting them rather than finding them one red run at a time turns up three more, all of them in the
*plan* prompt and none of them conditioned on `minimal_plan`:

| Where | What it said | Read on a team of alternatives |
| --- | --- | --- |
| `INVOCATION RULES` | *"If **an agent** has not been invoked yet, the workflow is NOT complete."* | Not *a plan-step agent*: an agent. With a one-step plan and three specialists, this is an instruction to run the other two. |
| The worked example | A three-agent plan, one step each | The repository has already learned that *"one step per agent"* is read as a template. An example is a stronger template than a rule, and it sat directly under the paragraph saying a one-step plan is complete. |
| `TEAM SCOPE POLICY` | *"When out of scope, the mandatory-inclusion rule below does NOT apply"* | Under `minimal_plan` there is no such rule below. Naming an exemption is how a reader infers the rule it exempts them from. |

All three are now the `minimal_plan` fork the other four already have, and a pipeline team's prompt is
byte-for-byte what it was. They were fixed **together**, which is a departure from how the first four
were found and is deliberate: fixing them one at a time costs one deploy and one ten-run rehearsal
each, and none of the three is desirable under `minimal_plan`, so there is no guess to get wrong.

## What six live runs said instead

The rate was measured before anything was changed — six Demo validator runs against `rg-macae-flw-v1`
on 2026-08-14, build `e21d6516`, three green and three red. **Not one of the three was the
troubleshooter.** Two were the **honest miss** and one was grounded-and-cited but failed downstream;
the cost table on every run named `Store SOP Assistant` and `Shift Tasks Agent` and nobody else.

That is the *original* symptom of this issue, and the ledger's request half ruled out the layer it
was built to rule out:

```
sop/ask: the orchestrator asked 'Please look up the store closing procedure for Store 223 …';
         retrieving against 'How do I close the store?' — the rehearsed turn's corpus wording
```

The marker fired. Dataverse was searched for the corpus's own words, and the panel came back with no
citation. So the same wording was then put to `/api/v4/sop/ask` ten times in the following two
minutes — the third layer asked directly, with no orchestrator in front of it:

```
failed=False cites=['SOP-102 Store Closing Procedure.docx']   × 10
```

Ten out of ten. Three out of six through the orchestrator, with the identical retrieval query, on one
replica. Both cannot be a property of the corpus or of the index, and the wording is now excluded by
measurement rather than by argument.

## The half of the log that was missing

What no record could say next is **what the SOP agent replied**. The Grounding panel renders an empty
citation list as the honest miss, and it renders it identically for two different faults:

- the agent searched the knowledge source and genuinely found nothing;
- the agent answered from its own instructions without consulting the knowledge source at all, so
  there was no appearance metadata for `citations_from_activity` to read.

The first is the corpus or the index. The second is the Copilot Studio agent's own generative
answering, and it is not fixed anywhere in this repository's prompt layer. Guessing between them is
the same shape of mistake as guessing between *must not run* and *must not have the last word*, which
has already cost three deploys.

So `/sop/ask` now logs the reply beside the question — the citation count, the document names, and the
first 400 characters of what the agent actually said. The request half was added for issue #54's first
acceptance criterion and did its job; this is that criterion applied to the other end of the hop, and
the next red run is readable from `az containerapp logs` alone.

## The answer: the agent's own Fallback topic, and neither of the two

It was the third possibility, and the reason no amount of asking the deployment had found it is that
every path through the deployment goes through the orchestrator, and the orchestrator was never the
variable.

The loop that found it asks the **agent** rather than the deployment: N fresh Direct Line
conversations, opened concurrently, each asking the rehearsed question and draining the whole window
rather than settling early, each classified as `cited`, `miss` (the honest-miss sentence, uncited),
`both`, or `uncited`. Sixty-nine of them, on 2026-08-14, against the agent exactly as it had been
authored since #18:

| Verdict | Count |
| --- | --- |
| `cited` — `SOP-102 Store Closing Procedure.docx` | 65 |
| `miss` — the honest-miss sentence alone | 3 |
| `both` — the cited procedure, and the honest-miss sentence 30 ms behind it | 1 |

That is the centrepiece beat failing about **6% of the time inside Copilot Studio**, with no
orchestrator, no rephrasing and no drain race anywhere near it. The 10-out-of-10 direct probe that
had made this look like a path difference was not measuring a different path; it was ten samples of a
6% fault, which come up clean about **half** the time (`0.94¹⁰ ≈ 0.54`). Ten green direct probes were
never evidence of a different path — they were a coin landing heads.

The `both` row is the one that names the cause. Nothing that *searched and found* `SOP-102` also
concludes the corpus does not hold it. Two different things spoke in that turn — and the second was
the **Fallback topic**, whose only action was `SendActivity(HONEST_MISS)`. Its trigger is
`OnUnknownIntent`, so it fires on the turns the generative planner did not answer, and on those turns
the agent said *the corpus does not hold this* **with nothing having searched the corpus**. The
sentence was never true; it was just usually not said.

### Deleting it is worse, and that is the useful half

The obvious fix — take the topic out, let the instructions carry the wording — was tried and
measured, which is the only reason it is not in this repository now. With no Fallback topic, the
platform's own unknown-intent handler answers instead:

```
Sorry, I am not able to find a related topic. Can you rephrase and try again?
```

**16 of 40** asks of the rehearsed question. Not a beat: a stack trace, in front of a customer. And
the out-of-corpus question got the same sentence, which loses the honest miss outright — the
[AC4](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/54) failure, caught by
`check-sop-agent.sh --probe` on the run that published it.

That number is also the measurement that reframes the whole issue: the planner leaves the turn
unanswered far more often than 6%. The old Fallback topic was *hiding* that behind a sentence that
read as a deliberate demonstration of honesty.

### So the search moves inside the fallback

`fallback_topic()` now runs `SearchAndSummarizeContent` over the agent's knowledge and reaches the
honest miss only through `elseActions`, when that search returned nothing. The shape is Microsoft's
own exported Conversational boosting topic; the `elseActions` branch is this repository's. The
answer is never re-sent from `Topic.Answer` — that activity is what carries the citation `entities`,
and re-sending the prose without them produces the honest miss's exact appearance from a search that
succeeded.

Measured against the published fix, same loop:

| Question | Runs | Result |
| --- | --- | --- |
| `How do I close the store?` | **80** | 80 cited to `SOP-102`, no miss, no contradiction |
| `How do I restart the car wash…?` | **15** | 15 honest misses, the authored sentence verbatim, no invented steps |

The honest miss is now what it always claimed to be: the corpus was searched, and it holds nothing.

Two things are deliberately not claimed. The instructions were changed in the same build — they
carry the honest-miss sentence verbatim and forbid saying it beside steps — so those 80 runs do not
separate the topic's contribution from the instructions'. And 80 clean runs bound the residual at
roughly 4%, not at zero; what closes that is the ten-run rehearsal through the browser.

## The rehearsal against the fix: nine, and then a different fault

Ten runs against build `38d2a6ca`, the agent published 2026-08-14T18:44Z:

| Runs | Outcome |
| --- | --- |
| 1–9 | **grounded** — `SOP-102` retrieved and cited on screen |
| 10 | **clarified** — retrieved and cited, and the surface asked the presenter a question back instead of showing it |

**Zero honest misses in ten browser runs**, where the same beat produced two in eight on the
afternoon the validator first ran and three in six a fortnight later. That is the fault this issue is
named after, and it is the fault the Fallback topic was causing. It did not happen.

The red run is the **first residual**, still open: the `Troubleshooting Agent` was billed on runs 3
and 10, and on run 10 it took the last word — a procedure lookup routed into a troubleshooting
clarification on a question with nothing broken in it. Seven prompt clauses have been forked on
`minimal_plan` chasing it and it still fires about one run in five. It is a *routing* failure, in the
backend, in a different layer from everything above; the answer was retrieved, cited and correct, and
the surface declined to show it.

So AC3 is unmet, and it is unmet for a reason the record can now name precisely rather than for the
reason it was opened about. Ten distinct rephrasings reached the SOP tool over the ten runs and every
one of them retrieved — the rephrasing question (AC1) stays answered.

## The residual gets an instrument instead of an eighth guess

Seven prompt clauses had been forked on `minimal_plan` chasing the troubleshooter, each costing a
twenty-minute deploy, each reducing the rate without removing it. The reason is above, in the table:
the only thing that could see the fault was **ten browser runs that stop at the first red one**, and
a rate cannot be measured one run at a time.

So the eighth change was not a prompt clause. It was the [Routing probe](routing-probe.md) —
`bash scripts/measure-routing.sh`, the same Fast-lane turn driven over plain HTTP and the
transparency WebSocket with no browser, one sample at a time, about two minutes each. This is
`bf7792a7`'s move one layer up: the honest miss was chased through the orchestrator for six
iterations and found in an afternoon by asking the agent directly sixty-nine times.

Twelve serial samples against build `8f0b77c7`:

```
   10  grounded
    2  no-tool-call
  FAIL  Troubleshooting Agent took part in 2 of 12 turns, on a question with nothing broken in
        it, and spoke on 2 of them
```

**The residual reproduces without a browser** — the same one-run-in-five as the ten-run rehearsal,
at a twentieth of the cost of observing it. That is the thing the next iteration has that the last
seven did not, and `e2e/artifacts/routing-evidence.jsonl` now carries, per sample, which agents were
billed, which spoke, and the wording that actually reached the SOP tool.

## The panel goes dark if anyone else is watching

The probe's own two `no-tool-call` samples were the more expensive finding, and they cost one
experiment rather than one deploy.

`_push_source_used` — the frame the Grounding panel renders — resolves its recipient server-side, and
the resolution was `sole_user()`: *the* connected user, when there is exactly one. A **positive
control**, one sample taken with a single idle bystander socket registered beside it:

```
  "outcome": "no-tool-call",
  "agents_billed": ["Shift Tasks Agent"],
  "citations": [],
  "answer": "Here's the Store 223 closing procedure from **SOP-102 Store Closing Procedure**: ..."
```

The retrieval worked, `SOP-102` was cited in the prose, and the panel stayed dark. This is not a
probe artefact: a presenter's second tab, a colleague's screen, or a reconnect the backend has not
noticed closing yet is enough to produce it on stage — the centrepiece panel empty on a turn that
retrieved correctly, for a reason nothing on the screen explains. It is also, exactly, the coarser
variant this issue describes in its own words: *"No tool call, no `source_used`, an honestly empty
panel."* Some of those may never have been the routing at all.

The fix asks the sharper question first: `sole_turn()`, the one user with a request **in flight**,
which was already being asked one module away for the troubleshooting tools, falling back to
`sole_user()`. Both refuse to guess between two, so the recipient is still resolved server-side and
is still never a UUID a model copied. They differ only in what they count, and **a connection is not
a question**.

## The deploy gate asked once, and once is a coin flip

The last thing measuring the fault changed is the check that had been green throughout it.

`check-deployed-surface.sh`'s `direct-sop-answer` row is the gate `deploy-main.yml` goes green on:
`azd` exiting zero is not the deployment working, so the workflow asks the running surface a real
procedure question before it goes green. It asked **one**. Against a fault that fires about 6% of
the time per Direct Line conversation, one asking is clean nineteen times in twenty, and against a
beat that was failing one browser run in four it was clean on every attempt across the afternoon
the browser watched it fail twice in eight. Renaming it from `grounded-answer` fixed the *claim* —
the row now says out loud that it asks the easier question — and left the *sample size* saying
nothing at all.

That is the same arithmetic the Fallback topic was found by, and `check-sop-agent.sh` had already
learned it: `--samples N` asks N times in N fresh conversations, and it took 69 of them to see a
fault that ten had made look like a difference of path (`0.94¹⁰ ≈ 0.54`). The gate had not.

So `--samples N` is on this check too, and the deploy gate passes `--samples 12`. Twelve Copilot
Studio messages against a step that already costs twenty minutes and a provision is the right price
for not approving a deploy on a coin landing heads.

**Twelve is derived, not picked.** A fault firing on a fraction `p` of conversations survives `n`
independent askings with probability `(1 − p)ⁿ`, and `0.94ⁿ ≤ ½` first holds at `n = 12`. Five
askings — the first number written here — would have let a 6% regression through about **three
deploys in four**, which is better than the 94% a single asking allowed and reads far stronger than
it is. `src/tests/ci/test_deploy_workflow.py` holds the gate to the arithmetic rather than to the
number, so a future edit that lowers the count fails with the odds it would be accepting.

And the row itself says by how much sampling is not proof:

```
  PASS  direct-sop-answers-every-time: 12 of 12 askings answered from the corpus, each in a
        fresh Direct Line conversation. Sampling is not proof: a fault firing on fewer than
        5.6% of conversations is likelier than not to survive 12 askings, and the one #54
        measured fires on about 6%
```

That sentence is in the check's output rather than only here because the operator reads the output.
A green row saying only *12 of 12* is exactly the shape of evidence that let `grounded-answer` be
believed across an afternoon the browser watched the same beat fail twice in eight.

Three more properties, each a mistake this repository has already paid for once:

- **One grading rule, two rows.** `direct_sop_fault` grades the first asking for `direct-sop-answer`
  and every asking for `direct-sop-answers-every-time`. A repeat held to a laxer bar than the first
  asking is a green row that means less than the row above it.
- **Broken is not intermittent.** A run in which *nothing* answered says so. They want different
  next moves: intermittent is a rate to measure, broken is a state to fix, and an operator reading
  "intermittent" of a beat that never worked goes looking for a rate that is not there.
- **A hop that did not happen is not the honest miss.** An asking the backend never answered carries
  no citations, and so does an agent that searched and found nothing; only one of them means the
  corpus is wrong. This is the distinction `/sop/ask`'s own reply log was given, one layer out.

A single asking still passes — the default is one, and a `--no-probe` run still fails both rows
rather than omitting them — but a green single sample now ends with what it is not evidence of.

Measured against `rg-macae-flw-v1` the afternoon it was written: `12 of 12 askings answered from
the corpus, each in a fresh Direct Line conversation`, the whole check in 2m05s. That is AC5. It
does not close AC3, and it is not meant to: this check asks the corpus's own wording with no
orchestrator in front of it, and the residual above is the orchestrator.

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

Each run is scoped to the **rehearsed hit's own beat**. With one spec that was the same run and the
difference never showed; since the fourth specialist got a beat of its own (#52) it is not. A red
**workforce** beat exits the validator non-zero, and this harness treats a non-zero exit as fatal to
the streak — deliberately, because a green ledger row behind a red run is a teardown failure. So on
2026-08-14 the hop's beat was green and cited, the run was red, and the centrepiece was unprovable
for a reason its own ledger said nothing about. That is this issue's mistake wearing the harness's
clothes, and scoping is what restores the exit code to being the verdict on the beat being graded.

The **Recorded fallback** is not lost by that; it is correctly declined. The walkthrough reporter
reads a positional spec as a filter and refuses to replace the recording from a run that is not a
whole walkthrough. Making the fallback is a plain Demo validator run's job.

**It is not a feedback loop and must not be added to a workflow** — the Demo validator's own rule
(`docs/demo-validator.md`) multiplied by ten. It drives a real browser through ten live conversations
with the deployed agent pool. `src/tests/ci/test_e2e_wiring.py` fails if a workflow ever runs it.

A presenter's own rehearsal leaves the same trace: `/sop/ask` logs both strings on every call, plus
what came back — the citation count, the documents named, and the opening of the answer — so
`az containerapp logs` answers both "what did the orchestrator actually ask?" and "what did the SOP
agent actually say?" without the validator.

## Reading a red run

The report names one of four layers:

- **the orchestrator's routing** — no tool call at all, or a grounded answer behind a clarification.
- **the orchestrator's rephrasing** — Dataverse was searched for the model's own wording, which means
  the marker did not fire. Check that the tapped Quick Task's prompt is still exactly
  `[rehearsed_hit].question`; the marker is armed on an exact match, deliberately.
- **the agent's Dataverse index** — the corpus's own wording was retrieved against and missed. The
  expensive one, and the only one that means the demonstration's *content* is wrong. Before believing
  it, ask the **agent** rather than the deployment: many fresh Direct Line conversations, concurrently,
  each draining the whole window. On 2026-08-14 that turned up a fault the deployment could not
  express — the agent's own Fallback topic answering, 4 conversations in 69 — and the index was
  never wrong. The backend log now carries what the agent replied, which is how a searched-and-missed
  turn is told from a turn where nothing searched.
- **unknown** — the evidence does not reach a layer, and the harness says so rather than guessing.
  Read `e2e/artifacts/report` and the run's `error-context.md`.
