"""The Workforce agent's HR procedure library, as authored text (issue #52).

Pure: no MCP, no network, no container. The library **is** the mocked HR
system, so it is data with a lookup over it, and
:mod:`services.workforce_service` is the thin adapter that serves it as two
tools. Splitting them is what lets the store pack's own suite ask, without a
running container, whether the walkthrough's seventh tap resolves to a
procedure that exists — the same question `[rehearsed_hit]` makes the SOP
corpus answer about the opening tap.

ADR-017 draws the boundary here rather than in a prompt: this text describes
what an associate *does*, and holds nobody's balance, rate, hours or
entitlement. Those stay the Identity boundary gate's business and are still
answered with no agent at all (``docs/mocked-unlock.md``).
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# What the answer says about itself, on every procedure and on the listing.
SIMULATED = (
    "This procedure library is simulated for this demonstration. It describes "
    "how a task is done; it holds nobody's personal employment record."
)

# The library covers scheduling procedures and says so when it does not cover
# something, in the **honest miss**'s own shape: a plausible answer that is not
# in the library is worse than no answer, because an associate acts on it.
NOT_IN_THE_LIBRARY = (
    "That is not in the workforce procedure library. Tell the associate "
    "plainly that this assistant does not cover it and that their shift lead "
    "or the store's HR contact can help. Do not describe the procedure from "
    "your own knowledge."
)


@dataclass(frozen=True)
class Procedure:
    """One authored HR process, and the words that reach it."""

    doc_id: str
    title: str
    steps: Tuple[str, ...]
    keywords: Tuple[str, ...]

    def rendered(self) -> str:
        numbered = "\n".join(
            f"{index}. {step}" for index, step in enumerate(self.steps, start=1)
        )
        return f"{self.doc_id} — {self.title}\n{numbered}\n\n{SIMULATED}"


SHIFT_SWAP = Procedure(
    doc_id="WF-401",
    title="Swapping a shift with another associate",
    steps=(
        "Open the scheduling app on the store device and find the shift you "
        "want covered.",
        "Choose Offer swap, and pick the associate you have already agreed it "
        "with. A swap nobody has agreed to is declined by default.",
        "The other associate accepts the offer on their own device. Until they "
        "do, the shift is still yours.",
        "The shift lead approves the swap. They check the store still has a "
        "keyholder and an age-restricted-sales trained associate on the floor.",
        "Both associates see the approved swap on the published rota. If it is "
        "not on the rota, the swap did not happen — do not rely on a verbal "
        "agreement.",
    ),
    keywords=(
        "swap",
        "swapping",
        "switch",
        "trade",
        "cover",
        "swap a shift",
        "shift swap",
    ),
)

AVAILABILITY_CHANGE = Procedure(
    doc_id="WF-402",
    title="Changing your availability for future weeks",
    steps=(
        "Open the scheduling app and choose Availability.",
        "Set the days and times you can work. Changes apply to rotas that have "
        "not been published yet.",
        "Submit the change for the shift lead to approve. A published rota is "
        "not changed by this — a shift already on it is swapped or covered "
        "instead.",
        "The shift lead approves or discusses it with you within one rota "
        "cycle.",
    ),
    keywords=(
        "availability",
        "available",
        "change my days",
        "which days i can work",
    ),
)

SHIFT_COVER = Procedure(
    doc_id="WF-403",
    title="Reporting that you cannot make a shift",
    steps=(
        "Call the store and speak to the shift lead. Do not send a message and "
        "assume it was read.",
        "Report it as early as you can. The store has to find cover, and the "
        "rota rules say a keyholder shift cannot be left open.",
        "Log the absence in the scheduling app so the rota shows the shift "
        "needs cover.",
        "The shift lead offers the shift to associates who are not already "
        "rostered, and the rota is republished.",
    ),
    keywords=(
        "cannot make",
        "can't make",
        "call in",
        "absence",
        "absent",
        "sick",
        "miss a shift",
        "no show",
    ),
)

OPEN_SHIFT = Procedure(
    doc_id="WF-404",
    title="Picking up an open shift",
    steps=(
        "Open the scheduling app and choose Open shifts. Only shifts the store "
        "still needs covered are listed.",
        "Claim the one you want. A claim that would put you over the store's "
        "rota rules is declined with the reason shown.",
        "The shift lead approves the claim, and it appears on the published "
        "rota.",
        "Check the rota before the day. A claim that was not approved is not a "
        "shift you are rostered for.",
    ),
    keywords=(
        "open shift",
        "extra shift",
        "pick up",
        "picking up",
        "claim a shift",
    ),
)

#: The whole library, in the order it is listed.
PROCEDURES: Tuple[Procedure, ...] = (
    SHIFT_SWAP,
    AVAILABILITY_CHANGE,
    SHIFT_COVER,
    OPEN_SHIFT,
)

_NON_WORD = re.compile(r"[^a-z0-9]+")


def _normalise(text: str) -> str:
    """Lowercase and pad, so a keyword matches as a whole phrase.

    The **Keyword fast path**'s own shape (``guardrail.keywords``), reused
    because it is the one this repository has already reasoned about.
    """
    return f" {_NON_WORD.sub(' ', (text or '').lower()).strip()} "


def find_procedure(topic: str) -> Optional[Procedure]:
    """The procedure a topic names, or ``None``.

    Pure and total: any string in, a Procedure or ``None`` out. The identifier
    is matched first so the listing's own ``WF-NNN`` always resolves, and the
    keywords after it so an associate's words do.
    """
    haystack = _normalise(topic)
    for procedure in PROCEDURES:
        if _normalise(procedure.doc_id).strip() in haystack:
            return procedure
    for procedure in PROCEDURES:
        if any(f" {keyword} " in haystack for keyword in procedure.keywords):
            return procedure
    return None


def format_procedure(topic: str) -> str:
    """Render one procedure, or say plainly that the library does not cover it."""
    procedure = find_procedure(topic)
    if procedure is None:
        return NOT_IN_THE_LIBRARY
    return procedure.rendered()


def format_topics() -> str:
    """Render what the library covers, by identifier and title."""
    listed: List[str] = [
        f"- {procedure.doc_id} — {procedure.title}" for procedure in PROCEDURES
    ]
    return "The workforce procedure library covers:\n" + "\n".join(listed) + (
        f"\n\n{SIMULATED}"
    )
