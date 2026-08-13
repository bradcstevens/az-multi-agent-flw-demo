"""The Lane, and how a declared one is parsed (issue #16, ADR-013).

Lane is the domain term; **Plan review** is its one mechanical consequence —
the value the Magentic builder's approval gate is built with. Keeping the
mapping here means the endpoint never reasons about booleans, and the whole
two-lane design has exactly one place where "fast means no approval gate" is
written down.
"""

from enum import Enum
from typing import Any, Optional


class Lane(str, Enum):
    """Which of the two request paths a request takes.

    A ``str`` enum so the value goes onto the wire — the lane taken is
    surfaced in the UI as a feature, not hidden as an implementation detail.
    """

    FAST = "fast"
    DELIBERATE = "deliberate"

    @property
    def plan_review(self) -> bool:
        """Whether the orchestration builder keeps the approval gate.

        The Fast lane is the same orchestration path with the gate off, not a
        bypass — no single-agent invocation path exists (ADR-013).
        """
        return self is Lane.DELIBERATE


def parse_lane(declared: Any) -> Optional[Lane]:
    """Parse a declared lane, or return ``None`` if it is not one.

    Total: any input at all, a Lane or ``None`` out, never an exception. The
    declared value arrives as unvalidated metadata on a Quick Task definition,
    so garbage is an expected input rather than a programming error.

    ``None`` rather than a default Lane is deliberate: the fail-open decision
    belongs to the router, where the reason for it is written down, not hidden
    inside a parser.
    """
    if not isinstance(declared, str):
        return None
    try:
        return Lane(declared.strip().lower())
    except ValueError:
        return None
