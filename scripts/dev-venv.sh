#!/usr/bin/env bash
# Idempotent developer virtualenv bootstrap, shared by every feedback-loop script.
#
# Source this file, then call dev_venv_ensure; it exports REPO_ROOT and
# VENV_PYTHON, creating or refreshing the virtualenv only when the pinned
# dependency set has changed. A stamp file records the hash of the inputs, so a
# warm worktree costs a single hash instead of a full `pip install`.
#
# Override the virtualenv location with DEV_VENV (useful for sharing one
# environment across git worktrees).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export REPO_ROOT

DEV_VENV="${DEV_VENV:-$REPO_ROOT/.venv}"
VENV_PYTHON="$DEV_VENV/bin/python"
export VENV_PYTHON

# The requirements CI installs, plus the linters the lint loop needs.
DEV_VENV_REQUIREMENTS="$REPO_ROOT/.github/requirements.txt"
DEV_VENV_EXTRA_TOOLS=("flake8==7.1.1")

_dev_venv_stamp_value() {
  {
    printf '%s\n' "${DEV_VENV_EXTRA_TOOLS[@]}"
    cat "$DEV_VENV_REQUIREMENTS"
  } | _dev_venv_sha256
}

# sha256sum on Linux, shasum on macOS; python3 is the always-present fallback.
_dev_venv_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | cut -d' ' -f1
  else
    python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())'
  fi
}

dev_venv_ensure() {
  local stamp_file="$DEV_VENV/.dev-venv-stamp"
  local want
  want="$(_dev_venv_stamp_value)"

  if [[ -x "$VENV_PYTHON" && -f "$stamp_file" && "$(cat "$stamp_file")" == "$want" ]]; then
    return 0
  fi

  if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "==> creating virtualenv at $DEV_VENV"
    python3 -m venv "$DEV_VENV"
  fi

  echo "==> installing pinned dependencies (runs only when they change)"
  "$VENV_PYTHON" -m pip install --quiet --upgrade pip
  "$VENV_PYTHON" -m pip install --quiet -r "$DEV_VENV_REQUIREMENTS"
  "$VENV_PYTHON" -m pip install --quiet "${DEV_VENV_EXTRA_TOOLS[@]}"

  printf '%s' "$want" >"$stamp_file"
}
