#!/usr/bin/env bash
# CI-tooling tests feedback loop.
#
# Covers the helpers the other loops and .github/workflows/test.yml depend on —
# the advisory coverage report — plus the invariants of the durable record (the
# ADR index, the corrections to the superseded requirements document, and
# documentation links). Kept separate from the backend and MCP suites because it
# tests the repository's own tooling and documentation, not the application.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/dev-venv.sh"
dev_python_test_venv_ensure

# No --cov: this suite measures the tooling, not the application, and its
# coverage must not land in the application's report.
"$VENV_PYTHON" -m pytest src/tests/ci -q
