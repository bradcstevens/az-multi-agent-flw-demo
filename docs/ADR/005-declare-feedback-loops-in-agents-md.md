# ADR-005: Declare the feedback loops in AGENTS.md, backed by scripts in `scripts/`

## Status

Accepted

## Date

2026-08-01

## Issue

#9 (spec #1)

## Context

After the MACAE merge (ADR-004) this repository has real tooling — pytest, coverage and flake8 —
but `AGENTS.md` declared no **feedback loops**. That is not merely a documentation gap: the
integration gate reads the `## Feedback loops` table out of `AGENTS.md` and runs those commands to
decide whether a merged lane is green. With no table it cannot gate at all and treats the merge as
red, so every lane would fail integration regardless of the quality of its work.

Three properties of this repo make a naive table insufficient:

- The **Two-phase test invocation** is load-bearing. `src/tests/backend/test_app.py` mutates
  `sys.modules` and the environment at import time, so it must run first in its own pytest process
  and the rest of the suite must follow with `--cov-append`. A single `pytest` command silently
  loses that.
- A bare `pytest` from the repo root is red by construction: it collects the root
  `test_mcp_tools.py`, which dials a live MCP server during collection, and `tests/e2e-test`, which
  needs Playwright.
- The gate runs each command through a plain shell in a **fresh worktree** with no virtualenv
  activated and no `PYTHONPATH` set. A command like `pytest ...` assumes an environment that a new
  worktree does not have.

Upstream also left `--cov-config=.coveragerc` in `.github/workflows/test.yml` after consolidating
that file into the root `pyproject.toml`, so the flag pointed at a file that no longer exists.

## Decision

Declare exactly two feedback loops in the `## Feedback loops` table of `AGENTS.md` — **Backend
lint** and **Backend tests** — and give each a single self-contained script under `scripts/`:

| Loop | Command |
| --- | --- |
| Backend lint | `bash scripts/backend-lint.sh` |
| Backend tests | `bash scripts/backend-tests.sh` |

Both scripts source `scripts/dev-venv.sh`, which bootstraps a virtualenv from
`.github/requirements.txt` (plus flake8) and stamps it with a hash of those inputs, so a cold
worktree self-provisions and a warm one re-checks a hash instead of re-installing. `DEV_VENV`
overrides the location so one environment can be shared across git worktrees.

**Amended by [ADR-043](./043-the-feedback-loops-virtualenv-is-shared-across-worktrees.md):** the
virtualenv is identified by that stamp rather than by the worktree that asked for it, so sharing
one environment across worktrees is the default and `DEV_VENV` is only the manual override.

`scripts/backend-tests.sh` encodes the Two-phase test invocation and the 80% coverage threshold
that `.github/workflows/test.yml` enforces, so the loop an agent runs locally and the gate the
runner runs at integration are the same check CI runs.

The dead `--cov-config=.coveragerc` flag is removed from `.github/workflows/test.yml`, and its path
filters now watch the root `pyproject.toml` (where that config actually lives) and `scripts/`.

## Consequences

- Integration can gate. A lane that breaks lint or the backend suite is caught at merge time
  instead of landing on the base branch.
- The loop commands have one definition. Changing how the suite runs means changing one script,
  not an `AGENTS.md` table, a workflow file and every agent's memory of the incantation.
- A cold worktree pays a one-off dependency install (roughly three to four minutes) on its first
  gate run; subsequent runs are seconds. **Amended by
  [ADR-043](./043-the-feedback-loops-virtualenv-is-shared-across-worktrees.md):** this consequence
  did not anticipate that the integration gate runs every merged lane in a *fresh* worktree, so the
  install was paid every time and stood between each lane and a green gate. Only the first worktree
  on a machine to want a given dependency set pays it now, and a bootstrap that cannot provision
  exits 3 rather than the 1 that means a finding about the code.
- The scripts install `.github/requirements.txt`, not `src/backend/pyproject.toml`. Those two have
  drifted — the backend project pins the Agent Framework packages and, as of this ADR,
  `agent-framework==1.6.0` and `agent-framework-foundry==1.6.0` do not resolve together against
  `agent-framework-core[all]`. The suite passes without them because it stubs those imports.
  Reconciling the two dependency sets is deliberately left as follow-up work; the loops mirror what
  CI installs today.
- Loops are fail-fast and ordered cheapest-first: lint runs before tests.
