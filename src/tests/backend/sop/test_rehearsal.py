"""The marker that carries the rehearsed hit through the rephrasing (#54).

`/process_request` arms it on the presenter's exact question and the SOP tool
calls of that turn retrieve against the corpus's wording whatever the model
rewrote it into. The rules that matter are about **lifetime**: it has to stand
for the whole turn, and it must not outlive it.
"""

import pytest
from types import SimpleNamespace

from sop import rehearsal
from troubleshooting.turn import forget_turns, note_turn


@pytest.fixture(autouse=True)
def clean_state():
    rehearsal.forget_rehearsals()
    forget_turns()
    yield
    rehearsal.forget_rehearsals()
    forget_turns()


def in_flight(session_id="session-1", user_id="user-1"):
    """Put one request in flight, the way `/process_request` does."""
    note_turn(user_id, session_id)


class TestTheMarkerStandsForTheWholeTurn:
    def test_a_second_reading_in_one_turn_still_sees_the_marker(self):
        """The defect this module was changed for.

        Reading it was a `pop` until #54, so the second
        `search_store_procedures` call of a turn retrieved against the raw
        rephrasing — and because the Grounding panel is written by whichever
        SOP call answered last, a correct retrieval was overwritten by it.
        """
        in_flight()
        rehearsal.note_rehearsal("session-1")

        assert rehearsal.rehearsal_stands_for_current_turn() is True
        assert rehearsal.rehearsal_stands_for_current_turn() is True

    def test_an_unarmed_session_never_sees_one(self):
        in_flight()

        assert rehearsal.rehearsal_stands_for_current_turn() is False

    def test_nothing_in_flight_reads_no_marker(self):
        """Two users in flight and `sole_turn` refuses to guess (issue #21).

        A tool call that cannot be attributed to a session must not borrow
        another session's rehearsal.
        """
        rehearsal.note_rehearsal("session-1")
        note_turn("user-1", "session-1")
        note_turn("user-2", "session-2")

        assert rehearsal.rehearsal_stands_for_current_turn() is False


class TestTheMarkerDoesNotOutliveItsTurn:
    def test_the_turn_that_armed_it_disarms_it_when_it_ends(self):
        in_flight()
        token = rehearsal.note_rehearsal("session-1")

        rehearsal.end_rehearsal_turn("session-1", token)

        assert rehearsal.rehearsal_stands_for_current_turn() is False

    def test_a_cancelled_turn_does_not_disarm_its_successors_marker(self):
        """The ordering that makes the token load-bearing.

        `/process_request` arms the new turn's marker *before* it cancels the
        prior one, and the cancelled turn's cleanup runs after that. Without
        the token, a presenter asking the rehearsed question twice would have
        the first turn's cleanup disarm the second turn's marker — the beat
        working the first time and not the second.
        """
        in_flight()
        first = rehearsal.note_rehearsal("session-1")
        second = rehearsal.note_rehearsal("session-1")

        rehearsal.end_rehearsal_turn("session-1", first)

        assert second != first
        assert rehearsal.rehearsal_stands_for_current_turn() is True

    def test_a_turn_that_armed_nothing_disarms_nothing(self):
        """A turn that armed no marker carries no token and must be inert.

        Its disarm already happened on the way in, when `/process_request`
        saw a description that was not the rehearsal. Clearing again when it
        ends would reach past its own turn: a non-rehearsal turn can still be
        unwinding after the rehearsed request that followed it has armed.
        """
        in_flight()
        rehearsal.note_rehearsal("session-1")

        rehearsal.end_rehearsal_turn("session-1", None)

        assert rehearsal.rehearsal_stands_for_current_turn() is True

    def test_any_other_request_in_the_session_disarms_it_outright(self):
        """What keeps the honest miss honest, unchanged by the turn scoping.

        "Restart the car wash" seconds later in the same session must not be
        canonicalised into the closing procedure.
        """
        in_flight()
        rehearsal.note_rehearsal("session-1")

        rehearsal.forget_rehearsal("session-1")

        assert rehearsal.rehearsal_stands_for_current_turn() is False


class TestArming:
    def test_a_session_less_request_arms_nothing_and_says_so(self):
        assert rehearsal.note_rehearsal("") is None
        assert rehearsal._sessions == {}

    def test_a_marker_older_than_the_ttl_is_gone(self, monkeypatch):
        """The bound that stops a stale marker outliving the demonstration.

        The turn-scoped disarm is the ordinary path; this is the one for a
        turn that never reached its `finally` — a cancelled process, a crash —
        and it is why the marker cannot silently arm tomorrow's session.

        Only the marker's clock is wound forward. Winding the shared one would
        expire the turn note too, and `sole_turn` returning nothing is a
        different reason for the same answer.
        """
        clock = SimpleNamespace(monotonic=lambda: clock.now)
        clock.now = 0.0
        monkeypatch.setattr(rehearsal, "time", clock)
        in_flight()
        rehearsal.note_rehearsal("session-1")
        assert rehearsal.rehearsal_stands_for_current_turn() is True

        clock.now = rehearsal._TTL_SECONDS + 1.0

        assert rehearsal.rehearsal_stands_for_current_turn() is False
