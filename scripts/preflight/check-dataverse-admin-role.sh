#!/usr/bin/env bash
# Preflight: does the build account hold Dataverse System Administrator in the
# Default environment?
#
# Re-runnable check behind the finding recorded in
# docs/preflight/dataverse-admin-role.md.
#
# Exits non-zero if any check fails, so it can be wired into a feedback loop.
#
#   scripts/preflight/check-dataverse-admin-role.sh             # check only
#   scripts/preflight/check-dataverse-admin-role.sh --elevate   # + self-elevate
#
# --environment <id> checks the environment identifier shown in the Copilot
# Studio URL instead of the tenant's Default one, because default-environment
# routing can silently land a maker in a personal Developer environment.
#
# --elevate needs a token carrying the Power Platform API's
# UserManagement.Users.Apply delegated scope, which the Azure CLI is not
# pre-authorised for; consent to it once with:
#
#   az login --scope "https://api.powerplatform.com/UserManagement.Users.Apply"
#
# The logic lives in dataverse_admin_role.py so it can be unit-tested by the
# CI-tooling loop (scripts/ci-tests.sh); this wrapper only fixes the entry point.

set -euo pipefail

command -v az >/dev/null 2>&1 || { echo "az CLI not found on PATH" >&2; exit 2; }

exec python3 "$(dirname "${BASH_SOURCE[0]}")/dataverse_admin_role.py" "$@"
