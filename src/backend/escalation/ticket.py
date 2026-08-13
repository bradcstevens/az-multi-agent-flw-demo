"""The shape of a Simulated ticket, and the rules TKT-001 already states.

Pure — no container, no model, no clock of its own. Every rule here is written
down in ``TKT-001 Service Incident Ticket Template.md`` and is repeated here
because a rule a model is *told* is a rule that holds most of the time, and this
one artefact leaves the room.

The asymmetry that shapes the module: an under-filled ticket costs the service
desk a phone call, while an over-filled one dispatches an engineer against a
symptom nobody reported. So every unanswered field degrades to
``"not reported"`` — never blank, never guessed — and no field the template does
not name survives at all.
"""

import hashlib
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

# The site this assistant runs for. Not a caller's to set: a ticket naming
# another site is a van sent to the wrong forecourt, and the model has no way
# of knowing it got it wrong.
SITE = "Brightpath Convenience Store 223"
SITE_NUMBER = "223"

# TKT-001's answer for a field nothing answered. It is not left blank — a blank
# row on a service ticket reads as *nothing to report*, which is a claim nobody
# made — it is not guessed, and it is not turned into another question.
NOT_REPORTED = "not reported"

# The ticket number carries the simulation with it, because the number travels
# further than the card it was rendered on: an associate can read it down a
# telephone long after the demonstration ended.
TICKET_ID_PREFIX = "SIM-223-"

SIMULATED_NOTICE = (
    "This ticket is simulated. No service desk receives it, no engineer is "
    "dispatched, and this ticket number means nothing outside this "
    "demonstration."
)


class TicketStatus:
    """TKT-001's two states: draft until confirmed, then submitted.

    Deliberately only two. A third — "cancelled", "pending" — would be a state
    the approval step does not produce, and a status nobody can reach is a
    status the UI can render.
    """

    draft = "draft"
    submitted = "submitted"


# The template's fields, in the order the template states them. The order is
# load-bearing rather than cosmetic: this is the order the associate reads the
# ticket back in before approving it, and a field that moves between the draft
# and the submitted card is a field they will not check twice.
FIELD_ORDER = (
    "ticket_id",
    "opened_at",
    "status",
    "priority",
    "site",
    "site_number",
    "site_contact",
    "asset",
    "asset_tag",
    "category",
    "symptom",
    "first_noticed",
    "steps_attempted",
    "runbook",
    "impact",
    "product_affected",
    "requested_response",
    "raised_by",
    "notes",
)

# Fields filled from the record and never from the caller. This is "nothing
# re-typed" as a property of the code rather than a line in a system message:
# a model that supplies these has its value discarded, silently, because the
# only correct value is the one the associate actually said.
CARRIED_FIELDS = ("steps_attempted",)

# Fields the ticket knows better than any caller does.
FIXED_FIELDS = {
    "site": SITE,
    "site_number": SITE_NUMBER,
}

# Fields that only the confirmation can fill, and so are never a caller's.
CONFIRMATION_FIELDS = ("ticket_id", "opened_at", "status")

# TKT-001 allows exactly these. Anything else is a service window that was
# never promised, read by somebody who will plan around it.
PRIORITIES = ("1", "2", "3", "4")


def ticket_id_for(session_id: str) -> str:
    """The ticket number one conversation's ticket gets.

    Derived from the session rather than drawn from a counter. A counter is
    shared state that a restart resets, and a reissued number is two different
    faults wearing one identity; derived, the same conversation's ticket keeps
    its number however often it is read, and no two conversations collide
    without colliding on their session first.
    """
    digest = hashlib.sha256((session_id or "").encode("utf-8")).hexdigest()
    return f"{TICKET_ID_PREFIX}{int(digest[:8], 16) % 10000:04d}"


def _text(value: Any) -> str:
    """A supplied field as text, or nothing at all.

    Anything that is not a string is *nothing*, not its ``repr``: a dictionary
    rendered into a ticket row is a field that looks filled and says nothing,
    which is the one outcome ``not reported`` exists to prevent.
    """
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return ""
    return value.strip()


def _priority(value: Any) -> str:
    """A priority TKT-001 has a service window for, or nothing."""
    text = _text(value)
    return text if text in PRIORITIES else NOT_REPORTED


def format_attempted(attempted: Iterable[str]) -> str:
    """The attempted steps as the ticket's one field, in the associate's words.

    Joined rather than rewritten. Each step is already one thing the associate
    said they did; re-phrasing them into runbook language here would produce a
    ticket that reads more professional and is no longer their account.
    """
    steps = [step.strip() for step in attempted or [] if str(step).strip()]
    if not steps:
        return NOT_REPORTED
    return "; ".join(steps)


def draft_fields(
    supplied: Optional[Mapping[str, Any]],
    *,
    attempted: Sequence[str],
    equipment: Optional[str] = None,
    previous: Optional[Mapping[str, Any]] = None,
) -> Dict[str, str]:
    """Build a draft ticket's fields from what the agent filled, what the
    draft being corrected already said, and what the record already knows.

    ``previous`` is the correction path. An associate corrects **one field**,
    said once; an agent re-drafting the whole ticket to change the priority
    would drop every field it did not happen to repeat, and the associate, who
    has already read the ticket through, would not read it again to notice.

    Total. Every field in ``FIELD_ORDER`` comes back, populated or
    ``not reported``; no field outside it comes back at all.
    """
    supplied = supplied if isinstance(supplied, Mapping) else {}
    previous = previous if isinstance(previous, Mapping) else {}

    fields: Dict[str, str] = {}
    for name in FIELD_ORDER:
        value = _text(supplied.get(name)) or _text(previous.get(name))
        fields[name] = value or NOT_REPORTED

    fields.update(FIXED_FIELDS)
    fields["priority"] = _priority(
        supplied.get("priority") or previous.get("priority")
    )
    fields["steps_attempted"] = format_attempted(attempted)

    # What broke, from the record, when the agent did not name something more
    # specific. The turn that reports a step is rarely the turn that named the
    # equipment, and the record carries it precisely so the ticket need not ask
    # a second time.
    if fields["asset"] == NOT_REPORTED and _text(equipment):
        fields["asset"] = _text(equipment)

    # A draft is not a ticket yet: no number, no opening time. A number printed
    # on a draft is one the associate could read down a telephone for a ticket
    # that was never raised.
    fields["ticket_id"] = NOT_REPORTED
    fields["opened_at"] = NOT_REPORTED
    fields["status"] = TicketStatus.draft
    return fields


def submitted_fields(
    fields: Mapping[str, str], *, session_id: str, opened_at: str
) -> Dict[str, str]:
    """The same ticket, confirmed.

    Confirmation may change **only** the three fields it is the confirmation
    of — the number it issues, the time it happened and the status. Everything
    the associate read before approving is carried through untouched, which is
    what "the associate sees exactly what will be submitted" means once the
    approval is the submission and there is no second screen.
    """
    confirmed = dict(fields or {})
    confirmed["ticket_id"] = ticket_id_for(session_id)
    confirmed["opened_at"] = opened_at or NOT_REPORTED
    confirmed["status"] = TicketStatus.submitted
    return confirmed


def render_ticket(fields: Mapping[str, str]) -> str:
    """The ticket as the associate reads it back, field by field.

    Every field, always, in the template's order — including the ones that say
    ``not reported``. A renderer that hid the empty rows would show a shorter,
    tidier ticket and hide exactly the fields the associate is best placed to
    correct.
    """
    fields = fields or {}
    lines = [f"{name}: {fields.get(name) or NOT_REPORTED}" for name in FIELD_ORDER]
    return "\n".join(lines) + f"\n\n{SIMULATED_NOTICE}"
