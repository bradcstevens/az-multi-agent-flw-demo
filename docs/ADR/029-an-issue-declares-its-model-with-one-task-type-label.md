# ADR-029: An issue declares its model with one `task-type:` label, over a committed table

## Status

Accepted

## Date

2026-08-16

## Issue

#82 (map #81)

## Context

`BRIEF.md` asks that every issue be *"labeled appropriately for parallelism as well as assessed to
determine the task type the issue is, as well as what model route the task should be assigned"* —
model, effort level and context — *"that best aligns to what git-loopy can support"*.

Measured against git-loopy **v0.9.0-dev.0** on 2026-08-16, that ask is expressible in part, and the
parts that are not are not the ones #82 assumed. Four of the six premises the issue was written on
had already moved:

**Routing is no longer inert in serial mode.** #82 recorded *"in serial mode every tier is inert"*
from git-loopy's ADR-0028. Its **ADR-0037, "Routing takes effect in every mode, not only in Parallel
mode"**, reverses that: *"A Routed pair now takes effect wherever it is resolved: a serial Iteration
runs on the pair its own Pickup resolved, exactly as a Lane does."* The consequence is not
theoretical. #101–#109 are `ready-for-agent` and `task-type:implementation` today, so the next
`git-loopy` run routes them whether or not anybody passes `--parallel`.

**The table that would route them is on one laptop and says something nobody chose.**
`git-loopy calibrate --status` reports `implementation` at **`gpt-5.6-luna @ medium`** from
`~/.config/git-loopy/config.toml` — the cheapest model on the roster, an uncommitted file, and not
the `claude-sonnet-5 @ low` that #82 recorded from git-loopy's built-in `RECOMMENDED_ROUTING`. Nine
queued issues on the demonstration build were one command away from a model nobody in this
repository had reviewed, and `AGENTS.md` already names that failure mode in another context: *"a
portal edit is a behaviour nobody here can review."*

**A context setting exists on paper and is inert in fact.** #82 recorded *"no context-size,
context-tier or long-context setting exists — not a flag, not an env var, not a config key"*.
git-loopy's **ADR-0017 is `accepted`** and decided the opposite: *"git-loopy sets `context_tier`
explicitly on session creation… The tier is a **run-level** setting with a `default` default, not a
per-task-type entry in the `[routing]` table."* But nothing reaches it — there is no flag, no config
key and no environment variable; `MODEL_CONTEXT_TIERS` is an empty dict, so `gate_context_tier()` is
a structural no-op; `RunConfig.context_tier` is never assigned by `cli.py`; and `create_session()` is
never passed it. This repository's own logs confirm the consequence: all 56 iterations that reported
a peak read `token_limit: 200000`, exactly `claude-opus-5`'s **`default`**-tier ceiling. The
`long_context` tier would have read `936000`.

**Calibration cannot run here, for a reason unrelated to labelling.** #82 asked whether to backfill
the 46 qualifying closed issues and measure. `calibrate` walks a price staircase sorted on each
model's *published premium multiplier*, and this environment's rate card publishes `multiplier:
null` for **all 24 models**. `git-loopy calibrate --dry-run` returns `Price staircase: none`,
`Maximum Trials: 0 (0 rungs x 5 Proving tasks)` and `Calibratable Task types: 0 of 7`. Because the
trial count is `rungs × 5`, **labelling all 46 issues leaves it at zero.**

Two facts about the mechanism shape the rest. The taxonomy is **closed** — the classifier's prompt
says *"Choose exactly one key from this closed list. Anything outside it is refused."* — and an
unlabelled issue is not skipped but classified by a **model call** that can return any of the seven.
And `labelled_task_type()` returns the **first** `task-type:` label it encounters in an unordered
list, so two labels is a coin flip rather than a merge, and an out-of-taxonomy label still counts as
"already labelled", silently defeating both routing and the classifier that would have corrected it.

Finally, what this repository's work actually costs, measured from `.git-loopy/logs/` across 14 runs:
the median iteration is **29 minutes** (n=56, max 112), and by [ADR-020](./020-deploy-main-on-every-commit.md)
a merge to `main` rebuilds three images, reprovisions and re-seeds, gated on a live procedure
question — about twenty minutes and real money, reaching the demonstration environment before anyone
reads it.

## Decision

**An issue declares which model runs it by carrying exactly one `task-type:` label, resolved against
a routing table committed to this repository at `git-loopy/config.toml`.**

Seven things follow, and they are part of this decision rather than separate work.

1. **All seven rows are populated, and every AFK issue carries exactly one label.** Not because this
   repository files all seven kinds of work in equal measure, but because the taxonomy is closed and
   an unlabelled issue is classified into *any* of the seven by a model call. Pruning the table would
   only open a gap between what we label and what we are routed to. The seven labels already in the
   tracker are the only ones that may ever exist: an eighth, however sensible its name, reads as
   "already labelled" and is never corrected.

2. **A multi-type issue is labelled by dominant risk, not by surface area.** The label names the
   dimension whose failure is most expensive, not the one with the most files. An issue touching
   frontend, backend, tests and `CONTEXT.md` is `implementation`, because the code is what reaches a
   deploying `main` and the glossary edit is not. This is what already happened: #101–#109 each span
   several dimensions and all nine are `implementation`.

3. **The governing rule is `BRIEF.md`'s, taken literally: the best balance of speed and quality,
   cost genuinely ignored, and speed wins a tie.** This is not `calibrate`'s rule and is not
   reconcilable with it — `calibration_search.py` states its objective as *"the cheapest pair that
   clears the AGENTS.md gate"*, which is a question this repository declines to ask. Under the rule
   adopted here, **effort is the speed dial**: raising it buys quality and spends wall clock, so
   "speed wins a tie" means stop raising effort where quality stops improving.

4. **The table.** All seven rows written explicitly, so the committed file is complete and
   authoritative:

   | Task type | Model | Effort | Window |
   | --- | --- | --- | --- |
   | `planning` | `claude-opus-5` | `max` | 200k |
   | `review` | `gpt-5.6-sol` | `xhigh` | 272k |
   | `implementation` | `gpt-5.6-terra` | `high` | 272k |
   | `test` | `gpt-5.6-terra` | `high` | 272k |
   | `docs` | `gpt-5.6-luna` | `medium` | 200k |
   | `chore` | `gpt-5.6-luna` | `low` | 200k |
   | `bugfix` | `claude-opus-5` | `xhigh` | 200k |

   `planning` takes `max` because nothing blocks on a planning ticket, so there is no speed tie to
   break, and because that work is verification-heavy: #97 caught a web claim that was false and #96
   found `BRIEF.md` factually wrong about a Direct Line MCP server. `implementation` and `test` take
   `gpt-5.6-terra` for its 272k window (decision 6). `review` takes `gpt-5.6-sol` rather than
   `gpt-5.6-terra` because the author is now `terra` and a reviewer that is literally the author is
   not a reviewer; `sol` keeps the 272k window a diff review needs while being materially stronger
   than the model whose work it reads. `docs` takes `gpt-5.6-luna` because the tie-break is speed
   and this is the row where it bites hardest — the documentation here is enforced (the runbook
   string-for-string, the ADR index by `test_durable_record.py`), so the bar is a bar every model on
   the roster clears, and once quality is not the discriminator the rule says take the fastest.
   `@ medium` rather than `chore`'s `@ low` because an enforced string is a narrower target to hit
   than a lockfile bump. `chore` stays on the roster's fastest model on **speed** grounds, which is
   the only justification the rule still permits now that price is not one; `@ low` rather than
   `@ none` because a lockfile bump that goes wrong is a red CI, and `none` disables reasoning
   outright.

5. **The table is project-scoped and committed.** `git-loopy config path` resolves the project table
   to `<repo-root>/git-loopy/config.toml` — no leading dot; `.git-loopy/` is the `.gitignore`d runner
   state and a different directory — and `git check-ignore` confirms it is tracked. Precedence is
   **per-key**, project over global, which is why all seven rows are written rather than only the
   rows that differ: a partial table silently inherits the rest from whatever is on the running
   laptop, and the effective routing would vary by machine. `src/tests/ci/test_routing_table.py`
   asserts the committed table against the table above, in the CI-tooling tests loop.

6. **Context is not an eligibility floor, because the quality-first rule already does that work.**
   With the tier unreachable (git-loopy ADR-0017, above), a model's `default`-tier ceiling *is* the
   entire context lever. Measured over 56 iterations, this repository's peaks are: median **144,326**;
   **44 of 56** above 100,000; **36 of 56 (64%)** above 128,000; **22 of 56 (39%)** above 150,000,
   git-loopy's effective ceiling and therefore its compaction trigger; **none** above 200,000. The two
   128k models — `mai-code-1.1-flash` and `mai-code-1-flash-picker` — would overflow on two
   iterations in three, but no row wants them anyway once quality is the criterion, so a separate
   floor would be redundant rather than protective. **It is recorded as chosen, not overlooked: the
   redundancy holds only while the rule is quality-first.** Choosing 272k for the three rows that
   generate code is the positive half of the same finding — re-scored at a 272k window, the same 56
   iterations breach the effective ceiling **zero** times, against 39% at 200k.

7. **`parallel-safe` is a separate judgement from `task-type:`, and `N` is 5.** They answer different
   questions with different failure costs: `task-type:` asks *what kind of work is this*, and getting
   it wrong costs a suboptimal model; `parallel-safe` asks *can this land beside another change*, and
   getting it wrong costs a merge conflict or a broken deploy. Only the second can damage another
   issue's work, and only the first has a fallback — there is no classifier for `parallel-safe`, so a
   missing label silently forfeits the parallelism rather than being inferred. The existing tickets
   already reflect this: all nine of #101–#109 are `implementation`, but only seven carry
   `parallel-safe`. Concurrency is `--parallel 5`; `adaptive_lane_limit` is advertised in every run,
   so the cap is a ceiling the tool throttles beneath rather than a quota it fills.

## Considered Options

- **Prune the taxonomy to the types this repository visibly files.** Rejected on decision 1. The
  classifier can return any of the seven regardless, so pruning changes what we *label*, never what
  we are *routed to*, and leaves unpopulated rows reachable.
- **Adopt `calibrate`'s objective and measure the table.** Rejected twice over, and both reasons are
  recorded deliberately. It is the **wrong question** — it optimises for the cheapest pair that
  clears the gate, and decision 3 rules cost out — and it is **inoperable** here, because the rate
  card publishes no premium multiplier for any of the 24 models, so the staircase has zero rungs and
  `rungs × 5` trials is zero. A future reader who sees multipliers appear should note that only the
  second reason has lapsed.
- **Backfill `task-type:` labels onto the 46 qualifying closed issues.** Rejected. `calibrate
  --status` names all 46 and they would grow the Proving set, but the Proving set feeds only
  calibration, and calibration yields zero trials at zero rungs however many issues are labelled.
  The effort buys nothing until the rate card changes.
- **Keep the table global.** Rejected on decision 5. It is the situation that produced this ADR: nine
  queued issues routed by an uncommitted file on one laptop, saying something nobody chose.
- **Write only the rows that differ from git-loopy's defaults.** Rejected on decision 5. Per-key
  precedence makes a partial table machine-dependent, which is the reviewability problem again in a
  smaller font.
- **`claude-opus-5 @ xhigh` for `implementation`**, the pair all 75 closed issues were actually built
  on. Rejected for `gpt-5.6-terra @ high` on decision 6: the demonstrated pair carries a measured 39%
  compaction rate that the 272k window removes entirely.
- **Keep `review` on `gpt-5.6-terra`.** Rejected on decision 4. It was cross-family only because
  `implementation` was `claude-opus-5`; moving the author to `terra` removes the premise the practice
  rested on rather than the practice.
- **Move `review` to `claude-opus-5` for a genuinely independent second opinion.** Rejected, but
  narrowly, and the trade is real: every 272k model on this roster is GPT, so **cross-family review
  and maximum context cannot both be had.** `sol` keeps the window and buys a stronger reader; it does
  not buy independence.

## Consequences

- **Positive.** Nine queued issues stop being routed by an unreviewable file. The three rows that
  generate code move from a measured 39% compaction rate to zero. The rule is one sentence a reader
  can apply to a row they have never seen.
- **Negative — the 200k rows keep the compaction exposure.** `planning`, `docs` and `bugfix` stay on
  200k models and therefore keep the measured 39% breach rate. `bugfix` is the sharpest case:
  diagnosis is context-hungry and something is already broken. This follows from decision 6 and is
  recorded as chosen. The measurement to revisit it already exists — `peak_context_window` in
  `.git-loopy/logs/*.jsonl`.
- **Negative — `review` and the code it reads are the same model family.** Decision 4 buys window and
  strength, not independence. Shared blind spots fail *invisibly*: the review returns clean on
  exactly the bug that family was always going to miss. If a 272k non-GPT model ever ships, this row
  should be revisited first.
- **`/to-tickets` cannot produce a conforming issue today.** The instrument that will write every
  issue for the six specs applies only `ready-for-agent`; it has no notion of `task-type:` or
  `parallel-safe`. The nine labels on #101–#109 were applied outside it. Extending it is tracked
  separately; until then, labelling is a manual step and a missing `parallel-safe` silently forfeits
  a lane.
- **Two tripwires, both recorded so the day is not missed.** *Context:* `long_context` is **free** on
  every Claude model — `claude-opus-5` is `500/2500` at both tiers, and the ceiling moves 200,000 →
  936,000; it is 2.0× only on GPT, Grok and Gemini-Pro. The day git-loopy wires ADR-0017 through to
  `create_session()`, this repository should turn it on and pay nothing. *Calibration:* if the rate
  card begins publishing premium multipliers, the staircase becomes buildable — but decision 3 still
  rules the objective out, so that alone does not make calibration the answer.
- **The global table is left alone.** `~/.config/git-loopy/config.toml` is not this repository's to
  edit; the committed table overrides it per key, which is precisely why all seven keys are written.
- **Testing.** `src/tests/ci/test_routing_table.py` joins the CI-tooling tests loop and fails if the
  committed table and this ADR disagree, or if a row names a task type outside the closed seven —
  the same discipline `test_durable_record.py` applies to the ADR index and
  `test_presenter_runbook.py` to the runbook.

## References

- [ADR-020: Deploy `main` on every commit, and make the deploy prove its own result](./020-deploy-main-on-every-commit.md)
- `CONTEXT.md` — **Routed pair**, **Proving set**, **Durable record**
- [docs/agents/triage-labels.md](../agents/triage-labels.md) — the triage roles and the additive
  `parallel-safe` marker this decision sits beside
- git-loopy v0.9.0-dev.0 — its ADR-0017 (context tier, accepted but unwired), ADR-0035 (the locked
  routing table), ADR-0037 (routing takes effect in every mode), and `calibration_search.py`'s stated
  objective. Verified with `git-loopy calibrate --status` and `git-loopy calibrate --dry-run`, both of
  which spend nothing.
- [#82](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/82) — the grilling this
  records, including the four premises that had moved before it was answered.
