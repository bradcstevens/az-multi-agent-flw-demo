#!/usr/bin/env bash
# Backend tests feedback loop — the Two-phase test invocation (see CONTEXT.md).
#
# src/tests/backend/test_app.py mutates sys.modules and the environment at import
# time, so it runs first in its own pytest process; the rest of the suite then
# runs with --cov-append and --ignore on that file. Mirrors the two pytest
# invocations in .github/workflows/test.yml, including its 80% coverage gate.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/dev-venv.sh"
dev_venv_ensure

cd "$REPO_ROOT"

export PYTHONPATH="src:src/backend"

ISOLATED_TEST="src/tests/backend/test_app.py"

# Phase 1 — the import-time-mutating module, alone in its own process.
"$VENV_PYTHON" -m pytest "$ISOLATED_TEST" \
  --cov=src/backend \
  -q

# Phase 2 — everything else, appending to phase 1's coverage data.
"$VENV_PYTHON" -m pytest src/tests/backend \
  --ignore="$ISOLATED_TEST" \
  --cov=src/backend \
  --cov-append \
  --cov-report=term \
  --cov-report=xml \
  --cov-fail-under=80 \
  --junitxml=pytest.xml \
  -q
