"""Server-side session state (issue #20).

A mid-demo browser reload must not lose the conversation's state, so the state
lives in the memory container rather than in browser storage. Two things are
held here today and both are read by somebody who cannot re-derive them:

* the **Session identity** the Identity boundary gate reads (ADR-014) — the
  mocked sign-in beat writes a name into it, and until then it is anonymous,
  which is the refusing state;
* the **Lane taken**, as the lane router decided it (ADR-013) — a reloaded or
  bookmarked plan page cannot re-derive it, and re-deriving it in the browser
  would be a second lane router with its own opinion.

The record is an ordinary document in the schemaless memory container:
partitioned by session, discriminated by data type, reached through the generic
CRUD the container already exposes. No new database method, and no migration.
"""

import logging
from typing import Any, Mapping, Optional

from common.models.messages import SessionIdentityState, SessionState
from guardrail.identity import ANONYMOUS, SessionIdentity, resolve_session_identity

logger = logging.getLogger(__name__)

# Sentinel distinguishing "this field was not mentioned" from "this field was
# explicitly cleared". Signing out is a write, not the absence of one.
_UNSET = object()

IdentityValue = Optional[Mapping[str, Any]]


def session_state_id(session_id: str) -> str:
    """The document id of a session's state.

    Derived from the session rather than freshly generated, which is what makes
    a read a point read on the session's own partition and makes a second write
    replace the first instead of accumulating a log nobody reads.
    """
    return f"session_state:{session_id}"


def _as_identity_state(value: IdentityValue) -> SessionIdentityState:
    """Coerce an identity offered as plain data into the stored shape.

    Takes a mapping or nothing — deliberately not the API layer's request
    model, so the store does not depend on the identity of a class defined
    above it. Total on purpose: this is written from a request body, and a
    value that cannot be read is the *anonymous* identity — the refusing state
    — rather than an exception thrown at a caller who has no better answer.
    """
    if isinstance(value, Mapping):
        display_name = value.get("display_name")
        if isinstance(display_name, str) and display_name.strip():
            return SessionIdentityState(display_name=display_name.strip())
    return SessionIdentityState()


class SessionStateStore:
    """Reads and writes one session's state.

    Every read is **total** — a session nobody has written to reads back as the
    state the demo opens in, not as ``None`` — because every caller of a read
    would otherwise have to invent that default, and the one that matters is
    the gate, whose default must be the refusing one.
    """

    def __init__(self, memory_store, user_id: str = ""):
        self._memory_store = memory_store
        self._user_id = user_id

    def _opening_state(self, session_id: str) -> SessionState:
        """The state the demo opens in: nobody signed in, no lane taken yet."""
        return SessionState(
            id=session_state_id(session_id),
            session_id=session_id,
            user_id=self._user_id or None,
        )

    async def read(self, session_id: str) -> SessionState:
        """Read a session's state, defaulting to the state the demo opens in.

        A record belonging to somebody else reads back as that default rather
        than as its contents, so one user's session record can never unlock
        another user's Identity boundary gate.
        """
        stored = await self._memory_store.get_item_by_id(
            session_state_id(session_id), session_id, SessionState
        )
        if isinstance(stored, SessionState) and self._owns(stored):
            return stored
        return self._opening_state(session_id)

    def _owns(self, state: SessionState) -> bool:
        """Whether the caller owns a stored record.

        An unowned record — one written before the owner was recorded — is
        readable by anyone, which is the same reading the container's other
        ownership predicates take of a missing owner.
        """
        return not state.user_id or state.user_id == self._user_id

    async def write(
        self,
        session_id: str,
        *,
        identity: Any = _UNSET,
        lane: Any = _UNSET,
    ) -> SessionState:
        """Merge the given fields into a session's state and return the result.

        A merge rather than a replace because two surfaces write this record —
        the sign-in beat writes an identity, the request path writes the lane
        taken — and a replace would let whichever wrote last erase the other.
        """
        state = await self.read(session_id)
        state.user_id = self._user_id or state.user_id
        if identity is not _UNSET:
            state.identity = _as_identity_state(identity)
        if lane is not _UNSET:
            state.lane = lane if isinstance(lane, str) else None
        await self._memory_store.update_item(state)
        return state

    async def resolve_identity(self, session_id: str) -> SessionIdentity:
        """The Session identity the Identity boundary gate reads.

        Fails closed all the way down: an unreadable record, an unreachable
        container and a half-written identity all resolve to ``ANONYMOUS``,
        which is the refusing state. The gate is the one caller that must never
        be handed an exception instead of an answer.
        """
        try:
            state = await self.read(session_id)
        except Exception:
            logger.warning(
                "Could not read session state for session '%s' — "
                "resolving the anonymous identity, which refuses",
                session_id,
                exc_info=True,
            )
            return ANONYMOUS
        return resolve_session_identity(state.model_dump(mode="json"))
