"""What the Grounding panel is allowed to claim (issue #23).

R6's assertion is not "a document was found". It is *this answer left Foundry
and came back from another platform* — so the signal carries the **platform**,
and it is emitted only when that hop actually produced an answer.

The one rule with teeth: a **failed** SOP reply emits nothing. #18's fixed
failure message is produced by the backend, not by Copilot Studio, and lighting
the Grounding panel over it would say the cross-platform hop happened on the
one occasion it did not. That is the same lie as a fallback to model knowledge,
wearing the panel's clothes.
"""

from typing import Any, Mapping, Optional

from transparency.payloads import SourceUsed


def source_used(reply: Mapping[str, Any]) -> Optional[SourceUsed]:
    """Build the Grounding panel's signal from a ``/sop/ask`` reply.

    ``None`` when the reply failed, or when it names no platform — the panel
    only ever claims a platform it was told about.

    An answer with **no citations** still emits. The rehearsed out-of-corpus
    probe (#26) is exactly that: Copilot Studio was reached, Dataverse was
    searched, nothing matched. Showing the hop with an empty document list is
    what makes the honest miss legible as a miss rather than as a silence.
    """
    if not reply:
        return None
    if reply.get("failed"):
        return None

    platform = reply.get("platform")
    if not platform:
        return None

    return SourceUsed(
        platform=platform,
        source=reply.get("source") or "",
        agent_name=reply.get("agent") or "",
        tool_query=reply.get("tool_query") or "",
        retrieval_query=reply.get("retrieval_query") or "",
        citations=list(reply.get("citations") or []),
        conversation_id=reply.get("conversation_id"),
    )
