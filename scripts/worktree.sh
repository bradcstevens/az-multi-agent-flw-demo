#!/usr/bin/env bash
# The one sanctioned way to make an agent worktree of this repository, and the
# sweep that collects them.
#
# ADR-044. Two rules:
#
#   Location — a worktree lives inside `<repo>.worktrees/`, never in the parent
#              directory beside the repository itself.
#   Lifetime — a worktree is collected once every commit in it is reachable
#              from `origin/main`.
#
#   scripts/worktree.sh add issue-123          # create, then sweep
#   scripts/worktree.sh add issue-123 origin/main
#   scripts/worktree.sh sweep                  # collect, acting by default
#   scripts/worktree.sh sweep --dry-run        # report without acting
#   scripts/worktree.sh sweep --json
#
# `add` is the trigger. The sweep runs on every creation, so the folder is
# smallest exactly when a new agent is about to look at it — no habit to
# remember, and creation is the one event guaranteed to happen.
#
# The sweep never passes `--force`. Uncommitted files are stashed with an
# identifying message before removal, so nothing it does leaves this machine
# and nothing it does is irreversible: `git stash list` is the way back.
#
# Exit codes:
#
#   0  nothing needs you — worktrees were collected, kept, or skipped by rule
#   1  something needs YOU: a stash failed, git refused a removal, or a
#      worktree holds commits that exist on no remote and is therefore the
#      only copy of that work. Nothing was destroyed; read the report.
#
# The logic lives in worktree_hygiene.py so the CI-tooling loop
# (scripts/ci-tests.sh) can unit-test the ladder that decides whether your
# uncommitted work survives, without a repository, a remote, or a disk.

set -euo pipefail

command -v git >/dev/null 2>&1 || { echo "git not found on PATH" >&2; exit 2; }

exec python3 "$(dirname "${BASH_SOURCE[0]}")/worktree_hygiene.py" "$@"
