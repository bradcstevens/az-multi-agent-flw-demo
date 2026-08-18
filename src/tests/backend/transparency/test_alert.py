"""The Presenter alert (issue #23).

R8's beat is fired, never scheduled — the acceptance criteria forbid a
wall-clock timer outright, and the reason is stagecraft: a timer lands the
proactive message when the timer says so, which on stage is an interruption of
the sentence that was going to explain it.
"""

import transparency.alert as alert_module
from transparency.alert import (REHEARSED_ALERT, REHEARSED_ALERTS,
                                presenter_alert)
from provenance import PRESENTER_ALERT_PROVENANCE


class TestPresenterAlert:
    def test_the_chord_carrying_no_words_fires_the_rehearsed_line(self):
        """The keyboard chord (#24) POSTs an empty body. The rehearsed
        shift-task alert is what an empty body means."""
        alert = presenter_alert()

        assert alert.title == REHEARSED_ALERT.title
        assert alert.content == REHEARSED_ALERT.content

    def test_the_presenter_may_choose_another_rehearsed_line(self):
        assert presenter_alert("delivery").title == REHEARSED_ALERTS["delivery"].title

    def test_an_unrecognised_name_is_the_default_not_an_error(self):
        """A mistyped chord on stage should still produce the beat."""
        assert presenter_alert("no-such-alert").title == REHEARSED_ALERT.title
        assert presenter_alert("  ").title == REHEARSED_ALERT.title

    def test_the_caller_cannot_compose_an_alert(self):
        """The route that calls this is hidden rather than authenticated and
        pushes onto the screen the audience is watching, so the words are the
        server's. There is no parameter here that accepts prose."""
        import inspect

        parameters = inspect.signature(presenter_alert).parameters
        assert list(parameters) == ["name"]

    def test_the_alert_is_stamped_with_when_it_was_fired(self):
        """A timestamp records that the chord was pressed. It does not decide
        when — that is the distinction between a stamp and a timer."""
        assert presenter_alert().timestamp

    def test_the_alert_names_the_shift_task_system_that_did_not_push_it(self):
        assert presenter_alert().provenance_line == PRESENTER_ALERT_PROVENANCE

    def test_every_rehearsed_alert_reads_as_a_shift_task_not_as_an_answer(self):
        """They answer nothing, so they must not look like replies. Each names
        the store and a task an associate would recognise from a real shift."""
        for alert in REHEARSED_ALERTS.values():
            assert "Store 223" in alert.content
            assert "?" not in alert.title

    def test_nothing_on_this_path_schedules_anything(self):
        """Pinned as a property of the module rather than as a promise in a
        review: no timer, no sleep, no loop callback."""
        import inspect

        source = inspect.getsource(alert_module)
        for forbidden in ("sleep", "Timer", "call_later", "create_task"):
            assert forbidden not in source


class TestShiftTaskAlertRoster:
    """The six-to-eight shift-task alerts (issue #19).

    R8 asks for a roster rather than one line, because a presenter who fires
    the same alert twice in a walkthrough has shown a string, not a behaviour.
    """

    def test_the_roster_holds_six_to_eight_shift_task_alerts(self):
        assert 6 <= len(REHEARSED_ALERTS) <= 8

    def test_every_alert_is_a_distinct_task(self):
        titles = [alert.title for alert in REHEARSED_ALERTS.values()]
        contents = [alert.content for alert in REHEARSED_ALERTS.values()]
        assert len(set(titles)) == len(titles)
        assert len(set(contents)) == len(contents)

    def test_every_alert_names_a_procedure_that_exists(self):
        """An alert that lands and leads nowhere is worse than no alert.

        Each one names the document its steps are in, and the identifier is
        checked against the **SOP corpus itself** rather than against a list
        here — the corpus is authored by a different tool in a different
        directory, so an alert pointing at a procedure that was renamed or
        never written would otherwise be found on stage.
        """
        import re
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[4]
        corpus = repo_root / "content" / "sop" / "src"
        available = {
            "SOP-" + path.name.split("-", 1)[0] for path in corpus.glob("*.md")
        }
        assert available, "the SOP corpus source directory is empty"

        for name, alert in REHEARSED_ALERTS.items():
            cited = re.findall(r"SOP-\d{3}", alert.content)
            assert cited, f"{name} names no procedure"
            for doc_id in cited:
                assert doc_id in available, f"{name} names {doc_id}, which is not authored"

    def test_the_default_alert_leads_into_the_procedure_hop(self):
        """The empty chord fires this one, and it is the beat the walkthrough
        is built around: the alert arrives unasked, and asking for the steps
        sends the next question across to Copilot Studio."""
        assert "SOP-104" in REHEARSED_ALERT.content
