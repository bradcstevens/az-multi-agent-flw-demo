#!/usr/bin/env bash
# The Copilot Studio SOP agent: author it, publish it, prove it over Direct Line.
#
# Re-runnable check behind the record in docs/copilot-studio/sop-agent.md.
#
# Exits non-zero if any check fails, so it can be wired into a feedback loop.
#
#   scripts/copilot_studio/check-sop-agent.sh                       # ask it
#   scripts/copilot_studio/check-sop-agent.sh --provision --publish --probe
#   scripts/copilot_studio/check-sop-agent.sh --export .artifacts
#
# A bare run probes: it opens a fresh Direct Line conversation and asks the two
# rehearsed questions. Unlike the Dataverse search preflight, probing here
# leaves nothing behind — a conversation is not a record — so the run that
# gathers no evidence is the one that needs a reason, not the other way round.
#
# --provision creates or converges the agent: the bot row, its instructions,
# the greeting, the honest-miss Fallback topic and the ten SOP documents from
# content/sop/docx. Idempotent by schema name.
#
# --publish publishes and waits. Direct Line serves published content, and
# `PvaPublish` returns before the publish has finished, so the wait matters:
# a probe against an in-flight publish reads the previous content.
#
# --export <dir> writes a solution export into <dir>. A Default environment
# cannot be backed up, restored or deleted, so that zip is the only copy of the
# agent that exists outside the tenant. Re-export after every change worth
# keeping.
#
# --environment <id> works against the environment identifier shown in the
# Copilot Studio URL instead of the tenant's Default one.
#
# The logic lives in sop_agent.py so it can be unit-tested by the CI-tooling
# loop (scripts/ci-tests.sh); this wrapper only fixes the entry point.

set -euo pipefail

command -v az >/dev/null 2>&1 || { echo "az CLI not found on PATH" >&2; exit 2; }

exec python3 "$(dirname "${BASH_SOURCE[0]}")/sop_agent.py" "$@"
