"""Parse the markdown-plus-TOML sources that are the SOP corpus' source of truth.

A source file is TOML front matter fenced by `+++`, followed by markdown restricted to
level-two headings, paragraphs, numbered steps and bullet lines. That restriction is
deliberate: every document has to render as numbered steps attributable to a named source
document once Copilot Studio answers from it.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

FRONT_MATTER_FENCE = "+++"
_NUMBERED_STEP = re.compile(r"^(\d+)\.\s+(.*)$")
_BULLET = re.compile(r"^[-*]\s+(.*)$")

PROCEDURE_HEADING = "Procedure"


@dataclass(frozen=True)
class Block:
    """A paragraph, a numbered step or a bullet inside a section."""

    kind: str
    text: str
    number: int | None = None


@dataclass(frozen=True)
class Section:
    heading: str
    blocks: tuple[Block, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    version: str
    owner: str
    effective: str
    sections: tuple[Section, ...]
    source_path: Path

    @property
    def filename(self) -> str:
        """The name the associate sees cited, so it has to read as a document title."""
        return f"{self.doc_id} {self.title}.docx"

    @property
    def steps(self) -> list[str]:
        for section in self.sections:
            if section.heading == PROCEDURE_HEADING:
                return [block.text for block in section.blocks if block.kind == "step"]
        return []


class CorpusError(ValueError):
    """A source file that would produce a document the SOP agent cannot ground on."""


@dataclass(frozen=True)
class HonestMiss:
    """The rehearsed question the corpus deliberately does not answer."""

    question: str
    quick_task: str
    absent_terms: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class Corpus:
    banner: str
    store: str
    locale: str
    documents: tuple[Document, ...]
    honest_miss: HonestMiss

    def text_of(self, document: Document) -> str:
        parts = [document.title, document.doc_id]
        for section in document.sections:
            parts.append(section.heading)
            parts.extend(block.text for block in section.blocks)
        return "\n".join(parts).lower()

    def honest_miss_coverage(self) -> list[tuple[str, str]]:
        """Every (term, doc_id) pair that would turn the honest miss into a hit."""
        hits = []
        for document in self.documents:
            haystack = self.text_of(document)
            for term in self.honest_miss.absent_terms:
                if term.lower() in haystack:
                    hits.append((term, document.doc_id))
        return hits


def split_front_matter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_FENCE:
        raise CorpusError("source must open with a +++ TOML front-matter fence")
    try:
        closing = lines.index(FRONT_MATTER_FENCE, 1)
    except ValueError as exc:
        raise CorpusError("front matter is never closed with +++") from exc
    metadata = tomllib.loads("\n".join(lines[1:closing]))
    return metadata, "\n".join(lines[closing + 1 :])


def parse_sections(body: str) -> tuple[Section, ...]:
    sections: list[Section] = []
    heading: str | None = None
    blocks: list[Block] = []
    blank_seen = True

    def flush() -> None:
        if heading is not None:
            sections.append(Section(heading=heading, blocks=tuple(blocks)))

    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            blank_seen = True
            continue
        if line.startswith("## "):
            flush()
            heading = line[3:].strip()
            blocks = []
            blank_seen = False
            continue
        if heading is None:
            raise CorpusError("content appears before the first '## ' heading")
        numbered = _NUMBERED_STEP.match(line)
        bullet = None if numbered else _BULLET.match(line)
        continues = blocks and not blank_seen and not numbered and not bullet
        blank_seen = False
        if continues:
            previous = blocks[-1]
            blocks[-1] = Block(
                kind=previous.kind,
                text=f"{previous.text} {line}",
                number=previous.number,
            )
            continue
        if numbered:
            blocks.append(
                Block(kind="step", text=numbered.group(2).strip(), number=int(numbered.group(1)))
            )
            continue
        if bullet:
            blocks.append(Block(kind="bullet", text=bullet.group(1).strip()))
            continue
        blocks.append(Block(kind="paragraph", text=line))

    flush()
    return tuple(sections)


def _check_step_numbering(sections: tuple[Section, ...]) -> None:
    """Steps are rendered with the number written in the source, so they must run 1..n."""
    for section in sections:
        numbers = [block.number for block in section.blocks if block.kind == "step"]
        if numbers and numbers != list(range(1, len(numbers) + 1)):
            raise CorpusError(
                f"steps under '{section.heading}' are numbered {numbers}, expected "
                f"{list(range(1, len(numbers) + 1))}"
            )


def load_document(path: Path) -> Document:
    metadata, body = split_front_matter(Path(path).read_text(encoding="utf-8"))
    missing = [
        key
        for key in ("doc_id", "title", "version", "owner", "effective")
        if not metadata.get(key)
    ]
    if missing:
        raise CorpusError(f"{path.name} is missing front-matter keys: {', '.join(missing)}")
    sections = parse_sections(body)
    _check_step_numbering(sections)
    return Document(
        doc_id=str(metadata["doc_id"]),
        title=str(metadata["title"]),
        version=str(metadata["version"]),
        owner=str(metadata["owner"]),
        effective=str(metadata["effective"]),
        sections=sections,
        source_path=Path(path),
    )


def load_corpus(content_dir: Path) -> Corpus:
    content_dir = Path(content_dir)
    manifest = tomllib.loads((content_dir / "corpus.toml").read_text(encoding="utf-8"))
    miss = manifest.get("honest_miss")
    if not miss:
        raise CorpusError("corpus.toml must declare the rehearsed [honest_miss] question")
    documents = tuple(
        load_document(path) for path in sorted((content_dir / "src").glob("*.md"))
    )
    return Corpus(
        banner=str(manifest.get("banner", "")),
        store=str(manifest.get("store", "")),
        locale=str(manifest.get("locale", "")),
        documents=documents,
        honest_miss=HonestMiss(
            question=str(miss["question"]),
            quick_task=str(miss["quick_task"]),
            absent_terms=tuple(miss["absent_terms"]),
            rationale=str(miss["rationale"]),
        ),
    )
