"""Citations parsed structurally out of a Direct Line activity (issue #18).

ADR-011 binds this: read the citation out of the activity's `entities`
collection, where the entity type is the schema.org `Message` type. The
markdown reference-style form in the activity text (`[1]: cite:1 "Citation-1"`)
is a parallel representation, not the source of truth — `cite:1` is not a URL
and resolves to nothing.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re

SCHEMA_ORG_MESSAGE = "https://schema.org/Message"

# What the Grounding panel can put beside a document name without dropping a
# whole SOP into the panel. `appearance.text` was 3311 characters for SOP-102.
DEFAULT_SNIPPET_LIMIT = 240

_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Citation:
    """One cited document, as the SOP agent delivers it."""

    position: int
    name: str
    abstract: str = ""
    text: str = ""
    url: Optional[str] = None

    def snippet(self, limit: int = DEFAULT_SNIPPET_LIMIT) -> str:
        """A short, plain-text extract of the cited document.

        Taken from `text`, not `abstract`: live, `abstract` is the filename and
        is identical to `name`, so a snippet taken from it renders the filename
        twice (see CONTEXT.md, "Citation appearance"). The markup is stripped
        because `text` arrives as HTML and the panel renders plain text.
        """
        plain = " ".join(_TAG.sub(" ", self.text).split())
        return plain[:limit]


def citations_from_activity(activity: Optional[Dict[str, Any]]) -> List[Citation]:
    """Return the citations an activity carries, in position order."""
    citations = []
    for entity in (activity or {}).get("entities") or []:
        if entity.get("type") != SCHEMA_ORG_MESSAGE:
            continue
        for claim in entity.get("citation") or []:
            appearance = claim.get("appearance") or {}
            citations.append(
                Citation(
                    position=claim.get("position", 0),
                    name=appearance.get("name") or "",
                    abstract=appearance.get("abstract") or "",
                    text=appearance.get("text") or "",
                    url=appearance.get("url") or claim.get("url"),
                )
            )
    return sorted(citations, key=lambda citation: citation.position)
