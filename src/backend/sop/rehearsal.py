"""Turn-scoped routing state for the closing-store demonstration beat.

The marker is armed by the presenter's exact question, stands for **every**
SOP tool call that turn makes, and is disarmed when the turn ends or when the
session's next request is something else.

It was one-shot until #54, spent by the first ``search_store_procedures`` call
of the turn. The Grounding panel is a claim about whichever SOP call answered
**last**, so a second call in the rehearsed turn retrieved against the raw
rephrasing and overwrote a correct retrieval with whatever that returned — the
centrepiece beat failing with no sign in the panel of which call it is showing.
Consuming the marker was never what kept the **honest miss** honest; disarming
it on any other request is, and that is unchanged.

What the marker cannot tell apart, stated rather than engineered around:
``sole_turn()`` resolves the session from the one user with a request in
flight, so a **direct** ``/api/v4/sop/ask`` call — a preflight probe, a
by-hand curl — is indistinguishable from the orchestrator's tool call and is
canonicalised too if it lands inside a rehearsed turn. One-shot narrowed that
to the first such call, not to none of them, and the turn-scoped bound is
*shorter* than the one-shot marker's for the case #54 is actually about: a
rehearsed turn that never reaches the SOP tool used to leave the marker
standing until the session's next request. No check probes ``/sop/ask`` with a
question the corpus cannot answer — ``check-deployed-surface.sh`` asks the
corpus's own wording and ``check-sop-agent.sh``'s out-of-corpus probe goes
through Direct Line — so nothing here is a live path today.
"""

import itertools
import time
from typing import Dict, Optional, Tuple

from troubleshooting.turn import sole_turn

_TTL_SECONDS = 900.0

# session_id -> (the turn that armed the marker, when it was armed). The token
# is what holds a turn's cleanup to its own marker: a cancelled turn unwinds
# asynchronously, and `/process_request` gives it one event-loop iteration
# before arming the successor's — one iteration, not a guarantee. Without the
# token, a cleanup that took longer would clear the marker of the turn that
# cancelled it: the presenter asking the rehearsed question twice and the beat
# working only the first time.
_sessions: Dict[str, Tuple[int, float]] = {}
_turn_tokens = itertools.count(1)


def _expire() -> None:
    now = time.monotonic()
    for session_id, (_token, noted_at) in list(_sessions.items()):
        if now - noted_at > _TTL_SECONDS:
            del _sessions[session_id]


def note_rehearsal(session_id: str) -> Optional[int]:
    """Arm the exact presenter question for its turn's SOP tool calls.

    Returns the token identifying this turn's marker, which the turn hands
    back to :func:`end_rehearsal_turn` when it finishes.
    """
    if not session_id:
        return None
    token = next(_turn_tokens)
    _sessions[session_id] = (token, time.monotonic())
    return token


def forget_rehearsal(session_id: str) -> None:
    """Disarm a session when its next request is not the rehearsal."""
    _sessions.pop(session_id, None)


def end_rehearsal_turn(session_id: str, token: Optional[int]) -> None:
    """Disarm at the end of the turn that armed the marker.

    Only if the marker is still that turn's. A turn ends by completing or by
    being cancelled, and a cancelled turn unwinds asynchronously — one turn
    disarming another's is how a presenter asking the rehearsed question twice
    loses the second one.
    """
    if token is None:
        return
    armed = _sessions.get(session_id)
    if armed is not None and armed[0] == token:
        del _sessions[session_id]


def rehearsal_stands_for_current_turn() -> bool:
    """Whether the sole request in flight is the rehearsal's own turn.

    Read, not consumed: see this module's docstring for what a spent marker
    costs the second SOP tool call of the same turn.
    """
    _expire()
    turn = sole_turn()
    if turn is None:
        return False
    _, session_id = turn
    return session_id in _sessions


def forget_rehearsals() -> None:
    """Drop all rehearsal state. Test seam."""
    _sessions.clear()
