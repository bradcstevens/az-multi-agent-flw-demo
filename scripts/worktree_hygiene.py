#!/usr/bin/env python3
"""Where agent worktrees and branches live, and when they are collected.

The answers to ADR-044 and ADR-047. The whole file implements their rules:

  **Location.** A worktree belongs inside ``<repo>.worktrees/``, never in the
  parent directory beside the repository itself.

  **Lifetime.** A worktree or branch is collected once every commit in it is
  reachable from ``origin/main``. A git-loopy lane defers only while its owner
  holds its run log open.

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
import re
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
RUN_ID_PATTERN = r"[0-9A-HJKMNP-TV-Z]{26}"
RUN_ID_RE = re.compile(rf"^{RUN_ID_PATTERN}$")
LOG_RUN_ID_RE = re.compile(
    rf"\.git-loopy/logs/[^/\n]*-(?P<run_id>{RUN_ID_PATTERN})\.(?:log|jsonl)(?:\s.*)?$"
)


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


def _run_id(value: str | None) -> str | None:
    """Return a git-loopy run ID only when the observation is unambiguous."""
    return value if value and RUN_ID_RE.fullmatch(value) else None


def owner_run_id_for_worktree(worktree: Path, repo: Path, branch: str | None) -> str | None:
    """Identify the run that owns a lane from its structural location or branch."""
    container = container_for(repo)
    try:
        relative = worktree.relative_to(container)
    except ValueError:
        relative = Path()
    if len(relative.parts) > 1:
        return _run_id(relative.parts[0])
    return owner_run_id_for_branch(branch)


def owner_run_id_for_branch(branch: str | None) -> str | None:
    """Extract a run ID from git-loopy's branch namespace."""
    if not branch or not branch.startswith(OWNED_BRANCH_PREFIXES):
        return None
    return _run_id(branch.split("/", 2)[1] if "/" in branch else None)


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
    owner_run_id: str | None
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
class Branch:
    """What the sweep needs to know about one local branch."""

    name: str
    checked_out: bool
    is_main: bool
    is_current: bool
    reachable_from_base: bool
    commits_absent_from_remote: int
    owner_run_id: str | None

    @property
    def label(self) -> str:
        return f"branch {self.name}"


@dataclass(frozen=True)
class Verdict:
    worktree: Worktree | Branch
    action: str
    reason: str

    @property
    def retained(self) -> bool:
        return self.action in RETAINING

    def as_dict(self) -> dict:
        if isinstance(self.worktree, Branch):
            return {
                "name": self.worktree.name,
                "label": self.worktree.label,
                "action": self.action,
                "reason": self.reason,
                "is_branch": True,
            }
        return {
            "path": str(self.worktree.path),
            "label": self.worktree.label,
            "branch": self.worktree.branch or f"(detached at {self.worktree.head[:8]})",
            "action": self.action,
            "reason": self.reason,
            "misplaced": not self.worktree.sanctioned,
        }


def _defer_for_live_owner(
    owner_run_id: str | None, live_run_ids: frozenset[str] | None
) -> str | None:
    """Return the reason to defer, or ``None`` when a known owner is dead."""
    if live_run_ids is None:
        return "owner liveness is undeterminable — reported, never collected"
    if owner_run_id is None:
        return "owner run is unknown — reported, never collected"
    if owner_run_id in live_run_ids:
        return f"owned by live run {owner_run_id} — reported, never collected"
    return None


def classify(
    worktree: Worktree,
    *,
    idle_seconds: float = IDLE_SECONDS,
    live_run_ids: frozenset[str] | None = None,
) -> Verdict:
    """Decide what happens to one worktree.

    The order of these branches is the safety property. A live worktree is
    stood down from *before* anything else is asked about it, so a session
    still working is never escalated at, never stashed under, and never
    removed from.
    """
    if worktree.is_primary:
        return Verdict(worktree, KEEP, "the primary checkout is never collected")

    if worktree.externally_owned:
        defer_reason = _defer_for_live_owner(worktree.owner_run_id, live_run_ids)
        if defer_reason:
            return Verdict(worktree, DEFER, defer_reason)

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


def classify_branch(
    branch: Branch, *, live_run_ids: frozenset[str] | None = None
) -> Verdict:
    """Apply the ADR-047 branch ladder after the worktree pass."""
    if branch.is_main:
        return Verdict(branch, KEEP, "the main branch is never collected")
    if branch.is_current:
        return Verdict(branch, KEEP, "the current branch is never collected")
    if branch.checked_out:
        return Verdict(branch, KEEP, "checked out in a worktree — the worktree goes first")

    defer_reason = _defer_for_live_owner(branch.owner_run_id, live_run_ids)
    if defer_reason and branch.owner_run_id is not None:
        return Verdict(branch, DEFER, defer_reason)

    if branch.reachable_from_base:
        return Verdict(branch, COLLECT, f"every commit is already on {BASE_REF}")
    if branch.commits_absent_from_remote:
        count = branch.commits_absent_from_remote
        plural = "s" if count != 1 else ""
        return Verdict(
            branch,
            ESCALATE,
            f"{count} commit{plural} exist on no remote — this is the only copy",
        )
    return Verdict(
        branch,
        KEEP,
        f"not yet on {BASE_REF}, but every commit is pushed — work in flight",
    )


def plan(
    worktrees, *, idle_seconds: float = IDLE_SECONDS, live_run_ids: frozenset[str] | None = None
) -> list[Verdict]:
    return [
        classify(worktree, idle_seconds=idle_seconds, live_run_ids=live_run_ids)
        for worktree in worktrees
    ]


def plan_branches(branches, *, live_run_ids: frozenset[str] | None = None) -> list[Verdict]:
    return [classify_branch(branch, live_run_ids=live_run_ids) for branch in branches]


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
            flag = (
                "  [misplaced]"
                if isinstance(verdict.worktree, Worktree) and not verdict.worktree.sanctioned
                else ""
            )
            lines.append(f"  {verdict.worktree.label}{flag} — {verdict.reason}")
        lines.append("")
    return "\n".join(lines).rstrip()


# --------------------------------------------------------------------------
# Everything below crosses a system boundary. Nothing below decides anything.
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


def parse_live_run_ids(lsof_output: str) -> frozenset[str]:
    """Read run IDs from lsof's ``-F n`` file-name records."""
    run_ids = set()
    for line in lsof_output.splitlines():
        path = line[1:] if line.startswith("n") else line
        match = LOG_RUN_ID_RE.search(path)
        if match:
            run_ids.add(match.group("run_id"))
    return frozenset(run_ids)


def liveness_observation(
    *, returncode: int, stdout: str, stderr: str
) -> frozenset[str] | None:
    """Turn lsof's result into either a known set or an unsafe-to-assume sentinel."""
    if returncode == 0 and not stderr:
        return parse_live_run_ids(stdout)
    # lsof uses 1 with no diagnostics when none of its explicit file arguments
    # is open. That is a known-empty observation, not a failed probe.
    if returncode == 1 and not stdout and not stderr:
        return frozenset()
    return None


def live_run_ids(repo: Path) -> frozenset[str] | None:
    """Observe runs that still hold one of their logs open.

    ``None`` is deliberately different from an empty set: a failed probe makes
    every externally owned lane retain, because clutter is safer than collecting
    a live run whose process table is unavailable.
    """
    logs = _primary(repo) / ".git-loopy" / "logs"
    try:
        if not logs.is_dir():
            return None
        log_files = [
            *logs.glob("*.log"),
            *logs.glob("*.jsonl"),
        ]
    except OSError:
        return None
    if not log_files:
        return frozenset()

    try:
        observed = subprocess.run(
            ["lsof", "-F", "n", "--", *(str(path) for path in log_files)],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return liveness_observation(
        returncode=observed.returncode,
        stdout=observed.stdout,
        stderr=observed.stderr,
    )


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
                owner_run_id=owner_run_id_for_worktree(path, primary, record.get("branch")),
                dirty=dirty,
                locked=bool(record.get("locked")) or _has_lock(repo, path),
                idle_seconds=_idle_seconds(path),
                reachable_from_base=reachable,
                commits_absent_from_remote=absent,
            )
        )
    return worktrees


def discover_branches(
    repo: Path,
    *,
    base: str = BASE_REF,
    owner_by_branch: dict[str, str] | None = None,
    released_branches: frozenset[str] = frozenset(),
) -> list[Branch]:
    """Observe local branches after the worktree pass has released checked-out refs."""
    records = _parse_worktree_list(_git(repo, "worktree", "list", "--porcelain"))
    checked_out = {
        branch
        for record in records
        if (branch := record.get("branch")) is not None
    }
    current = _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    names = _git(
        repo,
        "for-each-ref",
        "--format=%(refname:short)",
        "refs/heads",
    ).splitlines()
    owner_by_branch = owner_by_branch or {}

    branches: list[Branch] = []
    for name in names:
        reachable = (
            subprocess.run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", name, base],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
        absent = int(_git(repo, "rev-list", "--count", name, "--not", "--remotes") or 0)
        branches.append(
            Branch(
                name=name,
                checked_out=name in checked_out and name not in released_branches,
                is_main=name == "main",
                is_current=name == current,
                reachable_from_base=reachable,
                commits_absent_from_remote=absent,
                owner_run_id=owner_by_branch.get(name) or owner_run_id_for_branch(name),
            )
        )
    return branches


def _apply(repo: Path, verdict: Verdict, *, dry_run: bool) -> Verdict:
    """Carry out one verdict, downgrading to ESCALATE if the stash fails."""
    worktree = verdict.worktree
    if dry_run:
        return verdict

    if isinstance(worktree, Branch):
        if verdict.action != COLLECT:
            return verdict
        # ADR-047 rung 6: reachability above is the judgement; -D only updates
        # the local ref after that predicate has proved the branch safe.
        removed = subprocess.run(
            ["git", "-C", str(repo), "branch", "-D", worktree.name],
            capture_output=True,
            text=True,
            check=False,
        )
        if removed.returncode != 0:
            return replace(
                verdict,
                action=ESCALATE,
                reason=f"git refused to delete it: {removed.stderr.strip()}",
            )
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
    runs = live_run_ids(repo)
    worktrees = discover(repo)
    owner_by_branch = {
        worktree.branch: worktree.owner_run_id
        for worktree in worktrees
        if worktree.branch and worktree.externally_owned and worktree.owner_run_id
    }
    worktree_verdicts = plan(worktrees, idle_seconds=idle, live_run_ids=runs)
    applied_worktrees = [
        _apply(repo, verdict, dry_run=dry_run) for verdict in worktree_verdicts
    ]

    released_branches = frozenset(
        verdict.worktree.branch
        for verdict in applied_worktrees
        if isinstance(verdict.worktree, Worktree)
        and verdict.worktree.branch
        and verdict.action in {COLLECT, STASH_THEN_COLLECT}
    )
    branches = discover_branches(
        repo,
        owner_by_branch=owner_by_branch,
        released_branches=released_branches if dry_run else frozenset(),
    )
    branch_verdicts = plan_branches(branches, live_run_ids=runs)
    applied_branches = [_apply(repo, verdict, dry_run=dry_run) for verdict in branch_verdicts]
    _git(repo, "worktree", "prune", check=False)
    return [
        verdict
        for verdict in [*applied_worktrees, *applied_branches]
        if not isinstance(verdict.worktree, Worktree) or not verdict.worktree.is_primary
    ]


def discover_landed_remote_branches(repo: Path, *, base: str = BASE_REF) -> list[str]:
    """Return remote branches that are already in origin/main without deleting them."""
    refs = _git(
        repo,
        "for-each-ref",
        "--format=%(refname:short)",
        "refs/remotes/origin",
    ).splitlines()
    landed: list[str] = []
    for ref in refs:
        if ref in {"origin/HEAD", base}:
            continue
        if (
            subprocess.run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", ref, base],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        ):
            landed.append(ref.removeprefix("origin/"))
    return sorted(landed)


def render_remote_branches(branches: list[str]) -> str:
    """Print human-run commands for the remote backlog; never execute them."""
    if not branches:
        return "No remote branches are already on origin/main."
    commands = "\n".join(f"  git push origin --delete {branch}" for branch in branches)
    return f"Remote branches already on {BASE_REF} (reported only):\n{commands}"


def primary_report(repo: Path) -> str:
    """Describe the primary branch without changing it."""
    primary = _primary(repo)
    branch = _git(primary, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    label = branch or f"(detached at {_git(primary, 'rev-parse', 'HEAD')[:8]})"
    distance = _git(
        primary, "rev-list", "--left-right", "--count", f"{BASE_REF}...HEAD", check=False
    ).split()
    if len(distance) == 2:
        behind, ahead = distance
        return (
            f"primary: {label} — {ahead} ahead, {behind} behind {BASE_REF}; "
            "never changed"
        )
    return f"primary: {label} — distance from {BASE_REF} unavailable; never changed"


def agents_md_drift_message(repo: Path) -> str | None:
    """Warn when the checkout's agent instructions differ from origin/main."""
    local = repo / "AGENTS.md"
    try:
        local_content = local.read_bytes()
    except OSError:
        return f"warning: {local} is unavailable for comparison with {BASE_REF}:AGENTS.md"
    remote = subprocess.run(
        ["git", "-C", str(repo), "show", f"{BASE_REF}:AGENTS.md"],
        capture_output=True,
        check=False,
    )
    if remote.returncode != 0:
        return f"warning: unable to compare {local} with {BASE_REF}:AGENTS.md"
    if local_content != remote.stdout:
        return (
            f"warning: {local} differs from {BASE_REF}:AGENTS.md; "
            "read the current instructions before creating a worktree"
        )
    return None


def add(repo: Path, slug: str, base: str = BASE_REF) -> Path:
    """Create a worktree in the one place it belongs, then sweep."""
    target = container_for(_primary(repo)) / slug
    if target.exists():
        raise SystemExit(f"{target} already exists")

    target.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "fetch", "origin", "main", "--quiet", check=False)
    if warning := agents_md_drift_message(repo):
        print(warning, file=sys.stderr)
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
        "--remote",
        action="store_true",
        help="report landed remote branches without deleting them",
    )
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

    if args.remote:
        print(render_remote_branches(discover_landed_remote_branches(repo)))
        return 0

    verdicts = sweep(repo, dry_run=args.dry_run, idle=args.idle_seconds)
    if args.json:
        print(json.dumps([verdict.as_dict() for verdict in verdicts], indent=2))
    else:
        print(f"{primary_report(repo)}\n\n{render(verdicts)}")

    return exit_code(verdicts)


if __name__ == "__main__":
    sys.exit(main())
