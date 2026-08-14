#!/usr/bin/env bash
# The Routing probe (#54) — the centrepiece beat's residual, measured without a
# browser.
#
# NOT A FEEDBACK LOOP, and it must not be added to a workflow. Every sample is a
# live Fast-lane orchestration and a live Direct Line conversation with the
# deployed agent pool, so a pull request cannot run it and a scheduled run would
# spend Copilot Credits on nobody's behalf. The arithmetic over what the samples
# observed is covered by src/tests/ci/test_routing_probe.py, which runs in the
# CI-tooling loop and needs no deployment.
#
#   az login
#   bash scripts/measure-routing.sh                 # 12 turns, one at a time
#   bash scripts/measure-routing.sh --samples 20
#
# Serial by construction, and that is not a throughput decision: the Grounding
# panel's own frame is pushed to *the sole connected user*, so two samples at
# once drop it and the probe reports a working deployment as never having
# called the SOP tool. It did, on its first run, on 2 of 2 samples.
#
# Exit status: 0 every observed turn was answered by the agent the question
# needed and nobody else; 1 at least one was not; 2 nothing was observed at all
# — which is a state to fix, not a rate to measure.
#
# Its record is docs/routing-probe.md.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/dev-venv.sh"
dev_venv_ensure

exec "$VENV_PYTHON" "$REPO_ROOT/scripts/routing_probe.py" "$@"
