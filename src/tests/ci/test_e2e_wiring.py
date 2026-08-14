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
CROSS_PLATFORM_SPEC = E2E / "specs" / "01-cross-platform.spec.ts"
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


# ---------------------------------------------------------------------------
# The walkthrough's order, and the beats added by #49.
# ---------------------------------------------------------------------------

SPECS = E2E / "specs"
RUNBOOK = REPO_ROOT / "docs" / "presenter-runbook.md"
HONEST_MISS_SPEC = SPECS / "02-honest-miss.spec.ts"
BOUNDARY_SPEC = SPECS / "05-boundary.spec.ts"
UNLOCK_SPEC = SPECS / "06-sign-in-unlock.spec.ts"
ALERT_SPEC = SPECS / "07-shift-task-alert.spec.ts"
PLAN_SURFACE = E2E / "pages" / "PlanSurface.ts"
TRANSPARENCY_RAIL = E2E / "pages" / "TransparencyRail.ts"
TOKEN_METER = (
    REPO_ROOT
    / "src"
    / "App"
    / "src"
    / "components"
    / "transparency"
    / "TokenMeterPanel.tsx"
)

#: What the Token meter renders for a cost nobody reported.
NOT_REPORTED = "\u2014"


def _taps() -> dict[int, str]:
    """The presenter runbook's taps, in the order the presenter makes them."""
    return {
        int(number): title.strip()
        for number, title in re.findall(
            r"^### (\d+)\. (.+)$", _text(RUNBOOK), flags=re.MULTILINE
        )
    }


def test_the_recording_plays_the_walkthrough_in_the_presenters_order():
    """A spec file is named for the tap it asserts, so the fallback is in order.

    The **Recorded fallback** is "the beats in order, one after another" — the
    reporter says so and the presenter is handed it. But it reads the beats off
    the run, and Playwright runs spec *files* in path order, which is
    alphabetical. Left to the alphabet the recording opens on the boundary
    refusal, plays the cross-platform hop third and shows the sign-in unlock
    before the wall it is a door in: the walkthrough shuffled, which is worse
    than no recording because it looks exactly like one.

    So the number is in the filename, and it is the runbook's own tap number
    rather than a second ordering invented here.
    """
    taps = _taps()
    assert taps, "the presenter runbook no longer numbers its taps"

    specs = sorted(path.name for path in SPECS.glob("*.spec.ts"))
    assert specs, "there are no beats"

    for name in specs:
        match = re.match(r"^(\d\d)-", name)
        assert match, (
            f"{name} carries no tap number, so where it lands in the Recorded "
            "fallback is whatever the alphabet decides"
        )
        assert int(match.group(1)) in taps, (
            f"{name} is numbered for a tap the presenter runbook does not "
            f"make; its taps are {sorted(taps)}"
        )

    numbers = [int(name[:2]) for name in specs]
    assert numbers == sorted(numbers), "the specs do not sort into tap order"
    assert len(set(numbers)) == len(numbers), (
        "two beats claim the same tap, so which one plays first is undefined"
    )


def test_the_honest_miss_is_asserted_as_an_explicit_miss():
    """An empty panel, a missing panel and an honest miss are three states.

    From the browser the first two look alike, and the third looks like either
    of them to any assertion phrased as *the citation list is empty*. They mean
    entirely different things: no `source_used` arrived at all (the orchestrator
    never called the tool), the panel is not on the page (the image is old, or
    the rail did not render), and the SOP agent searched Dataverse and honestly
    found nothing — which is the beat, working.

    So the beat reads all of them and fails naming which one happened. It is
    the lesson `docs/demo-validator.md` records for the rehearsed hit, where
    asserting only on the citation "reports a miss as an empty string, which
    reads like a broken selector and sends the reader to the wrong place".
    Here the miss is the *expected* outcome, so the wrong place is every other
    layer in the stack.
    """
    spec = _flat(HONEST_MISS_SPEC)

    assert "grounding-miss" in _flat(TRANSPARENCY_RAIL), (
        "the rail no longer locates the honest miss"
    )
    assert "honestMiss" in spec, (
        "the beat never reads the Grounding panel's honest-miss state, so a "
        "panel that arrived empty passes as the rehearsed miss"
    )
    assert "groundingEmpty" in spec, (
        "the beat cannot tell an honest miss from a panel nothing ever "
        "reached: it never reads the empty state"
    )
    assert "groundingPanel" in spec, (
        "the beat never asserts the panel is on the page, so a rail that did "
        "not render is graded as a miss"
    )


def test_the_honest_miss_is_the_corpus_question_the_corpus_cannot_answer():
    """Read from `[honest_miss]`, never restated here or in the spec.

    The whole beat is *this question is not in the library*, and the corpus is
    the only thing that decides that. A validator that wrote the question down
    would keep asserting a miss after somebody added a car-wash procedure —
    reporting the corpus as unchanged for the one change that breaks the beat.
    """
    authored = _code(AUTHORED)
    spec = _code(HONEST_MISS_SPEC)

    assert "honest_miss" in authored, (
        "authored.ts does not read the corpus's [honest_miss] section"
    )
    assert "honestMiss()" in spec, (
        "the honest-miss beat does not read the corpus's rehearsed miss"
    )
    assert "car wash" not in spec.lower(), (
        "the beat restates the rehearsed miss instead of reading it out of "
        "corpus.toml"
    )


# ---------------------------------------------------------------------------
# The boundary refusal and the sign-in unlock (beats 5 and 6).
# ---------------------------------------------------------------------------


def test_the_refusal_is_asserted_before_any_agent_ran():
    """A refused request costs nothing *because nothing ran*.

    The claim the presenter makes over this beat is "refused by code, before
    any agent ran and before a single token was spent". A beat that only reads
    the gate's own row proves the first half and assumes the second: an
    orchestration that ran and *also* refused leaves the guardrail row reading
    a truthful zero and is graded green.

    So what is asserted is the shape of the whole table — the gate's row is the
    **only** row — and that no plan was raised. Both are browser-observable and
    neither is anybody's wording.
    """
    spec = _flat(BOUNDARY_SPEC)

    assert "toHaveLength(1)" in spec, (
        "the beat does not assert the gate's row is the only row, so an "
        "orchestration that ran and then refused is graded as a refusal that "
        "cost nothing"
    )
    assert "REFUSED" in spec, (
        "the beat does not identify the gate's row by the meter it is on, so "
        "it cannot tell the gate's zero from an agent's"
    )
    assert "/plan/" in spec, (
        "the beat never asserts the refusal raised no plan; a refusal that "
        "navigated is a refusal the orchestrator had already been handed"
    )


def test_the_refusals_zero_is_asserted_to_be_a_measurement():
    """`0` and `—` are the panel's two ways of being empty, and only one is this.

    `models/meter.ts` states the rule this beat exists to prove: "a refused
    request adds nothing to the meter, and the row that proves it only proves
    it if nothing is the only thing that looks like nothing". A beat that
    asserted the row is *present* passes on a pair of em dashes — the panel
    saying nobody reported a cost, which is exactly what it says about the
    Copilot Studio row's tokens, and which proves nothing about the gate.

    Both matchers are here on purpose and neither is redundant. `—` means the
    surface stopped distinguishing *not reported* from *nothing*; a number
    means the gate billed something. Different defects, different fixes, and a
    shared failure message would send the reader to one of them.
    """
    spec = _flat(BOUNDARY_SPEC)

    assert NOT_REPORTED in _text(TOKEN_METER), (
        "the Token meter no longer renders an em dash for an unreported cost; "
        "the beat below is asserting against a rule the surface dropped"
    )
    assert NOT_REPORTED in spec, (
        "the beat never mentions what the panel renders for a cost nobody "
        "reported, so it cannot be asserting the difference"
    )
    assert ".not.toBe(NOT_REPORTED)" in spec.replace(" ", ""), (
        "the beat does not refuse an em dash: a refusal whose cost the panel "
        "stopped reporting is graded as a refusal that cost nothing"
    )
    assert ".toBe('0')" in spec.replace(" ", ""), (
        "the refusal's cost is not asserted to be a measured zero"
    )
    for column in ("tokens", "credits"):
        assert f"refusal.{column}" in spec, (
            f"the beat never reads the refusal's {column} column, so half of "
            "the two-meter claim is unasserted"
        )


def test_the_door_is_asserted_to_be_inside_the_wall():
    """The sign-in renders **within** the refusal, not beside it.

    The runbook says it out loud — "it is deliberately not a separate login
    screen" — because the beat is the delta between one surface and the next.
    A page-wide lookup for the button passes just as happily against a sign-in
    rendered in the header, which is the same demonstration with its closing
    argument removed.
    """
    spec = _flat(UNLOCK_SPEC)
    page_object = _flat(STORE_SURFACE)

    assert "policyBlock.getByTestId('sign-in-to-continue')" in page_object, (
        "StoreSurface looks the sign-in up across the whole page, so a button "
        "rendered anywhere at all satisfies 'inside the refusal'"
    )
    assert "toHaveCount(1)" in spec, (
        "the beat does not assert there is exactly one sign-in on the page; a "
        "second one beside the refusal is invisible to it"
    )


def test_the_unlock_re_asks_the_words_the_gate_refused():
    """The same words, read off the request rather than off the screen.

    "The same question, unedited" is the whole beat: the audience has to see
    one set of words refused and the identical set answered. Nothing on the
    surface shows the question twice — the box is cleared by the refusal — so
    the only place the claim is observable is the request the browser sent.

    Asserted on `process_request`'s own body, which is neither model prose nor
    the store pack's: it is what the surface asked, which is the claim.
    """
    spec = _flat(UNLOCK_SPEC)
    page_object = _flat(STORE_SURFACE)

    assert "apiEndpoint('PROCESS_REQUEST')" in page_object, (
        "StoreSurface does not read the route it watches out of the surface's "
        "own endpoint table; a versioned route renamed in one place would "
        "leave the beat observing no traffic and reporting it as no re-ask"
    )
    assert "description" in page_object, (
        "the watcher reads no question out of the request it recorded"
    )
    assert "watchQuestionsAsked" in spec, (
        "the beat does not watch what the surface asked, so 'the same words' "
        "is asserted against nothing"
    )
    assert "toBe(refusedWords)" in spec, (
        "the beat does not assert the second asking is the words the gate "
        "refused; a re-ask of anything at all satisfies it"
    )
    assert "simulated-badge" in spec, (
        "the unlocked answer is not asserted to carry its simulated "
        "labelling; a stakeholder who finds that out afterwards stops "
        "believing the panels that are real"
    )


def test_a_sign_in_that_signs_nobody_in_is_asserted_not_to_re_ask():
    """The failure the surface fails *closed* on, asserted by making it happen.

    `HomeInput` states it: "a sign-in that signed nobody in does not re-ask.
    Asking again anonymously would show the identical refusal a second time and
    read on stage as the tap having done nothing at all." That branch runs only
    when the sign-in route fails, which a healthy deployment never does — so
    the beat has to break it deliberately, and a beat that does not is a
    requirement asserted by reading the code that implements it.
    """
    spec = _flat(UNLOCK_SPEC)

    assert "page.route(" in spec or "context.route(" in spec, (
        "the beat never fails the sign-in, so the fails-closed branch is "
        "asserted only by hoping it is never reached"
    )
    assert "sign_in" in spec, (
        "the beat intercepts something other than the sign-in route"
    )


# ---------------------------------------------------------------------------
# The shift-task alert and the hidden chord (beat 7).
# ---------------------------------------------------------------------------


def test_the_alert_is_asserted_to_be_an_alert_and_not_a_reply():
    """The beat is that a proactive message is a *different object*.

    `PresenterAlertCard` says why: "an alert is not a reply. It answers no
    question, because nobody asked one — that is the entire beat". Rendered
    among the replies it reads as an answer to whatever was asked last, "which
    is worse than not showing it".

    So the beat asserts the two signals that make it a different object — the
    ARIA role a screen reader hears and the message kind the DOM carries — and
    asserts it is outside the reply stream. A beat that only asserted the card
    is *visible* passes on the failure the card was designed against.
    """
    spec = _flat(ALERT_SPEC)

    assert "toHaveRole('alert')" in spec or "getByRole('alert')" in spec, (
        "the alert is not asserted to be an alert; a card that lost its role "
        "is announced to a screen reader as one more paragraph of reply"
    )
    assert "data-message-kind" in spec, (
        "the alert's message kind is unasserted, so the DOM's own statement "
        "that this is not a reply can be dropped without going red"
    )
    assert "agentTurns" in spec, (
        "the beat never asserts the alert is outside the reply stream, so an "
        "alert rendered among the answers passes"
    )
    assert "AI Agent" in spec, (
        "the beat does not check the alert is free of an agent's byline; a "
        "card wearing one is a reply whatever its role attribute says"
    )


def test_the_chord_is_read_out_of_the_repository_not_typed_into_the_beat():
    """`PRESENTER_CHORD_LABEL` is the chord's only public statement.

    It is what the runbook prints and what the presenter memorises. A beat with
    the combination typed into it goes red on a *working* demonstration the day
    somebody moves the chord off a key a European layout needs — the failure
    this whole suite exists not to produce.
    """
    authored = _code(AUTHORED)
    spec = _code(ALERT_SPEC)

    assert "PRESENTER_CHORD_LABEL" in authored, (
        "authored.ts does not read the chord off the label the presenter is "
        "given"
    )
    assert "presenterChord()" in spec, (
        "the alert beat does not read the chord out of the repository"
    )
    assert "Ctrl + Alt + Shift" not in spec, (
        "the beat restates the chord instead of reading it"
    )


def test_the_chord_is_asserted_not_to_fire_on_auto_repeat_or_under_altgr():
    """The two ways the chord fires when nobody meant it to.

    Both are already unit-tested in jsdom, and that is exactly why they are
    here as well. `CONTEXT.md` records the finding this suite was built for:
    every transparency signal was dropped in the browser while 223 frontend
    tests were green. A pure predicate passing in jsdom says the rule was
    written; only the running image says it is *deployed*.

    An auto-repeat POSTs an alert every repeat interval, and a stack of
    identical cards on stage reads as a bug rather than a beat. AltGr is worse:
    on Windows and several European layouts it is reported as Ctrl+Alt, so the
    chord would fire mid-sentence while the presenter typed an accented
    character into the question box.
    """
    spec = _flat(ALERT_SPEC)

    assert "repeat: true" in spec, (
        "the beat never dispatches an auto-repeat, so a chord that fires on "
        "every repeat interval passes"
    )
    assert "altGraph: true" in spec, (
        "the beat never dispatches the AltGr combination a European layout "
        "produces, so a chord that fires while the presenter types an "
        "accented character passes"
    )
    assert "modifierAltGraph" in _flat(PLAN_SURFACE), (
        "the synthetic dispatch does not set the AltGraph modifier state, so "
        "the AltGr negative is asserting an ordinary chord press"
    )


def test_the_chords_negatives_are_not_vacuous():
    """A negative asserted through a mechanism that never works proves nothing.

    Neither `repeat` nor `AltGraph` can be produced by driving a real keyboard,
    so both negatives are dispatched as synthetic `KeyboardEvent`s. If a
    synthetic event did not reach the listener at all — a hardened build, a
    listener moved onto a React root, an `isTrusted` check added — both
    negatives would pass for the wrong reason, and would go on passing after
    the chord itself broke.

    So the same synthetic event is dispatched *without* either flag and is
    required to fire. That control is what makes the two silences mean
    something.
    """
    spec = _flat(ALERT_SPEC)

    assert "control" in _text(ALERT_SPEC), (
        "the beat does not explain why its negatives are believable"
    )
    dispatches = spec.count("dispatchPresenterChord(")
    assert dispatches >= 3, (
        "fewer than three synthetic dispatches: the beat cannot be running "
        "both negatives and the control that proves they are not vacuous "
        f"(found {dispatches})"
    )
    assert "toBeGreaterThan" in spec, (
        "the control never requires the synthetic chord to fire, so a build "
        "that ignores synthetic events passes every negative here"
    )
