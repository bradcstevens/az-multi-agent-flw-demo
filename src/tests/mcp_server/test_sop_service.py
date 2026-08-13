"""The MCP container's backend seam, and the two tools that use it (issue #18).

The container reaches the backend over HTTP for everything it cannot do itself.
`AskUserService` used to build its `httpx.AsyncClient` inline, so there was no
seam to test at; both services now take a `BackendClient` whose request method
is the seam, the pattern `BaseAPIService` establishes on the backend side.
"""

from unittest.mock import AsyncMock

import httpx
import pytest

pytest.importorskip("fastmcp", reason="fastmcp not installed in backend venv; run with mcp_server venv")

from core.factory import Domain  # noqa: E402
from services.ask_user_service import AskUserService  # noqa: E402
from services.backend_client import BackendClient  # noqa: E402
from services.sop_service import (SOP_FAILURE, SopService,  # noqa: E402
                                  format_answer)

SOP_102 = "SOP-102 Store Closing Procedure.docx"


def client_with(payload=None, status=200, error=None):
    """A `BackendClient` whose request method returns a canned response."""
    backend = BackendClient("https://backend.example.com")
    if error is not None:
        backend._request = AsyncMock(side_effect=error)
        return backend
    request = httpx.Request("POST", "https://backend.example.com/x")
    response = httpx.Response(status, json=payload or {}, request=request)
    backend._request = AsyncMock(return_value=response)
    return backend


def tool_named(service, mcp, name):
    service.register_tools(mcp)
    for tool in mcp.tools:
        if tool["func"].__name__ == name:
            return tool["func"]
    raise AssertionError(f"{name} was not registered")


class TestBackendClient:
    @pytest.mark.asyncio
    async def test_posts_to_the_backend_and_returns_the_body(self):
        backend = client_with({"answer": "yes"})

        assert await backend.post_json("/api/v4/x", {"q": 1}) == {"answer": "yes"}
        assert backend._request.await_args.args == ("POST", "/api/v4/x")

    @pytest.mark.asyncio
    async def test_an_error_status_raises_rather_than_returning_a_body(self):
        backend = client_with({"detail": "nope"}, status=500)

        with pytest.raises(httpx.HTTPStatusError):
            await backend.post_json("/api/v4/x", {})

    def test_a_trailing_slash_on_the_backend_url_does_not_double(self):
        assert (
            BackendClient("https://backend.example.com/")._url("/api/v4/x")
            == "https://backend.example.com/api/v4/x"
        )

    @pytest.mark.asyncio
    async def test_it_can_read_as_well_as_write(self):
        """The troubleshooting record's read half (#21) carries no body: the
        backend resolves which session the turn belongs to, so there is nothing
        for the container to send."""
        backend = client_with({"attempted": []})

        assert await backend.get_json("/api/v4/x") == {"attempted": []}
        assert backend._request.await_args.args == ("GET", "/api/v4/x")
        assert backend._request.await_args.kwargs.get("json") is None


class TestSopService:
    def test_the_sop_agent_has_its_own_domain(self):
        # Its own domain so a team definition can give an agent the SOP tool
        # without also handing it every other domain's tools.
        assert SopService().domain == Domain.SOP

    def test_registers_one_tool(self, mock_mcp_server):
        service = SopService(backend=client_with())
        service.register_tools(mock_mcp_server)

        assert len(mock_mcp_server.tools) == service.tool_count == 1

    @pytest.mark.asyncio
    async def test_a_procedure_question_returns_the_copilot_studio_answer(
        self, mock_mcp_server
    ):
        service = SopService(
            backend=client_with(
                {
                    "text": "1. Count the drawer.",
                    "failed": False,
                    "platform": "Copilot Studio",
                    "source": "Dataverse",
                    "citations": [
                        {
                            "position": 1,
                            "name": SOP_102,
                            "snippet": "Store Closing Procedure",
                            "url": None,
                        }
                    ],
                }
            )
        )
        tool = tool_named(service, mock_mcp_server, "search_store_procedures")

        result = await tool("How do I close the store?")

        assert "1. Count the drawer." in result
        assert SOP_102 in result

    @pytest.mark.asyncio
    async def test_asks_the_backends_sop_bridge(self, mock_mcp_server):
        service = SopService(backend=client_with({"text": "ok", "citations": []}))
        tool = tool_named(service, mock_mcp_server, "search_store_procedures")

        await tool("How do I close the store?")

        assert service.backend._request.await_args.args[1] == "/api/v4/sop/ask"

    @pytest.mark.asyncio
    async def test_an_unreachable_backend_is_the_fixed_failure_message(
        self, mock_mcp_server
    ):
        # No fallback to model knowledge and no local copy of the SOP corpus:
        # a hidden fallback would make the cross-platform claim unfalsifiable.
        service = SopService(backend=client_with(error=httpx.ConnectError("down")))
        tool = tool_named(service, mock_mcp_server, "search_store_procedures")

        assert await tool("How do I close the store?") == SOP_FAILURE

    @pytest.mark.asyncio
    async def test_a_timeout_is_the_fixed_failure_message_too(self, mock_mcp_server):
        service = SopService(backend=client_with(error=httpx.TimeoutException("slow")))
        tool = tool_named(service, mock_mcp_server, "search_store_procedures")

        assert await tool("How do I close the store?") == SOP_FAILURE


class TestFormatAnswer:
    def test_names_the_cited_documents_so_the_answer_carries_its_source(self):
        formatted = format_answer(
            {"text": "1. Count the drawer.", "citations": [{"name": SOP_102}]}
        )

        assert formatted.splitlines()[0] == "1. Count the drawer."
        assert SOP_102 in formatted

    def test_an_uncited_answer_is_returned_as_it_stands(self):
        assert format_answer({"text": "No procedure covers that.", "citations": []}) == (
            "No procedure covers that."
        )

    def test_the_honest_miss_is_passed_through_unchanged(self):
        # The out-of-corpus refusal is the agent's own wording and the beat the
        # grounding claim rests on. Dressing it up would answer the question.
        miss = "I do not have a procedure for that. Please ask your shift lead."

        assert format_answer({"text": miss, "citations": []}) == miss

    def test_an_answer_the_backend_marked_failed_is_the_fixed_failure_message(self):
        assert format_answer({"text": "anything", "failed": True}) == SOP_FAILURE

    def test_names_each_document_once_however_many_times_it_is_cited(self):
        formatted = format_answer(
            {
                "text": "steps",
                "citations": [{"name": SOP_102}, {"name": SOP_102}],
            }
        )

        assert formatted.count(SOP_102) == 1


class TestAskUserService:
    """The analogue refactored for injection, with its behaviour pinned."""

    @pytest.mark.asyncio
    async def test_relays_the_question_and_returns_the_answer(self, mock_mcp_server):
        service = AskUserService(backend=client_with({"answer": "the walk-in"}))
        tool = tool_named(service, mock_mcp_server, "ask_user")

        assert await tool("Which unit?", "user-1") == "the walk-in"
        assert service.backend._request.await_args.args[1] == (
            "/api/v4/clarification/ask"
        )

    @pytest.mark.asyncio
    async def test_a_silent_user_is_not_an_empty_answer(self, mock_mcp_server):
        service = AskUserService(backend=client_with({"answer": ""}))
        tool = tool_named(service, mock_mcp_server, "ask_user")

        assert "did not provide an answer" in await tool("Which unit?", "user-1")

    @pytest.mark.asyncio
    async def test_a_timeout_tells_the_agent_to_proceed(self, mock_mcp_server):
        service = AskUserService(backend=client_with(error=httpx.TimeoutException("x")))
        tool = tool_named(service, mock_mcp_server, "ask_user")

        assert "did not respond in time" in await tool("Which unit?", "user-1")

    @pytest.mark.asyncio
    async def test_an_error_status_tells_the_agent_to_proceed(self, mock_mcp_server):
        service = AskUserService(backend=client_with({"detail": "no"}, status=503))
        tool = tool_named(service, mock_mcp_server, "ask_user")

        assert "Proceed with sensible defaults" in await tool("Which unit?", "user-1")
