"""The three transparency payloads (issue #23).

They live here rather than in ``models/messages.py`` for the same reason
``Citation`` lives in ``sop/`` — the package that decides what a signal may
claim owns the shape of the claim. ``models/messages.py`` is the MACAE
baseline's file and keeps the ``WebsocketMessageType`` enum, which is the
transport's business; these are the domain's.

The practical consequence is that the modules with the decisions in them import
nothing but ``dataclasses``, so they are testable as the pure things they are.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class TokenUsage:
    """One executor's reported token cost, for the Token meter (R7).

    Attributed by **executor identifier** — the same attribution the streaming
    header uses, and the only one that survives **Plan review** being off,
    because on the Fast lane there is no plan to read an agent name out of.
    """
    agent_name: str
    executor_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceUsed:
    """Which platform answered, and out of what, for the Grounding panel (R6).

    Carries the **platform** and not only the source: "Dataverse" alone does
    not distinguish the cross-platform hop from any other retrieval, and the
    claim being made is that this one answer left Foundry.
    """
    platform: str
    source: str
    agent_name: str
    citations: List[Dict[str, Any]] = field(default_factory=list)
    conversation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PresenterAlert:
    """A proactive shift-task message that answers nothing (R8).

    Rendered distinctly from a reply (#24) so it is never mistaken for one,
    which is why it carries a title of its own rather than an agent name.
    """
    title: str
    content: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
