#!/usr/bin/env bash
# Frontend tests feedback loop (issue #24).
#
# vitest, React Testing Library and jsdom were fully configured in the
# accelerator baseline and never used — there was no test file and no workflow.
# This is the loop that makes them real, and it is deliberately shaped like the
# Python ones: runnable from a clean checkout, a no-op re-install afterwards.
#
# `vitest run`, never a bare `vitest`: the bare form watches, which in CI is a
# job that never finishes and locally is a loop that never returns.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../src/App"

if [ ! -d node_modules ]; then
  npm ci
fi

npm run test:run
