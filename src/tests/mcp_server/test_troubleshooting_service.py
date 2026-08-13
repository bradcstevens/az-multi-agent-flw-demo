"""The troubleshooting record, reached from the MCP container (issue #21).

The container has **no Cosmos access at all** — no connection configuration and
no dependency — so it asks the backend over HTTP, through the same
`BackendClient` seam the SOP and clarification tools use. Tested at that seam
rather than against a network.
"""

from unittest.mock import AsyncMock

import httpx
import pytest

pytest.importorskip("fastmcp", reason="fastmcp not installed in backend venv; run with mcp_server venv")

from core.factory import Domain  # noqa: E402
from services.backend_client import BackendClient  # noqa: E402
from services.troubleshooting_service import (  # noqa: E402
    ATTEMPTED_PATH, NOTHING_RECORDED, RECORD_FAILED, TroubleshootingService,
    format_attempted, format_recorded)


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


class TestTheContainerKeepsNoState:
    """The criterion is about what the container *depends on*, so it is
    asserted against imports and the package manifest — not against prose,
    which names Cosmos on every second line and would satisfy a text search
    either way."""

    @staticmethod
    def _imported_roots(module):
        """The top-level packages a module actually imports."""
        import ast

        tree = ast.parse(open(module.__file__, encoding="utf-8").read())
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots.add(node.module.split(".")[0])
        return roots

    def test_it_imports_no_cosmos_and_no_azure(self):
        import services.troubleshooting_service as module

        roots = self._imported_roots(module)

        assert not {root for root in roots if "azure" in root or "cosmos" in root}

    def test_it_does_not_even_hold_the_http_client_itself(self):
        """`BackendClient` is the container's one way of reaching the backend
        and the seam every test here drives. A second, inline client would be
        an untestable second way out."""
        import services.troubleshooting_service as module

        assert "httpx" not in self._imported_roots(module)

    def test_the_container_declares_no_cosmos_dependency(self):
        """No Cosmos connection configuration and no Cosmos dependency is
        added to this container — asserted where a dependency would land."""
        from pathlib import Path

        manifest = (
            Path(__file__).resolve().parents[2] / "mcp_server" / "pyproject.toml"
        ).read_text(encoding="utf-8").lower()

        assert "cosmos" not in manifest

    def test_it_has_its_own_domain(self):
        """Its own domain so a team definition can give an agent the memory of
        this shift without also handing it every other domain's tools."""
        assert TroubleshootingService().domain == Domain.TROUBLESHOOTING

    def test_it_registers_the_two_tools_it_declares(self, mock_mcp_server):
        service = TroubleshootingService()
        service.register_tools(mock_mcp_server)

        assert service.tool_count == len(mock_mcp_server.tools) == 2


class TestListAttemptedSteps:
    @pytest.mark.asyncio
    async def test_it_reports_what_the_backend_holds(self, mock_mcp_server):
        service = TroubleshootingService(
            client_with({"attempted": ["Power cycled the brewer"], "note": "n"})
        )
        tool = tool_named(service, mock_mcp_server, "list_attempted_steps")

        answer = await tool()

        assert "Power cycled the brewer" in answer

    @pytest.mark.asyncio
    async def test_it_asks_the_backend_and_carries_no_identifier(
        self, mock_mcp_server
    ):
        """Nothing on the wire names a session or a user. The backend resolves
        the turn in flight; a model asked to carry a UUID mis-copies it, and a
        mis-copied one reads back another associate's fault."""
        service = TroubleshootingService(client_with({"attempted": []}))
        tool = tool_named(service, mock_mcp_server, "list_attempted_steps")

        await tool()

        method, path = service.backend._request.await_args.args
        assert (method, path) == ("GET", ATTEMPTED_PATH)
        assert service.backend._request.await_args.kwargs.get("json") is None

    @pytest.mark.asyncio
    async def test_nothing_recorded_says_so_plainly(self, mock_mcp_server):
        """An empty record must read as *nothing has been tried*, which offers
        the whole runbook — not as an error, which invites the agent to guess."""
        service = TroubleshootingService(client_with({"attempted": []}))
        tool = tool_named(service, mock_mcp_server, "list_attempted_steps")

        assert await tool() == NOTHING_RECORDED

    @pytest.mark.asyncio
    async def test_an_unreachable_backend_reports_nothing_recorded(
        self, mock_mcp_server
    ):
        """The safe direction: the runbook is offered in full and the associate
        repeats a step, rather than a step being skipped that nobody tried."""
        service = TroubleshootingService(
            client_with(error=httpx.ConnectError("no route"))
        )
        tool = tool_named(service, mock_mcp_server, "list_attempted_steps")

        assert await tool() == NOTHING_RECORDED

    @pytest.mark.asyncio
    async def test_the_note_forbidding_a_repeat_is_carried_verbatim(
        self, mock_mcp_server
    ):
        service = TroubleshootingService(
            client_with({
                "attempted": ["Power cycled the brewer"],
                "note": "Do NOT walk them through any of them again.",
            })
        )
        tool = tool_named(service, mock_mcp_server, "list_attempted_steps")

        assert "Do NOT walk them through any of them again." in await tool()


class TestRecordAttemptedSteps:
    @pytest.mark.asyncio
    async def test_it_sends_what_the_associate_said(self, mock_mcp_server):
        service = TroubleshootingService(
            client_with({"recorded": True, "attempted": ["power cycled it"]})
        )
        tool = tool_named(service, mock_mcp_server, "record_attempted_steps")

        await tool(steps="I power cycled it")

        assert service.backend._request.await_args.kwargs["json"] == {
            "steps": "I power cycled it",
            "equipment": "",
        }

    @pytest.mark.asyncio
    async def test_the_equipment_rides_along_for_the_ticket_that_follows(
        self, mock_mcp_server
    ):
        service = TroubleshootingService(client_with({"recorded": True}))
        tool = tool_named(service, mock_mcp_server, "record_attempted_steps")

        await tool(steps="I power cycled it", equipment="coffee brewer")

        assert (
            service.backend._request.await_args.kwargs["json"]["equipment"]
            == "coffee brewer"
        )

    @pytest.mark.asyncio
    async def test_a_write_the_backend_refused_is_reported_as_a_failure(
        self, mock_mcp_server
    ):
        """An agent told the write succeeded when it did not stops asking, and
        the next turn repeats a step believing it was recorded."""
        service = TroubleshootingService(client_with({"recorded": False}))
        tool = tool_named(service, mock_mcp_server, "record_attempted_steps")

        assert await tool(steps="I power cycled it") == RECORD_FAILED

    @pytest.mark.asyncio
    async def test_an_unreachable_backend_is_reported_as_a_failure(
        self, mock_mcp_server
    ):
        service = TroubleshootingService(
            client_with(error=httpx.ConnectError("no route"))
        )
        tool = tool_named(service, mock_mcp_server, "record_attempted_steps")

        assert await tool(steps="I power cycled it") == RECORD_FAILED

    @pytest.mark.asyncio
    async def test_a_successful_write_hands_the_record_straight_back(
        self, mock_mcp_server
    ):
        """So the turn that recorded a step is already told what it must not
        repeat, without a second tool call."""
        service = TroubleshootingService(
            client_with({
                "recorded": True,
                "attempted": ["power cycled it"],
                "note": "Do NOT walk them through any of them again.",
            })
        )
        tool = tool_named(service, mock_mcp_server, "record_attempted_steps")

        answer = await tool(steps="I power cycled it")

        assert "power cycled it" in answer
        assert "Do NOT walk them through any of them again." in answer


class TestRendering:
    def test_an_empty_record_renders_as_nothing_recorded(self):
        assert format_attempted({"attempted": []}) == NOTHING_RECORDED
        assert format_attempted({}) == NOTHING_RECORDED

    def test_every_step_is_named(self):
        rendered = format_attempted(
            {"attempted": ["Power cycled the brewer", "Checked the water line"]}
        )

        assert "Power cycled the brewer" in rendered
        assert "Checked the water line" in rendered

    def test_a_refused_write_renders_as_a_failure(self):
        assert format_recorded({"recorded": False}) == RECORD_FAILED
        assert format_recorded({}) == RECORD_FAILED
