"""The Workforce agent's mocked HR procedure library (issue #52, ADR-017).

The load-bearing tests in this file are the ones that check what the library
**cannot** say. ADR-017 draws the boundary in the vocabulary rather than in a
prompt: this agent answers *how an employment task is performed* and the
Identity boundary gate keeps answering *what is in an individual's record*, so
a tool here that returned a balance, a rate, hours or an entitlement would be
the collision ADR-014 and the Mocked unlock exist to prevent, re-opened from
the tool side where no gate is watching.

Unlike the SOP tool beside it, nothing here calls the backend. There is no HR
system behind this and the surface may not claim one, so the library is held in
the container as authored text and the tool says out loud that it is simulated.
"""

import inspect

import pytest

pytest.importorskip("fastmcp", reason="fastmcp not installed in backend venv; run with mcp_server venv")

from core.factory import Domain  # noqa: E402
from services.workforce_service import (  # noqa: E402
    NOT_IN_THE_LIBRARY,
    PROCEDURES,
    SHIFT_SWAP,
    WorkforceService,
    format_procedure,
    format_topics,
)


def tool_named(service, mcp, name):
    service.register_tools(mcp)
    for tool in mcp.tools:
        if tool["func"].__name__ == name:
            return tool["func"]
    raise AssertionError(f"{name} was not registered")


class TestTheProcedureLibrary:
    def test_the_beat_s_own_question_finds_the_shift_swap_procedure(self):
        # The walkthrough's seventh tap. A library that cannot answer the one
        # question the Quick Task asks is a card that reads as an honest miss
        # from an HR system nobody can inspect.
        answer = format_procedure("How do I swap a shift with another associate?")

        assert SHIFT_SWAP.doc_id in answer
        assert NOT_IN_THE_LIBRARY not in answer

    def test_a_topic_the_library_does_not_cover_is_said_plainly(self):
        assert format_procedure("how do I rebuild the fuel pump") == NOT_IN_THE_LIBRARY

    def test_the_topics_are_listed_by_identifier_and_title(self):
        listed = format_topics()

        for procedure in PROCEDURES:
            assert procedure.doc_id in listed
            assert procedure.title in listed


class TestNoToolReturnsAnIndividualSRecord:
    #: The vocabulary of a **personal question** — an individual's balance,
    #: rate, hours or entitlement. ADR-017's boundary, checked against the
    #: authored text rather than trusted to the prompt, because a procedure
    #: that quotes a balance is a language model stating somebody's pay with
    #: the gate two layers away and looking at the request, not the answer.
    RECORD_VOCABULARY = (
        "balance",
        "accrued",
        "entitlement",
        "hourly",
        "wage",
        "salary",
        "paycheck",
        "pay stub",
        "pto",
        "how much",
        "how many days",
    )

    @pytest.mark.parametrize("term", RECORD_VOCABULARY)
    def test_the_library_states_nobody_s_record(self, term):
        library = format_topics().lower() + " ".join(
            format_procedure(procedure.doc_id).lower() for procedure in PROCEDURES
        )

        assert term not in library

    def test_no_tool_takes_an_individual_to_look_up(self, mock_mcp_server):
        # A parameter naming a person is an invitation to look one up. The
        # tools take a topic and nothing else, so there is no argument a model
        # could fill with an associate and no answer that could come back
        # about one.
        service = WorkforceService()
        service.register_tools(mock_mcp_server)

        for tool in mock_mcp_server.tools:
            parameters = inspect.signature(tool["func"]).parameters
            for name in parameters:
                assert name in ("topic",), (
                    f"{tool['func'].__name__} takes {name!r}, which is not a "
                    "procedure topic"
                )


class TestTheServiceIsOnItsOwnDomain:
    def test_it_serves_the_workforce_domain(self):
        assert WorkforceService().domain is Domain.WORKFORCE

    def test_the_container_registers_it(self):
        # A service the container never registers serves no domain endpoint,
        # and an agent pointed at ``/workforce/mcp`` gets a 404 that the
        # framework reports to nobody — the **Silent agent skip**'s shape, one
        # layer down.
        import mcp_server

        assert Domain.WORKFORCE in mcp_server.factory.get_all_services()

    def test_it_registers_the_two_tools_it_counts(self, mock_mcp_server):
        service = WorkforceService()
        service.register_tools(mock_mcp_server)

        assert len(mock_mcp_server.tools) == service.tool_count == 2

    @pytest.mark.asyncio
    async def test_the_procedure_tool_answers_from_the_library(self, mock_mcp_server):
        service = WorkforceService()
        tool = tool_named(service, mock_mcp_server, "get_workforce_procedure")

        assert SHIFT_SWAP.doc_id in await tool("swap a shift")

    @pytest.mark.asyncio
    async def test_the_listing_tool_answers_from_the_library(self, mock_mcp_server):
        service = WorkforceService()
        tool = tool_named(service, mock_mcp_server, "list_workforce_procedures")

        assert SHIFT_SWAP.title in await tool()


class TestTheAnswerSaysWhereItCameFrom:
    def test_every_procedure_declares_it_is_simulated(self):
        # The build's governing rule: a surface may say nothing, but it may not
        # say something that is not so. There is no HR system behind this, and
        # an answer that reads like one is the claim ADR-017 refused when it
        # refused the name `WorkdayAgent`.
        assert "simulated" in format_procedure(SHIFT_SWAP.doc_id).lower()

    def test_the_listing_declares_it_is_simulated(self):
        assert "simulated" in format_topics().lower()
