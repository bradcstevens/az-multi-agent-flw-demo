"""Session identity as the Identity boundary gate reads it (issue #14).

ADR-014: the mocked unlock is a *parameter* of this gate, not a second gate.
So identity is a value the gate is handed, resolved by a pure function over
whatever the session-state record holds. It defaults to anonymous, which is the
state the whole demo opens in — a shared store device with nobody signed in.

Server-side session state itself is #20's work and the sign-in that populates
it is #27's; this is the seam both of them write through.
"""

from guardrail.identity import ANONYMOUS, SessionIdentity, resolve_session_identity


class TestResolveSessionIdentity:
    def test_no_session_state_is_anonymous(self):
        """The default the demo opens in, before #20 stores anything at all."""
        assert resolve_session_identity(None) is ANONYMOUS

    def test_session_state_without_an_identity_is_anonymous(self):
        assert resolve_session_identity({"other": "value"}) is ANONYMOUS

    def test_a_named_identity_is_carried_through(self):
        identity = resolve_session_identity({"identity": {"display_name": "Tanya Reyes"}})

        assert identity.display_name == "Tanya Reyes"
        assert identity.is_anonymous is False

    def test_a_blank_display_name_is_still_anonymous(self):
        """Fail closed on a half-written record: no name means no identity."""
        assert resolve_session_identity({"identity": {"display_name": "  "}}) is ANONYMOUS

    def test_a_malformed_identity_record_is_anonymous(self):
        """An unreadable record must not read as signed in.

        Anonymous is the refusing state, so degrading to it is the fail-closed
        direction — the opposite of the team-scope evaluation ADR-014 declines
        to be modelled on.
        """
        assert resolve_session_identity({"identity": "Tanya"}) is ANONYMOUS


class TestSessionIdentity:
    def test_anonymous_has_no_display_name(self):
        assert ANONYMOUS.is_anonymous is True
        assert ANONYMOUS.display_name is None

    def test_a_named_identity_is_not_anonymous(self):
        assert SessionIdentity(display_name="Tanya Reyes").is_anonymous is False
