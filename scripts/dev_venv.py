#!/usr/bin/env python3
"""Where the feedback loops' virtualenv lives, and whether it is already warm.

The decision logic behind `scripts/dev-venv.sh`, kept here as a pure module so
the CI-tooling loop can unit-test the verdict without building a virtualenv —
the same split the `scripts/preflight/` checks use.

ADR-005 gave every loop a self-provisioning virtualenv stamped with a hash of
its pinned inputs, and accepted that a cold worktree pays a one-off install.
The integration gate then made every worktree cold: it merges a lane into a
fresh worktree and runs the loops there, so that "one-off" install stood
between every merged lane and a green gate, and a package index that blinked
turned a good lane red. Reusing a warm environment is therefore not a speed
optimisation here; it is what stops the gate reporting the network as a defect
in somebody's code.

Two rules:

- **A virtualenv is identified by its stamp, not by its worktree.** The store
  lives outside every worktree and is keyed by the hash of the pinned inputs,
  so the second worktree to want a given dependency set reuses the first's and
  never reaches the network, while a worktree pinning something different gets
  its own rather than fighting over one directory.
- **The locations already documented keep working.** An explicit `DEV_VENV`
  wins outright, and a warm `.venv` inside the worktree is used untouched —
  AGENTS.md tells people to run `.venv/bin/python` directly for the guardrail
  corpus, and a fresh checkout still gets that path (as a link into the store).

Run directly to print the resolved location:

    python3 scripts/dev_venv.py --resolve   # -> "<path>\t<warm|cold>"
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# The bootstrap's own exit code, deliberately distinct from the 1 that flake8
# and pytest use for a real finding: "I could not build an environment" is not
# "your code is broken", and a gate that cannot tell them apart blames the
# wrong thing. Mirrors the 3 the preflight checks use for "could not prove".
EXIT_CANNOT_PROVISION = 3

# Enough hash to be unique on a machine, short enough to read in a path.
STAMP_PREFIX_LENGTH = 12

STAMP_FILENAME = ".dev-venv-stamp"


@dataclass(frozen=True)
class Resolution:
    """The virtualenv the loops should use, and whether it already exists."""

    path: Path
    warm: bool

    @property
    def python(self) -> Path:
        return self.path / "bin" / "python"


def stamp_value(requirements_text: str, extra_tools: list[str]) -> str:
    """Hash the pinned inputs that define a virtualenv.

    Byte-for-byte what `scripts/dev-venv.sh` hashed before this logic moved
    here — one line per extra tool, then the requirements file verbatim — so
    virtualenvs already stamped on developers' machines stay valid.
    """
    payload = "".join(f"{tool}\n" for tool in extra_tools) + requirements_text
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_warm(path: Path, stamp: str) -> bool:
    """Has this location got a usable interpreter built from these inputs?"""
    if not (path / "bin" / "python").exists():
        return False
    try:
        return (path / STAMP_FILENAME).read_text(encoding="utf-8").strip() == stamp
    except OSError:
        return False


def shared_location(stamp: str, cache_home: Path, repo_name: str) -> Path:
    """The store entry for a dependency set, shared by every worktree."""
    return cache_home / repo_name / f"venv-{stamp[:STAMP_PREFIX_LENGTH]}"


def default_cache_home(env: dict[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    xdg = env.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg)
    return Path(env.get("HOME", str(Path.home()))) / ".cache"


def resolve(
    repo_root: Path,
    stamp: str,
    *,
    env: dict[str, str],
    cache_home: Path,
    main_worktree: Path | None = None,
    repo_name: str = "az-multi-agent-flw-demo",
) -> Resolution:
    """Pick the virtualenv for this worktree.

    In order: an explicit `DEV_VENV`, a warm `.venv` in this worktree, a warm
    `.venv` in the checkout this worktree was cut from, then the shared store —
    which is also where a cold worktree builds, so the next one to ask for the
    same dependency set pays nothing.
    """
    repo_root = Path(repo_root)

    override = env.get("DEV_VENV")
    if override:
        path = Path(override)
        return Resolution(path=path, warm=is_warm(path, stamp))

    local = repo_root / ".venv"
    if is_warm(local, stamp):
        # The physical directory, never the link: a previous run may have left
        # `.venv` pointing into the store, and handing that link back as the
        # answer is how the next run links it to itself.
        return Resolution(path=local.resolve(), warm=True)

    if main_worktree is not None:
        shared_checkout = Path(main_worktree) / ".venv"
        if shared_checkout != local and is_warm(shared_checkout, stamp):
            return Resolution(path=shared_checkout, warm=True)

    shared = shared_location(stamp, Path(cache_home), repo_name)
    return Resolution(path=shared, warm=is_warm(shared, stamp))


def main_worktree_of(repo_root: Path) -> Path | None:
    """The checkout a `git worktree` was cut from, or None if unknowable.

    `--git-common-dir` is the one directory every worktree of a repository
    agrees on; its parent is the main checkout.
    """
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if common.returncode != 0:
        return None

    git_dir = Path(common.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (Path(repo_root) / git_dir).resolve()

    parent = git_dir.parent
    return parent if parent.is_dir() else None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="print the resolved virtualenv location and its warmth",
    )
    parser.add_argument(
        "--requirements",
        default=None,
        help="requirements file to stamp (default: .github/requirements.txt)",
    )
    parser.add_argument(
        "--tool",
        action="append",
        default=[],
        help="an extra pinned tool that joins the stamp; repeatable",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    requirements = (
        Path(args.requirements)
        if args.requirements
        else repo_root / ".github" / "requirements.txt"
    )
    try:
        requirements_text = requirements.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {requirements}: {exc}", file=sys.stderr)
        return EXIT_CANNOT_PROVISION

    stamp = stamp_value(requirements_text, args.tool)
    resolution = resolve(
        repo_root,
        stamp,
        env=dict(os.environ),
        cache_home=default_cache_home(),
        main_worktree=main_worktree_of(repo_root),
    )
    print(f"{resolution.path}\t{'warm' if resolution.warm else 'cold'}\t{stamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
