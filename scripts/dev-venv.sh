#!/usr/bin/env bash
# Idempotent developer virtualenv bootstrap, shared by every feedback-loop script.
#
# Source this file, then call dev_venv_ensure; it exports REPO_ROOT and
# VENV_PYTHON, creating the virtualenv only when no warm one for the pinned
# dependency set exists yet.
#
# The virtualenv is identified by a hash of its pinned inputs and stored
# **outside** any worktree, so worktrees share one environment instead of each
# building its own. That is what keeps the integration gate honest: the gate
# merges a lane into a fresh worktree and runs the loops there, so before this
# every merged lane needed a working package index to go green, and an index
# that blinked turned a good lane red (issue #117 burned four consecutive
# auto-resolution attempts on exactly that; issue #115's gate failed the same
# way while all six loops passed against a warm environment).
#
# The locations already documented still work: DEV_VENV overrides everything,
# and a warm $REPO_ROOT/.venv is used untouched. A fresh checkout gets
# $REPO_ROOT/.venv as a link into the shared store, so the `.venv/bin/python`
# commands in AGENTS.md keep working.
#
# The decision logic lives in dev_venv.py so the CI-tooling loop can unit-test
# it (scripts/ci-tests.sh); this file only carries out the verdict.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export REPO_ROOT

# The requirements CI installs, plus the linters the lint loop needs.
DEV_VENV_REQUIREMENTS="$REPO_ROOT/.github/requirements.txt"
DEV_VENV_EXTRA_TOOLS=("flake8==7.1.1")

# "I could not build an environment" is not "your code is broken". flake8 and
# pytest both report a real finding with 1, so the bootstrap must not.
DEV_VENV_EXIT_CANNOT_PROVISION=3

_dev_venv_die() {
  echo "==> cannot provision the feedback-loop virtualenv: $1" >&2
  echo "    This is an environment failure, not a lint or test failure." >&2
  echo "    Nothing was concluded about the code under test." >&2
  return "$DEV_VENV_EXIT_CANNOT_PROVISION"
}

# Ask dev_venv.py where this worktree's virtualenv should be, and whether it is
# already built. Sets _DEV_VENV_PATH, _DEV_VENV_WARM and _DEV_VENV_STAMP.
_dev_venv_resolve() {
  local tool_args=()
  local tool
  for tool in "${DEV_VENV_EXTRA_TOOLS[@]}"; do
    tool_args+=(--tool "$tool")
  done

  local resolved
  resolved="$(python3 "$REPO_ROOT/scripts/dev_venv.py" --resolve \
    --requirements "$DEV_VENV_REQUIREMENTS" "${tool_args[@]}")" || return $?

  _DEV_VENV_PATH="$(printf '%s' "$resolved" | cut -f1)"
  _DEV_VENV_WARM="$(printf '%s' "$resolved" | cut -f2)"
  _DEV_VENV_STAMP="$(printf '%s' "$resolved" | cut -f3)"
}

# Point $REPO_ROOT/.venv at the shared store, so the `.venv/bin/python`
# invocations in AGENTS.md work in a fresh worktree. Never clobbers a real
# directory — someone's hand-built .venv is theirs.
_dev_venv_link_into_worktree() {
  local target="$1"
  local link="$REPO_ROOT/.venv"

  # Compare where the two actually land, not how they are spelled: $REPO_ROOT
  # comes from `pwd` (logical) and the target from Python's resolve()
  # (physical), so on a path like /tmp -> /private/tmp the same directory has
  # two names, and linking one to the other makes .venv point at itself.
  local target_real link_real
  target_real="$(cd "$target" 2>/dev/null && pwd -P)" || return 0
  link_real="$(cd "$link" 2>/dev/null && pwd -P)" || link_real=""
  [[ -n "$link_real" && "$target_real" == "$link_real" ]] && return 0

  # A real directory someone built by hand is theirs; only ever replace a link.
  # Reaching here means it was built for different pinned inputs — a warm one
  # would have been the target and matched above — so say so: the loops run
  # against $VENV_PYTHON, but AGENTS.md documents `.venv/bin/python` directly
  # for the guardrail corpus and the fast-lane measurement, and those would
  # otherwise quietly get the stale environment.
  if [[ -e "$link" && ! -L "$link" ]]; then
    echo "==> note: $link was built for different pinned inputs and is left alone;" >&2
    echo "    the loops are using $target_real." >&2
    echo "    Delete $link to have AGENTS.md's .venv/bin/python commands follow them." >&2
    return 0
  fi

  ln -sfn "$target_real" "$link" 2>/dev/null || true
  return 0
}

# Serialise builds of the same store entry: worktrees now share it, and two
# pip installs into one directory is a corrupt environment nobody will debug.
_dev_venv_lock() {
  local lock="$1.lock"
  local waited=0

  # The store's parent may not exist on a cold machine, and `mkdir` failing
  # with ENOENT is indistinguishable here from the lock being held — which is
  # how the very first build on a machine waits ten minutes for nobody.
  mkdir -p "$(dirname "$lock")" 2>/dev/null || true

  while ! mkdir "$lock" 2>/dev/null; do
    if [[ ! -d "$(dirname "$lock")" ]]; then
      return 1
    fi
    if (( waited >= 600 )); then
      echo "==> stale build lock at $lock; taking it" >&2
      rm -rf "$lock"
      mkdir "$lock" 2>/dev/null || return 1
      break
    fi
    if (( waited == 0 )); then
      echo "==> another worktree is building this environment; waiting"
    fi
    sleep 2
    waited=$((waited + 2))
  done
  _DEV_VENV_LOCK="$lock"
  return 0
}

_dev_venv_unlock() {
  [[ -n "${_DEV_VENV_LOCK:-}" ]] && rm -rf "$_DEV_VENV_LOCK"
  _DEV_VENV_LOCK=""
  return 0
}

_dev_venv_build() {
  local path="$1"
  local python="$path/bin/python"

  mkdir -p "$(dirname "$path")" || return $?

  if [[ ! -x "$python" ]]; then
    echo "==> creating virtualenv at $path"
    python3 -m venv "$path" || return $?
  fi

  echo "==> installing pinned dependencies (runs only when they change)"
  # pip's own upgrade is a network round trip that no loop depends on.
  "$python" -m pip install --quiet --disable-pip-version-check --upgrade pip 2>/dev/null || true
  "$python" -m pip install --quiet --disable-pip-version-check \
    -r "$DEV_VENV_REQUIREMENTS" || return $?
  # Guarded: `pip install` with no arguments is an error, not a no-op.
  if (( ${#DEV_VENV_EXTRA_TOOLS[@]} > 0 )); then
    "$python" -m pip install --quiet --disable-pip-version-check \
      "${DEV_VENV_EXTRA_TOOLS[@]}" || return $?
  fi

  # The stamp is the warmth marker, so it goes on last: a half-built
  # environment stays cold and gets rebuilt rather than silently used.
  printf '%s' "$_DEV_VENV_STAMP" >"$path/.dev-venv-stamp"
}

dev_venv_ensure() {
  _dev_venv_resolve || return $?

  if [[ "$_DEV_VENV_WARM" == "warm" ]]; then
    VENV_PYTHON="$_DEV_VENV_PATH/bin/python"
    export VENV_PYTHON
    _dev_venv_link_into_worktree "$_DEV_VENV_PATH"
    return 0
  fi

  command -v python3 >/dev/null 2>&1 || { _dev_venv_die "python3 is not on PATH"; return $?; }

  _dev_venv_lock "$_DEV_VENV_PATH" || true

  # Another worktree may have finished the build while we waited on the lock.
  if ! _dev_venv_resolve; then
    _dev_venv_unlock
    _dev_venv_die "could not resolve a virtualenv location for $DEV_VENV_REQUIREMENTS"
    return $?
  fi

  if [[ "$_DEV_VENV_WARM" != "warm" ]]; then
    if ! _dev_venv_build "$_DEV_VENV_PATH"; then
      _dev_venv_unlock
      _dev_venv_die "could not install $DEV_VENV_REQUIREMENTS into $_DEV_VENV_PATH"
      return $?
    fi
  fi

  _dev_venv_unlock

  VENV_PYTHON="$_DEV_VENV_PATH/bin/python"
  export VENV_PYTHON
  _dev_venv_link_into_worktree "$_DEV_VENV_PATH"
}

dev_python_test_venv_ensure() {
  dev_venv_ensure || return $?
  cd "$REPO_ROOT"
  export PYTHONPATH="src:src/backend"
}
