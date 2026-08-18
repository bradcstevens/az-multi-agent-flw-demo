"""The Simulated ticket, drafted as a tool (issue #22).

This container holds no Cosmos — no connection configuration, no credentials
and no dependency — so the draft goes to the backend over HTTP through the same
``BackendClient`` seam the attempted-steps tools use, against the backend URL
already configured for it.

**The tools draft or read; neither submits.** The plan approval *is* the ticket
confirmation. Submission happens deterministically at the plan-approval seam in
the backend's orchestration manager, so no turn the model improvises can raise a
ticket the associate did not approve.

The tool has no ``steps_attempted`` parameter either, for the same class of
reason. A model given somewhere to put the attempted steps will put its
paraphrase of them there, and a paraphrase of what an associate tried is not
what they tried — nor can anybody downstream tell the difference. The backend
fills that field from the troubleshooting record and discards anything sent.
"""

import logging
import os
from typing import Any, Dict, Optional

from core.factory import Domain, MCPToolBase
from services.backend_client import BackendClient

logger = logging.getLogger(__name__)

TICKET_PATH = "/api/v4/escalation/ticket"

ESCALATION_TIMEOUT_SECONDS = float(os.environ.get("ESCALATION_TIMEOUT", "30"))

# A draft that did not land must say so. An agent told the ticket is waiting
# for approval presents it to the associate, the associate approves it, and the
# approval seam finds nothing to submit — a confirmation that confirmed
# nothing, with nothing on screen looking wrong.
DRAFT_FAILED = (
    "The ticket could NOT be drafted, so there is nothing for the associate to "
    "approve. Tell them the ticket was not raised and do not quote a ticket "
    "number. Do not claim it is waiting for approval."
)
TICKET_STATUS_UNAVAILABLE = (
    "There is no simulated ticket in this conversation to check."
)

# What the agent must not say yet. The number is issued by the confirmation,
# and the confirmation is the approval step the associate has not reached.
NOT_RAISED_YET = (
    "This ticket has NOT been raised. It is a draft. Show it to the associate "
    "field by field, invite them to correct anything, and let them approve it "
    "— approving the plan is what raises it, and there is no step after that. "
    "Do not quote a ticket number: one is issued when they approve. Every "
    "ticket here is simulated; say so."
)


def format_draft(payload: Optional[Dict[str, Any]]) -> str:
    """Render a drafted ticket as the agent reads it back.

    A response carrying no ticket is a **failure**, not a blank ticket: an
    empty ticket handed back here is one the associate would be asked to
    approve with nothing in it.
    """
    payload = payload or {}
    if not payload.get("drafted"):
        return DRAFT_FAILED
    rendered = (payload.get("rendered") or "").strip()
    if not rendered:
        return DRAFT_FAILED
    return f"{rendered}\n\n{NOT_RAISED_YET}"


def format_status(payload: Optional[Dict[str, Any]]) -> str:
    """Return this conversation's submitted ticket record, or say none exists."""
    payload = payload or {}
    fields = payload.get("fields")
    if not (payload or {}).get("drafted") or not isinstance(fields, dict):
        return TICKET_STATUS_UNAVAILABLE
    status = str(fields.get("status") or "").strip()
    rendered = payload.get("rendered")
    if status != "submitted" or not isinstance(rendered, str) or not rendered.strip():
        return TICKET_STATUS_UNAVAILABLE
    return rendered.strip()


class EscalationService(MCPToolBase):
    """The Simulated ticket's draft and conversation-scoped status."""

    def __init__(self, backend: Optional[BackendClient] = None):
        super().__init__(Domain.ESCALATION)
        self.backend = backend or BackendClient(timeout=ESCALATION_TIMEOUT_SECONDS)

    def register_tools(self, mcp) -> None:
        @mcp.tool(tags=[self.domain.value])
        async def draft_service_ticket(
            symptom: str = "",
            asset: str = "",
            asset_tag: str = "",
            category: str = "",
            priority: str = "",
            first_noticed: str = "",
            runbook: str = "",
            impact: str = "",
            product_affected: str = "",
            requested_response: str = "",
            site_contact: str = "",
            raised_by: str = "",
            notes: str = "",
        ) -> str:
            """Draft the simulated service ticket, or correct the draft.

            Call this when a fault cannot be fixed on the shift. It returns the
            whole ticket for the associate to read and correct, and it is the
            only ticket tool there is: the associate approving the plan is what
            raises the ticket, and there is no step after that one.

            You do NOT pass what the associate already tried. Those steps are
            filled in from this session's troubleshooting record, in the
            associate's own words, and anything you send for them is discarded
            — carrying them without re-asking is the whole reason the ticket is
            raised in this conversation.

            To correct a field the associate disagrees with, call this again
            with just that field. Everything else keeps what it said.

            Args:
                symptom:            What the associate saw, in their own words.
                asset:              The equipment in plain words.
                asset_tag:          From the store profile's equipment register.
                category:           equipment, food safety, forecourt, payment
                                    or facilities.
                priority:           1 to 4, from the store profile's service
                                    windows.
                first_noticed:      When they first saw it.
                runbook:            The runbook followed, e.g. RB-201.
                impact:             What the store cannot do while it is open.
                product_affected:   Product moved or discarded, and roughly how
                                    much.
                requested_response: The service window for the priority.
                site_contact:       The shift lead, or the duty manager.
                raised_by:          The associate, if signed in.
                notes:              Anything else they want to add.

            Returns:
                The whole ticket, or a statement that nothing was drafted.
            """
            fields = {
                "symptom": symptom,
                "asset": asset,
                "asset_tag": asset_tag,
                "category": category,
                "priority": priority,
                "first_noticed": first_noticed,
                "runbook": runbook,
                "impact": impact,
                "product_affected": product_affected,
                "requested_response": requested_response,
                "site_contact": site_contact,
                "raised_by": raised_by,
                "notes": notes,
            }
            try:
                payload = await self.backend.post_json(
                    TICKET_PATH,
                    {name: value for name, value in fields.items() if value},
                    timeout=ESCALATION_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                logger.error("draft_service_ticket: backend unreachable: %s", exc)
                return DRAFT_FAILED
            return format_draft(payload)

        @mcp.tool(tags=[self.domain.value])
        async def get_ticket_status() -> str:
            """Read this conversation's Simulated ticket status.

            Call this only when the associate asks what is happening with the
            ticket the conversation already raised. It accepts no ticket number
            and reads only the session of the turn in flight.
            """
            try:
                payload = await self.backend.get_json(
                    TICKET_PATH,
                    timeout=ESCALATION_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                logger.error("get_ticket_status: backend unreachable: %s", exc)
                return TICKET_STATUS_UNAVAILABLE
            return format_status(payload)

    @property
    def tool_count(self) -> int:
        return 2
