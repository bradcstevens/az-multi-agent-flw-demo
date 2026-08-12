# AGENTS.md

Repository instructions for coding agents working in this repo.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `bradcstevens/az-multi-agent-flw-demo`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles plus the additive `parallel-safe` marker. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Preflight records

Deployment preconditions that were verified before the build started are recorded under
`docs/preflight/`, one file per verified precondition, each backed by a re-runnable check in
`scripts/preflight/`. Read the record before assuming a subscription, tenant or environment
capability — and re-run its script rather than re-deriving the finding by hand.

| Record | Check |
| --- | --- |
| `docs/preflight/copilot-studio-payg-meter.md` | `scripts/preflight/check-copilot-studio-meter.sh` |
| `docs/preflight/dataverse-admin-role.md` | `scripts/preflight/check-dataverse-admin-role.sh` |
| `docs/preflight/copilot-studio-data-policy-and-egress.md` | `scripts/preflight/check-copilot-studio-dlp.sh` |
| `docs/preflight/deployed-environment.md` | `scripts/preflight/check-deployed-environment.sh` |

Each check keeps its decision logic in a pure, importable Python module beside the shell entry
point, so the CI-tooling loop can unit-test the verdict without a live tenant.

## Feedback loops

Run the loops your change touches before committing. Each command is self-contained: it
bootstraps a virtualenv from `.github/requirements.txt` on first use and is a no-op
re-install afterwards, so it can be run from a clean checkout with nothing but `python3`
on `PATH`. Set `DEV_VENV` to share one virtualenv across git worktrees.

| Loop | Command | Covers |
| --- | --- | --- |
| Backend lint | `bash scripts/backend-lint.sh` | flake8 over `src/backend`, same config as `.github/workflows/pylint.yml`. |
| Backend tests | `bash scripts/backend-tests.sh` | The Two-phase test invocation over `src/tests/backend` with an advisory 80% coverage report. |
| MCP server tests | `bash scripts/mcp-tests.sh` | pytest over `src/tests/mcp_server` with MCP coverage; CI appends this coverage to the backend report. |
| CI-tooling tests | `bash scripts/ci-tests.sh` | pytest over `src/tests/ci` — the repo's own tooling: the helpers the loops and `test.yml` share (the advisory coverage report and the `scripts/preflight/` checks) plus the durable record's invariants (ADR index, corrections record, documentation links). |

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
- **The 80% coverage threshold is advisory, not a gate.** `scripts/coverage_report.py`
  prints the number and emits a GitHub Actions warning below the threshold, but always
  exits zero; only a missing or unreadable `coverage.xml` is an error. Both the Backend
  tests loop and `test.yml` call that one script, so do not reintroduce `--cov-fail-under`
  or a threshold check inline in the workflow.
- A red integration gate is not always a red loop. The runner's diagnostic log,
  `.git-loopy/logs/<iso>-<run_id>.log`, distinguishes "gate could not run" (no runnable
  table) and "publish failed" (e.g. a dirty base worktree) from a loop that actually
  failed. Read it before assuming the loops are broken.
