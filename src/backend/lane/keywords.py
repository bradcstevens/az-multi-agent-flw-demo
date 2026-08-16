"""The lane router's keyword fallback, as a pure function (issue #16, ADR-013).

Lane is declared as metadata on a Quick Task, so the presenter's scripted taps
never reach this module. Free-typed input has no declaration at all, and this
is what stands in for one. Nothing here performs I/O.

**The requirement runs one way only.** Missing a Fast lane request is
survivable — it falls open to the Deliberate lane and costs an approval step.
Claiming an escalation for the Fast lane is not: the approval step *is* the
associate confirming the ticket before it is raised (#22), so losing it would
raise a simulated ticket nobody confirmed. That asymmetry is why the Deliberate
vocabulary is matched **first** and wins outright, why it is the broader of the
two lists, and why the default when nothing matches is Deliberate.

The terms are chosen for what the vocabulary *is* — the language of asking for
something to be raised, approved or handed on, against the language of looking
a procedure up — rather than tuned until they swept the phrasings in the tests.
"""

from typing import Any, Tuple

from lane.lane import Lane

# Asking for something to be raised, approved or handed to someone else.
# Matched first, and a match wins outright.
DELIBERATE_LANE_TERMS: Tuple[str, ...] = (
    # Escalation
    "escalate",
    "escalation",
    "escalating",
    "hand this over",
    "hand it over",
    # Normalisation splits "can't" into "can t"; a shared store device is also
    # where the apostrophe simply does not get typed, so both are listed.
    "can t fix",
    "cant fix",
    "cannot fix",
    "can t get it",
    "cant get it",
    "unable to fix",
    "out of ideas",
    "tried everything",
    "come out",
    "send someone",
    "someone to come",
    "call out",
    "callout",
    "repair",
    "engineer",
    "technician",
    "maintenance",
    # Tickets and requests
    "ticket",
    "work order",
    "job number",
    "log this",
    "log it",
    "raise",
    "submit",
    "request a",
    "request for",
    "order a",
    "order more",
    "reorder",
    # Approval
    "approve",
    "approval",
    "sign off",
    "authorise",
    "authorize",
)

# Looking a procedure up, reporting a fault, or asking what is due this shift.
FAST_LANE_TERMS: Tuple[str, ...] = (
    # SOP lookup
    "how do i",
    "how do we",
    "how does",
    "how to",
    "what is the procedure",
    "procedure for",
    "the steps",
    "steps for",
    "steps to",
    "sop",
    "policy on",
    "where do i find",
    "show me the",
    # Troubleshooting turn
    "is down",
    "is broken",
    "not working",
    "stopped working",
    "won t start",
    "will not start",
    "keeps",
    "error code",
    "troubleshoot",
    "leaking",
    "jammed",
    # Task query
    "what tasks",
    "what task",
    "which tasks",
    "s due",
    "is due",
    "are due",
    "checklist",
    "this shift",
    "on shift",
    "tonight",
)


def _normalise(text: Any) -> str:
    """Lowercase, collapse punctuation to single spaces, pad with spaces.

    The same shape the guardrail's Keyword fast path uses: padding lets a term
    be matched as ``" term "``, a whole-word test that costs no regular
    expression per term and treats "can't fix" and "cant fix" alike.
    """
    if not isinstance(text, str):
        return " "
    lowered = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    return f" {' '.join(lowered.split())} "


def keyword_lane(description: Any) -> Lane:
    """Select a Lane from free-typed text.

    Pure and total: any input in, a Lane out, no I/O and no exceptions. Fails
    open to the Deliberate lane — a router failure never becomes a policy
    failure on stage.
    """
    haystack = _normalise(description)
    if any(f" {term} " in haystack for term in DELIBERATE_LANE_TERMS):
        return Lane.DELIBERATE
    if any(f" {term} " in haystack for term in FAST_LANE_TERMS):
        return Lane.FAST
    return Lane.DELIBERATE
