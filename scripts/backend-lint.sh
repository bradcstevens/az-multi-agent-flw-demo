#!/usr/bin/env bash
# Backend lint feedback loop — mirrors the flake8 step in .github/workflows/pylint.yml.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/dev-venv.sh"
dev_venv_ensure

cd "$REPO_ROOT"

"$VENV_PYTHON" -m flake8 --config=.flake8 src/backend
