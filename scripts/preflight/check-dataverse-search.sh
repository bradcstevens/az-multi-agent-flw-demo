#!/usr/bin/env bash
# Preflight: is Dataverse search enabled and synced in the Default environment?
#
# Re-runnable check behind the finding recorded in
# docs/preflight/dataverse-search.md.
#
# Exits non-zero if any check fails, so it can be wired into a feedback loop.
#
#   scripts/preflight/check-dataverse-search.sh                 # read only
#   scripts/preflight/check-dataverse-search.sh --probe         # + prove the sync
#   scripts/preflight/check-dataverse-search.sh --enable --probe # + turn it on
#
# A bare run reads the toggle and the index status. It deliberately does NOT
# probe, because a probe writes a document into Dataverse — asking "is it on?"
# should not leave litter in an environment that cannot be restored.
#
# --probe writes a uniquely marked document, polls the search index until the
# marker comes back **out of the file's content**, and deletes the document
# again. That distinction is the point of the check: the toggle is true the
# instant the PATCH returns, while the index sync behind it runs on its own
# clock, and only the sync unblocks #17.
#
# --enable turns Dataverse search on if it is off, then re-reads rather than
# assuming. It needs Dataverse System Administrator — see
# docs/preflight/dataverse-admin-role.md, and its --elevate if the role is lost.
#
# --export <dir> writes a solution export into <dir>. A Default environment
# cannot be backed up, restored or deleted, so that zip is the only copy of its
# customisations that exists. --solution <uniquename> overrides which one.
#
# --environment <id> checks the environment identifier shown in the Copilot
# Studio URL instead of the tenant's Default one.
#
# The logic lives in dataverse_search.py so it can be unit-tested by the
# CI-tooling loop (scripts/ci-tests.sh); this wrapper only fixes the entry point.

set -euo pipefail

command -v az >/dev/null 2>&1 || { echo "az CLI not found on PATH" >&2; exit 2; }

exec python3 "$(dirname "${BASH_SOURCE[0]}")/dataverse_search.py" "$@"
