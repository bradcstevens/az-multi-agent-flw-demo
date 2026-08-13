"""The lane router (issue #16, ADR-013).

One function, three inputs' worth of precedence:

1. A **declared** Lane on the Quick Task wins. The presenter's scripted taps
   are routed by metadata, never by the wording of their prompt.
2. **No declaration** — free-typed input — falls back to the keyword fallback
   (`lane.keywords`).
3. An **unparseable** declaration goes straight to the Deliberate lane without
   consulting the keywords: corrupt metadata is a router failure, and guessing
   from a request whose metadata cannot be trusted is how a router failure
   becomes a policy failure on stage.

Deliberately a separate component from the Identity boundary gate: the gate
fails **closed**, this fails **open to the Deliberate lane**, and merging them
would force one failure mode onto both (ADR-013 §4).
"""

import logging
from typing import Any, Optional

from lane.keywords import keyword_lane
from lane.lane import Lane, parse_lane

logger = logging.getLogger(__name__)


def select_lane(declared: Any, description: Optional[str]) -> Lane:
    """Select the Lane a request takes.

    Pure and total: no I/O, and any input at all yields a Lane rather than an
    exception — the caller is a request handler, and the safe answer is always
    available.
    """
    if declared is None:
        return keyword_lane(description)

    lane = parse_lane(declared)
    if lane is None:
        logger.warning(
            "Unparseable declared lane %r — failing open to the Deliberate lane",
            declared,
        )
        return Lane.DELIBERATE
    return lane
