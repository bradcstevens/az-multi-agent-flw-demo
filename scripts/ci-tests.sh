#!/usr/bin/env bash
# CI-tooling tests feedback loop.
#
# Covers the repo's own tooling: the helpers the other loops and
# .github/workflows/test.yml depend on (the advisory coverage report) and the
# re-runnable preflight checks under scripts/preflight. Kept separate from the
# backend and MCP suites because it tests the tooling, not the application.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/dev-venv.sh"
dev_python_test_venv_ensure

# No --cov: this suite measures the tooling, not the application, and its
# coverage must not land in the application's report.
"$VENV_PYTHON" -m pytest src/tests/ci -q
