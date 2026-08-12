#!/usr/bin/env bash
# Preflight: does the deployed environment match what the vanilla flavour promises?
#
# Re-runnable check behind the finding recorded in
# docs/preflight/deployed-environment.md.
#
# Exits non-zero if any check fails, so it can be wired into a feedback loop.
#
#   scripts/preflight/check-deployed-environment.sh
#   scripts/preflight/check-deployed-environment.sh --no-probe
#   scripts/preflight/check-deployed-environment.sh --resource-group rg-other
#
# The roster is probed with one real request per model deployment by default,
# because #12's fact is that the models are *reachable*, not merely deployed.
# --no-probe skips that and reports the roster as unproven.
#
# The logic lives in deployed_environment.py so it can be unit-tested by the
# CI-tooling loop (scripts/ci-tests.sh); this wrapper only fixes the entry point.

set -euo pipefail

command -v az >/dev/null 2>&1 || { echo "az CLI not found on PATH" >&2; exit 2; }

exec python3 "$(dirname "${BASH_SOURCE[0]}")/deployed_environment.py" "$@"
