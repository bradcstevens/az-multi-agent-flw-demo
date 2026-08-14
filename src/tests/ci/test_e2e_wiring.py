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
# The two hardest beats (#50)
# ---------------------------------------------------------------------------
TROUBLESHOOTING = E2E / "specs" / "troubleshooting.spec.ts"
ESCALATION = E2E / "specs" / "escalation.spec.ts"
WIRE = E2E / "wire.ts"
BACKEND_READS = E2E / "backend.ts"


def test_the_two_hardest_beats_are_under_test():
    # The demonstration's strongest single claim — that the assistant remembers
    # what you tried — is the pair most worth having a browser assert.
    assert TROUBLESHOOTING.exists(), "the troubleshooting beat has no spec"
    assert ESCALATION.exists(), "the escalation beat has no spec"


def test_the_absence_claims_are_graded_on_the_wire():
    # "Asked only while a question is pending", "one confirmation, not two",
    # "never asked a second time" are all claims about things that do *not*
    # happen. A locator that is not there is equally the surface not having
    # rendered yet, so the frames are recorded and counted instead.
    assert WIRE.exists(), "nothing records the frames the browser received"
    for spec in (TROUBLESHOOTING, ESCALATION):
        assert "recordWire" in _code(spec), (
            f"{spec.name} makes its absence claims without reading the wire"
        )


def test_the_lane_and_the_record_are_read_server_side():
    # The badge is the browser's own recollection of what the router said, and
    # the chat is the associate's own words read back to them. A surface
    # rendering `Deliberate` over a request that went down the Fast lane is
    # exactly the failure neither can see.
    assert BACKEND_READS.exists(), "the suite has no server-side reads"
    escalation = _code(ESCALATION)

    assert "laneTaken" in escalation, (
        "the escalation beat does not read the lane from server-side state"
    )
    assert "attemptedSteps" in escalation, (
        "the ticket's attempted steps are not compared against the record the "
        "container holds"
    )


def test_the_ticket_and_the_lane_are_read_out_of_the_backend():
    # ADR-019's lesson again: the ticket prefix and the lane's name live in the
    # backend's own modules, and a validator repeating either passes a rename
    # it never saw.
    authored = _code(AUTHORED)

    assert "'escalation', 'ticket.py'" in authored, (
        "the ticket's number and its 'not reported' are not read out of the "
        "module that renders them"
    )
    assert "'lane', 'lane.py'" in authored, (
        "the Deliberate lane's name is not read out of the module that routes "
        "to it"
    )


def test_the_rejected_branch_is_asserted():
    # Where this requirement fails silently: a ticket raised from a plan the
    # associate declined dispatches an engineer against a repair nobody
    # authorised, and the surface has already navigated away.
    escalation = _code(ESCALATION)

    assert "rejected" in escalation, "nothing asserts what a rejected plan raises"


def test_the_walkthrough_is_never_retried():
    # A retry turns an intermittently-working demonstration into a green run,
    # and the presenter finds out in the room.
    assert "retries: 0" in _code(CONFIG), "the validator retries its walkthrough"
