"""The Demo validator is wired up, and the accelerator's browser suite is gone.

Issue #47, [ADR-016](../../../docs/ADR/016-typescript-playwright-for-the-demo-validator.md).

These are CI-tooling tests: the subject is the repository's own wiring, read
from disk as text — the same shape as `test_frontend_ci_wiring.py`, and for the
same reason. The **Demo validator** itself cannot run in CI: it needs a running
deployment, and the whole point of it is that it observes one. So the part of it
that *can* be asserted without a tenant is asserted here.

What they defend is narrow and specific:

- The loop exists, is executable, and bootstraps its own toolchain — ADR-005's
  binding half, which ADR-016 keeps while changing the language behind it.
- The recording is **unconditional**. It is the demonstration's own fallback
  (#51), so a config that keeps video only on failure has quietly deleted it.
- The suite reads its expectation **out of the repository** rather than
  restating it. A validator carrying its own copy of the corpus passes a rebrand
  it never saw — the ADR-019 lesson, one layer out.
- `tests/e2e-test/` stays deleted. It looks like the browser suite and is not:
  it drives a real identity-provider login against the pre-rebrand surface and
  is wired into no workflow.
"""

from pathlib import Path
import os
import re

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E = REPO_ROOT / "e2e"
LOOP = REPO_ROOT / "scripts" / "e2e-tests.sh"
CONFIG = E2E / "playwright.config.ts"
AUTHORED = E2E / "authored.ts"
AGENTS = REPO_ROOT / "AGENTS.md"
INHERITED = REPO_ROOT / "tests" / "e2e-test"
STORE_SURFACE = E2E / "pages" / "StoreSurface.ts"
CROSS_PLATFORM_SPEC = E2E / "specs" / "cross-platform.spec.ts"
HOME_INPUT = (
    REPO_ROOT / "src" / "App" / "src" / "components" / "content" / "HomeInput.tsx"
)

#: The Quick Tasks region, named once and asserted on both sides of the tap.
QUICK_TASKS_REGION = "home-input-quick-tasks"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(path: Path) -> str:
    """Return a TypeScript file's code with its comments stripped.

    The same move `test_transparency_contract.py` makes, for the same reason: a
    rule named only in prose would otherwise satisfy a check that nothing in the
    code satisfies. This file's own docstrings talk about `testDir`.
    """
    source = re.sub(r"/\*.*?\*/", "", _text(path), flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", source, flags=re.MULTILINE)


def _flat(path: Path) -> str:
    """Return a TypeScript file's code with its whitespace collapsed.

    So an assertion pinned here is pinned as the matcher it is, not as the line
    the formatter happened to wrap it onto.
    """
    return re.sub(r"\s+", " ", _code(path))


def test_the_validator_has_a_loop_script():
    assert LOOP.exists(), "no script runs the Demo validator"
    assert LOOP.stat().st_mode & 0o111, f"{LOOP.name} is not executable"


def test_the_loop_bootstraps_its_own_toolchain():
    # ADR-005's binding half, which ADR-016 preserves: runnable from a clean
    # checkout, a no-op re-install afterwards. A suite that needs a documented
    # `npm ci` first is a suite the presenter does not run.
    loop = _text(LOOP)

    assert "npm ci" in loop, "the loop does not install its dependencies"
    assert "playwright install" in loop, "the loop does not install its browser"


def test_the_loop_is_declared_in_agents_md():
    agents = _text(AGENTS)

    assert "scripts/e2e-tests.sh" in agents, (
        "the Demo validator is not in the declared Feedback loops table"
    )


def test_the_recording_is_unconditional():
    # The video is the demonstration's last-resort fallback (#51), produced by
    # the run that proved the walkthrough works. `retain-on-failure` would mean
    # the only run that leaves a recording is the one that went red.
    config = _code(CONFIG)

    assert "mode: 'on'" in config or "video: 'on'" in config, (
        "video is not recorded on passing runs"
    )
    for conditional in ("retain-on-failure", "on-first-retry", "off"):
        assert conditional not in config, (
            f"video or trace is conditional ('{conditional}'): the only run "
            "that would leave a recording is one that went red"
        )
    assert "trace: 'on'" in config, "the trace is not recorded on passing runs"
    assert "'html'" in config, "no HTML report is produced"


def test_the_same_specs_run_against_either_target():
    # One `testDir`, one spec set. Two targets is a base URL, not a second
    # suite — the same contract the Stage driver (#51) will reuse.
    config = _code(CONFIG)

    assert "resolveTarget" in config, (
        "the config does not resolve a target; the specs cannot run both ways"
    )
    assert config.count("testDir") == 1, (
        "more than one testDir: the walkthrough is described in two places"
    )


def test_the_expectation_is_read_out_of_the_repository():
    # Never pinned in the suite. `corpus.toml` names the document the opening
    # tap must be answered from, and the store pack names the Quick Task that
    # asks it; a validator repeating either passes a rename it never saw.
    authored = _code(AUTHORED)

    assert "corpus.toml" in authored, (
        "the validator does not read the SOP corpus manifest"
    )
    assert "store_assistant.json" in authored, (
        "the validator does not read the store pack's Quick Tasks"
    )


def test_the_inherited_accelerator_suite_is_gone():
    assert not INHERITED.exists(), (
        "tests/e2e-test/ is back: it drives an identity-provider login against "
        "the pre-rebrand surface and is wired into no workflow"
    )


def test_the_quick_task_tap_is_aimed_at_the_quick_tasks_region():
    # The validator's first action is a tap on a Quick Task, by the card title
    # the store pack authors. Those titles are substrings of the questions they
    # ask — "Close the store" of "How do I close the store?" — and every plan
    # the walkthrough has ever raised is listed in the task rail under exactly
    # that question. So a page-wide lookup matches one card on a fresh
    # deployment, two things after the first run, and twenty-one after the
    # twentieth: the loop rots by being run, which is the one failure mode a
    # loop must not have.
    #
    # The region is named on both sides and checked from both sides, the way
    # `authored.ts` reads the corpus rather than restating it: a hook renamed
    # in the surface and not in the page object goes red here, in a loop that
    # runs without a tenant, rather than on the morning of a demonstration.
    #
    # It is the surface's own layout class rather than a `data-testid`, because
    # the validator's target is a *running image*: an attribute this repository
    # authored this morning is not in it, and a locator that misses for that
    # reason reports "the image is old" as "the beat is broken".
    surface = _text(HOME_INPUT)
    page_object = _code(STORE_SURFACE)

    assert f'className="{QUICK_TASKS_REGION}"' in surface, (
        f"the Quick Tasks region no longer carries {QUICK_TASKS_REGION!r}; "
        "the validator has nothing to aim its tap at"
    )
    assert f"locator('.{QUICK_TASKS_REGION}')" in page_object, (
        "StoreSurface looks a Quick Task up across the whole page; the task "
        "rail carries the same words and the tap is ambiguous"
    )


def test_the_beat_does_not_grade_the_orchestrators_wording():
    # The rule this file's own subject states, applied to the one signal that
    # slipped past it. `docs/demo-validator.md` says model prose is asserted
    # only to have arrived, because "an empty answer and a paraphrased one look
    # identical to a suite that greps for a sentence, and only one of them is a
    # failure". The **retrieval query** is model prose: the orchestrator writes
    # the question the MCP tool is called with, and the backend's alias rewrites
    # it only when it recognises the wording verbatim.
    #
    # So an assertion that the retrieval query *equals* the corpus question is
    # an assertion that the orchestrator phrased itself in one of a handful of
    # rehearsed ways. It went red on a run where the hop, the route and
    # SOP-102 all landed — the demonstration working, reported as the
    # demonstration broken, which is the one thing this loop must never do.
    #
    # What is left is the invariant the backend actually guarantees, and it is
    # worth asserting: `_retrieval_query` is an **input alias, not an answer
    # fallback**, so the query it retrieves against is either the corpus's own
    # wording or the orchestrator's, and never a third thing. A null fails it
    # too, which is the routing failure the panel's absence already reports.
    spec = _code(CROSS_PLATFORM_SPEC)

    retrieval_expectations = [
        line for line in spec.splitlines()
        if "expect(" in line and "retrievalQuery" in line
    ]
    assert retrieval_expectations, (
        "the beat no longer says anything about the retrieval query; the "
        "evidence is captured and never read"
    )
    assert not any(
        re.search(r"expect\(retrievalQuery\)\.toBe\(hit\.question\)", line)
        for line in retrieval_expectations
    ), (
        "the beat grades the orchestrator's wording: it requires the retrieval "
        "query to be the corpus question, which only happens when the "
        "orchestrator's rephrasing is one the backend alias recognises "
        "verbatim. A green demonstration goes red on the sixth phrasing"
    )
    # Pinned as the whole matcher, not as "the word toolQuery appears
    # somewhere". A check that only forbids the old assertion is satisfied by
    # `.not.toContain(...)` — the invariant inverted — and one that only looks
    # for a substring is satisfied by a line that mentions it. Read from the
    # whitespace-normalised source so wrapping the call across lines, which is
    # what the formatter does to it, is not a failure.
    assert "expect([hit.question, toolQuery]).toContain(retrievalQuery);" in _flat(
        CROSS_PLATFORM_SPEC
    ), (
        "the beat does not accept the orchestrator's own query as a retrieval "
        "query: an un-aliased phrasing that retrieved SOP-102 anyway fails, "
        "and a third query the backend invented would pass"
    )


def test_the_beat_fails_when_the_evidence_is_absent():
    # The hole the invariant assertion leaves open on its own. Both queries are
    # read with `getAttribute`, which returns **null** for an attribute the
    # rendered panel does not carry — and a backend rolled back to before the
    # evidence fields existed renders neither. "One of the corpus wording or
    # the orchestrator's" is then "one of the corpus wording or null", which
    # null satisfies: the beat would pass against a deployment that cannot say
    # what it retrieved against.
    #
    # ADR-018's lesson, at this seam: an assertion that degrades to green when
    # the deployed build is older than the assertion is worse than no
    # assertion, because it is read as proof.
    spec = _code(CROSS_PLATFORM_SPEC)

    for name in ("retrievalQuery", "toolQuery"):
        assert f"expect({name}).toBeTruthy();" in _flat(CROSS_PLATFORM_SPEC), (
            f"the beat never requires {name} to be present, so a deployment "
            "that renders no evidence attribute passes on a null"
        )


# ---------------------------------------------------------------------------
# The evidence ledger and the ten-run proof (#54).
# ---------------------------------------------------------------------------


def test_the_ledger_is_written_on_every_run_not_only_on_failures():
    """A red-only ledger cannot measure an intermittent beat.

    Two runs in eight is a property of the *sequence*, and the denominator is
    the runs that passed. A ledger written from a failure handler records the
    numerator and silently discards the rest, which is how "it usually works"
    survived as a description for as long as it did.
    """
    spec = _code(CROSS_PLATFORM_SPEC)

    assert "recordRehearsal" in spec, "no run leaves any evidence behind"
    assert "test.afterEach" in spec, (
        "the evidence is not recorded from an afterEach hook, so a run that "
        "threw before the end of the test body records nothing — and those "
        "are the runs worth measuring"
    )
    for handler in ("test.afterAll", "onlyOnFailure", "if (testInfo.status"):
        assert handler not in spec or "recordRehearsal" not in spec.split(
            handler, 1)[1].split("});", 1)[0], (
            f"the ledger row is written under {handler}, so passing runs are "
            "missing from the denominator"
        )


def test_the_ledger_never_fails_a_run_it_only_observes():
    """Measurement that can break the thing it measures is not measurement.

    The validator's verdict is the browser's, and a full disk or a read-only
    artifacts directory must not turn a green beat red — nor a red one green.
    """
    evidence = _code(E2E / "evidence.ts")

    assert "catch" in evidence, (
        "evidence.ts has no catch: a write failure would propagate into the "
        "test result and the ledger would be able to fail the run"
    )


def test_the_outcome_distinguishes_no_tool_call_from_an_honest_miss():
    # The two failure modes are different bugs in different layers, and they
    # look identical in a screenshot: no answer from the corpus. One says the
    # orchestrator never called the tool; the other says it called it and the
    # index missed. A ledger that recorded only "failed" would have kept them
    # indistinguishable.
    evidence = _code(E2E / "evidence.ts")

    for outcome in ("grounded", "honest-miss", "no-tool-call", "clarified"):
        assert f"'{outcome}'" in evidence or f'"{outcome}"' in evidence, (
            f"the ledger cannot record the {outcome!r} outcome"
        )


def test_the_ten_run_proof_has_a_harness_and_it_is_not_a_loop():
    """`scripts/sop-rehearsal.sh` exists, runs, and stays out of CI.

    It drives the Demo validator ten times against a **running deployment**,
    holding ten real conversations with the agent pool. It is the Demo
    validator's own rule (see `docs/demo-validator.md`) multiplied by ten: a
    pull request cannot run it, and a scheduled run would spend Copilot
    Credits on nobody's behalf.
    """
    harness = REPO_ROOT / "scripts" / "sop-rehearsal.sh"

    assert harness.exists(), "nothing runs the ten-run proof"
    assert os.access(harness, os.X_OK), f"{harness.name} is not executable"

    workflows = (REPO_ROOT / ".github" / "workflows").glob("*.yml")
    for workflow in workflows:
        assert "sop-rehearsal" not in _text(workflow), (
            f"{workflow.name} runs the ten-run proof: it drives a real "
            "browser through ten conversations with the deployed agent pool"
        )


def test_the_proof_runs_the_loop_repeatedly_rather_than_repeat_each():
    # `--repeat-each` is in the walkthrough reporter's `filteredBy` list, so a
    # repeated run refuses to replace the Recorded fallback — and the recording
    # is what the presenter falls back to when the live demo fails. Ten runs of
    # the loop keep each run a whole, recordable walkthrough.
    harness = _text(REPO_ROOT / "scripts" / "sop-rehearsal.sh")

    assert "--repeat-each" not in harness, (
        "the proof uses --repeat-each, which the walkthrough reporter treats "
        "as a filter — ten runs would leave the Recorded fallback stale"
    )
    assert "e2e-tests.sh" in _text(REPO_ROOT / "scripts" / "sop_rehearsal.py"), (
        "the proof does not run the Demo validator itself"
    )


# ---------------------------------------------------------------------------
# The deployed build is the validator's first assertion (#48, ADR-018).
# ---------------------------------------------------------------------------

PROVENANCE = E2E / "deployedBuild.ts"
BUILD_CHECK = REPO_ROOT / "scripts" / "preflight" / "check-deployed-build.sh"


def test_the_build_is_checked_before_any_beat_runs():
    """ADR-018: "It is also the Demo validator's first assertion."

    A validator that proves seven beats against last month's code proves
    nothing, and the presenter needs to be told *"this is not the build you
    think it is"* before being told the beats are green. It cost a day once
    already: an integration branch was gated while the deployment served an
    image nine commits behind, the troubleshooting beat went red for the image,
    and the red was indistinguishable from a regression in the code.

    `globalSetup` rather than a spec, and this is not incidental. Playwright
    orders spec files by name, so "first" would rest on a filename; and a
    provenance beat inside the suite is a beat with no video and — if it were
    given its own project so it could be depended on — a second project. The
    **walkthrough reporter** refuses to replace the **Recorded fallback** for
    either, so the obvious shapes silently cost the presenter their fallback.
    """
    config = _code(CONFIG)

    assert PROVENANCE.exists(), (
        "nothing checks the deployed build before the beats run"
    )
    assert "globalSetup" in config, (
        "the build check is not wired as globalSetup, so the beats can run "
        "against an image nobody dated"
    )
    assert "deployedBuild" in config, (
        f"playwright.config.ts does not reach {PROVENANCE.name}"
    )


def test_the_build_check_is_not_a_second_project_or_a_beat():
    # The two shapes that would work and quietly delete the Recorded fallback.
    # `whyNotRecorded` refuses a run with more than one project, and refuses
    # one where any beat produced no video — and a provenance check drives no
    # browser.
    config = _code(CONFIG)

    assert config.count("name: '") == 2, (
        "a third project ran: the walkthrough reporter refuses a "
        "multi-project run, so the Recorded fallback stops being replaced"
    )
    assert not list(E2E.joinpath("specs").glob("*build*.spec.ts")), (
        "the build check is a spec: it produces a videoless beat, and the "
        "walkthrough reporter refuses to record a run containing one"
    )


def test_the_build_check_asks_the_preflight_rather_than_restating_it():
    # One description of the verdict. The preflight's decision logic is unit
    # tested without a tenant (`src/tests/ci/test_deployed_build.py`); a second
    # implementation in TypeScript is a second thing to disagree with it, which
    # is what `storeSurface.ts` and `authored.ts` both exist to prevent.
    provenance = _code(PROVENANCE)

    assert BUILD_CHECK.exists(), "the preflight check the validator calls is gone"
    assert BUILD_CHECK.name in provenance, (
        "the validator does not run the deployed-build preflight; it has its "
        "own copy of the verdict"
    )


def test_an_unproved_build_stops_the_run_as_firmly_as_a_drifted_one():
    # ADR-018's consequence, at this seam: "treating that as a pass would
    # rebuild the exact hole this closes". The check exits 3 for unknown and 1
    # for drift, and a setup that only refuses on 1 passes a deployment whose
    # images nobody could date.
    provenance = _flat(PROVENANCE)

    assert "!== 0" in provenance or "!= 0" in provenance, (
        "the setup grades the preflight's exit code selectively; only a zero "
        "exit is a proved build"
    )


def test_the_build_check_is_skipped_against_a_local_target():
    # `--target local` runs the same specs against a `npm run dev`. There is no
    # deployment to date, so a check that ran would refuse every local run.
    provenance = _code(PROVENANCE)

    assert "local" in provenance, (
        "the build check does not know about the local target, so "
        "`--target local` cannot run"
    )


def test_the_opt_out_is_a_deliberate_act_and_says_what_was_not_proved():
    # The Stage driver is presenter-facing, and it is what the presenter falls
    # back to when clicking through the walkthrough by hand goes wrong. A
    # refusal to start, mid-demonstration, over a one-commit drift is the check
    # doing more harm than the drift. So there is a way past it — an
    # environment variable nobody sets by accident, which prints what it did
    # not prove rather than pretending it did.
    provenance = _code(PROVENANCE)

    assert "E2E_SKIP_BUILD_CHECK" in provenance, (
        "there is no way past the build check; a one-commit drift stops a "
        "presenter mid-demonstration"
    )
    assert "NOT verified" in provenance or "not verified" in provenance, (
        "the opt-out is silent: a run that skipped the check looks exactly "
        "like one that passed it"
    )
