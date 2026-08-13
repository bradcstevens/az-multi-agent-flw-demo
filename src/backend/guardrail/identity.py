"""Session identity, as the Identity boundary gate reads it (issue #14).

ADR-014 settles that the mocked unlock is a **parameter of the gate, not a
second gate**: the same classifier refuses before sign-in and admits after it.
This module is that parameter — a value object plus a pure resolver over the
session-state record.

Nothing here performs I/O. Server-side session state is #20's work and the
mocked sign-in that writes a name into it is #27's; both write through
`resolve_session_identity`, and until they land the router resolves against no
record at all and gets `ANONYMOUS`.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional

# The key the identity record lives under inside a session-state document.
IDENTITY_KEY = "identity"
DISPLAY_NAME_KEY = "display_name"


@dataclass(frozen=True)
class SessionIdentity:
    """Who, if anyone, is signed in on the shared store device."""

    display_name: Optional[str] = None

    @property
    def is_anonymous(self) -> bool:
        """No name means no identity, and no identity means the gate refuses."""
        return not (self.display_name or "").strip()


# The state the demo opens in and returns to: a shared device, nobody signed in.
ANONYMOUS = SessionIdentity()


def resolve_session_identity(
    session_state: Optional[Mapping[str, Any]],
) -> SessionIdentity:
    """Read a session identity out of a session-state record.

    Total and fail-closed: absent, empty, half-written and malformed records
    all resolve to `ANONYMOUS`, which is the *refusing* state. Degrading
    towards a refusal is the direction ADR-014 requires — the neighbouring
    team-scope evaluation degrades the other way, and this gate is explicitly
    not modelled on it.
    """
    if not session_state:
        return ANONYMOUS

    record = session_state.get(IDENTITY_KEY)
    if not isinstance(record, Mapping):
        return ANONYMOUS

    display_name = record.get(DISPLAY_NAME_KEY)
    if not isinstance(display_name, str) or not display_name.strip():
        return ANONYMOUS

    return SessionIdentity(display_name=display_name.strip())
