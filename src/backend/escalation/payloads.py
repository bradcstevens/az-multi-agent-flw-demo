"""The Simulated ticket as it reaches the browser (issue #22).

Beside ``transparency/payloads.py`` and for the recorded reason: the package
that decides what a signal may claim owns the shape of the claim.
``models/messages.py`` keeps the ``WebsocketMessageType`` member, because the
transport is that file's business; the shape is this one's.

The payload carries the fields as an **ordered list of rows** rather than a map.
TKT-001's field order is the order the associate read the ticket back in before
approving it, and a card that re-ordered the rows between the reading and the
record would be showing them a different document. A list makes that order a
claim the payload makes rather than an accident of how two languages happen to
iterate a dictionary.

There is no ``simulated`` flag. Every ticket this system raises is simulated —
there is no other kind and no code path that could produce one — so the badge is
a property of the card, not of the payload. A flag would be one omission away
from an unbadged ticket.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping

from escalation.ticket import FIELD_ORDER, NOT_REPORTED


@dataclass(slots=True)
class TicketField:
    """One row of the ticket, in the template's own field name."""
    name: str
    value: str


@dataclass(slots=True)
class TicketRaised:
    """A ticket that has been confirmed and persisted (R4).

    Only ever built from a ticket the container took. The approval seam does
    not push this until ``TicketStore.submit`` has returned a record, so a card
    on screen is evidence of a stored ticket rather than of an intention.
    """
    ticket_id: str
    status: str
    fields: List[TicketField] = field(default_factory=list)

    @classmethod
    def from_fields(cls, fields: Mapping[str, str]) -> "TicketRaised":
        fields = fields or {}
        return cls(
            ticket_id=fields.get("ticket_id") or NOT_REPORTED,
            status=fields.get("status") or NOT_REPORTED,
            fields=[
                TicketField(name=name, value=fields.get(name) or NOT_REPORTED)
                for name in FIELD_ORDER
            ],
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
