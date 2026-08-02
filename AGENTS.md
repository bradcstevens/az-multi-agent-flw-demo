# AGENTS.md

Repository instructions for coding agents working in this repo.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `bradcstevens/az-multi-agent-flw-demo`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles plus the additive `parallel-safe` marker. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Feedback loops

Run the loops your change touches before committing. Each command is self-contained: it
bootstraps a virtualenv from `.github/requirements.txt` on first use and is a no-op
re-install afterwards, so it can be run from a clean checkout with nothing but `python3`
on `PATH`. Set `DEV_VENV` to share one virtualenv across git worktrees.

| Loop | Command | Covers |
| --- | --- | --- |
| Backend lint | `bash scripts/backend-lint.sh` | flake8 over `src/backend`, same config as `.github/workflows/pylint.yml`. |
| Backend tests | `bash scripts/backend-tests.sh` | The Two-phase test invocation over `src/tests/backend` with the 80% coverage gate, same as `.github/workflows/test.yml`. |

Notes:

- The **Two-phase test invocation** is load-bearing, not incidental — see `CONTEXT.md`.
  `src/tests/backend/test_app.py` mutates `sys.modules` and the environment at import
  time, so it runs first in its own pytest process and the rest of the suite follows
  with `--cov-append`. Preserve both phases.
- A bare `pytest` from the repo root is **not** a loop: it collects `test_mcp_tools.py`
  (which dials a live MCP server) and `tests/e2e-test` (which needs Playwright). Scope
  runs to `src/tests/backend`.
- Coverage and lint configuration live in the root `pyproject.toml` and `.flake8`. There
  is no `.coveragerc`.
- A red integration gate is not always a red loop. The runner's diagnostic log,
  `.git-loopy/logs/<iso>-<run_id>.log`, distinguishes "gate could not run" (no runnable
  table) and "publish failed" (e.g. a dirty base worktree) from a loop that actually
  failed. Read it before assuming the loops are broken.
