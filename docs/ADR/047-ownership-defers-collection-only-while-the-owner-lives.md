# ADR-047: Ownership defers collection only while the owner lives, and a landed branch is collected like a worktree

## Status

Accepted — amends [ADR-044](./044-an-agent-worktree-lives-in-the-containing-folder.md)'s ownership
clause and extends its sweep to branches; renames the `AGENTS.md` stanza to cover both

## Date

2026-08-18

## Issue

#174

## Context

[ADR-044](./044-an-agent-worktree-lives-in-the-containing-folder.md) collects a worktree once every
commit in it is reachable from `origin/main`, and defers any worktree a run owns:

> A run that is paused, blocked, or waiting on a gate is indistinguishable from an abandoned
> worktree **by idleness alone**.

That sentence is true, it was the right call on the evidence available, and it names its own escape
hatch in its last three words. Two days later the deferral it created is the entire remaining
problem.

### The deferral closed a loop

Measured with `scripts/worktree.sh sweep`, with **no git-loopy process running at all**:

- **16 worktrees** reported `defer-owner` — "created by a run that manages its own worktrees" —
  belonging to **6 distinct runs, every one of them dead**.
- **12 local branches** were provably reachable from `origin/main`. Deleting them destroys nothing:
  reachability means every commit is already in `origin/main`'s history, which is to say already on
  GitHub. But each one is *checked out* in one of those deferred worktrees, and git refuses to
  delete a checked-out branch.

The worktree is kept because a run owns it. The branch cannot be deleted because the worktree holds
it. The run has not existed since the day before. Neither half can ever release the other, and no
amount of sweeping changes that, because the sweep is the thing declining to act.

This is worth stating precisely, because it determines the fix: ADR-044 did not accumulate clutter
it forgot to collect. It created a category — *externally owned* — whose members are **structurally
immortal**, and then put 16 of 21 worktrees in it.

### Ownership was conflated with liveness

`is_externally_owned` answers "who made this?" The rung above it spends that answer on a different
question: "may I remove it?" Those come apart the moment the owner exits, and ADR-044 had no way to
notice the difference — so ownership, correctly identified, silently became permanent.

The fix is not to collect lanes. A live run's lane must still be untouchable; collecting one still
costs a run. The fix is that **ownership should defer collection only while the owner is there to
own it.**

### Age cannot carry that distinction, and nearly got picked anyway

The obvious liveness proxy is a heartbeat, and it fails on this repository's own numbers:

- The live run was observed **silent for 26 minutes** while genuinely working.
- `GIT_LOOPY_SEND_TIMEOUT_SECONDS` defaults to **7200** — a run may legitimately block for two
  hours inside one `send_and_wait`.
- `GIT_LOOPY_GATE_TIMEOUT_SECONDS` defaults to **3600**.

Any threshold short enough to collect yesterday's runs is short enough to kill a live one. This is
the same finding ADR-044 recorded when it rejected age-based collection — *"age is uncorrelated with
safety"* — reappearing one level up, about the owner rather than the work.

Nor can the run's own records answer it. git-loopy 0.9.0 writes `.git-loopy/runs/<iso>-<run-id>.json`
containing `run_id`, `started_at`, `iterations` and `skill_adoption` — the union of every key across
all 25 run files on disk. There is no `finished_at`, no status, no exit code and no PID. **A clean
finish and a `kill -9` are byte-identical.** There are no lock files and no PID files. And there is
no `resume`: a run is single-shot, and re-running mints a new ULID, so a run whose process is gone
will never write to those lanes again.

### The signal that does work

A live run **holds its own log open**:

```
$ lsof -p 47514
… /az-multi-agent-flw-demo/.git-loopy/logs/2026-08-17T19-20-30Z-01M08JP4GPHSKED91XXPRX8AGZ.log
… /az-multi-agent-flw-demo/.git-loopy/logs/2026-08-17T19-20-30Z-01M08JP4GPHSKED91XXPRX8AGZ.jsonl
```

The run ULID is in the filename of an open file descriptor. That maps process to run **exactly**,
with no threshold and no guessing from a working directory. It is immune to the two-hour silence
that defeats a heartbeat, because the handle stays open while the process blocks. And it cannot go
stale in the dangerous direction: the kernel closes the descriptor on exit, crash, `kill -9` or
reboot, so the signal fails *towards* "collectable" only when the run really is gone.

### What a branch sweep can destroy, which is less than it sounds

A branch has no working tree, so the stash rung that dominates ADR-044's risk analysis does not
apply. The only question is whether deleting the ref orphans commits — and "reachable from
`origin/main`" answers it more strongly for a branch than it did for a worktree: the commits are on
the remote, in `main`'s own history, and additionally in the reflog. Deleting such a ref is
recoverable three ways.

Against that, the branches that must **not** be touched are visible in the same measurement: six
local branches hold commits that exist on no remote at all. Every one belongs to a dead run. They
must escalate, exactly as a worktree in that state does, and liveness must never be the only thing
standing between the developer and the sole copy of some work.

### `git branch -d` is the wrong oracle

ADR-044's posture is *"No `--force`, ever. If git objects, git is right."* For worktrees that holds:
`git worktree remove` refuses a dirty tree on its own judgement, and that refusal is real.

It does not transfer. `git branch -d` refuses unless the branch is merged into **HEAD or its
upstream** — the local-drift trap ADR-044 was written to escape, wearing a different hat. Standing
on a stale `main`, `-d` refuses branches that are provably on `origin/main`; standing on an
unrelated branch it can accept ones that are not. Deferring to it is not deferring to git's
judgement, it is deferring to `git branch --merged`, the specific question ADR-044 established
cannot tell a landed branch from a stale one.

### The remote accumulates for a different reason entirely

`deleteBranchOnMerge` was **`false`**, so a merged PR's head branch was never deleted. **40 of 56**
remote branches were reachable from `origin/main` — every commit already landed — up from 11 of 46
a day earlier.

No sweep is required for that. ADR-044's deepest move was choosing a trigger *guaranteed to happen
anyway* — creation — so nobody had to remember a habit. The remote already has a better one: PR
merge, server-side, on every machine at once.

### Hand-cleaning does not hold, and the sweep can eat a live session

Between the grilling rounds that produced this ADR, local branches were cleaned by hand from 58 to
35 — and the same pass took the branch of the session writing this document. In the same window the
remote grew from 46 to 56. Manual cleanup is not a smaller version of the rule; it is a different
thing that loses work and does not converge.

The sweep also twice collected the worktree of that live session, which was clean, reachable and
merely idle between questions. That is ADR-044's declared and accepted trade-off — *"the mtime and
lock guards are heuristics"* — and this ADR does not change it. It is recorded because it is the
same conflation, a third time: **idleness is not liveness**, for a run or for a session.

### The rule did not reach the next agent

The session that produced this ADR began by creating a worktree in the wrong place — nested inside
the repository — one day after ADR-044 merged specifically to prevent that.

The cause is measurable. `AGENTS.md` is read from whatever branch the primary worktree is parked on,
and a runner parks it wherever it is working:

| Branch the primary was on | occurrences of `## Worktrees` in its `AGENTS.md` |
| --- | --- |
| `git-loopy/01M06AYP…/issue-108` | **0** |
| `issue-168-chat-panel-column` | 1 |

ADR-044's diagnosis was *"no document this repository publishes said where a worktree belongs."* The
document now exists and still did not arrive, because the channel it travels on drifts. This is,
once more, the trap ADR-044 named: the sweep reads `origin/main` deliberately because local `main`
drifts, while the rule commanding the sweep is read from a checkout that drifts considerably worse.

## Decision

**Ownership defers collection only while the owner is alive, and a branch is collected on the same
terms as a worktree, in the same pass.**

1. **Ownership becomes liveness-scoped.** `defer-owner` applies while the owning run is alive. A
   lane whose run is gone falls through to the *ordinary* rungs — locked, recently touched,
   reachable, only-copy — and is collected, skipped or escalated on its merits like any other
   worktree. Ownership no longer outranks every other state; it outranks them only for a run that
   still exists.

2. **A run is alive if, and only if, some process holds its run log open.** Determined from the open
   file descriptors naming `.git-loopy/logs/<iso>-<run-id>.log`. No age threshold participates in
   this decision.

3. **An undeterminable liveness signal means alive.** If the open-descriptor check cannot be run —
   `lsof` absent, blocked, or blind to another user's process — every run is treated as live,
   everything is deferred, the reason is reported, and the sweep exits **0**. A folder that stays
   cluttered is recoverable; a collected live run is not. This matches ADR-044's existing stance
   that a kept worktree is the rule working, not the rule failing.

4. **Branches are collected in the same sweep, after worktrees.** The order is forced, not stylistic:
   19 of 35 local branches are checked out, and a branch only becomes deletable once its worktree is
   collected. One pass, worktrees first.

5. **A branch reachable from `origin/main` is deleted.** A branch holding commits that exist on no
   remote **escalates** and is never deleted. A branch that is pushed but not landed is kept — work
   in flight, bounded by the work and not by time, exactly as for worktrees.

6. **The reachability predicate is computed here, and `-D` is the mechanism, never the judgement.**
   `git merge-base --is-ancestor <branch> origin/main` after a fetch, in the pure layer, unit-tested.
   Only a branch that passes is passed to `git branch -D`. This is not forcing past a real
   objection; it is declining to consult an oracle this repository has already proved reads the
   wrong ref. Nothing that fails the predicate is offered to `-D` at all.

7. **The sweep never deletes a remote branch.** The remote is fixed at its own trigger:
   `deleteBranchOnMerge` is **`true`**, retiring every future merged head branch server-side. The
   backlog of already-landed remote branches is *reported* — printing the commands — for a human to
   run.

8. **The primary worktree's branch is never changed.** It is reported, with its distance from
   `origin/main`, and nothing more. The first rung of the ladder promises the primary is never
   touched, and a documentation-freshness problem does not justify checking out `main` under a live
   runner or a human mid-edit.

9. **`scripts/worktree.sh add` warns when the checkout's `AGENTS.md` differs from `origin/main`'s.**
   Creation is already the guaranteed trigger and it is the exact instant an agent is about to
   improvise. This is the one intervention that would have prevented the misplaced worktree that
   opened this session.

The logic lives in `scripts/worktree_hygiene.py` beside ADR-044's, with liveness entering the pure
layer as an *observation* — the set of run IDs holding an open log — so
`src/tests/ci/test_worktree_hygiene.py` can test the ladder without a process table, a remote or a
disk. The `AGENTS.md` stanza becomes **`## Worktrees and branches`** and states both rules, because
that stanza is what an agent reads before it improvises, and this ADR exists partly because it was
incomplete.

## Considered Options

**Collect a run's lanes unconditionally.** Rejected, and still rejected — this is what ADR-044
refused and it was right. A live run's lane is untouchable. The change is only that "live" is now
something we can measure rather than assume.

**Keep deferring, and accept the growth.** Rejected once the loop was measured. 16 of 21 worktrees
and 12 of 15 deletable branches were immortal, with no live run on the machine. Deferring is not a
conservative default when the deferred set never drains.

**A heartbeat or age threshold for the owning run.** Rejected on this repository's numbers: 26
minutes of observed silence, a 2-hour send timeout and a 1-hour gate timeout. Any threshold that
collects is a threshold that kills.

**Read the run's own state file.** Rejected because it cannot answer: `started_at` and nothing else,
across all 25 files. A clean finish and a `kill -9` are indistinguishable in it.

**Ask git-loopy to clean up after itself.** The right long-term answer and not available: 0.9.0 has
no cleanup subcommand and no resume, and it is not this repository's code. Recorded so that if it
ever grows one, rung 1 should defer to it.

**Use `git branch -d` and treat refusal as escalation.** Rejected: its merged test reads HEAD and
the upstream, which is precisely the local-drift error ADR-044 exists to correct. It would refuse
provably-safe branches and, from an odd HEAD, accept unsafe ones.

**Report branches, never delete them.** Rejected for the reason ADR-044 rejected "refuse dirty
worktrees and move on" — it *"leaves the clutter it was written to remove, and leaves it in the
least legible state."* A report nobody acts on is the landfill with a lid, and here there is
provably nothing to lose.

**Let the sweep delete remote branches it proves reachable.** Rejected on blast radius rather than
on safety. Local deletion is recoverable from the reflog and from the remote; remote deletion has no
reflog, races other machines and a live run, and on a public repository can break another fetch.
`deleteBranchOnMerge` achieves more, at the right trigger, with none of that.

**A separate `branch_hygiene.py`.** Rejected: it fights the ordering coupling, needs a third
component to sequence the two passes, and offers two entry points for one habit — which is the shape
of the original defect.

**Rename the module and script to `repo_hygiene` / `hygiene.sh`.** Genuinely tempting, and the
cheapest it will ever be. Rejected because ADR-044's references are one day old and load-bearing in
`AGENTS.md`, the ADR body and the test name, and because `worktree.sh add` remains an honest
description of the *trigger*. The naming debt is real and is recorded here rather than denied.

**Restore the primary to `main` when no run is live.** Rejected: it breaks the one promise the
ladder makes unconditionally, to fix a problem better addressed at creation time by rung 9.

**Amend ADR-044 in place.** Rejected per this repository's own instruction not to edit a superseded
ADR's body. ADR-044's reasoning is sound and unchanged; what changed is that one clause acquired a
qualifier it could not have known it needed.

## Consequences

- The deferred set drains. 16 worktrees and 12 branches become collectable the moment no process
  holds their runs' logs, and the container is bounded by *running work* rather than by history.
- `defer-owner` stops being a terminal state and becomes a temporary one. A report showing it now
  means a run is actually running.
- **`-D` appears in the source.** Anyone grepping for it will read it as a violation of ADR-044's
  no-force posture, and a future session may "fix" it back to `-d` and silently break collection.
  That is why the reasoning is in rung 6 and in this ADR rather than in a comment.
- The sweep now depends on inspecting open file descriptors, a platform-specific capability. Rung 3
  makes that dependency fail safe, at the cost of doing nothing at all on a machine without it.
- The remote is fixed for the future but not the past: 40 already-landed branches remain until a
  human runs the reported commands.
- Collecting a lane of a dead run can still surprise someone who intended to resume it by hand.
  There is no resume, so the intent was already unachievable, but the worktree was a visible
  reminder and will no longer be there.
- Nothing here reaches other repositories; that remains #163.

## References

- Issue #174 — the decision and the evidence behind it
- [ADR-044](./044-an-agent-worktree-lives-in-the-containing-folder.md) — the containing folder, the
  sweep, and the ownership clause this amends
- [ADR-005](./005-declare-feedback-loops-in-agents-md.md) — why a rule that matters is declared in
  `AGENTS.md` and backed by a script in `scripts/`
- [ADR-041](./041-the-copilot-studio-chat-url-is-a-credential.md) — why remediation stashes rather
  than commits
- Issue #163 — the same improvisation in every other checkout, deliberately not absorbed here
- `scripts/worktree_hygiene.py`, `scripts/worktree.sh`, `src/tests/ci/test_worktree_hygiene.py`
