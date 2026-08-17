# ADR-044: An agent worktree lives in the containing folder, and is collected once its commits are on `origin/main`

## Status

Accepted — introduces the **worktree containing folder** and the **sweep** to `AGENTS.md`; bounds
what an agent may create beside this repository

## Date

2026-08-16

## Issue

#161

## Context

Thirteen worktrees of this repository sat as flat siblings in the developer's `github` folder,
alphabetically wedged between unrelated projects:

```
az-mafd-grill-92      az-mafd-issue-102   az-mafd-review-101
az-mafd-grill-94      az-mafd-issue-106   az-mafd-spec-1
az-mafd-grill-spec4   az-mafd-issue-110   az-mafd-spec-2
az-mafd-issue-101     az-mafd-issue-156   az-mafd-spec-4
                      az-mafd-issue-54
```

### Nothing created them on purpose

There is no script in this repository that makes a worktree, and there was no rule about them
either. There is nothing in the installed skills: grepping all ~50 skills under `~/.copilot/skills/`
for `worktree add` returns **zero matches**. Twelve separate agent sessions each independently
reasoned *"I need an isolated checkout for this,"* each invented `../az-mafd-<slug>`, and none of
them removed it afterwards.

That is the shape of the defect, and it is worth naming precisely, because it determines what can
fix it. This was not a tool behaving badly — it was **improvisation filling a vacuum**. No document
this repository publishes said where an agent worktree belongs or who collects it, so every session
answered the question from scratch and answered it differently.

git-loopy, meanwhile, already had the answer: it files its lanes under
`az-multi-agent-flw-demo.worktrees/<run-id>/<lane>`, one containing folder outside the repository,
and its own tests assert that arrangement. Twelve of its worktrees were sitting there correctly the
whole time. The convention existed; nothing pointed at it.

### Two defects, not one

**Location** is the visible one — the parent directory is a list of *projects*, and thirteen
transient checkouts do not belong in it.

**Lifetime** is the one that makes it recur. Nothing removes a worktree of either kind. A containing
folder with no collection rule is a landfill with a lid on it: the clutter moves out of sight and
keeps growing.

### What "safe to remove" nearly got wrong

The obvious lifetime rule is *"remove it once the branch is merged to `main`,"* and it contains two
traps that would have shipped.

**Local `main` drifts.** When this was decided, `main` was **two commits behind `origin/main`**. A
sweep asking `git branch --merged main` gets an answer that is wrong in a way that grows quietly the
longer nobody pulls, and it is wrong in the dangerous direction — it under-collects at first, and
then, after a bad pull, over-collects.

**`git branch --merged` cannot tell landed from stale.** `issue-106`'s branch answered "merged"
because it was an *ancestor* of `origin/main` — not because it contributed anything, but because it
was two commits behind and had never been pushed anywhere. A branch that merged and a branch that
was abandoned at an old base are indistinguishable to that question. Both are, in fact, safe to
collect — but only because of a property that "merged" does not name.

The property both cases actually share is **reachability**: every commit in the worktree is already
in `origin/main`, so removing the worktree destroys no commit. Phrasing the rule that way also
disposes of `az-mafd-review-101`, a detached HEAD for which "merged" is undefined, with no special
case at all.

### What a sweep can destroy

Every commit in all thirteen worktrees was already on `origin` — including the two whose branches
had not landed. The only thing a sweep could actually destroy was **uncommitted working-tree
edits**, which at the time was exactly one worktree: `az-mafd-issue-106`, with seven modified files
and an untracked `src/tests/ci/test_plan_contract.py`.

That narrows the remediation question to one thing, and rules out the tempting answer. Committing
whatever is lying around to a rescue branch and pushing it would eventually push a **credential** to
a public repository — that is the entire subject of
[ADR-041](./041-the-copilot-studio-chat-url-is-a-credential.md), and `docs/preflight/` routinely
reads `.azure/*.env`. A stash cannot leave the machine.

### A sweep can race a live session

`az-mafd-issue-156` was observed with three uncommitted files at the start of the grilling session
that produced this ADR, and clean twenty minutes later: another session had finished four minutes
before. A sweep that acts by default has to assume a worktree may be in use *right now*.

## Decision

**An agent worktree lives inside `<repo>.worktrees/`, and is collected once every commit in it is
reachable from `origin/main`.**

Concretely:

1. **Location.** Every worktree of this repository lives inside
   `az-multi-agent-flw-demo.worktrees/`. Nothing goes in the parent directory, ever. Nesting below
   the container is free — git-loopy keeps `<run-id>/<lane>` unchanged, because the rule is about
   the containing folder and not about a naming scheme, and there is no reason to disturb tooling
   that is already correct and already tested.

2. **Lifetime.** A worktree is collected when `git merge-base --is-ancestor HEAD origin/main`
   succeeds, after a fetch. Against the remote ref, never against local `main`. This covers a
   branch and a detached HEAD identically.

3. **The sweep acts by default, and never `--force`s.** `git worktree remove` refuses a dirty
   worktree on its own; that refusal is a feature and is not overridden.

4. **Uncommitted files are stashed, then the worktree is removed.**
   `git stash push --include-untracked` with a message naming the worktree, its branch and the
   date. Local, reversible, and incapable of publishing anything.

5. **It escalates in exactly two cases** — the stash failed, or the worktree holds commits that
   exist on no remote and is therefore the only copy of that work. Both exit non-zero, having
   removed nothing.

6. **It skips a worktree that is locked or was modified recently** (15 minutes), so a running
   session is stood down from before any other question is asked about it.

7. **The trigger is creation.** `scripts/worktree.sh add <slug>` makes the worktree in the right
   place and then sweeps. Creation is the one event guaranteed to happen — it happened thirteen
   times — so the folder is smallest exactly when a new agent is about to look at it, and there is
   no new habit for anyone to remember.

8. **A worktree another tool owns is reported, never collected.** git-loopy creates lanes under
   `<run-id>/<lane>` and manages their lifecycle across a run. Ownership is read from structure —
   anything more than one level below the container was placed by a run, because `add` creates
   exactly one level down — or from an owned branch namespace. Ownership outranks every other
   state, including the one that would otherwise escalate.

The decision logic lives in `scripts/worktree_hygiene.py` as pure functions over a `Worktree`
record, so `src/tests/ci/test_worktree_hygiene.py` can test the ladder that decides whether
uncommitted work survives without a repository, a remote, or a disk — the same separation every
check under `scripts/preflight/` uses.

## Considered Options

**Remove when the branch merges to `main`.** Rejected on the wording, not the intent: it reads
local `main`, and it cannot distinguish a landed branch from a stale one. "Reachable from
`origin/main`" is what it meant.

**Refuse dirty worktrees and move on.** The first draft of this rule. Rejected because it leaves the
clutter it was written to remove, and leaves it in the least legible state — a folder that is mostly
collected, with survivors nobody explains. Remediating and reporting leaves nothing unaccounted for.

**Commit uncommitted work to a rescue branch and push it.** Rejected: it is the one remediation that
can publish a secret, in a public repository, against a tenant this repository is careful about
(ADR-041). A stash achieves the same preservation with none of the exposure.

**Age-based collection.** Rejected: age is uncorrelated with safety. `az-mafd-issue-106` was among
the oldest and held the only copy of eight files.

**Collecting git-loopy's lanes too.** Rejected once the sweep was run: it found thirty worktrees,
not thirteen, and seventeen of them were git-loopy's. A run that is paused, blocked, or waiting on a
gate is indistinguishable from an abandoned worktree by idleness alone, so collecting a landed lane
could pull the floor out from under a live run. git-loopy's container is one folder entry either
way, and the clutter this ADR exists to remove was the flat siblings. Deferring costs a line in a
report; collecting costs a run.

**A CI test asserting no misplaced worktrees exist.** Rejected as theatre. CI checks out a fresh
clone with zero worktrees, so the assertion would pass vacuously forever — the same limit
`docs/agents/wayfinder.md` already concedes about home-directory state. What CI *can* assert is that
the sanctioned path and the documented rule agree, and that is what it asserts.

**Fix the shared skills instead.** Rejected for this ADR, and kept as a separate concern. There is
nothing in the skills to fix — none of them mention worktrees — and there is no global instruction
file to put a cross-repository rule in. Writing one here would be promising something nothing
enforces.

## Consequences

- The parent directory holds projects again. Thirteen entries became three, and the three that
  remain are named in the sweep's report with the reason each was kept.
- `scripts/worktree.sh add` is the sanctioned way to make a worktree of this repository. An agent
  that reaches for `git worktree add ../<slug>` is contradicting `AGENTS.md`.
- Collection is coupled to `origin/main`, so a worktree whose branch is still in flight is kept
  indefinitely and deliberately. The folder is bounded by *work in progress*, not by time.
- The sweep can be wrong about a live session — the mtime and lock guards are heuristics. The cost
  of being wrong is bounded to a `git stash pop`, which is why acting by default is acceptable at
  all.
- Nothing here is enforced outside this repository. Every other checkout in that folder remains
  exposed to the same improvisation; that problem is tracked separately.

## References

- Issue #161 — the decision and the evidence behind it
- [ADR-005](./005-declare-feedback-loops-in-agents-md.md) — why a rule that matters is declared in
  `AGENTS.md` and backed by a script in `scripts/`
- [ADR-041](./041-the-copilot-studio-chat-url-is-a-credential.md) — why the remediation stashes
  rather than commits
- [docs/agents/wayfinder.md](../agents/wayfinder.md) — the precedent for what CI cannot check about
  a developer's machine
- `scripts/worktree_hygiene.py`, `scripts/worktree.sh`, `src/tests/ci/test_worktree_hygiene.py`
