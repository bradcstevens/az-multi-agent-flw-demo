"""The Presenter alert (issue #23).

R8's beat: a proactive shift-task message that arrives without anyone asking a
question, to show the assistant is not only reactive.

Two things about it are decisions rather than details.

**It is fired, never scheduled.** There is no wall-clock timer here or on the
route that calls this — the beat has to land when the presenter is talking
about it, and a timer that fires thirty seconds early on stage interrupts the
sentence that was going to explain it.

**It answers nothing.** The alert is not a reply and must not be rendered as
one (#24), so it carries a title of its own rather than an agent name: an alert
mistaken for an answer is worse than no alert.

**The words are the server's.** The route that fires it is hidden rather than
authenticated, and it pushes onto the screen the audience is watching. A caller
names a rehearsed line; it never composes one.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from transparency.payloads import PresenterAlert

# The rehearsed roster. The words are the **server's**, never the caller's: the
# route that fires these is hidden rather than authenticated, and it pushes to
# the screen the audience is watching, so a caller may choose a line and may
# not compose one.
#
# Seven of them (#19), and each is a task an associate would recognise from a
# real shift rather than a demo string. Each also **names the document its
# steps are in**, which is the difference between a proactive message and a
# dead end: the alert lands, the associate asks for the steps, and the question
# has somewhere to go. Those identifiers are asserted against the SOP corpus,
# so an alert cannot come to point at a procedure that was never written.
REHEARSED_ALERTS: Dict[str, PresenterAlert] = {
    "shift-task": PresenterAlert(
        title="Shift task due",
        content=(
            "Heads up — the coffee station deep clean is due before the 15:00 "
            "handover at Store 223. That is the bean hopper, the grinder purge "
            "and the drip trays. The steps are in SOP-104; ask me for them if "
            "you have not done it before."
        ),
        timestamp="",
    ),
    "delivery": PresenterAlert(
        title="Delivery arriving",
        content=(
            "The chilled delivery is due at the Store 223 back dock in ten "
            "minutes. Clear the receiving bay and have the handheld ready. "
            "Receiving and put-away are in SOP-109."
        ),
        timestamp="",
    ),
    "temperature-log": PresenterAlert(
        title="Temperature check due",
        content=(
            "The hot food case temperature check is due now at Store 223. "
            "Probe the thickest item on the middle shelf and record it on the "
            "daily log. SOP-107 has the holding rules and what to do if it "
            "reads low."
        ),
        timestamp="",
    ),
    "safe-drop": PresenterAlert(
        title="Safe drop due",
        content=(
            "The till at Store 223 is over its drop limit. Take a safe drop "
            "before the next rush and record the drop number. SOP-106 has the "
            "counting and witness rules."
        ),
        timestamp="",
    ),
    "restroom-check": PresenterAlert(
        title="Restroom check due",
        content=(
            "The two-hourly restroom inspection is due at Store 223 and the "
            "sheet has not been signed since 11:00. SOP-103 has the check "
            "list and what to do if something needs closing off."
        ),
        timestamp="",
    ),
    "age-check": PresenterAlert(
        title="Age-restricted sales reminder",
        content=(
            "A reminder for the late shift at Store 223: every age-restricted "
            "sale is challenged, whatever the queue looks like. SOP-108 has "
            "the accepted forms of identification and the refusal wording."
        ),
        timestamp="",
    ),
    "handover": PresenterAlert(
        title="Handover in fifteen minutes",
        content=(
            "Handover at Store 223 is in fifteen minutes. The task board, the "
            "temperature log and any equipment left out of service all go on "
            "the handover sheet. SOP-110 has the order to work through."
        ),
        timestamp="",
    ),
}

# What an empty chord means.
DEFAULT_ALERT = "shift-task"
REHEARSED_ALERT = REHEARSED_ALERTS[DEFAULT_ALERT]


def presenter_alert(name: Optional[str] = None) -> PresenterAlert:
    """The rehearsed alert to push, stamped with when it was fired.

    An unrecognised name is the default rather than an error: a mistyped chord
    on stage should still produce the beat.

    A timestamp is not a timer. It records that the presenter pressed the
    chord; it does not decide when they do.
    """
    alert = REHEARSED_ALERTS.get((name or "").strip(), REHEARSED_ALERT)
    return PresenterAlert(
        title=alert.title,
        content=alert.content,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
