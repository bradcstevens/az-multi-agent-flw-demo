"""The Simulated ticket, drafted from the MCP container (issue #22).

The container has **no Cosmos access at all** — no connection configuration and
no dependency — so it drafts the ticket over the same `BackendClient` seam the
attempted-steps tools reach the record over. Tested at that seam rather than
against a network.

The load-bearing test in this file is the one that counts the tools: there is
**one**, and it drafts. A tool that submitted would be the second confirmation
step TKT-001 says does not exist, reachable by a model on its own turn.
"""

from unittest.mock import AsyncMock

import httpx
import pytest

pytest.importorskip("fastmcp", reason="fastmcp not installed in backend venv; run with mcp_server venv")

from core.factory import Domain  # noqa: E402
from services.backend_client import BackendClient  # noqa: E402
from services.escalation_service import (  # noqa: E402
    DRAFT_FAILED, TICKET_PATH, EscalationService, format_draft)


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


def drafted(**fields):
    base = {
        "status": "draft",
        "ticket_id": "not reported",
        "steps_attempted": "Power cycled the brewer",
        "symptom": "the coffee comes out cold",
    }
    base.update(fields)
    return {
        "drafted": True,
        "fields": base,
        "rendered": "\n".join(f"{k}: {v}" for k, v in base.items()),
    }


class TestThereIsNoWayToRaiseATicket:
    """The plan approval **is** the confirmation. Enforced by the toolbox
    holding nothing that could raise one, rather than by a system message
    asking the model not to — an instruction a model follows most of the time
    is not a gate, and this one guards the one artefact that leaves the room.
    """

    def test_the_service_offers_exactly_one_tool(self, mock_mcp_server):
        service = EscalationService()
        service.register_tools(mock_mcp_server)

        assert service.tool_count == len(mock_mcp_server.tools) == 1

    def test_and_that_tool_drafts(self, mock_mcp_server):
        service = EscalationService()
        service.register_tools(mock_mcp_server)

        assert [tool["func"].__name__ for tool in mock_mcp_server.tools] == [
            "draft_service_ticket"
        ]

    def test_no_tool_here_submits_confirms_or_raises_anything(
        self, mock_mcp_server
    ):
        """Named against the words a later iteration would reach for."""
        service = EscalationService()
        service.register_tools(mock_mcp_server)

        names = " ".join(tool["func"].__name__ for tool in mock_mcp_server.tools)
        for forbidden in ("submit", "confirm", "raise", "send"):
            assert forbidden not in names


class TestTheContainerKeepsNoState:
    """Asserted against imports rather than prose, which names Cosmos in the
    module docstring and would satisfy a text search either way."""

    @staticmethod
    def _imported_roots(module):
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
        import services.escalation_service as module

        roots = self._imported_roots(module)

        assert not {root for root in roots if "azure" in root or "cosmos" in root}

    def test_it_does_not_hold_the_http_client_itself(self):
        import services.escalation_service as module

        assert "httpx" not in self._imported_roots(module)

    def test_it_has_its_own_domain(self):
        """Its own domain so the escalation agent can draft a ticket without
        also being handed the shared ``ask_user`` — whose contract needs a
        ``SESSION_USER_ID`` nothing injects, and which is itself a second
        question to the associate at the exact moment the requirement says
        there is none."""
        assert EscalationService().domain == Domain.ESCALATION


class TestDraftServiceTicket:
    @pytest.mark.asyncio
    async def test_it_sends_the_fields_the_agent_filled(self, mock_mcp_server):
        service = EscalationService(client_with(drafted()))
        tool = tool_named(service, mock_mcp_server, "draft_service_ticket")

        await tool(symptom="the coffee comes out cold", priority="2")

        method, path = service.backend._request.await_args.args
        assert (method, path) == ("POST", TICKET_PATH)
        sent = service.backend._request.await_args.kwargs["json"]
        assert sent["symptom"] == "the coffee comes out cold"
        assert sent["priority"] == "2"

    @pytest.mark.asyncio
    async def test_it_carries_no_session_and_no_user(self, mock_mcp_server):
        """The backend resolves the turn in flight. A mis-copied identifier
        here drafts one associate's fault onto another associate's approval."""
        service = EscalationService(client_with(drafted()))
        tool = tool_named(service, mock_mcp_server, "draft_service_ticket")

        await tool(symptom="cold coffee")

        sent = service.backend._request.await_args.kwargs["json"]
        assert not {key for key in sent if "session" in key or "user" in key}

    @pytest.mark.asyncio
    async def test_the_tool_cannot_send_the_attempted_steps_at_all(
        self, mock_mcp_server
    ):
        """Not a parameter. A model with somewhere to put them will put them
        there, and what it puts there is its paraphrase of what the associate
        said rather than what the associate said."""
        import inspect

        service = EscalationService(client_with(drafted()))
        tool = tool_named(service, mock_mcp_server, "draft_service_ticket")

        assert "steps_attempted" not in inspect.signature(tool).parameters

    @pytest.mark.asyncio
    async def test_it_hands_back_the_whole_ticket_for_the_associate_to_read(
        self, mock_mcp_server
    ):
        """"The associate sees exactly what will be submitted": the tool
        returns the ticket, not a confirmation that one exists."""
        service = EscalationService(client_with(drafted()))
        tool = tool_named(service, mock_mcp_server, "draft_service_ticket")

        answer = await tool(symptom="the coffee comes out cold")

        assert "the coffee comes out cold" in answer
        assert "Power cycled the brewer" in answer

    @pytest.mark.asyncio
    async def test_the_steps_it_reports_are_the_ones_the_backend_filled_in(
        self, mock_mcp_server
    ):
        service = EscalationService(
            client_with(drafted(steps_attempted="Fitted a fresh paper filter"))
        )
        tool = tool_named(service, mock_mcp_server, "draft_service_ticket")

        assert "Fitted a fresh paper filter" in await tool(symptom="cold")

    @pytest.mark.asyncio
    async def test_it_says_the_ticket_is_not_raised_yet(self, mock_mcp_server):
        """The associate has not approved anything at this point, and an agent
        that reads *raised* here tells them so."""
        service = EscalationService(client_with(drafted()))
        tool = tool_named(service, mock_mcp_server, "draft_service_ticket")

        answer = await tool(symptom="cold coffee")

        assert "not been raised" in answer.lower()

    @pytest.mark.asyncio
    async def test_a_draft_that_did_not_land_says_so(self, mock_mcp_server):
        """An agent told the draft was kept presents a ticket to the associate
        that the approval seam will never find — so approving it confirms
        nothing at all, silently."""
        service = EscalationService(client_with({"drafted": False, "fields": {}}))
        tool = tool_named(service, mock_mcp_server, "draft_service_ticket")

        assert await tool(symptom="cold coffee") == DRAFT_FAILED

    @pytest.mark.asyncio
    async def test_an_unreachable_backend_says_so_too(self, mock_mcp_server):
        service = EscalationService(client_with(error=httpx.ConnectError("no route")))
        tool = tool_named(service, mock_mcp_server, "draft_service_ticket")

        assert await tool(symptom="cold coffee") == DRAFT_FAILED

    def test_a_response_with_no_ticket_in_it_is_a_failure_not_a_blank_ticket(self):
        """A blank ticket read back as a draft is a ticket the associate would
        be asked to approve with nothing in it."""
        assert format_draft({}) == DRAFT_FAILED
        assert format_draft(None) == DRAFT_FAILED
