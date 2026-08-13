"""Parse the documents the store pack indexes.

These are authored as the artefact that is uploaded, not as a source that is
built into one. ``index_datasets.py`` decodes anything that is not a PDF or a
DOCX as UTF-8 and indexes it whole, so markdown *is* the indexed document —
which removes a build step and, with it, the class of drift where the built
copy and the edited copy disagree. The SOP corpus needs its build because
Copilot Studio will only ingest ``.docx``; this one does not.

What this module knows is the shape a runbook has to keep, and the shape is
load-bearing rather than decorative:

* **Ask First** is what makes the multi-turn beat answerable. An open "what
  have you tried?" to an associate mid-shift gets a shrug; the runbook names
  the two or three things worth asking about.
* **Branches** are the difference between a runbook and a recital. Each states
  the observation that selects it, so the agent asks for one thing and takes
  one path.
* **Stop and Escalate** is where the runbook admits it is out of ideas, which
  is the hand-off the escalation agent picks up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

DOC_ID_LINE = re.compile(r"^Document ID:\s*(\S+)\s*$")
BRANCH_HEADING = re.compile(r"^###\s+(Branch\s+.+)$")
_CONDITION = re.compile(r"^If\s+(.+?):\s*$", re.IGNORECASE)
_BULLET = re.compile(r"^-\s+(.*)$")
_FIELD = re.compile(r"^([a-z_]+):\s*(.*)$")

ASK_FIRST_HEADING = "Ask First"
STOP_HEADING = "Stop and Escalate"
FIELDS_HEADING = "Fields"


class ContentError(ValueError):
    """A document the agent would ground on and answer wrongly from."""


@dataclass(frozen=True)
class Branch:
    heading: str
    condition: str


@dataclass(frozen=True)
class Document:
    path: Path
    text: str
    doc_id: str
    headings: List[str] = field(default_factory=list)
    branches: List[Branch] = field(default_factory=list)
    already_tried: List[str] = field(default_factory=list)
    fields: Dict[str, str] = field(default_factory=dict)


def parse_document(path: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    doc_id = ""
    headings: List[str] = []
    branches: List[Branch] = []
    already_tried: List[str] = []
    fields: Dict[str, str] = {}

    section = ""
    pending_branch = ""

    for line in lines:
        stripped = line.strip()

        match = DOC_ID_LINE.match(stripped)
        if match:
            doc_id = match.group(1)
            continue

        branch_heading = BRANCH_HEADING.match(stripped)
        if branch_heading:
            pending_branch = branch_heading.group(1)
            continue

        if stripped.startswith("## "):
            section = stripped[3:].strip()
            headings.append(section)
            pending_branch = ""
            continue

        if pending_branch:
            condition = _CONDITION.match(stripped)
            if condition:
                branches.append(
                    Branch(heading=pending_branch, condition=condition.group(1).strip())
                )
                pending_branch = ""
            continue

        if section == ASK_FIRST_HEADING:
            bullet = _BULLET.match(stripped)
            if bullet:
                already_tried.append(bullet.group(1).strip())
            continue

        if section == FIELDS_HEADING:
            named = _FIELD.match(stripped)
            if named:
                fields[named.group(1)] = named.group(2).strip()

    if not doc_id:
        raise ContentError(f"{path.name} carries no 'Document ID:' line")

    return Document(
        path=path,
        text=text,
        doc_id=doc_id,
        headings=headings,
        branches=branches,
        already_tried=already_tried,
        fields=fields,
    )
