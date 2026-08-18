"""The `## Feedback loops` table is the integration gate's runnable list.

Issue #115, [ADR-046](../../../docs/ADR/046-the-feedback-loops-table-is-what-the-gate-runs.md),
which amends [ADR-005](../../../docs/ADR/005-declare-feedback-loops-in-agents-md.md).

`AGENTS.md` is the single source of truth for the loop commands, and the runner
does not carry its own copy: at integration it merges a lane into a **fresh
worktree**, parses that table, and runs every runnable row there — unattended,
with no `az login`, and on a branch that has not been deployed. A row is
therefore not a suggestion to a reader. It is a command the gate will execute
against every lane that ever merges.

That makes two failure modes worth a test rather than a convention:

- **A row nothing can run there.** The **Demo validator** was a row for weeks.
  Its first assertion (ADR-018) is that the Container Apps serve `HEAD`, and
  deployment happens on a push to `main` (ADR-020) — so on an integration
  branch, which by definition has not been merged, it is red *by construction*.
  Issue #115 spent three auto-resolution attempts on a gate that no diff could
  turn green.
- **No runnable row at all.** The gate raises rather than passing when the table
  is missing, empty, or still carrying `<PLACEHOLDER>` stubs, and the safe reading
  of "cannot gate" is "do not land". A table that stops parsing takes every lane
  down with it.

The subject here is the repository's own documentation, read off disk exactly as
the runner reads it — the parser below mirrors the gate's, including locating the
columns by header name and ending the section at the first heading or prose line
after the table.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTS = REPO_ROOT / "AGENTS.md"

# The gate's own patterns, mirrored so this test and the runner disagree about
# nothing: the heading at any level, any heading ending the section, unescaped
# pipes splitting a row, a dashes-and-colons separator cell, and an UPPER_SNAKE
# `<PLACEHOLDER>` marking a row a fresh repository has not filled in yet.
_SECTION_RE = re.compile(r"^#{1,6}\s+feedback loops\s*$", re.IGNORECASE)
_HEADING_RE = re.compile(r"^#{1,6}\s")
_UNESCAPED_PIPE_RE = re.compile(r"(?<!\\)\|")
_SEPARATOR_CELL_RE = re.compile(r":?-+:?")
_PLACEHOLDER_RE = re.compile(r"<[A-Z][A-Z0-9_]*>")

#: A `#`-comment line in a shell script, and a `#` comment in Python.
_SHELL_COMMENT_RE = re.compile(r"^\s*#.*$", re.MULTILINE)
#: Any `scripts/…` path a script names, so one level of indirection is followed.
_SCRIPT_REFERENCE_RE = re.compile(r"scripts/[A-Za-z0-9_./-]+\.(?:sh|py)")
#: An Azure CLI invocation, as a command rather than as the word "az".
_AZ_INVOCATION_RE = re.compile(r"(?:^|[\s(`$\"'])az\s+[a-z]")

#: The entry points in this repository that observe a **deployment**.
#:
#: Each needs `az login`, a provisioned environment, and — for the three that
#: drive the walkthrough — Container Apps serving this very commit. None of
#: those hold in the gate's fresh worktree, so a table row naming one is a gate
#: that can only ever be red. `AGENTS.md` already says of the last three that
#: each "is not a loop and is not in the table"; this is that sentence made
#: enforceable, and the Demo validator joined them in #115.
DEPLOYMENT_OBSERVING = {
    "scripts/e2e-tests.sh": (
        "the Demo validator (and the Stage driver behind --stage): it resolves the "
        "deployed frontend with `az containerapp show` and refuses to open a browser "
        "until the Container Apps serve HEAD (ADR-018)"
    ),
    "scripts/sop-rehearsal.sh": (
        "the SOP rehearsal: ten live conversations with the deployed agent pool"
    ),
    "scripts/measure-routing.sh": (
        "the Routing probe: every sample is a live turn against the deployed pool"
    ),
    "scripts/measure_fast_lane_latency.py": (
        "fast-lane latency: it needs a live Foundry project and an agent pool"
    ),
}


def _split_row(line: str) -> list[str]:
    parts = _UNESCAPED_PIPE_RE.split(line.strip())
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [part.replace("\\|", "|").strip() for part in parts]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(
        _SEPARATOR_CELL_RE.fullmatch(cell) is not None for cell in cells
    )


def _strip_backticks(cell: str) -> str:
    return cell.strip().strip("`").strip()


def feedback_loops(markdown: str) -> list[tuple[str, str]]:
    """Return the table's ``(name, command)`` rows, the way the gate reads them.

    Finds the `Feedback loops` heading, then the first table under it, locates
    the "Loop" and "Command" columns by header name, and stops at the next
    heading or the first non-table line after the table.
    """
    lines = markdown.splitlines()
    index, count = 0, len(lines)
    while index < count and _SECTION_RE.match(lines[index]) is None:
        index += 1
    if index >= count:
        return []
    index += 1

    rows: list[tuple[str, str]] = []
    header_seen = False
    name_idx, cmd_idx = 0, None
    while index < count:
        line = lines[index]
        if _HEADING_RE.match(line) is not None:
            break
        if "|" in line:
            cells = _split_row(line)
            if not header_seen:
                lowered = [cell.lower() for cell in cells]
                if "command" in lowered:
                    cmd_idx = lowered.index("command")
                    name_idx = lowered.index("loop") if "loop" in lowered else 0
                    header_seen = True
            elif not _is_separator(cells) and cmd_idx is not None and len(cells) > cmd_idx:
                name = cells[name_idx] if len(cells) > name_idx else ""
                rows.append((name, _strip_backticks(cells[cmd_idx])))
            index += 1
            continue
        if header_seen:
            break
        index += 1
    return rows


def _declared() -> list[tuple[str, str]]:
    return feedback_loops(AGENTS.read_text(encoding="utf-8"))


def _uncommented(path: Path) -> str:
    """A script's code with its `#` comment lines removed.

    `sop-rehearsal.sh` and `measure-routing.sh` both *document* `az login` in a
    banner comment. A guard that read those would be answered by prose instead
    of by what the script runs.
    """
    return _SHELL_COMMENT_RE.sub("", path.read_text(encoding="utf-8"))


def _reachable_scripts(command: str) -> list[Path]:
    """Every repository script a loop command runs, one level of indirection deep.

    A loop that shells out to another script inherits that script's needs, and
    `sop-rehearsal.sh` is exactly that shape — it needs no Azure CLI of its own
    and runs the validator ten times.
    """
    seen: dict[str, Path] = {}
    frontier = [
        reference
        for reference in _SCRIPT_REFERENCE_RE.findall(command)
        if (REPO_ROOT / reference).is_file()
    ]
    while frontier:
        reference = frontier.pop()
        if reference in seen:
            continue
        path = REPO_ROOT / reference
        seen[reference] = path
        for nested in _SCRIPT_REFERENCE_RE.findall(_uncommented(path)):
            if nested not in seen and (REPO_ROOT / nested).is_file():
                frontier.append(nested)
    return [seen[reference] for reference in sorted(seen)]


def test_the_table_declares_at_least_one_runnable_loop():
    """A table that stops parsing is a gate that cannot run, and a lane that cannot land."""
    declared = _declared()

    assert declared, (
        "AGENTS.md declares no feedback loops: the integration gate parses this "
        "table to decide whether a merged lane is green, and with no rows it "
        "cannot gate at all"
    )
    for name, command in declared:
        assert command, f"the '{name}' loop declares no command"
        assert _PLACEHOLDER_RE.search(command) is None, (
            f"the '{name}' loop still carries a <PLACEHOLDER> stub, so the gate "
            "will not treat it as runnable"
        )


def test_no_declared_loop_observes_a_deployment():
    """The gate runs this table on a branch that has not been deployed.

    Named entry points, because the repository already knows which of its tools
    hold a live conversation — `AGENTS.md` says so in prose for three of them.
    """
    for name, command in _declared():
        for script, why in DEPLOYMENT_OBSERVING.items():
            assert script not in command, (
                f"the '{name}' loop runs {script} — {why}. The integration gate "
                "runs every row of this table unattended, in a fresh worktree, "
                "on a branch that is not deployed, so this row can only ever be "
                "red. Move it out of the table and into the notes below it."
            )


def test_no_declared_loop_needs_the_azure_cli():
    """The derived half, for a tool nobody thought to name above.

    A loop is run through a plain shell with no `az login` behind it, so a
    command that reaches the Azure CLI fails on the environment rather than on
    the code — and `az` and `flake8` both report that with exit 1.
    """
    for name, command in _declared():
        for script in _reachable_scripts(command):
            assert _AZ_INVOCATION_RE.search(_uncommented(script)) is None, (
                f"the '{name}' loop reaches {script.relative_to(REPO_ROOT)}, "
                "which invokes the Azure CLI. The gate runs this table with no "
                "`az login`, so the row reports a missing sign-in as a finding "
                "about somebody's diff."
            )


def test_the_demo_validator_is_documented_where_it_is_not_declared():
    """Out of the table is not out of the record.

    The validator is still how this repository observes a deployment, and the
    reason it is not gated has to travel with it — otherwise the next reader
    puts the row back.
    """
    agents = AGENTS.read_text(encoding="utf-8")

    assert "scripts/e2e-tests.sh" in agents, (
        "AGENTS.md no longer tells anyone how to run the Demo validator"
    )
    assert "docs/demo-validator.md" in agents, (
        "AGENTS.md does not point at the Demo validator's record"
    )
    assert "is not a loop and is not in the table" in agents, (
        "AGENTS.md does not say that the deployment-observing tools are kept "
        "out of the runnable table, so nothing stops one being added back"
    )
