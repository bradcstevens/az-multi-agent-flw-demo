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
import subprocess

from sop_rehearsal import REHEARSED_BEAT

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E = REPO_ROOT / "e2e"
LOOP = REPO_ROOT / "scripts" / "e2e-tests.sh"
CONFIG = E2E / "playwright.config.ts"
AUTHORED = E2E / "authored.ts"
AGENTS = REPO_ROOT / "AGENTS.md"
INHERITED = REPO_ROOT / "tests" / "e2e-test"
STORE_SURFACE = E2E / "pages" / "StoreSurface.ts"
CROSS_PLATFORM_SPEC = E2E / "specs" / "cross-platform.spec.ts"
SPECS = tuple(sorted(E2E.joinpath("specs").rglob("*.spec.ts")))
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


def test_each_claimed_beat_has_a_spec_and_every_spec_is_reachable():
    """The validator runs every spec under its one authored directory.

    A spec added after this test must be covered without editing a roster here:
    the filesystem is the source of the set. The explicit names are the
    walkthrough beats this repository claims to demonstrate; an absent one is
    a claim with no browser assertion behind it.
    """
    names = {spec.name for spec in SPECS}
    claimed = {
        "cross-platform.spec.ts",
        "escalation.spec.ts",
        "troubleshooting.spec.ts",
        "workforce.spec.ts",
    }

    assert claimed <= names, (
        "the Demo validator claims beats with no browser spec: "
        f"{sorted(claimed - names)}"
    )

    config = _code(CONFIG)
    assert "testDir: './specs'" in config, (
        "the validator no longer selects the directory containing its specs"
    )
    assert "testMatch" not in config, (
        "the validator filters its spec directory, so an authored spec can be "
        "unreachable"
    )
    assert "testIgnore" not in config, (
        "the validator excludes files from its spec directory, so an authored "
        "spec can be unreachable"
    )
    for spec in SPECS:
        assert spec.suffixes == [".spec", ".ts"], (
            f"{spec.name} is not a Playwright default spec filename"
        )


def test_every_rebased_spec_leaves_rehearsal_evidence():
    # The run is an observation of a deployed build, so every beat writes a
    # result even when its assertion fails. Select from the filesystem-derived
    # set: the new specifications cannot land without the current recorder.
    rebased = {
        spec.name: spec
        for spec in SPECS
        if spec.name in {"escalation.spec.ts", "troubleshooting.spec.ts"}
    }
    assert set(rebased) == {"escalation.spec.ts", "troubleshooting.spec.ts"}
    for spec in rebased.values():
        source = _code(spec)
        assert "test.afterEach" in source, (
            f"{spec.name} records no result after a failing beat"
        )
        assert "recordRehearsal" in source, (
            f"{spec.name} has an afterEach but leaves no rehearsal evidence"
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


def _loop_argv(tmp_path, *args):
    """The `playwright test` argv `scripts/e2e-tests.sh` builds for `args`.

    Through a stub `npx` on `PATH`, because the seam the bug lived at is the
    argv and nothing else: asserting on the script's *text* would have passed
    for both spellings of `--project`, and running the real Playwright needs a
    browser this loop is not allowed to open.
    """
    binaries = tmp_path / "bin"
    binaries.mkdir(parents=True)
    argv_log = tmp_path / "argv"
    stub = binaries / "npx"
    stub.write_text(
        '#!/usr/bin/env bash\n'
        'if [ "${2:-}" = "test" ]; then\n'
        '  shift 1\n'
        '  printf "%s\\n" "$@" > "$ARGV_LOG"\n'
        'fi\n'
        'exit 0\n'
    )
    stub.chmod(0o755)

    environment = dict(os.environ)
    environment["PATH"] = f"{binaries}{os.pathsep}{environment['PATH']}"
    environment["ARGV_LOG"] = str(argv_log)
    subprocess.run(
        ["bash", str(LOOP), "--target", "local", *args],
        env=environment,
        check=True,
        capture_output=True,
    )
    return argv_log.read_text(encoding="utf-8").splitlines()


def test_the_loop_lets_a_spec_filter_through_instead_of_the_project_eating_it(
    tmp_path,
):
    """Playwright's `--project` is **variadic**, and the spec came after it.

    Found by review before it ever ran (#54). The rehearsal scopes each run to
    the rehearsed hit's spec, and `--project validator specs/…` made Playwright
    read the spec as a *second project name*:

        Error: Project(s) "specs/cross-platform.spec.ts" not found.

    Which is the worst available failure for this harness: ten runs that each
    exit non-zero without opening a browser, attributed to whatever the ledger
    last said. `--project=validator` binds the value to the flag and the
    positional survives as a filter.
    """
    argv = _loop_argv(tmp_path, REHEARSED_BEAT)

    assert REHEARSED_BEAT in argv, (
        "the spec filter never reached Playwright"
    )
    assert "--project" not in argv, (
        "the loop passes --project as two arguments, and Playwright's "
        "--project is variadic: it swallows the spec filter after it and the "
        "run dies with 'Project(s) not found'"
    )
    assert "--project=validator" in argv, (
        "the loop no longer names the validator project, so an unattended run "
        "would also run the headed Stage driver"
    )


def test_the_loop_can_filter_to_each_authored_spec(tmp_path):
    # `SPECS` is read from the filesystem above. A new spec must therefore
    # traverse the same argv seam without somebody adding it to a hand-written
    # test roster; otherwise it exists in the repository but cannot be run by
    # the validator loop.
    for spec in SPECS:
        filter_path = str(spec.relative_to(E2E))
        argv = _loop_argv(tmp_path / spec.stem, filter_path)

        assert filter_path in argv, (
            f"the loop cannot pass {spec.name} through to Playwright"
        )
        assert "--project" not in argv, (
            f"the project flag swallowed {spec.name} as another project name"
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


# ---------------------------------------------------------------------------
# The build a rehearsal's runs were about (#54).
# ---------------------------------------------------------------------------


def test_the_gate_publishes_the_build_it_verified():
    """A verdict nobody can read back is a verdict the ledger cannot record.

    The gate dates the deployment before a browser opens and then, until this,
    kept the answer to itself. The **rehearsal** is a claim about ten
    consecutive runs of *one* build, so the run has to be able to say which —
    and the gate is the only thing in the suite that has asked.
    """
    provenance = _code(PROVENANCE)

    assert "--json" in provenance, (
        "the setup reads the preflight's prose rather than its verdict, so "
        "the commit it verified can only be recovered by parsing a report"
    )
    assert "DEPLOYED_BUILD" in provenance and "BUILD_VERIFIED" in provenance, (
        "the setup does not publish what it verified, so the ledger row "
        "cannot name the build the run was about"
    )


def test_the_ledger_records_the_build_and_whether_it_was_verified():
    # The hole this closes: `E2E_SKIP_BUILD_CHECK` is offered by the gate's own
    # failure message — rightly, for a presenter mid-demonstration — and a
    # rehearsal run under it appended a row indistinguishable from a verified
    # one. Ten of those printed "the beat is proved".
    evidence = _code(E2E / "evidence.ts")

    assert "deployedBuild" in evidence, (
        "the ledger row cannot name the build the run observed"
    )
    assert "buildVerified" in evidence, (
        "a run that skipped the deployed-build gate is recorded exactly like "
        "one that passed it"
    )


def test_the_proof_refuses_a_streak_it_cannot_attribute_to_a_build():
    # The arithmetic is Python's, unit-tested without a tenant. What is
    # asserted here is only that it is *wired* to the fields the harness writes
    # — a ledger that records the build and a verdict that ignores it is the
    # same hole with a longer row.
    proof = _text(REPO_ROOT / "scripts" / "sop_rehearsal.py")

    assert "buildVerified" in proof and "deployedBuild" in proof, (
        "the ten-run proof never reads the build its runs were about"
    )


def test_the_cost_table_is_read_after_the_turn_not_when_the_panel_lights():
    """The ledger's `agentsBilled` was reading a table still filling up (#54).

    Measured 2026-08-14 against `rg-macae-flw-v1`, on the first rehearsal run
    that could name its build. The ledger recorded:

        agentsBilled: ["Store SOP Assistant"]

    while the cost table in that same run's DOM snapshot carried three rows —
    `Store SOP Assistant`, `Shift Tasks Agent` at 4,032 tokens, and
    `Troubleshooting Agent` at 6,906. The beat had failed `clarified`, and the
    ledger said the troubleshooter never ran.

    That is the precise wrong answer. `agentsBilled` was added to separate two
    fixes — *the troubleshooter must not run* from *the troubleshooter must not
    have the last word* — because guessing between them cost three deploys. A
    reader that under-reports it sends the next diagnosis to the first when the
    evidence says the second.

    The cause is that it was read in the block that fires when the **Grounding
    panel** arrives. That block is right for everything `source_used` carries:
    the whole frame lands at once, so reading it in one place is what stops a
    run that failed the first assertion from recording nothing about the rest.
    The cost table is not in that frame. It fills from `token_usage`, one frame
    per executor, as each agent finishes — all of it *after* the SOP tool
    answered and the panel lit. So it has to be read last.
    """
    spec = _code(CROSS_PLATFORM_SPEC)

    grounding_block = spec.split("waitForGrounding", 1)[1].split("finally", 1)[0]
    assert "agentsBilled" not in grounding_block, (
        "the cost table is read when the Grounding panel lights, which is "
        "before the specialists have run — the ledger under-reports who was "
        "billed and names the wrong fix"
    )

    after_each = spec.split("test.afterEach", 1)[1].split("});", 1)[0]
    assert "agentsBilled" in after_each, (
        "nothing reads the cost table at the end of the turn, so the ledger "
        "cannot say which agents the turn billed"
    )


def test_reading_the_cost_table_can_never_fail_the_beat():
    # The ledger observes the run; it must not be able to decide it. A page
    # closed by a timeout, a rail that never rendered — neither is a reason to
    # turn a green beat red, and `recordRehearsal` already follows this rule.
    spec = _code(CROSS_PLATFORM_SPEC)
    after_each = spec.split("test.afterEach", 1)[1].split("recordRehearsal", 1)[0]

    assert "catch" in after_each, (
        "the end-of-turn read is unguarded: a page that has gone away would "
        "fail the beat from inside the measurement"
    )


# ---------------------------------------------------------------------------
# The fourth specialist's beat (#52, ADR-017).
# ---------------------------------------------------------------------------

WORKFORCE_SPEC = E2E / "specs" / "workforce.spec.ts"


def test_the_fourth_specialist_has_a_beat_of_its_own():
    """#52: "The beat is asserted by the browser suite."

    A specialist nothing drives is a specialist nobody has watched answer. The
    spec is a spec rather than another assertion inside the hop's, because the
    two beats fail for unrelated reasons and a shared one would attribute
    either failure to whichever ran first — the mistake #54 spent a day on.
    """
    assert WORKFORCE_SPEC.exists(), (
        "the fourth specialist's beat is asserted by no browser spec"
    )


def test_the_beat_reads_its_question_out_of_the_store_pack():
    # Never restated. The Quick Task's title and prompt are authored in
    # `content_packs/`, and a spec carrying its own copy passes a rename it
    # never saw — `authored.ts` exists precisely so no spec has to.
    spec = _code(WORKFORCE_SPEC)

    assert "quickTaskNamed" in spec or "quickTasks" in spec, (
        "the beat does not read its Quick Task out of the store pack"
    )
    assert "How do I swap a shift" not in spec, (
        "the beat restates the prompt the store pack authors; a reworded card "
        "would leave it tapping a button that is not there"
    )


def test_the_beat_asserts_the_boundary_it_was_allowed_to_cross():
    # ADR-017's whole risk, and the only assertion here that is about safety
    # rather than about the feature. The **Identity boundary gate** has a live
    # similarity tier, and a process question phrased near the personal probes
    # can be refused on stage. A refusal renders as the **Policy block**, so
    # the beat watches for it by name rather than timing out on an answer that
    # was never going to come.
    spec = _code(WORKFORCE_SPEC)

    assert "policyBlock" in spec, (
        "the beat does not check that the gate admitted the question, so a "
        "refusal on stage reads as a slow surface"
    )


def test_the_beat_grades_the_meter_rather_than_the_answer():
    # The same rule the hop's beat follows: model prose is asserted only to
    # have arrived. What says the *fourth specialist* answered is the cost
    # table — the panel the presenter is looking at — not the wording of the
    # reply.
    spec = _code(WORKFORCE_SPEC)

    assert "agentsBilled" in spec, (
        "the beat never reads which agents the turn billed, so it passes when "
        "the manager routes the question to somebody else"
    )
    assert "WorkforceAgent" in spec, (
        "the beat does not name the agent it exists to watch answer"
    )
