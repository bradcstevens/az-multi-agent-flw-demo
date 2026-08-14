"""The Copilot Studio SOP agent, reached as a tool (issue #18, ADR-011).

The orchestrator calls the low-code agent the way it calls anything else: an
MCP tool. This is the cross-platform proof — a Foundry orchestrator, a Copilot
Studio agent, one real network call between two platforms.

The Direct Line client itself lives in the **backend** (`src/backend/sop/`).
This container ships only its own directory and `httpx`, so it asks the backend
over HTTP, the pattern `ask_user` already uses and the one #21 declares for
everything this container cannot do itself.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from core.factory import Domain, MCPToolBase
from services.backend_client import BackendClient

logger = logging.getLogger(__name__)

SOP_ASK_PATH = "/api/v4/sop/ask"

# A generative answer over the corpus came back in 5-20 seconds live, and the
# backend retries once behind this.
SOP_TIMEOUT_SECONDS = float(os.environ.get("SOP_TIMEOUT", "120"))

# The fixed failure message, in the orchestrator's own vocabulary. It offers no
# procedure of its own: never fall back to model knowledge, and never keep a
# local copy of the SOP corpus as a safety net — a hidden fallback would make
# the cross-platform claim untestable and, if it fired on stage, unfalsifiable.
SOP_FAILURE = (
    "The store procedure assistant could not be reached, so there is no "
    "procedure to report. Tell the associate to ask their shift lead, and do "
    "not answer the procedure question from any other source."
)


def format_answer(payload: Dict[str, Any]) -> str:
    """Render the bridge's reply as the string the agent reads.

    The cited document names are appended so the answer carries its own
    provenance into the transcript. An answer the backend marked failed is
    replaced wholesale — a failure that still looks like an answer is the one
    outcome this demo cannot survive.
    """
    if payload.get("failed"):
        return SOP_FAILURE

    text = (payload.get("text") or "").strip()
    if not text:
        return SOP_FAILURE

    names: List[str] = []
    for citation in payload.get("citations") or []:
        name = citation.get("name")
        if name and name not in names:
            names.append(name)
    if not names:
        return text
    return f"{text}\n\nSource: {', '.join(names)}"


class SopService(MCPToolBase):
    """The store-procedure tool, on its own domain."""

    def __init__(self, backend: Optional[BackendClient] = None):
        super().__init__(Domain.SOP)
        self.backend = backend or BackendClient(timeout=SOP_TIMEOUT_SECONDS)

    def register_tools(self, mcp) -> None:
        @mcp.tool(tags=[self.domain.value])
        async def search_store_procedures(question: str) -> str:
            """Answer a store procedure question from the official SOP library.

            Use this for anything about how a task at the store is *done* —
            opening, closing, cash handling, cleaning, deliveries, safety.
            The answer comes from the store's published procedure documents,
            not from your own knowledge.

            If this tool reports that the procedure assistant could not be
            reached, say so. Do NOT answer the procedure question yourself and
            do NOT reconstruct the steps from memory.

            Args:
                question: The associate's complete question. Preserve its
                    procedure wording; do not summarize or rephrase it.

            Returns:
                The procedure, followed by the documents it came from.
            """
            try:
                payload = await self.backend.post_json(
                    SOP_ASK_PATH,
                    {"question": question},
                    timeout=SOP_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                logger.error("search_store_procedures: backend unreachable: %s", exc)
                return SOP_FAILURE
            return format_answer(payload)

    @property
    def tool_count(self) -> int:
        return 1
