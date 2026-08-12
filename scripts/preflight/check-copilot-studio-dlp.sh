#!/usr/bin/env bash
# Preflight: Copilot Studio data policy and network egress for the SOP agent.
#
# Re-runnable check behind the findings recorded in
# docs/preflight/copilot-studio-data-policy-and-egress.md.
#
# Exits 0 when everything the demo depends on is unblocked and reachable, 1 when
# something is blocked or unreachable, and 2 when a verdict could not be reached
# — the data-policy half needs interactive multi-factor re-authentication that an
# unattended run cannot do, or a required WebSocket row was reached but could not
# be confirmed without a Direct Line secret. Undetermined is not a pass.
#
#   scripts/preflight/check-copilot-studio-dlp.sh              # both halves
#   scripts/preflight/check-copilot-studio-dlp.sh --egress-only # no token needed
#   scripts/preflight/check-copilot-studio-dlp.sh --policies-file saved.json
#
# The data-policy half reads tenant policies with the signed-in Azure CLI
# identity, which needs the Power Platform administrator role. Save the payload
# alongside the record and replay it with --policies-file to re-check a finding
# without a token.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,19p' "$0"
  exit 0
fi

command -v python3 >/dev/null 2>&1 || { echo "python3 not found on PATH" >&2; exit 2; }

# Standard library only, so this runs from a clean checkout with no virtualenv.
exec python3 "$HERE/copilot_studio_preflight.py" "$@"
