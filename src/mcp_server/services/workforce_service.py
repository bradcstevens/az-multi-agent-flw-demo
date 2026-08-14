"""The Workforce agent's HR procedure library, as a tool (issue #52, ADR-017).

The fourth specialist answers an **HR process question** — how an employment
task is performed — and never a **personal question**, which is an individual's
own record. That boundary is drawn here, in the vocabulary, rather than in a
prompt:

* every tool takes a **topic** and nothing else, so there is no argument a model
  could fill with an associate and no answer that could come back about one;
* the library describes what an associate *does*, and holds nobody's balance,
  rate, hours or entitlement — the numbers ADR-014 and the **Mocked unlock**
  keep a language model away from.

Unlike the SOP tool beside it, nothing here calls the backend and nothing here
is real. There is no HR system behind this deployment, the surface may not claim
one, and so every answer says out loud that it is simulated. That is the same
rule ADR-017 applied when it refused the name ``WorkdayAgent``: the association
is the presenter's to make out loud, not software's to claim on screen.
"""

import logging

from core.factory import Domain, MCPToolBase
from services.workforce_library import (  # noqa: F401  (re-exported)
    NOT_IN_THE_LIBRARY,
    PROCEDURES,
    SHIFT_SWAP,
    SIMULATED,
    Procedure,
    find_procedure,
    format_procedure,
    format_topics,
)

logger = logging.getLogger(__name__)


class WorkforceService(MCPToolBase):
    """The HR procedure library, on its own domain."""

    def __init__(self):
        super().__init__(Domain.WORKFORCE)

    def register_tools(self, mcp) -> None:
        @mcp.tool(tags=[self.domain.value])
        async def list_workforce_procedures() -> str:
            """What employment procedures this assistant can explain.

            Call this when you are not sure the library covers what the
            associate asked, so you can say what it does cover instead of
            guessing at an answer.

            The library explains **how a task is done**. It holds no personal
            employment record, so it cannot answer a question about one
            associate's own time off, pay, hours or benefits — and neither can
            you. Say so plainly and stop.

            Returns:
                Each procedure, by identifier and title.
            """
            return format_topics()

        @mcp.tool(tags=[self.domain.value])
        async def get_workforce_procedure(topic: str) -> str:
            """The steps for one employment procedure, from the library.

            Call this for anything about how an employment task is performed —
            swapping a shift, changing availability, reporting that a shift
            cannot be worked, picking up an open one. Answer only from what it
            returns, and quote the ``WF-NNN`` it cites so the associate can
            find the procedure.

            Never answer a procedure question from your own knowledge and never
            fill a gap in what this returned. If it says the library does not
            cover the topic, tell the associate that and suggest their shift
            lead.

            Args:
                topic: What the associate wants to do, in their own words, or
                    the ``WF-NNN`` identifier of a procedure already listed.

            Returns:
                The procedure and the identifier it came from, or a statement
                that the library does not cover it.
            """
            return format_procedure(topic)

    @property
    def tool_count(self) -> int:
        return 2
