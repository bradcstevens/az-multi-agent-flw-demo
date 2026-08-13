"""Which session a user's in-flight request belongs to (issue #21).

The MCP container calls back to the backend with no session of its own, and the
model has no session identifier in its context to pass one. So the backend
resolves the session itself, from a note the request path leaves as it goes by —
deliberately **not** a UUID copied by the model the way ``ask_user`` asks for
one, which is the same reasoning ``connection_config.sole_user()`` records
(#23): a mis-copied identifier here writes one associate's attempted steps onto
another associate's fault.

Process-local, like the workflow cache, and for the same reason: the application
runs as a single replica. ``sole_turn`` refuses to guess between two users
rather than picking one — the third of the three constraints #21 names, stated
out loud rather than engineered around.
"""

import os
import sys

_backend_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
)
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

import pytest  # noqa: E402

from troubleshooting.turn import (forget_turns, note_turn,  # noqa: E402
                                  sole_turn, turn_for)


@pytest.fixture(autouse=True)
def clean_turns():
    forget_turns()
    yield
    forget_turns()


class TestNoteTurn:
    def test_the_session_a_users_request_belongs_to_is_recoverable(self):
        note_turn("u-1", "s-1")

        assert turn_for("u-1") == "s-1"

    def test_a_later_request_replaces_the_earlier_one(self):
        """One associate, one device, one fault at a time. The turn in flight
        is the only one anything asks about."""
        note_turn("u-1", "s-1")
        note_turn("u-1", "s-2")

        assert turn_for("u-1") == "s-2"

    def test_a_user_who_has_made_no_request_has_no_turn(self):
        assert turn_for("u-1") is None

    def test_a_note_missing_either_half_is_not_recorded(self):
        """Half a note resolves to a session that is not the associate's, and
        writing an attempted step onto the wrong fault is worse than losing it."""
        note_turn("", "s-1")
        note_turn("u-1", "")

        assert sole_turn() is None
        assert turn_for("u-1") is None


class TestSoleTurn:
    def test_one_user_with_a_turn_in_flight_is_the_turn(self):
        note_turn("u-1", "s-1")

        assert sole_turn() == ("u-1", "s-1")

    def test_nobody_in_flight_is_no_turn_rather_than_a_guess(self):
        assert sole_turn() is None

    def test_two_users_in_flight_refuses_to_pick_one(self):
        """The same rule ``sole_user()`` applies: exactly one or nothing, never
        a choice between two. A wrong choice here is one associate's memory
        written onto another's."""
        note_turn("u-1", "s-1")
        note_turn("u-2", "s-2")

        assert sole_turn() is None


class TestANoteExpires:
    """Without an expiry a *second* user ever reaching this process would leave
    two notes standing forever and ``sole_turn`` refusing for the rest of the
    process's life — one stray request silently disabling the memory for the
    demo that follows it."""

    def test_a_note_older_than_any_turn_no_longer_stands(self, monkeypatch):
        import troubleshooting.turn as turn_module

        clock = [0.0]
        monkeypatch.setattr(turn_module.time, "monotonic", lambda: clock[0])

        note_turn("u-1", "s-1")
        clock[0] = turn_module.TURN_TTL_SECONDS + 1

        assert turn_for("u-1") is None
        assert sole_turn() is None

    def test_a_stale_note_stops_blocking_the_user_who_is_actually_here(
        self, monkeypatch
    ):
        import troubleshooting.turn as turn_module

        clock = [0.0]
        monkeypatch.setattr(turn_module.time, "monotonic", lambda: clock[0])

        note_turn("u-1", "s-1")
        clock[0] = turn_module.TURN_TTL_SECONDS + 1
        note_turn("u-2", "s-2")

        assert sole_turn() == ("u-2", "s-2")

    def test_the_expiry_outlives_the_clarification_wait(self):
        """A turn can last as long as the associate takes to answer, and the
        clarification path waits 300 seconds for that. A note that expired
        first would lose the answer it was left for."""
        import troubleshooting.turn as turn_module

        assert turn_module.TURN_TTL_SECONDS > 300.0
