#!/usr/bin/env python3
"""The rehearsal: ten consecutive Demo validator runs of the centrepiece beat.

Issue #54. The walkthrough's opening beat — *"How do I close the store?"*,
answered from the SOP corpus through Copilot Studio — came back as the **honest
miss** two runs in eight on the afternoon the Demo validator first ran. One
green run is what that state already produces three times in four, so the beat
is proved by **ten consecutive** runs or it is not proved at all.

This module is the arithmetic over what those runs observed. The runs need a
deployment; the arithmetic does not, and `src/tests/ci/test_sop_rehearsal.py`
holds it to its contract without one.

Two of the issue's acceptance criteria live here as code rather than as prose:

- **The rephrasing is measured, not guessed.** Every validator run appends what
  the orchestrator actually handed ``search_store_procedures`` to an append-only
  ledger (``e2e/evidence.ts``), and `rephrasings` reads the distinct wordings
  back off it. "Some rephrasings miss" is a claim about a distribution, and this
  is the only place that distribution exists.
- **A red run is attributed to a layer.** The tool's instructions, the agent's
  Dataverse index and the orchestrator's routing each have a different fix, and
  guessing wrong leaves the beat intermittent. `attribution` decides which one a
  red run implicates *from what that run saw* — and says `unknown` rather than
  naming one when the evidence does not reach.

    bash scripts/sop-rehearsal.sh              # ten runs against the deployment
    bash scripts/sop-rehearsal.sh --runs 3     # a shorter look
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

#: Ten, because nine is what the intermittent state produces often enough to be
#: believed. The number is the criterion, so it lives here rather than in a
#: caller's default.
WANTED_RUNS = 10

#: What one run saw. Written by the spec, read by nothing else.
GROUNDED = "grounded"
HONEST_MISS = "honest-miss"
NO_TOOL_CALL = "no-tool-call"
UNKNOWN = "unknown"

#: The three layers the issue names, plus the refusal to name one.
ROUTING = "the orchestrator's routing"
REPHRASING = "the orchestrator's rephrasing"
INDEX = "the agent's Dataverse index"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO_ROOT, "e2e", "artifacts", "sop-evidence.jsonl")
VALIDATOR = os.path.join(REPO_ROOT, "scripts", "e2e-tests.sh")


# ---------------------------------------------------------------------------
# Reading the evidence
# ---------------------------------------------------------------------------

def read_evidence(path, skip: int = 0) -> List[Dict[str, Any]]:
    """Return the ledger's rows, skipping the first ``skip`` of them.

    Tolerant on purpose, in both directions. A ledger that does not exist is
    **no evidence**, not an error: the first run of a rehearsal may be killed
    before the beat ever appends. And a torn final line — a browser suite
    interrupted mid-write — must not cost the nine complete runs in front of it.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []

    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows[skip:]


def rephrasings(rows) -> List[str]:
    """The distinct queries the orchestrator sent the SOP tool, first seen first.

    A run on which the tool was never called contributes nothing: it has no
    phrasing, and counting its absence as one would report a **routing** failure
    as a rephrasing, which is the wrong layer and the wrong fix.
    """
    seen: List[str] = []
    for row in rows:
        query = (row.get("toolQuery") or "").strip()
        if query and query not in seen:
            seen.append(query)
    return seen


# ---------------------------------------------------------------------------
# The attribution
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Attribution:
    """Which layer a red run implicates, and what said so."""

    layer: str
    detail: str


def attribution(row) -> Optional[Attribution]:
    """Attribute one red run to a layer, or return ``None`` for a green one.

    The order matters, and it is the order of what the run can rule out:

    1. **No tool call at all.** Nothing reached Copilot Studio, so neither the
       tool's instructions nor the index can be at fault. This is the
       orchestrator answering from context, or handing the turn to a specialist
       with no procedure knowledge.
    2. **A miss on the orchestrator's own wording.** The hop completed and the
       corpus was searched for something it was never rehearsed against. The
       fix is at the query.
    3. **A miss on the corpus's own wording.** The words the corpus was written
       around were retrieved against and Dataverse still found nothing. This is
       the one attribution that means the demonstration's *content* is wrong
       rather than its plumbing, and it is the expensive one to guess at.

    Anything else is `unknown`, deliberately. A beat that went red while the
    answer was grounded and cited is a selector, a timeout or an assertion this
    module knows nothing about, and naming a layer for it would be exactly the
    guess the issue exists to forbid.
    """
    if row.get("passed"):
        return None

    outcome = row.get("outcome")
    tool_query = (row.get("toolQuery") or "").strip()
    retrieval_query = (row.get("retrievalQuery") or "").strip()

    if outcome == NO_TOOL_CALL:
        return Attribution(
            ROUTING,
            "the SOP tool was never called: no Grounding panel arrived, so "
            "the orchestrator answered from context or gave the turn to a "
            "specialist that has no procedure knowledge",
        )

    if outcome == HONEST_MISS:
        if retrieval_query and retrieval_query == tool_query:
            return Attribution(
                REPHRASING,
                f"Dataverse was searched for {retrieval_query!r}, which was "
                "not normalised to the corpus wording — the orchestrator "
                "rephrased the question and the rephrasing missed",
            )
        return Attribution(
            INDEX,
            f"Dataverse was searched for {retrieval_query!r} — the corpus's "
            "own wording — and found no matching procedure",
        )

    return Attribution(
        UNKNOWN,
        f"the run saw {outcome!r} and still failed; the evidence does not "
        "reach a layer, so none is named",
    )


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------

@dataclass
class Summary:
    """What a rehearsal proved, and what it saw on the way."""

    rows: List[Dict[str, Any]] = field(default_factory=list)
    wanted: int = WANTED_RUNS
    consecutive: int = 0
    first_red: Optional[Dict[str, Any]] = None

    @property
    def ok(self) -> bool:
        return self.consecutive >= self.wanted


def summarise(rows, wanted: int = WANTED_RUNS) -> Summary:
    """Summarise a rehearsal's runs. Pure.

    ``consecutive`` is the **trailing** streak, because consecutive means
    consecutive: a rehearsal that went red on run four has proved nothing about
    the three in front of it, and a count of "greens seen" would report it as
    almost there.
    """
    rows = list(rows)
    streak = 0
    for row in reversed(rows):
        if not row.get("passed"):
            break
        streak += 1
    first_red = next((row for row in rows if not row.get("passed")), None)
    return Summary(
        rows=rows, wanted=wanted, consecutive=streak, first_red=first_red
    )


def format_report(summary: Summary) -> str:
    """Return the human-readable report for a `Summary`. Pure."""
    lines = []
    for index, row in enumerate(summary.rows, start=1):
        verdict = "PASS" if row.get("passed") else "FAIL"
        query = row.get("toolQuery") or "(the tool was never called)"
        lines.append(
            f"  {verdict}  run {index} of {summary.wanted}: "
            f"{row.get('outcome')}, asked {query!r}"
        )
        blame = attribution(row)
        if blame:
            lines.append(f"        layer: {blame.layer} — {blame.detail}")

    observed = rephrasings(summary.rows)
    if observed:
        lines.append(
            f"  ----  {len(observed)} distinct phrasing(s) reached the SOP "
            f"tool over {len(summary.rows)} run(s)"
        )

    if summary.ok:
        lines.append(
            f"  ----  the rehearsed hit answered from the corpus "
            f"{summary.consecutive} consecutive times: the beat is proved"
        )
    else:
        lines.append(
            f"  ----  {summary.consecutive} consecutive of "
            f"{summary.wanted} wanted: the beat is NOT proved"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

def run_validator(index: int, extra=()) -> bool:
    """Run the Demo validator once. Returns whether it was green."""
    command = ["bash", VALIDATOR, *extra]
    print(f"\n=== rehearsal run {index}: {' '.join(command)}", flush=True)
    return subprocess.call(command, cwd=REPO_ROOT) == 0


def main(argv=None, run: Optional[Callable[[int], bool]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs", type=int, default=WANTED_RUNS,
        help="how many consecutive green runs prove the beat (default: 10)",
    )
    parser.add_argument("--ledger", default=LEDGER)
    parser.add_argument(
        "--target", default=None, choices=("deployed", "local"),
        help="passed through to scripts/e2e-tests.sh",
    )
    args = parser.parse_args(argv)

    extra = ["--target", args.target] if args.target else []
    runner = run or (lambda index: run_validator(index, extra))

    # The ledger is append-only across every validator run ever made from this
    # checkout — that is what makes the phrasings a measurement rather than a
    # snapshot. A rehearsal reports on its **own** runs, so it starts where the
    # ledger already ended.
    skip = len(read_evidence(args.ledger))

    for index in range(1, args.runs + 1):
        green = runner(index)
        rows = read_evidence(args.ledger, skip=skip)
        if not green or not rows or not rows[-1].get("passed"):
            # Over the moment it goes red. The streak is broken, and nine more
            # live conversations spend Copilot Credits proving nothing.
            break

    summary = summarise(read_evidence(args.ledger, skip=skip), args.runs)
    print(f"\nRehearsed hit, {args.runs} consecutive runs wanted:")
    print(format_report(summary))
    return 0 if summary.ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
