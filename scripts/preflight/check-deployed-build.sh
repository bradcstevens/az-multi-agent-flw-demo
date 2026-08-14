#!/usr/bin/env bash
# Preflight: is the deployed build the build we think it is?
#
# Re-runnable check behind the record in docs/preflight/deployed-build.md,
# and the answer to ADR-018.
#
# Read-only: an `az containerapp list` and a handful of `git` queries. Nothing
# here writes to the tenant or moves a ref, so it can be run before every
# rehearsal and before every validator run without cost.
#
#   scripts/preflight/check-deployed-build.sh
#   scripts/preflight/check-deployed-build.sh --resource-group rg-other
#   scripts/preflight/check-deployed-build.sh --json
#
# Exit codes, and the difference between them is the point:
#
#   0  every check passed — the deployment is this commit
#   1  a check FAILED — the deployment is a different commit, and the report
#      names the distance and what is not deployed
#   3  nothing failed and something could not be PROVED. An image whose tag
#      names no commit, or a commit this checkout has never heard of. ADR-018:
#      treating unknown as a pass rebuilds the exact hole this closes.
#
# The logic lives in deployed_build.py so it can be unit-tested by the
# CI-tooling loop (scripts/ci-tests.sh); this wrapper only fixes the entry point.

set -euo pipefail

command -v az >/dev/null 2>&1 || { echo "az CLI not found on PATH" >&2; exit 2; }
command -v git >/dev/null 2>&1 || { echo "git not found on PATH" >&2; exit 2; }

exec python3 "$(dirname "${BASH_SOURCE[0]}")/deployed_build.py" "$@"
