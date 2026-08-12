#!/usr/bin/env bash
# Preflight: does the Default environment's Copilot Studio meter bill pay-as-you-go?
#
# Re-runnable check behind the finding recorded in
# docs/preflight/copilot-studio-payg-meter.md.
#
# Exits non-zero if any check fails, so it can be wired into a feedback loop.
#
#   scripts/preflight/check-copilot-studio-meter.sh          # check only
#   scripts/preflight/check-copilot-studio-meter.sh --link   # + attach the
#                                                            #   Default environment
#
# The logic lives in copilot_studio_meter.py so it can be unit-tested by the
# CI-tooling loop (scripts/ci-tests.sh); this wrapper only fixes the entry point.

set -euo pipefail

command -v az >/dev/null 2>&1 || { echo "az CLI not found on PATH" >&2; exit 2; }

exec python3 "$(dirname "${BASH_SOURCE[0]}")/copilot_studio_meter.py" "$@"
