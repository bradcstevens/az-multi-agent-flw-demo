"""The memory of one shift, reached as a tool (issue #21).

What an associate has already tried is not knowledge — the store's runbooks are
knowledge, and they live in a Foundry IQ Knowledge Base. This is memory of the
fault in front of them, and it is held in the backend's Cosmos memory container.

This container has **no Cosmos access at all**: no connection configuration, no
credentials and no dependency. It asks the backend over HTTP through the same
``BackendClient`` seam the SOP and clarification tools use, against the backend
URL already configured for it.

Neither tool takes a session or a user. The backend resolves the turn in flight
itself, which is deliberate: ``ask_user``'s pattern has a model copying a UUID
out of its instructions, and a mis-copy here writes one associate's attempted
steps onto another associate's fault, or reads back steps nobody on this shift
tried and skips a real runbook branch.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from core.factory import Domain, MCPToolBase
from services.backend_client import BackendClient

logger = logging.getLogger(__name__)

ATTEMPTED_PATH = "/api/v4/troubleshooting/attempted"

TROUBLESHOOTING_TIMEOUT_SECONDS = float(os.environ.get("TROUBLESHOOTING_TIMEOUT", "30"))

# An empty record and an unreachable backend read the same, and on purpose.
# Both mean "nothing is known to have been tried", which offers the whole
# runbook: the associate repeats a step at worst. The other direction — a step
# claimed as tried that was not — is silently skipped and leaves the equipment
# broken, so it is never what a failure produces.
NOTHING_RECORDED = (
    "Nothing has been recorded as already tried on this fault. Ask the "
    "associate what they have already tried before giving them steps."
)

# A write that did not land must say so. An agent told the record was kept
# stops asking, and the next turn repeats a step believing it was recorded.
RECORD_FAILED = (
    "The attempted steps could NOT be recorded. Keep them in the conversation "
    "yourself and do not rely on them being remembered on a later turn."
)


def format_attempted(payload: Dict[str, Any]) -> str:
    """Render the record as the string the agent reads."""
    steps: List[str] = [
        step for step in (payload or {}).get("attempted") or [] if step
    ]
    if not steps:
        return NOTHING_RECORDED

    note = ((payload or {}).get("note") or "").strip()
    listed = "\n".join(f"- {step}" for step in steps)
    header = (
        "The associate has already reported trying these on this fault, in "
        "this session:"
    )
    return f"{header}\n{listed}\n\n{note}".strip()


def format_recorded(payload: Dict[str, Any]) -> str:
    """Render the outcome of a write, and the record it produced."""
    if not (payload or {}).get("recorded"):
        return RECORD_FAILED
    return f"Recorded.\n\n{format_attempted(payload)}"


class TroubleshootingService(MCPToolBase):
    """The attempted-steps memory, on its own domain."""

    def __init__(self, backend: Optional[BackendClient] = None):
        super().__init__(Domain.TROUBLESHOOTING)
        self.backend = backend or BackendClient(
            timeout=TROUBLESHOOTING_TIMEOUT_SECONDS
        )

    def register_tools(self, mcp) -> None:
        @mcp.tool(tags=[self.domain.value])
        async def list_attempted_steps() -> str:
            """What this associate has ALREADY TRIED on the fault they reported.

            Call this FIRST, on every troubleshooting turn, before you give any
            steps. It is the record of this session, not your memory of the
            conversation, and it survives a turn that the conversation does not.

            It answers only "what has been tried". It holds no repair steps and
            no equipment knowledge — those come from your knowledge base, which
            you must still search.

            Never walk the associate through a step this reports: skip it, say
            you are skipping it and why, and go to the next branch of the
            runbook.

            Returns:
                The steps already tried, or a note that nothing is recorded.
            """
            try:
                payload = await self.backend.get_json(
                    ATTEMPTED_PATH, timeout=TROUBLESHOOTING_TIMEOUT_SECONDS
                )
            except Exception as exc:
                logger.error("list_attempted_steps: backend unreachable: %s", exc)
                return NOTHING_RECORDED
            return format_attempted(payload)

        @mcp.tool(tags=[self.domain.value])
        async def record_attempted_steps(steps: str, equipment: str = "") -> str:
            """Record what the associate has told you they already tried.

            Call this as soon as an associate reports having tried something —
            in their opening message or anywhere in the turn — so a later turn
            does not offer it again.

            Pass their own words. Do not rewrite them into runbook language and
            do not add a step they did not report: a step recorded here is one
            the assistant will skip, and skipping a step nobody tried leaves the
            equipment broken.

            Args:
                steps:     What the associate said they tried, in their words.
                equipment: What is broken, if they have named it.

            Returns:
                Whether it was recorded, and everything recorded so far.
            """
            try:
                payload = await self.backend.post_json(
                    ATTEMPTED_PATH,
                    {"steps": steps, "equipment": equipment},
                    timeout=TROUBLESHOOTING_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                logger.error("record_attempted_steps: backend unreachable: %s", exc)
                return RECORD_FAILED
            return format_recorded(payload)

    @property
    def tool_count(self) -> int:
        return 2
