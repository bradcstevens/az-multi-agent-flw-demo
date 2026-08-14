#!/usr/bin/env bash
# The rehearsal: ten consecutive Demo validator runs of the centrepiece beat.
#
# Issue #54. The walkthrough's opening beat -- "How do I close the store?",
# answered from the SOP corpus through Copilot Studio -- came back as the honest
# miss two runs in eight on the afternoon the Demo validator first ran. One
# green run is what that state already produces three times in four, so the beat
# is proved by ten consecutive runs or it is not proved at all.
#
#   bash scripts/sop-rehearsal.sh                 # ten runs against the deployment
#   bash scripts/sop-rehearsal.sh --runs 3        # a shorter look
#   bash scripts/sop-rehearsal.sh --target local  # against a local surface
#
# This is NOT a feedback loop and must not be added to one, for the reason
# `docs/demo-validator.md` gives about the validator it runs: it drives a real
# browser against a running deployment and holds ten live conversations with the
# agent pool. A pull request cannot run it and a schedule would spend Copilot
# Credits on nobody's behalf. Run it deliberately, after `az login`, and read
# the report.
#
# It stops at the first red run and names the layer that run implicates -- the
# orchestrator's routing, its rephrasing, or the agent's Dataverse index. The
# decision logic lives in sop_rehearsal.py so the CI-tooling loop can unit-test
# the verdict without a tenant; this wrapper only fixes the entry point.

set -euo pipefail

exec python3 "$(dirname "${BASH_SOURCE[0]}")/sop_rehearsal.py" "$@"
