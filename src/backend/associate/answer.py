"""The Personal answer as it reaches the browser (issue #27).

Beside ``escalation/payloads.py`` and for the recorded reason: the package that
decides what a claim may say owns the shape of the claim.

This is the **Mocked unlock**'s output — the previously refused question,
answered. It is the mirror image of ``guardrail/refusal.py``: the same keyword
match decides both, one surface renders both, and the only thing that differs
between them is whether anybody is signed in. So the two shapes are deliberately
siblings, each naming its own ``kind``, and the browser switches on that name
rather than on the shape of what it received.

Two rules bind what may be said here.

**The record is shown whole.** The answer does not pick out the field the
question asked about. Deciding *which* number a phrasing wants would be a third
classifier behind the two the gate already has, and a third classifier can
report the wrong number — which, for a question about somebody's pay, is the
worst thing this system could say. A record shown whole is a true answer to
"how much PTO do I have?", to "what am I owed?" and to a phrasing nobody
rehearsed.

**A half-written fact is dropped, not blanked.** A label with no value renders
as *nothing owed*, and that is a claim about an associate's entitlement that
nobody authored. The answer may say less than the record holds; it may not say
something the record does not.

There is no ``simulated`` flag, for the reason ``TicketRaised`` has none: every
answer this system produces comes from authored content, there is no other kind
and no code path that could produce one, so the framing is a property of the
answer rather than a field one caller could leave off.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from associate.records import AssociateRecord
from provenance import ASSOCIATE_RECORD_PROVENANCE

# The discriminator the browser switches on, beside ``POLICY_BLOCK_KIND``. The
# two are the same beat's two outcomes and must never be mistaken for each
# other: one says *we cannot tell who you are*, the other says *here is your
# record*.
PERSONAL_ANSWER_KIND = "personal_answer"

@dataclass(slots=True)
class AnswerFact:
    """One labelled row of the answer, in the record's own words."""

    label: str
    value: str


@dataclass(slots=True)
class PersonalAnswer:
    """A signed-in associate's record, as the request path returns it."""

    display_name: str
    role: str = ""
    facts: List[AnswerFact] = field(default_factory=list)
    provenance: str = ASSOCIATE_RECORD_PROVENANCE

    @classmethod
    def from_record(cls, record: AssociateRecord) -> "PersonalAnswer":
        """Build the answer for one associate's record.

        Total: a record with no facts, or with only half-written ones, still
        answers — it says who is signed in and lists nothing, which is true.
        Raising here would turn a thin record into a failed request, and a
        failed request at this seam looks on stage exactly like the refusal the
        sign-in was supposed to lift.
        """
        return cls(
            display_name=record.display_name,
            role=record.role,
            facts=[
                AnswerFact(label=fact.label, value=fact.value)
                for fact in record.facts
                if fact.label.strip() and fact.value.strip()
            ],
        )


def personal_answer_detail(record: AssociateRecord) -> Dict[str, Any]:
    """The answer as the payload the request path returns.

    A fresh dictionary each call, so a caller that annotates one response does
    not quietly edit the one behind every other — the same rule
    ``policy_block_detail`` follows for the refusal.
    """
    payload = asdict(PersonalAnswer.from_record(record))
    payload["kind"] = PERSONAL_ANSWER_KIND
    return payload
