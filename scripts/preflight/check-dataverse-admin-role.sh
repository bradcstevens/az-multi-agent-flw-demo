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
#   scripts/preflight/check-dataverse-admin-role.sh --elevate   # + grant it
#
# --environment <id> checks the environment identifier shown in the Copilot
# Studio URL instead of the tenant's Default one, because default-environment
# routing can silently land a maker in a personal Developer environment.
#
# --elevate needs no interactive step and no extra scope: it grants the role
# through a bootstrap application user, which the BAP admin API registers as a
# Dataverse System Administrator and which is deleted again afterwards. The
# signed-in account must be a Global, Power Platform or Dynamics 365 admin.
#
# It is NOT Microsoft's documented applyAdminRole self-elevation: that needs a
# user token carrying UserManagement.Users.Apply, a scope no amount of consent
# adds to an Azure CLI token (AADSTS65002 — first-party preauthorisation).
#
# The logic lives in dataverse_admin_role.py so it can be unit-tested by the
# CI-tooling loop (scripts/ci-tests.sh); this wrapper only fixes the entry point.

set -euo pipefail

command -v az >/dev/null 2>&1 || { echo "az CLI not found on PATH" >&2; exit 2; }

exec python3 "$(dirname "${BASH_SOURCE[0]}")/dataverse_admin_role.py" "$@"
