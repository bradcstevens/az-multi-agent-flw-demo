"""The Identity boundary gate's keyword fast path, as a pure function.

ADR-014 makes the classifier hybrid: this list catches the obvious cases with
no embedding round trip at all, and the similarity tier
(`guardrail.similarity`) catches the paraphrase the presenter
improvises live. Nothing here performs I/O.

The terms are **HR and payroll vocabulary chosen for what it is**, not tuned
until it swept the Guardrail corpus. A list fitted to the corpus would stop the
corpus being evidence, which is the failure mode ADR-015 rejected for the
anchors. What *is* asserted at 10/10 is the other direction: no store-level
control may trip this path, because a false positive refuses a legitimate store
question and ADR-014 calls that worse on stage than a miss.

That is also why nearly every term is a noun phrase that only occurs in an
individual-employment question. The three that lean on a first-person
possessive — "my shift", "my hours", "my schedule" — are there precisely
because their pronoun-free forms are store-scope: "the night shift" is on a
cleaning checklist, and one of the negative controls says exactly that.
"""

import re
from typing import Tuple

# Personal, individual-employment vocabulary. Matched on word boundaries after
# normalisation, so "sick day" does not match "sick days" — both are listed
# where both are natural.
PERSONAL_SCOPE_TERMS: Tuple[str, ...] = (
    # Time off
    "pto",
    "paid time off",
    "vacation balance",
    "vacation day",
    "vacation days",
    "sick day",
    "sick days",
    "sick leave",
    "holiday request",
    "time off request",
    "leave balance",
    # Pay
    "paycheck",
    "pay check",
    "payslip",
    "pay slip",
    "pay stub",
    "payroll",
    "hourly wage",
    "wage",
    "wages",
    "salary",
    "take home",
    "take home pay",
    "direct deposit",
    "w 2",
    "overtime",
    "timecard",
    "time card",
    "timesheet",
    "time sheet",
    # Benefits
    "dental plan",
    "health benefits",
    "health insurance",
    "open enrollment",
    # Record and identity
    "employee id",
    "employee number",
    "badge number",
    "personnel file",
    "performance review",
    # First-person possessives whose pronoun-free forms are store-scope
    "my shift",
    "my shifts",
    "my schedule",
    "my hours",
    "my rota",
    "my pay",
    "my rate",
    "my raise",
    "a raise",
)

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalise(text: str) -> str:
    """Lowercase, collapse punctuation to single spaces, pad with spaces.

    Padding lets a term be matched as `" term "` — a whole-word test that costs
    no regular expression per term and treats "take-home", "take home" and
    "W-2" as the same shape the terms are written in.
    """
    return f" {_NON_WORD.sub(' ', (text or '').lower()).strip()} "


def matches_personal_keyword(text: str) -> bool:
    """Whether a request is obviously a personal, individual-identity one.

    Pure and total: any string in, a bool out, no I/O and no exceptions. The
    gate calls this before spending an embedding round trip, so an obvious
    personal question is refused at zero cost.
    """
    haystack = normalise(text)
    return any(f" {term} " in haystack for term in PERSONAL_SCOPE_TERMS)
