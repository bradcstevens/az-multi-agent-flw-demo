#!/usr/bin/env bash
# CI-tooling tests feedback loop.
#
# Covers the helpers the other loops and .github/workflows/test.yml depend on —
# today, the advisory coverage report. Kept separate from the backend and MCP
# suites because it tests the loops themselves, not the application.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/dev-venv.sh"
dev_python_test_venv_ensure

# No --cov: this suite measures the tooling, not the application, and its
# coverage must not land in the application's report.
"$VENV_PYTHON" -m pytest src/tests/ci -q
