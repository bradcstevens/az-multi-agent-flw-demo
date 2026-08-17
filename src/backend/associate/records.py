"""What a signed-in associate's record holds (issue #27).

The **Mocked unlock** is the post-sign-in state in which the Identity boundary
gate admits the previously refused question and answers it **from mocked
data**. This module is that data.

It is authored demo content, and it is the demo's most sensitive content: every
other invented thing here is about a store, and this is about a person's pay
and time off. So three rules bind it.

* **It is labelled.** Everything shown from here carries the **Simulated
  label**, unconditionally — there is no unlabelled path, because a flag that
  can be omitted is a fabricated pay record that looks real.
* **It is looked up by whole name.** A loose match would answer one associate's
  question out of another associate's record, which is the identity form of the
  claim the gate exists to refuse. A first name matches because a display name
  may be a full one; a *substring* of a name does not.
* **No record is a true answer.** A name nobody authored a record for resolves
  to nothing, and the request path falls through to the ordinary agents rather
  than inventing a balance. Degrading towards *we hold nothing about you* is
  the same direction the gate degrades in.

Nothing here performs I/O and nothing here is a real HR system. No identity
provider produced this name and no payroll system produced these numbers.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple

# The store the demo's associates work at, matching the rest of the authored
# content (`content/sop/corpus.toml`, the store content pack).
STORE_NUMBER = "223"


@dataclass(frozen=True)
class AssociateFact:
    """One labelled line of an associate's record."""

    label: str
    value: str


@dataclass(frozen=True)
class AssociateRecord:
    """One associate's mocked personal record.

    Facts default to none so the type does not require the demo's own content:
    a record is a name and whatever is known about it, and *nothing known* is a
    state it must be able to be in.
    """

    display_name: str
    role: str = ""
    facts: Tuple[AssociateFact, ...] = field(default_factory=tuple)


# The one associate the mocked sign-in signs in as. The boundary probe Quick
# Task says "My name is Clara", so signing in as anybody else makes the beat a
# non sequitur — the audience is watching one question be refused and then
# answered, and the name has to be the same one both times.
DEMO_ASSOCIATE = AssociateRecord(
    display_name="Clara Workman",
    role=f"Store associate, Store {STORE_NUMBER}",
    facts=(
        AssociateFact("PTO balance", "34.5 hours"),
        AssociateFact("PTO accrued this year", "61.0 hours"),
        AssociateFact("PTO taken this year", "26.5 hours"),
        AssociateFact("Hours scheduled this week", "32"),
        AssociateFact("Next scheduled shift", "Thursday, 06:00 - 14:00"),
        AssociateFact("Benefits enrolment", "Open until 30 November"),
    ),
)

# Every associate the mocked sign-in knows about. One today, and a tuple rather
# than a single value so a second one costs no shape change.
ASSOCIATE_RECORDS: Tuple[AssociateRecord, ...] = (DEMO_ASSOCIATE,)


def _comparable(name: str) -> str:
    """A name reduced to what two spellings of it have in common."""
    return " ".join(name.lower().split())


def lookup_associate(display_name: object) -> Optional[AssociateRecord]:
    """The record for a display name, or nothing.

    Total: anything that is not a usable name — absent, empty, whitespace, not
    a string at all — is a name nobody has a record for, which is exactly the
    answer *no record* already means. There is no failure mode here that should
    reach a caller as an exception, because the caller's next move is the same
    either way: fall through to the ordinary request path.

    Matching is on the **whole** display name or the **whole** first name.
    Deliberately not on a substring: "Clar" is not Clara, and a record shown to
    the wrong associate is the claim the Identity boundary gate exists to
    refuse, made by the code that was supposed to be the reward for passing it.
    """
    if not isinstance(display_name, str):
        return None

    wanted = _comparable(display_name)
    if not wanted:
        return None

    for record in ASSOCIATE_RECORDS:
        full = _comparable(record.display_name)
        if wanted == full:
            return record
        first, _, _ = full.partition(" ")
        if first and wanted == first:
            return record

    return None
