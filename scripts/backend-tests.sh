#!/usr/bin/env bash
# Backend tests feedback loop — the Two-phase test invocation (see CONTEXT.md).
#
# src/tests/backend/test_app.py mutates sys.modules and the environment at import
# time, so it runs first in its own pytest process; the rest of the suite then
# runs with --cov-append and --ignore on that file. Mirrors the workflow's two
# backend pytest invocations, including its advisory coverage report.
#
# Both phases deselect the `integration` marker: the Guardrail corpus (#13)
# scores against the live embedding deployment, which an unattended run has no
# subscription for. Run it deliberately -- see that suite's module docstring.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/dev-venv.sh"
dev_python_test_venv_ensure

ISOLATED_TEST="src/tests/backend/test_app.py"

# Phase 1 — the import-time-mutating module, alone in its own process.
"$VENV_PYTHON" -m pytest "$ISOLATED_TEST" \
  --cov=src/backend \
  -m "not integration" \
  -q

# Phase 2 — everything else, appending to phase 1's coverage data.
"$VENV_PYTHON" -m pytest src/tests/backend \
  --ignore="$ISOLATED_TEST" \
  --cov=src/backend \
  --cov-append \
  --cov-report=term \
  --cov-report=xml \
  --junitxml=pytest.xml \
  -m "not integration" \
  -q

# The advisory 80% report — same script CI runs, so the loop and the workflow
# report the same number the same way. Never fails the loop.
"$VENV_PYTHON" scripts/coverage_report.py
