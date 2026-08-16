"""The routing table and ADR-029 must agree.

A CI-tooling test, not an application test: the subject is this repository's own
`git-loopy/config.toml` — the committed table that decides which model runs an
issue — read from disk exactly as `git-loopy` would resolve it.

ADR-029 exists because that table used to live in `~/.config/git-loopy/config.toml`,
where it said `implementation = gpt-5.6-luna @ medium` and nine `ready-for-agent`
issues were one command away from a model nobody here had reviewed. A committed
table fixes that only for as long as it still says what the ADR says it says.
"""

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTING_CONFIG = REPO_ROOT / "git-loopy" / "config.toml"
ADR = REPO_ROOT / "docs" / "ADR" / "029-an-issue-declares-its-model-with-one-task-type-label.md"

# git-loopy's closed taxonomy, in its own stable presentation order. The
# classifier refuses anything outside it, so an eighth key here would be a row
# nothing can ever route to.
TASK_TYPES = (
    "planning",
    "review",
    "implementation",
    "test",
    "docs",
    "chore",
    "bugfix",
)

# git-loopy's REASONING_EFFORT_ORDER.
EFFORTS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
)

# | `planning` | `claude-opus-5` | `max` | 200k |
# Leading whitespace is significant: the decision's table is indented inside a
# numbered list item, so the row does not start at column zero.
ADR_ROW = re.compile(
    r"^[ \t]*\|\s*`(?P<task_type>[a-z]+)`\s*\|\s*`(?P<model>[^`]+)`\s*\|\s*`(?P<effort>[a-z]+)`\s*\|",
    re.MULTILINE,
)


def _committed_table() -> dict[str, tuple[str, str]]:
    """The `[routing]` table as `git-loopy` would resolve it from this repo."""
    config = tomllib.loads(ROUTING_CONFIG.read_text(encoding="utf-8"))
    return {
        task_type: (pair["model"], pair["effort"])
        for task_type, pair in config["routing"].items()
    }


def _adr_table() -> dict[str, tuple[str, str]]:
    """The table as ADR-029 states it, parsed out of the decision's own markdown."""
    return {
        row["task_type"]: (row["model"], row["effort"])
        for row in ADR_ROW.finditer(ADR.read_text(encoding="utf-8"))
    }


def test_routing_config_is_committed():
    """The table is project-scoped and tracked, not global and invisible.

    `git-loopy config path` resolves the project table to `<repo-root>/git-loopy/`
    — no leading dot. `.git-loopy/` is the `.gitignore`d runner state and is a
    different directory; writing the table there would silently un-track it.
    """
    assert ROUTING_CONFIG.is_file(), (
        f"{ROUTING_CONFIG.relative_to(REPO_ROOT)} is missing. Without it the "
        "routing table falls back to whatever is in the running laptop's "
        "~/.config/git-loopy/config.toml — see ADR-029."
    )


def test_every_task_type_has_a_row():
    """All seven, because the classifier can return any of them.

    An unlabelled issue is not skipped; it is classified by a model call that
    chooses from the closed seven. A missing row is a type nothing has decided.
    """
    assert set(_committed_table()) == set(TASK_TYPES)


def test_rows_name_a_known_effort():
    committed = _committed_table()
    unknown = {
        task_type: effort
        for task_type, (_, effort) in committed.items()
        if effort not in EFFORTS
    }
    assert not unknown, f"efforts outside git-loopy's roster: {unknown}"


def test_committed_table_matches_the_adr():
    """The decision and the file that enacts it must not drift apart.

    ADR-029 is where the reasoning for each pair lives — why `review` is not the
    same model as `implementation`, why `chore` is fast rather than cheap, why
    three rows are 272k. A row changed here and not there is a routing decision
    nobody recorded.
    """
    committed = _committed_table()
    adr = _adr_table()

    assert adr, (
        "no routing rows parsed out of ADR-029 — the decision's table must stay "
        "in the `| `task-type` | `model` | `effort` |` shape this test reads."
    )
    assert committed == adr, (
        "git-loopy/config.toml and ADR-029 disagree. Differences: "
        + repr(
            {
                task_type: {
                    "config.toml": committed.get(task_type),
                    "ADR-029": adr.get(task_type),
                }
                for task_type in set(committed) | set(adr)
                if committed.get(task_type) != adr.get(task_type)
            }
        )
    )
