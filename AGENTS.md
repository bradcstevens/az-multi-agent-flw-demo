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
| `docs/preflight/dataverse-search.md` | `scripts/preflight/check-dataverse-search.sh --probe` |
| `docs/preflight/copilot-studio-data-policy-and-egress.md` | `scripts/preflight/check-copilot-studio-dlp.sh` |
| `docs/preflight/azure-subscription-rights-and-policy.md` | `scripts/preflight/check-azure-subscription.sh` |
| `docs/preflight/deployed-environment.md` | `scripts/preflight/check-deployed-environment.sh` |
| `docs/preflight/deployed-surface.md` | `scripts/preflight/check-deployed-surface.sh` |

Each check keeps its decision logic in a pure, importable Python module beside the shell entry
point, so the CI-tooling loop can unit-test the verdict without a live tenant.

## Live tenant records

Work that lives in the tenant rather than in this repository is recorded the same way — a record
under `docs/`, backed by a re-runnable check whose logic is unit-tested by the CI-tooling loop.

| Record | Check |
| --- | --- |
| `docs/copilot-studio/sop-agent.md` | `scripts/copilot_studio/check-sop-agent.sh` |
| `docs/copilot-studio/direct-line-client.md` | `scripts/copilot_studio/check-sop-agent.sh --probe` |

The Copilot Studio SOP agent is authored **from this repository**, through the Dataverse Web API,
because `pac` cannot authenticate unattended. Change the agent by editing
`scripts/copilot_studio/sop_agent.py` and re-running the check with `--provision --publish --probe`,
not by editing it in the portal: the check fails on any component this repository did not author,
and a portal edit is a behaviour nobody here can review.

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
| CI-tooling tests | `bash scripts/ci-tests.sh` | pytest over `src/tests/ci` — the repo's own tooling: the helpers the loops and `test.yml` share (the advisory coverage report and the `scripts/preflight/` checks) plus the durable record's invariants (ADR index, corrections record, documentation links), the presenter runbook's (every string it quotes is the repository's own) and the deploy path's stock-pack suppression. |
| Frontend tests | `bash scripts/frontend-tests.sh` | vitest over `src/App/src` — the transparency panels and the WebSocket message contract they render. `npm ci` on first use, a no-op afterwards; runs in `.github/workflows/frontend-tests.yml`. |
| SOP corpus | `python3 -m pytest tools/tests -q` | `content/sop/` and its builder `tools/sop_corpus/`. After editing a source, rebuild with `PYTHONPATH=tools python3 -m sop_corpus build`. |
| Demo validator | `bash scripts/e2e-tests.sh` | TypeScript `@playwright/test` over `e2e/` — the walkthrough asserted through a real browser against a **running deployment**. The only loop here that observes one; every other loop runs against fakes. `--target local` runs the same specs against a local surface. Not in any workflow, deliberately (see below). |

Notes:

- The **Two-phase test invocation** is load-bearing, not incidental — see `CONTEXT.md`.
  `src/tests/backend/test_app.py` mutates `sys.modules` and the environment at import
  time, so it runs first in its own pytest process and the rest of the suite follows
  with `--cov-append`. Preserve both phases.
- A bare `pytest` from the repo root is **not** a loop: it collects `test_mcp_tools.py`,
  which dials a live MCP server. Scope runs to `src/tests/backend`.
- The **Demo validator** is not in any workflow and must not be added to one. It drives a
  real browser against a running deployment and holds a live conversation with the agent
  pool, so a pull request cannot run it and a scheduled run would spend Copilot Credits on
  nobody's behalf. What *can* be asserted without a tenant — that the loop exists, that the
  recording is unconditional, that the expectation is read out of the repository — is
  asserted by `src/tests/ci/test_e2e_wiring.py` in the CI-tooling loop. Run the validator
  deliberately, after `az login`, and read `e2e/artifacts/report`. Its record is
  `docs/demo-validator.md`.
- Both backend phases pass `-m "not integration"`, so the **Guardrail corpus** — which
  scores against the live embedding deployment — stays out of unattended runs.
  `src/tests/ci/test_integration_marker.py` fails if that deselection is dropped from
  either the loop or `test.yml`. Run the corpus deliberately, after `az login`:

  ```bash
  export GUARDRAIL_EMBEDDING_ENDPOINT="$(grep AZURE_OPENAI_ENDPOINT .azure/macae-flw-v1/.env | cut -d= -f2- | tr -d '"')"
  .venv/bin/python -m pytest src/tests/backend/guardrail/test_guardrail_corpus.py -m integration -s
  ```
- **Fast-lane latency** is measured by `scripts/measure_fast_lane_latency.py`, not by a loop —
  it needs a live Foundry project and an agent pool to orchestrate. ADR-013 makes the number
  the sole trigger for reopening the orchestrator-bypass question, so run it and read it before
  building anything faster:

  ```bash
  export FAST_LANE_PROJECT_ENDPOINT="$(grep AZURE_AI_PROJECT_ENDPOINT .azure/macae-flw-v1/.env | cut -d= -f2- | tr -d '"')"
  python scripts/measure_fast_lane_latency.py     # add --plan-review for the Deliberate lane
  ```

  It needs `agent_framework`, which the repo's `.venv` deliberately does **not** carry (the
  backend suites stub it), so run it from the backend's own environment —
  `cd src/backend && uv sync && uv run python ../../scripts/measure_fast_lane_latency.py`.
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
