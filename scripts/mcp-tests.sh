#!/usr/bin/env bash
# MCP server tests feedback loop.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/dev-venv.sh"
dev_python_test_venv_ensure

# Coverage is intentionally advisory; do not add --cov-fail-under here.
"$VENV_PYTHON" -m pytest src/tests/mcp_server \
  --cov=src/mcp_server \
  --cov-report=term \
  --cov-report=xml \
  -q
