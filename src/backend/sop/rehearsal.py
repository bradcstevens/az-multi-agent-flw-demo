"""One-shot routing state for the closing-store demonstration beat."""

import time
from typing import Dict

from troubleshooting.turn import sole_turn

_TTL_SECONDS = 900.0
_sessions: Dict[str, float] = {}


def _expire() -> None:
    now = time.monotonic()
    for session_id, noted_at in list(_sessions.items()):
        if now - noted_at > _TTL_SECONDS:
            del _sessions[session_id]


def note_rehearsal(session_id: str) -> None:
    """Arm the exact presenter question for its next SOP tool call."""
    if session_id:
        _sessions[session_id] = time.monotonic()


def forget_rehearsal(session_id: str) -> None:
    """Disarm a session when its next request is not the rehearsal."""
    _sessions.pop(session_id, None)


def take_rehearsal_for_current_turn() -> bool:
    """Consume the rehearsal marker for the sole request currently in flight."""
    _expire()
    turn = sole_turn()
    if turn is None:
        return False
    _, session_id = turn
    return _sessions.pop(session_id, None) is not None


def forget_rehearsals() -> None:
    """Drop all rehearsal state. Test seam."""
    _sessions.clear()
