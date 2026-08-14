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

from preflight.deployed_surface import rehearsed_question as _rehearsed_question
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
CLARIFIED = "clarified"
UNKNOWN = "unknown"

#: The three layers the issue names, plus the refusal to name one.
ROUTING = "the orchestrator's routing"
REPHRASING = "the orchestrator's rephrasing"
INDEX = "the agent's Dataverse index"

#: The deliberate act that gets a validator run past the deployed-build gate,
#: named here because this module's whole job is to notice that it was used.
#: `e2e/deployedBuild.ts` offers it to a presenter mid-demonstration on purpose
#: — a refusal to start over a one-commit drift does more harm than the drift —
#: and what is right for the Stage driver is a lie in a rehearsal's ledger.
SKIP_BUILD_CHECK = "E2E_SKIP_BUILD_CHECK"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO_ROOT, "e2e", "artifacts", "sop-evidence.jsonl")
VALIDATOR = os.path.join(REPO_ROOT, "scripts", "e2e-tests.sh")
SOP_MANIFEST = os.path.join(REPO_ROOT, "content", "sop", "corpus.toml")

#: The beat this harness proves, relative to `e2e/`.
#:
#: Ten runs of the **rehearsed hit**, not of the walkthrough. With one spec
#: those were the same run; since the fourth specialist got a beat of its own
#: (#52) they are not, and a red **workforce** beat exits the validator
#: non-zero — which this harness treats as fatal to the streak, deliberately,
#: because a green row behind a red run is a teardown failure. Unscoped, the
#: centrepiece could not be proved while any other beat was failing: a proof
#: hostage to a beat its ledger says nothing about.
#:
#: The **Recorded fallback** is not lost by this, it is correctly declined: the
#: walkthrough reporter reads a positional filter as a filter and refuses to
#: replace the recording from a run that is not a whole walkthrough. The
#: fallback is a plain Demo validator run's job.
REHEARSED_BEAT = os.path.join("specs", "cross-platform.spec.ts")


def rehearsed_question(manifest: str = SOP_MANIFEST) -> str:
    """The question the walkthrough opens with, read out of the corpus.

    Section-scoped, because `question` is a key under `[honest_miss]` too and
    that one names the question the corpus deliberately cannot answer — an
    attribution built on it would call every honest miss an index failure.
    """
    return _rehearsed_question(manifest)


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

    A grounded, cited run that still went red because the surface asked a
    question back is the **routing** too, and it is the reason this list has a
    fourth entry rather than three. It was `unknown` for a day: every signal
    this module had said the hop worked, and it did — the answer was on the
    page, behind a clarification the orchestrator was required to plan.

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

    if outcome == CLARIFIED:
        return Attribution(
            ROUTING,
            "the answer was retrieved and cited, and the surface asked the "
            "presenter a question back instead of showing it — a procedure "
            "lookup routed into a troubleshooting clarification",
        )

    if outcome == HONEST_MISS:
        if not retrieval_query:
            return Attribution(
                UNKNOWN,
                "the panel reported an honest miss without saying what was "
                "retrieved against; the evidence does not reach a layer",
            )
        # Against the corpus's own question, not against the tool query. The
        # two are equal on a turn the orchestrator did not rephrase at all —
        # and a run where it asked verbatim and Dataverse still missed is the
        # *index*, which comparing the two strings to each other reports as a
        # rephrasing that never happened.
        if retrieval_query == rehearsed_question():
            return Attribution(
                INDEX,
                f"Dataverse was searched for {retrieval_query!r} — the "
                "corpus's own wording — and found no matching procedure",
            )
        return Attribution(
            REPHRASING,
            f"Dataverse was searched for {retrieval_query!r}, which is not "
            "the corpus wording — the marker did not fire and the "
            "orchestrator's own phrasing missed",
        )

    return Attribution(
        UNKNOWN,
        f"the run saw {outcome!r} and still failed; the evidence does not "
        "reach a layer, so none is named",
    )


# ---------------------------------------------------------------------------
# The build the runs were about
# ---------------------------------------------------------------------------

def provenance(rows):
    """Why these runs are not ten consecutive runs of one build, or None.

    A streak is necessary and not sufficient. The Demo validator dates the
    deployed build before a browser opens (#48, ADR-018), and there are two
    signposted ways past that gate — `E2E_SKIP_BUILD_CHECK`, which the gate's
    own failure message offers, and `--target local`, which dates no deployment
    at all. Rows produced either way are green, well-formed, and about a build
    nobody can name; ten of them used to print *the beat is proved*.

    So this returns the reason a rehearsal's rows fall short of a proof about a
    single verified build, and `None` when they do not fall short. An absent
    field is a reason, not a pass — ADR-018's rule, inherited: a build that
    could not be dated has not been proved current, and the name is the whole
    point of recording it.
    """
    rows = list(rows)
    if not rows:
        return None

    for index, row in enumerate(rows, start=1):
        if not row.get("buildVerified"):
            where = row.get("target") or "unknown"
            if where == "local":
                return (
                    f"run {index} of {len(rows)} ran against a local surface, "
                    "which dates no deployed build: these runs prove the "
                    "harness, not the deployment"
                )
            return (
                f"run {index} of {len(rows)} did not verify the deployed "
                f"build — {SKIP_BUILD_CHECK}, or a harness older than the "
                "field. Whatever these runs are about, it is not a build this "
                "rehearsal can name"
            )

    builds = []
    for row in rows:
        build = (row.get("deployedBuild") or "").strip()
        if not build:
            return (
                "a run verified the deployed build and recorded no commit for "
                "it, so there is nothing to say these runs were about"
            )
        if build not in builds:
            builds.append(build)

    if len(builds) > 1:
        # `deploy-main.yml` runs on every push to `main`, so a rehearsal begun
        # before one and finished after it is not a hypothetical. Ten green
        # runs across two builds is two rehearsals of five.
        return (
            f"these runs span {len(builds)} builds ({', '.join(builds)}): "
            "consecutive runs of two builds are not consecutive runs of either"
        )
    return None


def proved_build(rows):
    """The one build a clean rehearsal was about, or None."""
    builds = {(row.get("deployedBuild") or "").strip() for row in rows}
    builds.discard("")
    return builds.pop() if len(builds) == 1 else None


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
    #: Why the runs are not about one verified build, or None. A streak with a
    #: reason here is a streak about nothing nameable.
    unnameable: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.consecutive >= self.wanted and self.unnameable is None


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
        rows=rows,
        wanted=wanted,
        consecutive=streak,
        first_red=first_red,
        unnameable=provenance(rows),
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
        billed = row.get("agentsBilled") or []
        if billed:
            lines.append(f"        billed: {', '.join(billed)}")
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
        build = proved_build(summary.rows)
        lines.append(
            f"  ----  the rehearsed hit answered from the corpus "
            f"{summary.consecutive} consecutive times against {build}: "
            f"the beat is proved"
        )
    else:
        lines.append(
            f"  ----  {summary.consecutive} consecutive of "
            f"{summary.wanted} wanted: the beat is NOT proved"
        )
    if summary.unnameable:
        # Printed whatever the streak did, because a rehearsal that went red on
        # run three *and* skipped the build check has two things wrong with it
        # and a reader who fixes one will run the other again.
        lines.append(f"  ----  and {summary.unnameable}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

def validator_command(extra=()) -> List[str]:
    """The Demo validator invocation one rehearsal run makes. Pure.

    Scoped to `REHEARSED_BEAT`, so the exit code this harness grades is the
    verdict on the beat its ledger describes.
    """
    return ["bash", VALIDATOR, *extra, REHEARSED_BEAT]


def run_validator(index: int, extra=()) -> bool:
    """Run the Demo validator once. Returns whether it was green."""
    command = validator_command(extra)
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

    # Tracked separately from the ledger, because they can disagree. The beat
    # appends its row from an `afterEach` hook, so a run whose test body passed
    # and whose reporter, teardown or browser teardown then failed leaves a
    # `passed` row behind a non-zero exit. Trusting the ledger alone would let
    # the tenth such run report the beat as proved.
    ran_clean = True

    for index in range(1, args.runs + 1):
        green = runner(index)
        rows = read_evidence(args.ledger, skip=skip)
        if not green:
            ran_clean = False
        if not green or not rows or not rows[-1].get("passed"):
            # Over the moment it goes red. The streak is broken, and nine more
            # live conversations spend Copilot Credits proving nothing.
            break

    summary = summarise(read_evidence(args.ledger, skip=skip), args.runs)
    print(f"\nRehearsed hit, {args.runs} consecutive runs wanted:")
    print(format_report(summary))
    if summary.ok and not ran_clean:
        print(
            "  ----  but the validator itself exited non-zero on a run whose "
            "beat passed: the ledger says proved and the loop does not, so "
            "this rehearsal proves nothing. Read e2e/artifacts/report."
        )
    return 0 if summary.ok and ran_clean else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
