# Copyright (c) Microsoft. All rights reserved.
"""The revision lineage a **Reviewable plan** carries.

Disagreeing with a plan sends it back; it does not destroy it (#108). The
lineage is what makes a revised plan legible: which revision the associate is
looking at, and what they asked to change to get it. Pure, no I/O — it is
computed here once and then written in two places, the **Plan record** that
persists it and the ``MPlan`` the surface reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True, slots=True)
class PlanRevision:
    """Which revision of a Reviewable plan this is, and what asked for it.

    ``number`` counts the plans the associate has been shown, so the first plan
    is revision 1 and the plan produced by the first send-back is revision 2.
    ``feedback`` holds what was said each time, oldest first, and is always one
    shorter than ``number``.
    """

    number: int = 1
    feedback: tuple[str, ...] = ()

    @property
    def latest_feedback(self) -> Optional[str]:
        """What the associate asked to change to get this revision."""
        return self.feedback[-1] if self.feedback else None

    def sent_back(self, feedback: str) -> "PlanRevision":
        """The lineage of the plan this send-back asks for.

        Raises:
            ValueError: if nothing was asked. A send-back with no feedback is
                not a verdict — it is the destroyed plan by another name, and
                the associate would get an identical plan back with no idea
                why.
        """
        said = (feedback or "").strip()
        if not said:
            raise ValueError("A plan sent back carries the associate's feedback")
        return PlanRevision(number=self.number + 1, feedback=self.feedback + (said,))

    @classmethod
    def restored(
        cls,
        revision: Optional[int],
        feedback: Optional[Iterable[str]],
    ) -> "PlanRevision":
        """Read a lineage back off a record that may predate this field."""
        return cls(
            number=revision or 1,
            feedback=tuple(feedback or ()),
        )
