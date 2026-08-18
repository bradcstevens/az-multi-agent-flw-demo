"""The **settle-write** — one terminal status, written once (#157, ADR-043).

*The server settles the turn it ended.* Every writer of a **Settled status**
goes through one operation: write this terminal status onto the session's latest
**Plan record**, unless that Plan already reached a Settled status. This module
is the half of that with no Cosmos in it — what may be written, what happened,
and what a caller is allowed to call success.

Two rules live here, and both are the sort a reviewer has to be able to check by
reading:

* **Only a Settled status settles a turn.** The set is `chat.deletion`'s, not a
  second copy: `in_progress`, `approved`, `created` — and the orchestration's
  wire word `error` — are not terminal statuses, and asking to settle one is a
  programming error rather than a store outcome (ADR-043 decision 4: the wire's
  vocabulary is not the record's, and nothing under this decision coins a fourth
  member).
* **A Settled status is never overwritten.** A later write of a different
  terminal status leaves the first alone, so the first true answer stands
  (ADR-043 decision 6). The refusal is an outcome the caller can read, not an
  error: a late echo, a delete-door cancel and #120's end-of-turn primitive all
  converge on the same document, and finding it already settled is the ordinary
  case rather than a fault.

`no_such_chat`, `superseded`, `lost_race` and `refused` are told apart
deliberately, because only the last two are a write this system believed it had
made and had not.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from chat.deletion import SETTLED_STATUSES


class SettleOutcome(str, Enum):
    """What a settle-write did, in the five ways it can differ."""

    #: The terminal status was written onto the latest Plan record.
    settled = "settled"
    #: The Plan had already reached a Settled status, and keeps it.
    already_settled = "already_settled"
    #: The session's latest Plan is **not** the one this turn ran. A newer turn
    #: started, so settling the latest Plan would stamp a terminal status onto a
    #: live answer — the one direction of error ADR-043 exists to prevent.
    superseded = "superseded"
    #: No Plan of this user's in that session. Nothing to settle.
    no_such_chat = "no_such_chat"
    #: The Plan moved between the read and the conditional write. Somebody
    #: else's write landed first, and by the rule above theirs is the one that
    #: stands.
    lost_race = "lost_race"
    #: The store refused the write for any other reason. **Not success** — the
    #: record does not say what this process believes it says.
    refused = "refused"


@dataclass(frozen=True)
class TurnSettled:
    """The result of asking for a turn to be settled.

    ``status`` is what the **record** carries now — the status just written, or
    the one it already had — so a caller that lost the race can log which answer
    stood rather than only that its own did not.
    """

    outcome: SettleOutcome
    status: Optional[str] = None

    @property
    def persisted(self) -> bool:
        """Whether the record now carries a Settled status.

        True for a write that landed **and** for one refused because the Plan
        had already settled, because the fact this operation exists to make
        durable is durable either way. False for everything else, which is what
        a caller reports as a failure rather than as a turn that ended.
        """
        return self.outcome in (
            SettleOutcome.settled,
            SettleOutcome.already_settled,
        )


def settled_status(status: Any) -> str:
    """The wire value a settle-write may carry, or a `ValueError`.

    Total over the `PlanStatus` members and over bare strings alike — a caller
    holding the enum and one holding the value it serialises to are asking the
    same thing. Anything that is not one of the three **Settled status** members
    is refused *before* the store is touched: a settle-write that could write
    `in_progress` would be a way of un-ending a turn, and one that could write
    the orchestration's `error` would coin a fourth terminal status by accident.
    """
    reported = getattr(status, "value", status)

    if not isinstance(reported, str) or reported.strip() not in SETTLED_STATUSES:
        raise ValueError(
            f"{status!r} is not a settled status; a turn settles at one of "
            f"{sorted(SETTLED_STATUSES)}"
        )

    return reported.strip()
