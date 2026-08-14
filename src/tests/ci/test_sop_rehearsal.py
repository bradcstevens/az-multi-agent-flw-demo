"""The rehearsal that proves the centrepiece beat is not intermittent (#54).

One green Demo validator run is what the intermittent state already produces
three times in four, so the beat is proved by **ten consecutive** runs or not at
all. The runs need a deployment; the arithmetic over what they observed does
not, and that is the seam under test here.

Two things are asserted, and both of them are the issue's own acceptance
criteria made executable rather than written down:

- **The rephrasing is measured.** Every run appends what the orchestrator
  actually handed ``search_store_procedures`` to a ledger, so the distinct
  phrasings are read off the evidence instead of being guessed at.
- **A failure is attributed to a layer.** Routing, rephrasing and the agent's
  Dataverse index each have a different fix, and guessing wrong leaves the beat
  intermittent. `attribution` decides which one a red run implicates from what
  that run saw, and it is a function precisely so it can be argued with.
"""

import json
from pathlib import Path

from sop_rehearsal import (CLARIFIED, GROUNDED, HONEST_MISS, INDEX,
                           NO_TOOL_CALL, REHEARSED_BEAT, REPHRASING, ROUTING,
                           UNKNOWN, WANTED_RUNS, attribution, format_report,
                           main, read_evidence, rephrasings, summarise,
                           validator_command)

REPO_ROOT = Path(__file__).resolve().parents[3]

CORPUS_QUESTION = "How do I close the store?"
SOP_102 = "SOP-102 Store Closing Procedure.docx"

#: The commit the deployment was serving when the run observed it. Twelve hex
#: characters, because that is what `deploy-main.yml` stamps an image with.
DEPLOYED_BUILD = "530bacfa364e"


def row(**overrides):
    """One validator run's evidence, as the spec appends it."""
    base = {
        "at": "2026-08-14T07:00:00.000Z",
        "target": "deployed",
        "baseURL": "https://app.example",
        "commit": "0eb208cb",
        "deployedBuild": DEPLOYED_BUILD,
        "buildVerified": True,
        "passed": True,
        "outcome": GROUNDED,
        "toolQuery": CORPUS_QUESTION,
        "retrievalQuery": CORPUS_QUESTION,
        "citations": [SOP_102],
    }
    base.update(overrides)
    return base


def ledger(tmp_path, rows):
    path = tmp_path / "sop-evidence.jsonl"
    path.write_text(
        "".join(json.dumps(entry) + "\n" for entry in rows), encoding="utf-8"
    )
    return path


# ---------------------------------------------------------------------------
# Reading the evidence
# ---------------------------------------------------------------------------

def test_given_no_ledger_when_read_then_no_rows():
    # A rehearsal whose first run never reached the beat leaves nothing behind.
    # That is zero evidence, which must read as zero rather than as an error a
    # caller has to distinguish from a bad run.
    assert read_evidence("/nowhere/at/all.jsonl") == []


def test_given_a_ledger_when_read_then_every_row_comes_back(tmp_path):
    path = ledger(tmp_path, [row(), row(passed=False, outcome=HONEST_MISS)])

    rows = read_evidence(path)

    assert [entry["outcome"] for entry in rows] == [GROUNDED, HONEST_MISS]


def test_given_a_half_written_line_when_read_then_the_rest_survives(tmp_path):
    # The ledger is appended to by a browser suite that can be killed mid-run.
    # A torn last line must not cost the nine runs in front of it.
    path = ledger(tmp_path, [row(), row()])
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"at": "2026-08-14T07:0')

    assert len(read_evidence(path)) == 2


def test_given_an_offset_when_read_then_earlier_rows_are_skipped(tmp_path):
    # A rehearsal reports on its own runs. The ledger accumulates across every
    # validator run ever made against this checkout, and that is the point of
    # it — but yesterday's reds are not this rehearsal's.
    path = ledger(tmp_path, [row(passed=False), row(), row()])

    assert len(read_evidence(path, skip=1)) == 2


# ---------------------------------------------------------------------------
# The measurement
# ---------------------------------------------------------------------------

def test_given_runs_when_rephrasings_then_distinct_tool_queries_in_order():
    # The orchestrator's wording is model prose and is never asserted on. It is
    # *recorded*, because "some rephrasings miss" is a claim about a
    # distribution and this is the only place the distribution exists.
    rows = [
        row(toolQuery=CORPUS_QUESTION),
        row(toolQuery="What is the store closing procedure?"),
        row(toolQuery=CORPUS_QUESTION),
    ]

    assert rephrasings(rows) == [
        CORPUS_QUESTION,
        "What is the store closing procedure?",
    ]


def test_given_a_run_with_no_tool_call_when_rephrasings_then_it_is_not_counted():
    # A turn the orchestrator never called the tool on contributes no phrasing.
    # Counting its absent query as a phrasing would report the routing failure
    # as a rephrasing, which is the wrong layer.
    rows = [row(), row(outcome=NO_TOOL_CALL, toolQuery=None, passed=False)]

    assert rephrasings(rows) == [CORPUS_QUESTION]


# ---------------------------------------------------------------------------
# The attribution
# ---------------------------------------------------------------------------

def test_given_a_green_run_when_attributed_then_nothing_is_blamed():
    assert attribution(row()) is None


def test_given_no_tool_call_when_attributed_then_the_orchestrators_routing():
    # No Grounding panel at all: the Group Chat Manager answered from context,
    # or another specialist took the turn. Nothing reached Copilot Studio, so
    # neither the tool's instructions nor the index can be at fault.
    verdict = attribution(row(passed=False, outcome=NO_TOOL_CALL,
                              toolQuery=None, retrievalQuery=None,
                              citations=[]))

    assert verdict is not None
    assert "routing" in verdict.layer
    assert "never called" in verdict.detail


def test_given_a_miss_on_the_orchestrators_own_wording_then_the_rephrasing():
    # The hop completed and the corpus was searched for something the corpus
    # was never rehearsed against. The fix is at the query, not at the index.
    verdict = attribution(row(
        passed=False,
        outcome=HONEST_MISS,
        toolQuery="Please look up Store 223's end-of-night lockup steps.",
        retrievalQuery="Please look up Store 223's end-of-night lockup steps.",
        citations=[],
    ))

    assert verdict is not None
    assert "rephrasing" in verdict.layer
    assert "not the corpus wording" in verdict.detail


def test_given_a_miss_on_the_corpus_wording_then_the_dataverse_index():
    # The one attribution that means the demonstration's content is wrong
    # rather than its plumbing: the corpus's own words were retrieved against
    # and Dataverse still found nothing.
    verdict = attribution(row(
        passed=False,
        outcome=HONEST_MISS,
        toolQuery="What are the steps for closing the store tonight?",
        retrievalQuery=CORPUS_QUESTION,
        citations=[],
    ))

    assert verdict is not None
    assert "index" in verdict.layer
    assert CORPUS_QUESTION in verdict.detail


def test_given_a_grounded_answer_that_failed_then_the_layer_is_not_guessed():
    # Grounded, cited, and the beat still red — a selector, a timeout or an
    # assertion this file knows nothing about. Naming a layer here would be the
    # guess the issue exists to forbid.
    verdict = attribution(row(passed=False, outcome=GROUNDED))

    assert verdict is not None
    assert verdict.layer == UNKNOWN


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------

def test_given_ten_green_runs_when_summarised_then_the_beat_is_proved():
    summary = summarise([row() for _ in range(WANTED_RUNS)], WANTED_RUNS)

    assert summary.ok
    assert summary.consecutive == WANTED_RUNS


def test_given_nine_green_runs_when_summarised_then_it_is_not_proved():
    # The whole shape of the criterion. Nine is what the intermittent state
    # produces often enough to be believed, which is why the number is ten and
    # why "mostly green" is not a verdict this reports.
    summary = summarise([row() for _ in range(WANTED_RUNS - 1)], WANTED_RUNS)

    assert not summary.ok
    assert summary.consecutive == WANTED_RUNS - 1


def test_given_a_red_run_when_summarised_then_the_streak_starts_after_it():
    # Consecutive means consecutive. A rehearsal that went red on run four and
    # green afterwards has not proved anything about the four in front of it.
    rows = [row(), row(), row(), row(passed=False, outcome=HONEST_MISS)] + [
        row() for _ in range(3)
    ]

    summary = summarise(rows, WANTED_RUNS)

    assert not summary.ok
    assert summary.consecutive == 3
    assert summary.first_red is not None


def test_given_no_runs_when_summarised_then_it_is_not_proved():
    # A rehearsal nobody ran proves nothing, and must not read as ten greens
    # by an empty-streak accident.
    summary = summarise([], WANTED_RUNS)

    assert not summary.ok
    assert summary.consecutive == 0


def test_given_a_red_run_when_reported_then_the_layer_is_named(tmp_path):
    rows = [row(), row(passed=False, outcome=NO_TOOL_CALL, toolQuery=None)]

    report = format_report(summarise(rows, WANTED_RUNS))

    assert "routing" in report
    assert "1 of 10" in report or "1/10" in report


def test_given_a_proof_when_reported_then_the_phrasings_are_shown():
    # The report is the evidence a reader is asked to trust, so the queries the
    # orchestrator actually used are in it — including on a run that passed,
    # where they are the record of what the fix had to survive.
    rows = [row(toolQuery=f"phrasing {index}") for index in range(WANTED_RUNS)]

    report = format_report(summarise(rows, WANTED_RUNS))

    assert "phrasing 0" in report
    assert "phrasing 9" in report


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

def test_given_every_run_green_when_main_then_it_exits_zero(tmp_path):
    path = tmp_path / "sop-evidence.jsonl"
    written = []

    def fake_run(index):
        written.append(index)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row()) + "\n")
        return True

    code = main(["--runs", "3", "--ledger", str(path)], run=fake_run)

    assert code == 0
    assert written == [1, 2, 3]


def test_given_a_red_run_when_main_then_it_stops_there(tmp_path):
    # A rehearsal is over the moment it goes red: the streak is broken, and
    # nine more live conversations spend Copilot Credits proving nothing.
    path = tmp_path / "sop-evidence.jsonl"
    written = []

    def fake_run(index):
        written.append(index)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(row(passed=index == 2 and False or True,
                               outcome=HONEST_MISS if index == 2 else GROUNDED))
                + "\n"
            )
        return index != 2

    code = main(["--runs", "5", "--ledger", str(path)], run=fake_run)

    assert code == 1
    assert written == [1, 2]


def test_given_an_earlier_rehearsal_when_main_then_its_rows_are_not_counted(
        tmp_path):
    # The ledger is append-only across every run ever made from this checkout.
    # A rehearsal that counted the rows already in it would report ten greens
    # after running once.
    path = tmp_path / "sop-evidence.jsonl"
    path.write_text(
        "".join(json.dumps(row()) + "\n" for _ in range(WANTED_RUNS)),
        encoding="utf-8",
    )

    def fake_run(index):
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row(passed=False,
                                        outcome=NO_TOOL_CALL)) + "\n")
        return False

    assert main(["--runs", "10", "--ledger", str(path)], run=fake_run) == 1


class TestTheClarificationIsRouting:
    """The outcome that hid inside a success (#54).

    Measured 2026-08-14 against `rg-macae-flw-v1`: a run whose Grounding panel
    named Copilot Studio, reported Dataverse and cited `SOP-102 Store Closing
    Procedure.docx` — and which was **red**, because the conversation showed
    the Group Chat Manager asking *"What is stopping Store 223 from closing
    right now?"* The answer was on the page. The presenter was still looking at
    a question.

    Attributed to `unknown` at the time, correctly: nothing in the ledger could
    tell that run from a broken selector. That is what this outcome is for.
    """

    def test_a_grounded_run_that_asked_back_is_the_routing(self):
        blame = attribution({
            "passed": False,
            "outcome": CLARIFIED,
            "toolQuery": "the closing procedure for store 223",
            "retrievalQuery": "How do I close the store?",
            "citations": ["SOP-102 Store Closing Procedure.docx"],
        })

        assert blame.layer == ROUTING

    def test_it_is_not_blamed_on_the_index_that_answered_correctly(self):
        # The trap. The retrieval query differs from the tool query on this run
        # -- the marker fired -- which is the shape `honest-miss` reads as an
        # index failure. Reindexing a corpus that returned the right document
        # is a day spent on the wrong layer.
        blame = attribution({
            "passed": False,
            "outcome": CLARIFIED,
            "toolQuery": "the closing procedure for store 223",
            "retrievalQuery": "How do I close the store?",
            "citations": ["SOP-102 Store Closing Procedure.docx"],
        })

        assert blame.layer != INDEX
        assert blame.layer != REPHRASING

    def test_a_green_run_is_still_attributed_to_nothing(self):
        assert attribution({"passed": True, "outcome": CLARIFIED}) is None

    def test_the_report_names_the_layer_for_it(self):
        summary = summarise([{
            "passed": False,
            "outcome": CLARIFIED,
            "toolQuery": "the closing procedure",
            "retrievalQuery": "How do I close the store?",
        }], wanted=10)

        report = format_report(summary)

        assert ROUTING in report
        assert "NOT proved" in report


class TestTheHonestMissIsAttributedToTheRightLayer:
    """The comparison that decides between a query bug and a corpus bug.

    Reindexing Dataverse and normalising the orchestrator's query are days of
    work apiece, in different repositories, by different people. Getting this
    branch backwards spends one of them on the other's bug.
    """

    def test_a_verbatim_question_that_missed_is_the_index_not_the_rephrasing(self):
        # The case the obvious comparison gets wrong. When the orchestrator
        # does not rephrase at all, the tool query and the retrieval query are
        # *equal* -- the shape that reads as "not normalised". But nothing
        # needed normalising: the corpus's own words were searched for and
        # Dataverse missed, which is the index.
        verdict = attribution({
            "passed": False,
            "outcome": HONEST_MISS,
            "toolQuery": CORPUS_QUESTION,
            "retrievalQuery": CORPUS_QUESTION,
            "citations": [],
        })

        assert verdict.layer == INDEX

    def test_the_corpus_question_is_read_rather_than_pinned(self):
        from sop_rehearsal import rehearsed_question

        assert rehearsed_question() == CORPUS_QUESTION

    def test_a_miss_with_no_retrieval_query_names_no_layer(self):
        # A panel that reported the miss but not what it searched for is a
        # backend older than the evidence fields. Guessing from the tool query
        # alone would attribute it to whichever branch happened to match.
        verdict = attribution({
            "passed": False,
            "outcome": HONEST_MISS,
            "toolQuery": "anything",
            "retrievalQuery": None,
            "citations": [],
        })

        assert verdict.layer == UNKNOWN


class TestTheRehearsalRunsTheBeatItIsAbout:
    """Ten runs of the **rehearsed hit**, not of the walkthrough (#54).

    With one spec these were the same run and the difference never showed.
    Since the fourth specialist got a beat of its own (#52) they are not: a red
    **workforce** beat exits the validator non-zero, and the harness — which
    treats a non-zero exit as fatal to the streak, deliberately — could never
    report the centrepiece proved while an unrelated beat was failing. Measured
    2026-08-14: the hop's beat green and cited, the run red, the proof
    unobtainable.

    That is this issue's own mistake wearing the harness's clothes. The
    conflation `direct-sop-answer` was renamed for is a check and a browser
    asking different questions of the same agent; this is a proof and a ledger
    describing different runs.

    Scoping restores what the exit-code guard meant when it was written — a
    green row behind a red run is a **teardown** failure — and halves the live
    conversations a rehearsal holds.
    """

    def test_the_validator_is_scoped_to_the_rehearsed_hits_spec(self):
        assert REHEARSED_BEAT in validator_command([])

    def test_the_spec_it_names_is_a_spec_that_exists(self):
        # A filter that matches nothing is Playwright's most dangerous exit: it
        # reports "No tests found" and returns zero, which this harness would
        # read as ten green runs of a beat that never ran.
        assert (REPO_ROOT / "e2e" / REHEARSED_BEAT).exists()

    def test_the_target_still_reaches_the_loop(self):
        command = validator_command(["--target", "local"])

        assert "--target" in command and "local" in command

    def test_a_rehearsal_asks_the_loop_for_that_spec(self, tmp_path):
        seen = []

        def run(index):
            seen.append(index)
            with open(tmp_path / "l.jsonl", "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row()) + "\n")
            return True

        assert main(
            ["--runs", "2", "--ledger", str(tmp_path / "l.jsonl")], run=run
        ) == 0
        assert seen == [1, 2]


class TestAProofNamesTheBuildItProved:
    """Ten green runs against *which* build? (#54)

    The rehearsal is the proof of the centrepiece beat, and until this it
    reported that proof without ever saying what it was a proof *of*. The
    validator gates on the deployed build before a browser opens — and the
    error it prints when that gate goes red ends with the way past it:

        To go anyway — knowing the beats are about another build — set
        E2E_SKIP_BUILD_CHECK=1.

    Which is the right thing for the **Stage driver** to offer a presenter
    mid-demonstration, and the wrong thing to leave invisible in the ledger: a
    rehearsal run under that flag appends a row indistinguishable from a
    verified one, and ten of them print *the beat is proved*. `--target local`
    is the same hole through a different door — ten green runs against a
    `npm run dev` and a fake, reported in the words reserved for the
    deployment.

    So the streak is necessary and not sufficient. Every run in a rehearsal
    must have verified the build, and it must be the **same** build.
    """

    def test_ten_verified_runs_of_one_build_name_it_in_the_report(self):
        summary = summarise([row() for _ in range(WANTED_RUNS)])

        assert summary.ok
        assert DEPLOYED_BUILD in format_report(summary)

    def test_a_run_that_skipped_the_build_check_is_not_part_of_a_proof(self):
        rows = [row() for _ in range(WANTED_RUNS)]
        rows[3] = row(buildVerified=False, deployedBuild=None)

        summary = summarise(rows)

        assert not summary.ok
        assert summary.consecutive == WANTED_RUNS
        assert "E2E_SKIP_BUILD_CHECK" in format_report(summary)

    def test_local_runs_prove_the_harness_and_say_so(self):
        summary = summarise([
            row(target="local", buildVerified=False, deployedBuild=None)
            for _ in range(WANTED_RUNS)
        ])

        assert not summary.ok
        assert "local" in format_report(summary)

    def test_a_rehearsal_spanning_a_redeploy_is_not_ten_consecutive_runs(self):
        # Ten green runs across two builds is two rehearsals of five, and
        # neither of them is the proof. `deploy-main.yml` runs on every push to
        # `main`, so a rehearsal begun before one and finished after it is not
        # a hypothetical.
        rows = [row() for _ in range(WANTED_RUNS)]
        for index in range(5, WANTED_RUNS):
            rows[index] = row(deployedBuild="a96b44815f80")

        summary = summarise(rows)

        assert not summary.ok
        report = format_report(summary)
        assert DEPLOYED_BUILD in report and "a96b44815f80" in report

    def test_a_ledger_older_than_the_field_is_unproved_not_proved(self):
        # ADR-018's rule, which this module now inherits: an unproved build is
        # not a passing one. A row from a harness that never dated its build
        # cannot be told from one that did, so it counts as neither.
        legacy = row()
        del legacy["buildVerified"]
        del legacy["deployedBuild"]

        summary = summarise([legacy for _ in range(WANTED_RUNS)])

        assert not summary.ok

    def test_a_verified_run_that_named_no_build_is_not_a_proof(self):
        summary = summarise([
            row(buildVerified=True, deployedBuild=None)
            for _ in range(WANTED_RUNS)
        ])

        assert not summary.ok


class TestAFailedValidatorIsNeverAProof:
    """The ledger and the loop can disagree, and the loop wins.

    The beat appends its row from an `afterEach` hook, so a run whose test body
    passed and whose teardown, reporter or browser then failed leaves a
    `passed` row behind a non-zero exit. Ten of those would be reported as the
    beat proved -- on the strength of ten runs nobody would call green.
    """

    def test_ten_passing_rows_behind_a_failed_run_do_not_prove_the_beat(
        self, tmp_path
    ):
        ledger = tmp_path / "sop-evidence.jsonl"
        calls = []

        def run(index):
            calls.append(index)
            with open(ledger, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "passed": True,
                    "outcome": GROUNDED,
                    "toolQuery": "the closing procedure",
                    "retrievalQuery": CORPUS_QUESTION,
                }) + "\n")
            return index != 10

        exit_code = main(
            ["--runs", "10", "--ledger", str(ledger)], run=run)

        assert calls == list(range(1, 11))
        assert exit_code == 1

    def test_ten_clean_runs_still_prove_it(self, tmp_path):
        ledger = tmp_path / "sop-evidence.jsonl"

        def run(index):
            with open(ledger, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row()) + "\n")
            return True

        assert main(["--runs", "10", "--ledger", str(ledger)], run=run) == 0
