"""Read the store assistant's content pack off disk.

The pack is the demo's own — not one of the accelerator's **stock content
packs**, which #25 suppresses — so it is uploaded on every deployment
regardless of the stock use-case selection, and everything it declares is read
from here rather than restated anywhere else.

Pure: this module opens files and parses them, and makes no network call and no
Azure call. The live half lives in ``store_pack.__main__``.
"""

from __future__ import annotations

import ast
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set

PACK_DIR = Path("content_packs") / "store_assistant"
TEAM_FILE = PACK_DIR / "agent_teams" / "store_assistant.json"
PACK_FILE = PACK_DIR / "pack.json"
SEED_KB_FILE = Path("infra") / "scripts" / "post-provision" / "seed_knowledge_bases.py"
SOP_CORPUS_MANIFEST = Path("content") / "sop" / "corpus.toml"
SOP_CORPUS_SOURCES = Path("content") / "sop" / "src"

_HEX_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class PackError(ValueError):
    """A pack that would not upload, or would upload and mean the wrong thing."""


def is_hex_uuid(value: str) -> bool:
    """Is this the hex-only, dashed identifier a team definition needs?

    The content-pack rules require hex characters only (0-9, a-f). Enforced
    here rather than at upload because the upload does not enforce it: the
    route accepts whatever the ``team_id`` query parameter carries, and a
    surface that recognises the store assistant **by identifier** finds nothing
    if that identifier is a hex character out.
    """
    return bool(_HEX_UUID.match(value or ""))


@dataclass(frozen=True)
class StorePack:
    """The authored pack: its roster, its declared indexes and its documents."""

    root: Path
    team: Dict[str, Any]
    pack: Dict[str, Any]

    @property
    def agents(self) -> List[Dict[str, Any]]:
        return list(self.team.get("agents", []))

    @property
    def starting_tasks(self) -> List[Dict[str, Any]]:
        return list(self.team.get("starting_tasks", []))

    def agent(self, name: str) -> Dict[str, Any]:
        for agent in self.agents:
            if agent.get("name") == name:
                return agent
        raise PackError(f"no agent named {name!r} in the roster")

    @property
    def index_names(self) -> List[str]:
        """Every Azure AI Search index this pack creates."""
        names = [
            item["index_name"]
            for item in self.pack.get("blob_indexes", []) or []
            if item.get("index_name")
        ]
        names += [
            item["index_name"]
            for item in self.pack.get("search_indexes", []) or []
            if item.get("index_name")
        ]
        return names

    @property
    def knowledge_base_names(self) -> List[str]:
        """Every Foundry IQ Knowledge Base the roster asks for."""
        return [
            agent["knowledge_base_name"]
            for agent in self.agents
            if agent.get("use_knowledge_base") and agent.get("knowledge_base_name")
        ]

    def documents(self, source: str) -> List[Path]:
        """The documents one ``blob_indexes`` source directory will index."""
        directory = self.root / PACK_DIR / source
        return sorted(p for p in directory.glob("*.md") if p.is_file())

    @property
    def sources(self) -> List[str]:
        return [
            item["source"]
            for item in self.pack.get("blob_indexes", []) or []
            if item.get("source")
        ]

    def all_documents(self) -> List[Path]:
        found: List[Path] = []
        for source in self.sources:
            found.extend(self.documents(source))
        return found


def load_pack(repo_root: Path) -> StorePack:
    team = json.loads((repo_root / TEAM_FILE).read_text(encoding="utf-8"))
    pack = json.loads((repo_root / PACK_FILE).read_text(encoding="utf-8"))
    return StorePack(root=repo_root, team=team, pack=pack)


# ---------------------------------------------------------------------------
# What the deploy path seeds
# ---------------------------------------------------------------------------


def _knowledge_base_literal(repo_root: Path) -> ast.Dict:
    source = (repo_root / SEED_KB_FILE).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            # `KNOWLEDGE_BASES: dict = {...}` is an annotated assignment, which
            # is a different node type and would otherwise be invisible here.
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "KNOWLEDGE_BASES":
                if not isinstance(node.value, ast.Dict):
                    raise PackError("KNOWLEDGE_BASES is not a dict literal")
                return node.value
    raise PackError("KNOWLEDGE_BASES is not assigned in seed_knowledge_bases.py")


def seeded_knowledge_base_names(repo_root: Path) -> Set[str]:
    """The knowledge bases the deploy path knows how to create.

    Parsed rather than imported: ``seed_knowledge_bases.py`` reaches for
    ``httpx``, ``azure.identity`` and a ``.env`` at import time, none of which
    a test of the *registration* has any business needing.
    """
    literal = _knowledge_base_literal(repo_root)
    return {
        key.value
        for key in literal.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def seeded_knowledge_base_indexes(repo_root: Path) -> Dict[str, Set[str]]:
    """Each seeded knowledge base, and the search indexes its sources read."""
    literal = _knowledge_base_literal(repo_root)
    seeded: Dict[str, Set[str]] = {}
    for key, value in zip(literal.keys, literal.values):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            continue
        indexes: Set[str] = set()
        if isinstance(value, ast.Dict):
            for inner_key, inner_value in zip(value.keys, value.values):
                if not (
                    isinstance(inner_key, ast.Constant) and inner_key.value == "sources"
                ):
                    continue
                if not isinstance(inner_value, ast.List):
                    continue
                for source in inner_value.elts:
                    if not isinstance(source, ast.Dict):
                        continue
                    for field, field_value in zip(source.keys, source.values):
                        if (
                            isinstance(field, ast.Constant)
                            and field.value == "index_name"
                            and isinstance(field_value, ast.Constant)
                        ):
                            indexes.add(field_value.value)
        seeded[key.value] = indexes
    return seeded


# ---------------------------------------------------------------------------
# The rehearsed honest miss, read out of the SOP corpus' own manifest
# ---------------------------------------------------------------------------


def sop_manifest(repo_root: Path) -> Dict[str, Any]:
    """The SOP corpus' own manifest, ``content/sop/corpus.toml``.

    Read rather than restated. The Quick Tasks are authored in
    ``content_packs/`` and the corpus in ``content/sop/`` — different
    directories, built by different tools — so a rehearsed question that
    drifted from the corpus it was written against would go unnoticed on both
    sides.
    """
    return tomllib.loads((repo_root / SOP_CORPUS_MANIFEST).read_text(encoding="utf-8"))


def honest_miss(repo_root: Path) -> Dict[str, Any]:
    """The rehearsed question the SOP corpus deliberately does not answer."""
    return dict(sop_manifest(repo_root).get("honest_miss", {}))


def honest_miss_absent_terms(repo_root: Path) -> List[str]:
    """The terms the SOP corpus keeps out, so its honest miss stays a miss.

    Read from ``content/sop/corpus.toml`` rather than repeated here. A
    troubleshooting runbook covering the car wash would answer the question the
    walkthrough exists to have refused, and the two corpora are authored in
    different directories by different tools — so nothing but this would
    notice.
    """
    return list(honest_miss(repo_root).get("absent_terms", []))


def rehearsed_hit(repo_root: Path) -> Dict[str, Any]:
    """The rehearsed question the corpus **does** answer, and which document.

    The mirror image of the honest miss, and the walkthrough's opening beat:
    the cross-platform hop is what the whole architecture claim rests on, so
    the first thing the presenter taps has to land on a document that is
    actually in the library. A miss here does not fail — it answers, honestly,
    that the procedure is not there, which looks exactly like the beat that
    comes second.
    """
    return dict(sop_manifest(repo_root).get("rehearsed_hit", {}))


def sop_doc_ids(repo_root: Path) -> Dict[str, Path]:
    """Every ``SOP-NNN`` the corpus actually holds, and the file it came from.

    Read out of each source's TOML front matter rather than from the filename,
    because the identifier the corpus is cited by is the one in the front
    matter and only that one reaches an answer.
    """
    found: Dict[str, Path] = {}
    for path in sorted((repo_root / SOP_CORPUS_SOURCES).glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "+++":
            continue
        try:
            closing = lines.index("+++", 1)
        except ValueError:
            continue
        metadata = tomllib.loads("\n".join(lines[1:closing]))
        doc_id = metadata.get("doc_id")
        if isinstance(doc_id, str):
            found[doc_id] = path
    return found
