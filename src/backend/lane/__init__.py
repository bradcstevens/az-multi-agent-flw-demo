"""The lane router (issue #16, ADR-013).

Deliberately a separate component from the Identity boundary gate
(``guardrail/``): they have opposite failure modes — the gate fails closed, the
router fails open to the Deliberate lane — and merging them would force one
failure mode onto both.
"""

from lane.lane import Lane, parse_lane
from lane.router import select_lane

__all__ = ["Lane", "parse_lane", "select_lane"]
