#!/usr/bin/env bash
# The Demo validator feedback loop (issue #47, ADR-016).
#
# The one loop in this repository that observes a **deployment**. Every other
# loop runs against fakes and stubs, which is how the Container Apps came to be
# running the stock accelerator for weeks while all of them stayed green.
#
# Shaped like the Python loops where it matters: runnable from a clean checkout
# with nothing but `node` and `az` on PATH, a no-op re-install afterwards. What
# ADR-016 changed is the language behind the script, not the contract in front
# of it.
#
#   bash scripts/e2e-tests.sh                    # the deployed surface
#   bash scripts/e2e-tests.sh --target local     # a local `npm run dev`
#   bash scripts/e2e-tests.sh --headed           # anything after is Playwright's
#
# A passing run leaves a video of the walkthrough and an HTML report under
# `e2e/artifacts/`. Both are produced on **every** run, passing included: the
# recording is the demonstration's own last-resort fallback, not a failure
# artefact.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TARGET="${E2E_TARGET:-deployed}"
PLAYWRIGHT_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --target=*)
      TARGET="${1#*=}"
      shift
      ;;
    --)
      # Everything after `--` is Playwright's, verbatim — including a literal
      # `--target`, which is Playwright's own project filter. The separator
      # itself must not travel: Playwright reads a bare `--` as the start of
      # its test-name filters, so forwarding it turns `--headed` into a grep
      # for a test called "--headed" and the run reports "No tests found" —
      # a green-looking exit from a suite that ran nothing.
      shift
      PLAYWRIGHT_ARGS+=("$@")
      break
      ;;
    *)
      PLAYWRIGHT_ARGS+=("$1")
      shift
      ;;
  esac
done

if [ "$TARGET" != "deployed" ] && [ "$TARGET" != "local" ]; then
  echo "--target must be 'deployed' or 'local', not '$TARGET'" >&2
  exit 2
fi

# Where the deployment is, is written down once — in the preflight check that
# already reads it. Asking that module rather than repeating the resource group
# here is what keeps the validator and `check-deployed-surface.sh` pointed at
# the same deployment.
if [ "$TARGET" = "deployed" ] && [ -z "${E2E_BASE_URL:-}" ]; then
  read -r RESOURCE_GROUP FRONTEND_APP <<<"$(
    cd "$REPO_ROOT" && python3 -c "
import sys
sys.path.insert(0, 'scripts/preflight')
import deployed_surface as surface
print(surface.RESOURCE_GROUP, surface.FRONTEND_CONTAINER_APP)
"
  )"
  FQDN="$(az containerapp show \
    -g "$RESOURCE_GROUP" -n "$FRONTEND_APP" \
    --query "properties.configuration.ingress.fqdn" -o tsv)"
  if [ -z "$FQDN" ]; then
    echo "the deployed frontend has no ingress; is $FRONTEND_APP running?" >&2
    exit 1
  fi
  export E2E_BASE_URL="https://$FQDN"
fi

export E2E_TARGET="$TARGET"

cd "$REPO_ROOT/e2e"

if [ ! -d node_modules ]; then
  npm ci
fi

# Chromium only. The demonstration is given from one browser on one laptop, and
# a matrix of engines is a matrix of ways for the morning to go wrong.
npx playwright install --with-deps chromium

echo "Demo validator: $TARGET (${E2E_BASE_URL:-http://localhost:3001})"
npx playwright test "${PLAYWRIGHT_ARGS[@]+"${PLAYWRIGHT_ARGS[@]}"}"
