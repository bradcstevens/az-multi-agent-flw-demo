#!/usr/bin/env bash
# Check: is the deployed surface the demonstration, or the accelerator?
#
# Re-runnable check behind the record in docs/preflight/deployed-surface.md.
#
# Exits non-zero if any check fails, so it can be wired into a feedback loop.
#
#   scripts/preflight/check-deployed-surface.sh
#   scripts/preflight/check-deployed-surface.sh --no-probe
#   scripts/preflight/check-deployed-surface.sh --resource-group rg-other
#
# `check-deployed-environment.sh` proves the infrastructure and stays green
# against Container Apps running last month's code. This one reads the running
# deployment the way the presenter will — the page the frontend serves, the
# Quick Tasks the backend hands back, the setting the SOP tool needs, and one
# real procedure question — because that is the only way the drift showed.
#
# The question is asked by default. --no-probe skips it and reports the
# cross-platform hop as unproven, exiting non-zero: a run that asked nothing is
# no evidence that the Copilot Studio SOP agent is reachable.
#
# The logic lives in deployed_surface.py so it can be unit-tested by the
# CI-tooling loop (scripts/ci-tests.sh); this wrapper only fixes the entry point.

set -euo pipefail

command -v az >/dev/null 2>&1 || { echo "az CLI not found on PATH" >&2; exit 2; }

exec python3 "$(dirname "${BASH_SOURCE[0]}")/deployed_surface.py" "$@"
