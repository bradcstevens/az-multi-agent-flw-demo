# ADR-043: The feedback loops' virtualenv is keyed by its inputs and shared across worktrees

## Status

Accepted — amends ADR-005's per-worktree bootstrap

## Date

2026-08-17

## Issue

#115 (auto-resolution of the post-merge gate)

## Context

ADR-005 gave every feedback loop a self-provisioning virtualenv: `scripts/dev-venv.sh` builds
`$REPO_ROOT/.venv` from `.github/requirements.txt`, stamps it with a hash of those pinned inputs,
and re-checks the hash on a warm run. It accepted one cost explicitly:

> A cold worktree pays a one-off dependency install (roughly three to four minutes) on its first
> gate run; subsequent runs are seconds.

What that consequence did not anticipate is **who runs in a cold worktree**. The integration gate
merges each lane into a *fresh* worktree and runs the loops there, so the "one-off" install is not
paid once by a developer — it is paid by every merged lane, every time. The install stands between
each lane and a green gate, and it is the only part of the gate that requires the public package
index to be reachable.

So a network blip is indistinguishable from broken code. Two failures on one machine on
2026-08-17 make the point:

- Issue #117's integration failed its post-merge gate on **Backend lint** and then failed the same
  way on all three auto-resolution attempts — four consecutive reds, none of them about #117's
  diff.
- Issue #115's post-merge gate failed on **Backend lint** while every one of the six loops in
  `AGENTS.md` passed against a warm environment. The lane was green; the bootstrap could not reach
  `files.pythonhosted.org`.

The second failure compounded the first: `flake8` and `pytest` both report a real finding with
exit 1, and the bootstrap failed with exit 1 too. The gate had no way to tell "your code is
broken" from "I could not build an environment to check your code in", so it reported the outage
as a defect in somebody's lane.

Meanwhile the machine already had what it needed. The main checkout carried a fully provisioned,
**stamp-identical** virtualenv the whole time, and the local package cache held every wheel. The
bootstrap simply had no way to look outside the worktree it was standing in — `DEV_VENV` could
point it at one, but nothing set `DEV_VENV`, and a gate does not read `AGENTS.md`'s advice.

## Decision

**A virtualenv is identified by its pinned inputs, not by the worktree that asked for it.**

`dev_venv_ensure` resolves a location before it builds anything, in this order:

1. `DEV_VENV`, when set — an explicit override still wins outright.
2. `$REPO_ROOT/.venv`, when warm — a hand-built environment is used untouched.
3. The **main checkout's** `.venv`, when warm — `git worktree` cuts every lane from one checkout,
   and that checkout has been provisioned since ADR-005.
4. A **shared store** outside every worktree, keyed by the stamp:
   `${XDG_CACHE_HOME:-~/.cache}/az-multi-agent-flw-demo/venv-<stamp>`.

A cold worktree builds into (4), so the *next* worktree to want that dependency set finds it warm
and never reaches the network. Keying on the stamp rather than on the repository is what makes the
store safe to share: a worktree pinning different requirements gets its own entry instead of two
worktrees reinstalling over each other. Builds of one entry are serialised by a lock, and the
stamp is written **last**, so an interrupted build stays cold and is rebuilt rather than silently
used.

`$REPO_ROOT/.venv` is left as a symlink into the resolved store so the `.venv/bin/python`
invocations `AGENTS.md` documents — the Guardrail corpus, the fast-lane measurement — keep working
in a fresh checkout. A real directory is never replaced; only a link is.

**A bootstrap that cannot provision exits 3, not 1.** Exit 1 belongs to flake8 and pytest, and
means a finding about the code. Exit 3 means no conclusion was reached about the code at all — the
same "could not prove" code the `scripts/preflight/` checks already use — and the message says so
in as many words.

The decision logic moves to `scripts/dev_venv.py`, a pure importable module beside the shell entry
point, so the CI-tooling loop unit-tests the verdict without building a virtualenv. That is the
split the preflight checks already use. The shell's job — *carrying* that verdict — is exercised in
the same loop and without a package index, because a distinct exit code that `dev-venv.sh` does not
actually return buys nothing.

## Considered Options

- **Leave it; treat the red gates as flakes and re-run.** Rejected: it had already cost four
  consecutive auto-resolution attempts on #117 plus #115's gate, and each re-run spends an agent
  iteration to re-learn that the network was down. It also trains readers to discount a red gate,
  which is the one thing a gate cannot survive.
- **Tell agents to set `DEV_VENV`.** This is what `AGENTS.md` already said, and it did not help:
  the gate runs the loop commands directly and reads no advice. A convention that only works when
  someone remembers it is not a fix for an unattended runner.
- **Install from the local package cache with `--no-index`.** Rejected: pip still needs an index
  to *resolve* pinned requirements, which the reproduction confirmed — a 6 GB warm cache produced
  `No matching distribution found for fastapi==0.137.1` with the index unreachable. The cache
  makes a working install faster; it does not make a broken index survivable.
- **Vendor wheels into the repository.** Rejected: it trades a network dependency for hundreds of
  megabytes of tracked binaries and a second dependency set to keep honest against
  `.github/requirements.txt`, which ADR-005's consequences already flag as drifting.
- **One shared virtualenv per repository, not per stamp.** Rejected: two worktrees on commits with
  different pins would reinstall over each other on every alternating run — slower than the
  per-worktree build it replaced, and intermittently corrupt.

## Consequences

- The gate stops depending on the package index once any worktree on the machine has provisioned.
  The reproduction — a cold `git worktree` with the index pointed at a dead port — went from
  exit 1 to exit 0.
- A cold *machine* still needs the network, and still fails when it is unreachable. That is
  honest and unavoidable; what changes is that it now fails with exit 3 and a message naming the
  environment, so nobody reads it as a lint error again.
- `$REPO_ROOT/.venv` may now be a symlink. It is already `.gitignore`d, and `.venv/bin/python`
  resolves through it correctly, so the documented manual commands are unaffected.
- A `.venv` that is a real directory is never replaced — deleting one somebody built by hand is
  data loss — so a checkout holding one built for *different* pinned inputs keeps it while the
  loops run elsewhere. That is the one case where `.venv/bin/python` and the loops disagree, and
  the bootstrap says so on stderr rather than letting it be silent.
- The store accumulates one directory per distinct dependency set under `~/.cache`. Old entries
  are inert and can be deleted at any time; the next run rebuilds what it needs.
- `AGENTS.md`'s "set `DEV_VENV` to share one virtualenv across git worktrees" is now a manual
  override of behaviour that happens by default. It is kept, because pointing several checkouts of
  *different* repositories at one environment is still a thing people do.

## References

- [ADR-005](./005-declare-feedback-loops-in-agents-md.md) — the feedback-loop table and the
  per-worktree bootstrap this amends
- `scripts/dev_venv.py` — the resolution logic
- `scripts/dev-venv.sh` — the shell entry point every loop sources
- `src/tests/ci/test_dev_venv.py` — the CI-tooling loop's proof of both rules
