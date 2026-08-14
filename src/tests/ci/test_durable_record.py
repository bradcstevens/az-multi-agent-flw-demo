"""Invariants of the durable record — the tracked documentation that outlives the
superseded, `.gitignore`d build-requirements document.

These are CI-tooling tests, not application tests: the subject is the repository's
own documentation, read from disk exactly as a future reader (or a Linux CI runner)
would encounter it.
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CORRECTIONS = REPO_ROOT / "docs" / "superseded-requirements-corrections.md"
ADR_DIR = REPO_ROOT / "docs" / "ADR"
ADR_INDEX = ADR_DIR / "README.md"

CORRECTION_HEADING = re.compile(r"^### (\d+)\. (.+)$", re.MULTILINE)
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6} +(.+?)\s*$", re.MULTILINE)


def _linking_docs() -> list[Path]:
    """Every tracked document that links into the durable record.

    Every markdown file in the record this repository authors — the ADRs and
    the ``agents``, ``copilot-studio`` and ``preflight`` folders, plus the SOP
    corpus' own documentation under ``content`` — not just the ADRs: the live
    tenant records and the preflight records cite ADRs by relative path too, and
    ``docs/adr`` for ``docs/ADR`` resolves on a developer's macOS checkout and
    404s on github.com. ``content`` is wholly this fork's own — the corpus and
    its README exist nowhere upstream — and its README cites ADRs the same way,
    which is how the ADR-019 rebrand shipped a lowercase link nothing was
    reading. The **presenter runbook** is named explicitly rather than by
    folder: it sits beside the accelerator's inherited documentation in
    ``docs/``, and it is the one document here whose reader is holding it in
    front of a customer with no way to recover from a dead link. The
    accelerator's inherited documentation is deliberately out of scope; it is a
    one-way baseline (ADR-006), so editing it to satisfy a guard here buys merge
    friction rather than a working link.
    """
    authored = ("ADR", "agents", "copilot-studio", "preflight")
    return [
        REPO_ROOT / "CONTEXT.md",
        REPO_ROOT / ".reference" / "README.md",
        CORRECTIONS,
        REPO_ROOT / "docs" / "presenter-runbook.md",
        *sorted(
            doc
            for folder in authored
            for doc in (REPO_ROOT / "docs" / folder).rglob("*.md")
        ),
        *sorted((REPO_ROOT / "content").rglob("*.md")),
    ]


def _anchors(doc: Path) -> set[str]:
    """GitHub's heading slugs: lowercase, punctuation dropped, spaces hyphenated."""
    slugs = set()
    for heading in HEADING.findall(doc.read_text(encoding="utf-8")):
        slug = re.sub(r"[^\w\- ]", "", heading.replace("`", "").lower())
        slugs.add(slug.strip().replace(" ", "-"))
    return slugs


def _adr_files() -> set[str]:
    return {path.name for path in ADR_DIR.glob("[0-9][0-9][0-9]-*.md")}


def _index_links() -> list[str]:
    """Index links, normalised to bare filenames (links carry a `./` prefix)."""
    raw = MARKDOWN_LINK.findall(ADR_INDEX.read_text(encoding="utf-8"))
    return [link.split("#", 1)[0].removeprefix("./") for link in raw]


def _correction_sections() -> dict[int, str]:
    """Split the corrections record into ``{number: body}``."""
    text = CORRECTIONS.read_text(encoding="utf-8")
    matches = list(CORRECTION_HEADING.finditer(text))
    sections: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[int(match.group(1))] = text[match.end():end]
    return sections


def test_corrections_record_exists():
    assert CORRECTIONS.is_file(), (
        f"{CORRECTIONS.relative_to(REPO_ROOT)} is the durable home of the ten "
        "corrections to the superseded build-requirements document"
    )


def test_ten_corrections_are_numbered_one_to_ten():
    assert sorted(_correction_sections()) == list(range(1, 11))


def test_every_correction_states_the_wrong_claim_and_the_correct_one():
    for number, body in sorted(_correction_sections().items()):
        claimed = re.search(r"\*\*Claimed:\*\*(.+?)(?=\n\*\*)", body, re.DOTALL)
        correct = re.search(r"\*\*Correct:\*\*(.+?)(?=\n\n|\Z)", body, re.DOTALL)
        assert claimed and claimed.group(1).strip(), (
            f"correction {number} does not state the wrong claim"
        )
        assert correct and correct.group(1).strip(), (
            f"correction {number} does not state the correct position"
        )


def test_adr_index_lists_every_adr():
    """Nothing is recorded as a decision without being reachable from the index."""
    missing = _adr_files() - set(_index_links())
    assert not missing, f"ADRs absent from the index: {sorted(missing)}"


def test_adr_index_links_only_to_adrs_that_exist():
    dangling = [
        link
        for link in _index_links()
        if not link.startswith(("http://", "https://"))
        and not (ADR_DIR / link).exists()
    ]
    assert not dangling, f"index links to missing files: {dangling}"


def _resolves_case_sensitively(base: Path, relative: str) -> bool:
    """`Path.exists()` is case-insensitive on macOS; CI runs on Linux.

    Every path component is checked against its parent's real listing, so a
    directory whose case drifted (``docs/adr`` for ``docs/ADR``) is caught on a
    developer machine rather than at the next CI run.
    """
    current = base
    for part in Path(relative).parts:
        if part == "..":
            current = current.parent
            continue
        if part == ".":
            continue
        if not current.is_dir() or part not in {
            entry.name for entry in current.iterdir()
        }:
            return False
        current = current / part
    return current.exists()


def test_every_relative_documentation_link_resolves():
    broken: list[str] = []
    for doc in _linking_docs():
        for link in MARKDOWN_LINK.findall(doc.read_text(encoding="utf-8")):
            if link.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if not _resolves_case_sensitively(doc.parent, link.split("#", 1)[0]):
                broken.append(f"{doc.relative_to(REPO_ROOT)} -> {link}")
    assert not broken, "unresolvable documentation links: " + ", ".join(broken)


def test_the_durable_record_is_tracked_by_git():
    """Untracked is exactly the failure mode this record exists to fix.

    `.reference/` is ignored, so the marker only survives via the
    `!.reference/README.md` negation — and a new ADR or the corrections record is
    one forgotten `git add` away from being as lost as the document it replaces.
    Assert on git's view of these files, not the filesystem's.
    """
    expected = [
        ".reference/README.md",
        "CONTEXT.md",
        str(CORRECTIONS.relative_to(REPO_ROOT)),
        str(ADR_INDEX.relative_to(REPO_ROOT)),
        *sorted(str((ADR_DIR / name).relative_to(REPO_ROOT)) for name in _adr_files()),
    ]

    listed = subprocess.run(
        ["git", "ls-files", "--", *expected],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert listed.returncode == 0, f"could not read git's index: {listed.stderr.strip()}"
    tracked = set(listed.stdout.split())

    untracked = [path for path in expected if path not in tracked]
    assert not untracked, (
        f"the durable record is not durable — untracked: {untracked}. "
        "For `.reference/README.md`, check the `!.reference/README.md` negation "
        "in .gitignore; otherwise `git add` the file."
    )


def test_the_superseded_reference_marker_points_at_the_durable_record():
    marker = (REPO_ROOT / ".reference" / "README.md").read_text(encoding="utf-8")

    assert "SUPERSEDED" in marker
    assert "superseded-requirements-corrections.md" in marker


def test_every_cross_document_anchor_resolves():
    """A renamed heading silently breaks every deep link that pointed at it."""
    broken: list[str] = []
    for doc in _linking_docs():
        for link in MARKDOWN_LINK.findall(doc.read_text(encoding="utf-8")):
            if link.startswith(("http://", "https://", "mailto:")) or "#" not in link:
                continue
            path, _, anchor = link.partition("#")
            target = (doc.parent / path).resolve() if path else doc
            if not target.is_file() or anchor not in _anchors(target):
                broken.append(f"{doc.relative_to(REPO_ROOT)} -> {link}")
    assert not broken, "unresolvable anchors: " + ", ".join(broken)
