"""The Simulated ticket, read and written through the memory container.

An ordinary document in the schemaless memory container, exactly like the
troubleshooting record beside it: partitioned by session, discriminated by data
type, reached through the generic CRUD. No new database method, no migration.

The one place it deliberately parts company with its sibling is **totality**.
``TroubleshootingStore.read`` is total — a session nobody wrote to reads back an
empty record — because its caller is about to offer a runbook and the safe
default is to offer all of it. This store's caller is the plan-approval seam,
which runs on **every** approved plan on the Deliberate lane, and most of those
are not tickets. So "no draft" is ``None`` here and stays ``None`` all the way
out: a total read would raise a blank service ticket every time anybody approved
anything.

Writes are honest rather than total for the same reason. A write that did not
land returns nothing, and the layers above turn that into "no ticket was
raised" — because a card on the associate's screen for a ticket the container
never took is precisely the lie this package exists to prevent.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from common.models.messages import ServiceTicket
from escalation.ticket import (
    NOT_REPORTED,
    TicketStatus,
    draft_fields,
    render_ticket,
    submitted_fields,
)

logger = logging.getLogger(__name__)

__all__ = [
    "NOT_REPORTED",
    "ServiceTicket",
    "TicketStatus",
    "TicketStore",
    "render_ticket",
    "ticket_record_id",
]


def ticket_record_id(session_id: str) -> str:
    """The document id of a conversation's ticket.

    One conversation raises one ticket. Derived from the session rather than
    freshly generated, which makes a read a point read on the session's own
    partition and makes a re-draft **correct** the draft it replaces — the
    associate's correction landing on the ticket they corrected, instead of
    beside it.
    """
    return f"ticket:{session_id}"


class TicketStore:
    """Reads, drafts and submits one conversation's Simulated ticket."""

    def __init__(self, memory_store, user_id: str = ""):
        self._memory_store = memory_store
        self._user_id = user_id

    def _owns(self, ticket: ServiceTicket) -> bool:
        """Whether the caller owns a stored ticket.

        An unowned ticket — one written before the owner was recorded — is
        readable by anyone, the same reading the container's other ownership
        predicates take of a missing owner.
        """
        return not ticket.user_id or ticket.user_id == self._user_id

    async def read(self, session_id: str) -> Optional[ServiceTicket]:
        """This conversation's ticket, or nothing.

        Nothing is also what an unreadable container produces. Not an empty
        ticket: see the module docstring — the caller is the approval seam.
        """
        try:
            stored = await self._memory_store.get_item_by_id(
                ticket_record_id(session_id), session_id, ServiceTicket
            )
        except Exception:
            logger.warning(
                "Could not read the ticket for session '%s' — treating it as "
                "no ticket rather than raising an empty one",
                session_id,
                exc_info=True,
            )
            return None
        if isinstance(stored, ServiceTicket) and self._owns(stored):
            return stored
        return None

    async def draft(
        self,
        session_id: str,
        supplied: Optional[Mapping[str, Any]],
        *,
        attempted: Sequence[str],
        equipment: Optional[str] = None,
    ) -> Optional[ServiceTicket]:
        """Draft — or re-draft — this conversation's ticket.

        ``attempted`` is the troubleshooting record's list and is the *only*
        source of ``steps_attempted``; ``draft_fields`` discards a supplied one.
        That is "nothing re-typed" enforced rather than instructed.

        Returns nothing when the draft could not be persisted, so an agent is
        never told a ticket is waiting for approval that the approval seam will
        not find — and nothing when the ticket has already been raised, because
        editing it then would rewrite a record the associate was shown and told
        was submitted, with nothing on screen looking wrong.
        """
        existing = await self.read(session_id)
        if existing is not None and existing.fields.get("status") == (
            TicketStatus.submitted
        ):
            logger.info(
                "Ticket for session '%s' is already raised — not re-drafting it",
                session_id,
            )
            return None

        ticket = ServiceTicket(
            id=ticket_record_id(session_id),
            session_id=session_id,
            user_id=self._user_id or None,
            fields=draft_fields(
                supplied,
                attempted=attempted,
                equipment=equipment,
                previous=existing.fields if existing else None,
            ),
        )
        try:
            await self._memory_store.update_item(ticket)
        except Exception:
            logger.warning(
                "Could not persist the ticket draft for session '%s' — the "
                "agent is told nothing was drafted",
                session_id,
                exc_info=True,
            )
            return None
        return ticket

    async def submit(
        self, session_id: str, *, opened_at: Optional[str] = None
    ) -> Optional[ServiceTicket]:
        """Confirm this conversation's draft, if there is one.

        Called from the plan-approval seam and nowhere else: the approval step
        **is** the confirmation, and a second caller would be the second
        confirmation step TKT-001 says there is not.

        Idempotent. A turn can carry more than one plan review, and a second
        submission that reissued the number would hand the associate two
        numbers for one fault.
        """
        ticket = await self.read(session_id)
        if ticket is None:
            return None
        if ticket.fields.get("status") == TicketStatus.submitted:
            return ticket

        ticket.fields = submitted_fields(
            ticket.fields,
            session_id=session_id,
            opened_at=opened_at or datetime.now(timezone.utc).isoformat(),
        )
        try:
            await self._memory_store.update_item(ticket)
        except Exception:
            logger.warning(
                "Could not persist the submitted ticket for session '%s' — no "
                "ticket was raised and nothing claims one was",
                session_id,
                exc_info=True,
            )
            return None
        return ticket
