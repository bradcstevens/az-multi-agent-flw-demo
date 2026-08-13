"""
Human-in-the-loop MCP tool — ask_user.

Provides an ``ask_user`` tool that any domain agent can call to request
clarification from the human user.  The tool POSTs the question to the
backend's ``/api/clarification/ask`` endpoint, which relays it over WebSocket
to the browser and blocks until the user responds (or times out).

The answer is returned as a plain string — the agent continues with it
in context like any other tool result.

The HTTP client is injected rather than built inline (issue #18): this service
is the container's original backend caller, and giving it the same
``BackendClient`` seam the SOP tool uses is what makes both testable without an
outbound-HTTP mocking dependency.
"""

import logging
import os
from typing import Optional

import httpx
from core.factory import MCPToolBase
from services.backend_client import BackendClient

logger = logging.getLogger(__name__)

CLARIFICATION_ASK_PATH = "/api/v4/clarification/ask"

# Timeout for the round-trip (user may take a while to respond).
ASK_USER_TIMEOUT = float(os.environ.get("ASK_USER_TIMEOUT", "300"))


class AskUserService(MCPToolBase):
    """Cross-domain tool that pauses the workflow to ask the user a question."""

    def __init__(self, backend: Optional[BackendClient] = None):
        # Use a sentinel domain — this service is registered on every
        # domain server, not just one.
        from core.factory import Domain
        super().__init__(Domain.GENERAL)
        self.backend = backend or BackendClient(timeout=ASK_USER_TIMEOUT)

    def register_tools(self, mcp) -> None:
        """Register the ask_user tool on the given FastMCP server."""

        @mcp.tool()
        async def ask_user(question: str, user_id: str) -> str:
            """Ask the human user one or more clarifying questions and return their answer.

            Call this tool when you need information that was not provided in
            the original task and cannot be discovered by any other tool.  Ask
            about ALL unknown parameters — both required and optional.

            IMPORTANT: You must call this tool AT MOST ONCE per turn.  If you
            need multiple pieces of information, combine ALL questions into the
            single ``question`` string as a numbered list.  Example:

                question: "I need a few details to proceed:\n1. Employee full name?\n2. Start date?\n3. Department?"

            Do NOT call this tool multiple times in a row.

            Args:
                question: One or more questions formatted as a numbered list.
                          Combine all missing information into this single string.
                user_id:  REQUIRED — copy the EXACT value from the very first
                          line of your system instructions which reads
                          ``SESSION_USER_ID: <value>``.  It is a UUID like
                          ``00000000-0000-0000-0000-000000000000``.
                          DO NOT guess, invent, or use placeholder values like
                          "default".  If you cannot find SESSION_USER_ID in
                          your instructions, do NOT call this tool.

            Returns:
                The user's answer as a plain string.
            """
            logger.info(
                "ask_user: relaying question to backend (user=%s): %.120s",
                user_id,
                question,
            )

            try:
                data = await self.backend.post_json(
                    CLARIFICATION_ASK_PATH,
                    {"question": question, "user_id": user_id},
                    timeout=ASK_USER_TIMEOUT,
                )
                answer = data.get("answer", "")
                logger.info(
                    "ask_user: received answer (user=%s): %.120s",
                    user_id,
                    answer,
                )
                return answer or "The user did not provide an answer."
            except httpx.TimeoutException:
                logger.warning("ask_user: timed out waiting for user response.")
                return "The user did not respond in time. Proceed with sensible defaults."
            except httpx.HTTPStatusError as exc:
                logger.error("ask_user: backend returned %s", exc.response.status_code)
                return f"Unable to reach the user (HTTP {exc.response.status_code}). Proceed with sensible defaults."
            except Exception as exc:
                logger.error("ask_user: unexpected error: %s", exc)
                return "Unable to reach the user. Proceed with sensible defaults."

    @property
    def tool_count(self) -> int:
        return 1
