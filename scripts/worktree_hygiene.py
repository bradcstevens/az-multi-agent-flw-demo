#!/usr/bin/env python3
"""Where an agent worktree lives, and when it is collected.

The answer to ADR-044. Two rules, and the whole file is their implementation:

  **Location.** A worktree belongs inside ``<repo>.worktrees/``, never in the
  parent directory beside the repository itself.

  **Lifetime.** A worktree is collected once every commit in it is reachable
  from ``origin/main``.

The second rule is phrased against the *remote* ref deliberately. Local ``main``
drifts — it was two commits behind when this was written — and a sweep that asks
``git branch --merged main`` gets an answer that is wrong in a way that grows
quietly the longer nobody pulls. ``git branch --merged`` also cannot tell a
branch that landed from one that is merely stale: both are ancestors. Asking
"is this HEAD reachable from ``origin/main``" is what that question was reaching
for, and it makes a detached HEAD fall out with no special case.

Removal never passes ``--force``. Uncommitted files are **stashed** first, with
an identifying message, because a stash stays on this machine: committing
whatever is lying around would eventually push a credential to a public
repository, which is the entire subject of ADR-041.

The pure layer below takes a ``Worktree`` record and returns a ``Verdict``. It
touches nothing, which is how the CI-tooling loop can test the ladder — the part
that decides whether your uncommitted work survives — without a repository, a
remote, or a disk.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

CONTAINER_SUFFIX = ".worktrees"
BASE_REF = "origin/main"

#: How long a worktree must sit untouched before the sweep will consider it.
#: A worktree observed during the ADR-044 grilling went from three uncommitted
#: files to clean four minutes before that session started, so "nothing has
#: happened here recently" is a real precondition, not a formality.
IDLE_SECONDS = 900

COLLECT = "collect"
STASH_THEN_COLLECT = "stash-then-collect"
SKIP_ACTIVE = "skip-active"
ESCALATE = "escalate"
KEEP = "keep"
DEFER = "defer-owner"

#: Outcomes that leave the worktree on disk.
RETAINING = frozenset({SKIP_ACTIVE, ESCALATE, KEEP, DEFER})

#: A branch namespace whose worktrees belong to the tool that made them.
OWNED_BRANCH_PREFIXES = ("git-loopy/",)


def is_externally_owned(worktree: Path, repo: Path, branch: str | None) -> bool:
    """Does something other than ``worktree.sh`` manage this worktree's life?

    Two signals, either sufficient. A branch in an owned namespace is the
    obvious one. The structural one is better: a run-scoped tool files its
    worktrees under a run directory, so anything **more than one level** below
    the container was placed by a run, not by ``worktree.sh add <slug>``, which
    creates exactly one level down.

    That matters because a run which is paused, blocked, or waiting on a gate
    is indistinguishable from an abandoned worktree by idleness alone — and
    collecting a live run's lane to tidy a folder is a bad trade.
    """
    if branch and branch.startswith(OWNED_BRANCH_PREFIXES):
        return True
    container = container_for(repo)
    try:
        relative = worktree.relative_to(container)
    except ValueError:
        return False
    return len(relative.parts) > 1


def container_for(repo: Path) -> Path:
    """The one directory every worktree of ``repo`` belongs inside."""
    return repo.parent / f"{repo.name}{CONTAINER_SUFFIX}"


def is_sanctioned(worktree: Path, repo: Path) -> bool:
    """Is ``worktree`` inside the containing folder?

    Nesting below the container is fine — git-loopy files its lanes under
    ``<run-id>/<lane>`` and that arrangement is already correct and tested.
    ADR-044 governs the containing folder, not a naming scheme.
    """
    container = container_for(repo)
    try:
        worktree.relative_to(container)
    except ValueError:
        return False
    return worktree != container


@dataclass(frozen=True)
class Worktree:
    """What the sweep needs to know about one worktree.

    Every field is an observation, never a judgement — the judgement is
    :func:`classify`, and keeping the two apart is what makes it testable.
    """

    path: Path
    head: str
    branch: str | None
    is_primary: bool
    sanctioned: bool
    externally_owned: bool
    dirty: bool
    locked: bool
    idle_seconds: float
    reachable_from_base: bool
    commits_absent_from_remote: int

    @property
    def label(self) -> str:
        """A name that distinguishes this worktree from every other one.

        git-loopy files lanes under ``<run-id>/<lane>``, so three live runs
        produce three worktrees all called ``issue-103``. A report — and above
        all an escalation — that names one of them ``issue-103`` tells you
        nothing about which one.
        """
        parts = self.path.parts
        for index, part in enumerate(parts):
            if part.endswith(CONTAINER_SUFFIX):
                return "/".join(parts[index + 1 :]) or self.path.name
        return self.path.name


@dataclass(frozen=True)
class Verdict:
    worktree: Worktree
    action: str
    reason: str

    @property
    def retained(self) -> bool:
        return self.action in RETAINING

    def as_dict(self) -> dict:
        return {
            "path": str(self.worktree.path),
            "label": self.worktree.label,
            "branch": self.worktree.branch or f"(detached at {self.worktree.head[:8]})",
            "action": self.action,
            "reason": self.reason,
            "misplaced": not self.worktree.sanctioned,
        }


def classify(worktree: Worktree, *, idle_seconds: float = IDLE_SECONDS) -> Verdict:
    """Decide what happens to one worktree.

    The order of these branches is the safety property. A live worktree is
    stood down from *before* anything else is asked about it, so a session
    still working is never escalated at, never stashed under, and never
    removed from.
    """
    if worktree.is_primary:
        return Verdict(worktree, KEEP, "the primary checkout is never collected")

    if worktree.externally_owned:
        return Verdict(
            worktree,
            DEFER,
            "created by a run that manages its own worktrees — reported, never collected",
        )

    if worktree.locked:
        return Verdict(worktree, SKIP_ACTIVE, "a git lock is present — a session is using it")

    if worktree.idle_seconds < idle_seconds:
        touched = int(worktree.idle_seconds)
        return Verdict(worktree, SKIP_ACTIVE, f"modified {touched}s ago — too recent to be idle")

    if worktree.reachable_from_base:
        if worktree.dirty:
            return Verdict(
                worktree,
                STASH_THEN_COLLECT,
                f"every commit is on {BASE_REF}; uncommitted files are stashed first",
            )
        return Verdict(worktree, COLLECT, f"every commit is already on {BASE_REF}")

    if worktree.commits_absent_from_remote:
        count = worktree.commits_absent_from_remote
        plural = "s" if count != 1 else ""
        return Verdict(
            worktree,
            ESCALATE,
            f"{count} commit{plural} exist on no remote — this is the only copy",
        )

    return Verdict(
        worktree,
        KEEP,
        f"not yet on {BASE_REF}, but every commit is pushed — work in flight",
    )


def plan(worktrees, *, idle_seconds: float = IDLE_SECONDS) -> list[Verdict]:
    return [classify(worktree, idle_seconds=idle_seconds) for worktree in worktrees]


def exit_code(verdicts) -> int:
    """0 when nothing needs a human, 1 when something does.

    Only :data:`ESCALATE` earns a non-zero exit. A kept or skipped worktree is
    the rule working, not the rule failing.
    """
    return 1 if any(verdict.action == ESCALATE for verdict in verdicts) else 0


def stash_message(worktree: Worktree, *, now: str) -> str:
    """Identify the stash well enough to find it a month later."""
    label = worktree.branch or f"detached-{worktree.head[:8]}"
    return f"worktree-hygiene: {worktree.path.name} ({label}) collected {now}"


def render(verdicts) -> str:
    if not verdicts:
        return "No worktrees besides the primary checkout."

    order = [STASH_THEN_COLLECT, COLLECT, ESCALATE, KEEP, SKIP_ACTIVE, DEFER]
    lines: list[str] = []
    for action in order:
        chosen = [verdict for verdict in verdicts if verdict.action == action]
        if not chosen:
            continue
        lines.append(f"{action} ({len(chosen)}):")
        for verdict in chosen:
            flag = "  [misplaced]" if not verdict.worktree.sanctioned else ""
            lines.append(f"  {verdict.worktree.label}{flag} — {verdict.reason}")
        lines.append("")
    return "\n".join(lines).rstrip()


# --------------------------------------------------------------------------
# Everything below talks to git. Nothing below decides anything.
# --------------------------------------------------------------------------


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _parse_worktree_list(porcelain: str) -> list[dict]:
    records: list[dict] = []
    current: dict = {}
    for line in porcelain.splitlines():
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current = {"worktree": value}
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
        elif key == "HEAD":
            current["HEAD"] = value
        elif key in {"detached", "locked", "prunable", "bare"}:
            current[key] = True
    if current:
        records.append(current)
    return records


def _idle_seconds(path: Path) -> float:
    """Seconds since anything under the worktree's git state or index moved."""
    candidates = [path, path / ".git"]
    newest = 0.0
    for candidate in candidates:
        try:
            newest = max(newest, candidate.stat().st_mtime)
        except OSError:
            continue
    if not newest:
        return float("inf")
    return max(0.0, time.time() - newest)


def _has_lock(repo: Path, path: Path) -> bool:
    gitdir = _git(path, "rev-parse", "--absolute-git-dir", check=False)
    if not gitdir:
        return False
    return any(Path(gitdir).glob("*.lock")) or (Path(gitdir) / "index.lock").exists()


def _primary(repo: Path) -> Path:
    """The main worktree, which git guarantees is listed first.

    ``rev-parse --show-toplevel`` answers with whichever worktree you happen to
    be standing in — so running the sweep from inside a worktree would make it
    believe *that* is the repository, put the container in the wrong place, and
    call every real worktree misplaced.
    """
    records = _parse_worktree_list(_git(repo, "worktree", "list", "--porcelain"))
    if not records:
        raise RuntimeError("git reported no worktrees")
    return Path(records[0]["worktree"]).resolve()


def discover(repo: Path, *, base: str = BASE_REF) -> list[Worktree]:
    primary = _primary(repo)
    records = _parse_worktree_list(_git(repo, "worktree", "list", "--porcelain"))

    worktrees: list[Worktree] = []
    for record in records:
        path = Path(record["worktree"]).resolve()
        head = record.get("HEAD", "")
        is_primary = path == primary

        if is_primary:
            reachable, absent, dirty = False, 0, False
        else:
            reachable = (
                subprocess.run(
                    ["git", "-C", str(repo), "merge-base", "--is-ancestor", head, base],
                    capture_output=True,
                    check=False,
                ).returncode
                == 0
            )
            absent = int(_git(repo, "rev-list", "--count", head, "--not", "--remotes") or 0)
            dirty = bool(_git(path, "status", "--porcelain", check=False))

        worktrees.append(
            Worktree(
                path=path,
                head=head,
                branch=record.get("branch"),
                is_primary=is_primary,
                sanctioned=is_sanctioned(path, primary),
                externally_owned=is_externally_owned(path, primary, record.get("branch")),
                dirty=dirty,
                locked=bool(record.get("locked")) or _has_lock(repo, path),
                idle_seconds=_idle_seconds(path),
                reachable_from_base=reachable,
                commits_absent_from_remote=absent,
            )
        )
    return worktrees


def _apply(repo: Path, verdict: Verdict, *, dry_run: bool) -> Verdict:
    """Carry out one verdict, downgrading to ESCALATE if the stash fails."""
    worktree = verdict.worktree
    if dry_run:
        return verdict

    if verdict.action == STASH_THEN_COLLECT:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        stashed = subprocess.run(
            [
                "git",
                "-C",
                str(worktree.path),
                "stash",
                "push",
                "--include-untracked",
                "-m",
                stash_message(worktree, now=now),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if stashed.returncode != 0:
            return replace(
                verdict,
                action=ESCALATE,
                reason=f"stash failed, nothing removed: {stashed.stderr.strip()}",
            )

    if verdict.action in {COLLECT, STASH_THEN_COLLECT}:
        # No --force, ever. If git objects, git is right.
        removed = subprocess.run(
            ["git", "-C", str(repo), "worktree", "remove", str(worktree.path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if removed.returncode != 0:
            return replace(
                verdict,
                action=ESCALATE,
                reason=f"git refused to remove it: {removed.stderr.strip()}",
            )
    return verdict


def sweep(repo: Path, *, dry_run: bool = False, idle: float = IDLE_SECONDS) -> list[Verdict]:
    _git(repo, "fetch", "origin", "main", "--quiet", check=False)
    verdicts = plan(discover(repo), idle_seconds=idle)
    applied = [_apply(repo, verdict, dry_run=dry_run) for verdict in verdicts]
    _git(repo, "worktree", "prune", check=False)
    return [verdict for verdict in applied if not verdict.worktree.is_primary]


def add(repo: Path, slug: str, base: str = BASE_REF) -> Path:
    """Create a worktree in the one place it belongs, then sweep."""
    target = container_for(_primary(repo)) / slug
    if target.exists():
        raise SystemExit(f"{target} already exists")

    target.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "fetch", "origin", "main", "--quiet", check=False)
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", str(target), "-b", slug, base],
        check=True,
    )
    return target


def main(argv: list[str] | None = None) -> int:
    # Shared flags are declared on a parent so they work on either side of the
    # subcommand: `sweep --dry-run` is the form AGENTS.md documents, and a CLI
    # that rejects its own documented invocation is worse than no CLI.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable report")
    common.add_argument("--dry-run", action="store_true", help="report without acting")
    common.add_argument(
        "--idle-seconds",
        type=float,
        default=IDLE_SECONDS,
        help=f"how long a worktree must be untouched to be swept (default {IDLE_SECONDS})",
    )

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)
    added = sub.add_parser(
        "add",
        parents=[common],
        help="create a worktree in the containing folder, then sweep",
    )
    added.add_argument("slug")
    added.add_argument("base", nargs="?", default=BASE_REF)
    sub.add_parser(
        "sweep",
        parents=[common],
        help="collect every worktree whose commits are on origin/main",
    )

    args = parser.parse_args(argv)
    repo = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel")).resolve()

    if args.command == "add":
        target = add(repo, args.slug, args.base)
        print(f"created {target}")

    verdicts = sweep(repo, dry_run=args.dry_run, idle=args.idle_seconds)

    if args.json:
        print(json.dumps([verdict.as_dict() for verdict in verdicts], indent=2))
    else:
        print(render(verdicts))

    return exit_code(verdicts)


if __name__ == "__main__":
    sys.exit(main())
