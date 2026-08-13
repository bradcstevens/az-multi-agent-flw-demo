"""Reading attempted steps out of what an associate actually typed (issue #21).

Pure and no I/O, like ``lane.keywords`` and the guardrail's keyword fast path,
and for the same reason: the requirement *never walk an associate through the
same failed step twice* is only mechanical if "the same step" is something code
can decide. A prompt that asks a model to remember is not a record.

The hard requirement runs **one way only**. ``already_attempted`` may miss —
the associate says so again and the record grows, which costs one wasted line
of dialogue — but it may never claim a step was attempted that was not, because
that step is then silently skipped and the equipment stays broken.
"""

import re
from typing import Iterable, List, Optional, Sequence

# How many distinct attempted steps make a fault one the shift is not going to
# fix. Three is one round of clarification plus one branch of a runbook; below
# that an offer to raise a ticket reads as the assistant giving up, which is the
# opposite of the beat R-escalation exists to show.
ESCALATION_AFTER = 3

# List markers an associate's answer arrives with.
_BULLET = re.compile(r"^\s*(?:[-*\u2022\u00b7]|\(?\d+[.)])\s*")

# The lead-in that says "this is a thing I tried" rather than naming the thing.
# Stripped so the recorded step is the step, not the report of it: "I already
# tried restarting it" and "restarted it" are one fact.
_REPORT_LEAD_IN = re.compile(
    r"^\s*(?:and\s+)?(?:i\s+|we\s+)?(?:have\s+|had\s+|has\s+)?"
    r"(?:already\s+)?(?:tried\s+|did\s+|done\s+)?(?:already\s+)?"
    r"(?:to\s+)?",
    re.IGNORECASE,
)

# Answers that are a reply to the question rather than a step. Recording one
# would make the record claim the associate tried something, and the record is
# read as permission to skip.
_DENIALS = {
    "",
    "no",
    "none",
    "nope",
    "nothing",
    "nothing yet",
    "not yet",
    "n/a",
    "na",
    "no response received from user timeout",
    "i havent tried anything",
    "i havent tried anything yet",
    "we havent tried anything",
    "havent tried anything",
    "nothing at all",
    "dont know",
    "unsure",
}

# Words the backend substitutes for an answer it never received. They are the
# backend's words, not the associate's, and they are not a step.
_SUBSTITUTED_ANSWER_PREFIXES = (
    "no response received from user",
    "error receiving response",
    "the user did not",
    "unable to reach the user",
)

# Filler that changes the wording of a step without changing the step. Removed
# only for *comparison*; the associate's own words are what get stored, because
# they are what #22's ticket carries.
_FILLER = {
    "a",
    "an",
    "the",
    "it",
    "its",
    "i",
    "we",
    "have",
    "has",
    "had",
    "did",
    "do",
    "done",
    "already",
    "tried",
    "try",
    "trying",
    "just",
    "then",
    "and",
    "also",
    "again",
    "to",
    "of",
    "on",
    "at",
    "my",
    "our",
    "this",
    "that",
    "one",
    "another",
    "some",
    "there",
    "was",
    "is",
    "been",
    "being",
    "be",
}

# Verb endings an associate switches between freely — "restart", "restarted",
# "restarting" are one step, and "power cycle" is "power-cycled".
_SUFFIXES = ("ing", "ed", "es", "s")

# Where one typed sentence becomes two steps. Only conjunctions that separate
# *actions*; "off and on again" is deliberately protected below.
_SPLIT = re.compile(
    r"(?:\r?\n)+|;|,\s*(?:and\s+|then\s+)?|\s+and\s+then\s+|\s+and\s+(?=i\s|we\s)|\s+then\s+",
    re.IGNORECASE,
)


def _strip_markers(line: str) -> str:
    return _BULLET.sub("", line or "").strip()


def _is_substituted(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return any(lowered.startswith(prefix) for prefix in _SUBSTITUTED_ANSWER_PREFIXES)


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            word = word[: -len(suffix)]
            break
    # A trailing "e" goes too, so "descale" and "descaled" stem alike: an
    # associate switches tense between turns and the record must not.
    if len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    return word


def normalise_step(step: str) -> str:
    """The comparable form of a step: its content words, stemmed and sorted.

    Sorted because an associate reports the same action in whatever order the
    words arrive — "power cycled the brewer" and "brewer power-cycle" are one
    step — and stemmed because they switch tense freely between turns.
    """
    return " ".join(sorted({_stem(word) for word in _words(step) if word not in _FILLER}))


def _is_denial(step: str) -> bool:
    lowered = re.sub(r"[^a-z0-9 ]", "", (step or "").strip().lower())
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered in _DENIALS


def parse_attempted_steps(answer: Optional[str]) -> List[str]:
    """The discrete steps an associate's clarification answer reports trying.

    Total: anything that is not a step — a blank answer, a denial, the fixed
    words the clarification path substitutes when nobody replied — yields no
    steps rather than one empty step. An empty attempted step would compare
    equal to every runbook step and skip the whole runbook.
    """
    if not answer or not str(answer).strip():
        return []
    if _is_substituted(answer):
        return []

    steps: List[str] = []
    for line in str(answer).splitlines():
        cleaned = _strip_markers(line)
        if not cleaned:
            continue
        for fragment in _SPLIT.split(cleaned):
            step = _REPORT_LEAD_IN.sub("", (fragment or "").strip()).strip(" .!?")
            if not step or _is_denial(step) or not normalise_step(step):
                continue
            steps.append(step)
    return steps


def merge_attempted(
    existing: Sequence[str], incoming: Iterable[str]
) -> List[str]:
    """Fold newly reported steps into a record without duplicating one.

    The **first** wording wins on a repeat. The second telling is the same
    fact, not a better one, and the wording the associate first used is what a
    ticket quotes back to them.
    """
    merged = list(existing or [])
    seen = {normalise_step(step) for step in merged}
    for step in incoming or []:
        key = normalise_step(step)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(step)
    return merged


def already_attempted(
    candidate: str, recorded: Sequence[str]
) -> Optional[str]:
    """The recorded step ``candidate`` repeats, or ``None``.

    Matches on the content words the two share rather than on equality, because
    a runbook says "Power cycle the brewer at the wall switch" and an associate
    says "turned it off and on again". Both directions of containment count: the
    runbook's wording is longer than the associate's about as often as not.

    Containment on a **single** shared word is refused. "Check the drip tray"
    and "checked the water line" share only *check*, and claiming that step is
    this function failing in the one direction it may not fail in.
    """
    wanted = set(normalise_step(candidate).split())
    if not wanted:
        return None
    for step in recorded or []:
        have = set(normalise_step(step).split())
        if not have:
            continue
        if wanted == have:
            return step
        if min(len(wanted), len(have)) < 2:
            continue
        if wanted <= have or have <= wanted:
            return step
    return None


def escalation_due(recorded: Sequence[str]) -> bool:
    """Whether enough has been tried that a service ticket is the next move."""
    return len(recorded or []) >= ESCALATION_AFTER


def attempted_note(recorded: Sequence[str]) -> str:
    """What the agent is told about the record, or nothing.

    Nothing is said by saying nothing: an "already tried" heading over an empty
    list reads to a model as a list it may fill in, and an invented attempted
    step skips a real runbook branch.
    """
    steps = [step for step in (recorded or []) if step]
    if not steps:
        return ""

    lines = [
        "The associate has already reported trying these, on this fault, in this "
        "session. Do NOT walk them through any of them again: skip the step, say "
        "you are skipping it and why, and go to the next branch of the runbook.",
    ]
    lines.extend(f"- {step}" for step in steps)
    if escalation_due(steps):
        lines.append(
            "They have now tried enough that the shift is unlikely to fix this. "
            "If the runbook has no branch left, say so and offer to raise a "
            "service ticket."
        )
    return "\n".join(lines)
