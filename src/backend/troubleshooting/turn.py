"""Which session a user's in-flight request belongs to (issue #21).

The MCP container calls back to the backend with no session of its own — it has
no Cosmos connection, no credentials and no request context — and the model has
no session identifier anywhere in its instructions to hand one over. So the
backend resolves the session itself, from a note the request path leaves as it
goes by.

Deliberately **not** a UUID copied by the model the way ``ask_user`` asks for
one. That is the reasoning ``connection_config.sole_user()`` already records
(#23), and it is sharper here: a mis-copied identifier there costs a
clarification prompt, while one here writes one associate's attempted steps onto
another associate's fault, or reads back steps nobody on this shift tried and
skips a real runbook branch.

Process-local, like the workflow cache, and legitimate for the same recorded
reason: the application runs as a single replica. ``sole_turn`` refuses to guess
between two users rather than picking one — the third of the three constraints
issue #21 names as acceptable for a single-presenter demo and unacceptable for
production, stated out loud rather than engineered around.
"""

import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# How long a note stands for a request that is still in flight. It has to
# outlive a turn, and the longest a turn can be is the 300-second clarification
# wait plus the agent's own time — hence generous. But it is bounded, and that
# is the point: without an expiry a *second* user ever reaching this process
# would leave two notes standing forever and ``sole_turn`` refusing for the
# rest of the process's life, so one stray request would silently disable the
# memory for the demo that follows it.
TURN_TTL_SECONDS = 900.0

# user_id -> (session of that user's most recent request, when it was noted).
_turns: Dict[str, Tuple[str, float]] = {}


def _live() -> Dict[str, str]:
    """The notes still standing for a request that could be in flight."""
    now = time.monotonic()
    for user_id, (_session, noted_at) in list(_turns.items()):
        if now - noted_at > TURN_TTL_SECONDS:
            del _turns[user_id]
    return {user_id: session for user_id, (session, _at) in _turns.items()}


def note_turn(user_id: str, session_id: str) -> None:
    """Record that ``user_id``'s request in flight belongs to ``session_id``.

    Called from the request path once the caller and the session are both
    known. Half a note is no note: a note missing either half would resolve to
    a session that is not the associate's, and an attempted step written onto
    the wrong fault is worse than one that was never written.
    """
    if not user_id or not session_id:
        return
    _turns[user_id] = (session_id, time.monotonic())


def turn_for(user_id: str) -> Optional[str]:
    """The session of ``user_id``'s most recent request, if there was one."""
    if not user_id:
        return None
    return _live().get(user_id)


def sole_turn() -> Optional[Tuple[str, str]]:
    """The one user with a request in flight, when there is exactly one.

    The resolution for a call that originates outside a request the associate
    made — the MCP container's troubleshooting tools, which have no user of
    their own. Refuses to guess with two users in flight, the same rule
    ``sole_user()`` applies to the transparency pushes.
    """
    live = _live()
    if len(live) == 1:
        return next(iter(live.items()))
    if live:
        logger.info(
            "[TROUBLESHOOTING] %d users have a request in flight — refusing to "
            "guess which session a tool call belongs to",
            len(live),
        )
    return None


def forget_turns() -> None:
    """Drop every noted turn. Test seam; nothing in the request path calls it."""
    _turns.clear()
