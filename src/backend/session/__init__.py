"""Server-side session state (issue #20).

Held in the memory container rather than in browser storage, so a mid-demo
reload does not lose the conversation's state.
"""

from session.store import SessionStateStore, session_state_id

__all__ = ["SessionStateStore", "session_state_id"]
