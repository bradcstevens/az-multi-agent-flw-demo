"""The frontend tests run in CI, and keep running there.

Issue #24. vitest, React Testing Library and jsdom were fully configured in the
accelerator baseline and **no test file existed and no workflow ran them** — a
test loop that is present but never invoked is indistinguishable from one that
is absent, right up until the moment it would have caught something.

These are CI-tooling tests: the subject is the repository's own wiring, read
from disk as text. Deliberately no YAML parser — the repo's other workflow
assertions read text too, and this suite should not be the reason a dependency
has to be added to `.github/requirements.txt`.

They fail if the frontend suite is ever quietly disconnected: by dropping the
workflow, by narrowing its paths so a frontend change no longer triggers it, by
running the tests before installing, or by pointing it at the watching form of
vitest, which in CI is a job that never finishes.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
APP = REPO_ROOT / "src" / "App"
PACKAGE_JSON = APP / "package.json"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "frontend-tests.yml"
LOOP = REPO_ROOT / "scripts" / "frontend-tests.sh"

RUN_TESTS = "npm run test:run"
INSTALL = "npm ci"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_there_is_a_non_watching_test_script():
    # `vitest` alone watches. In CI that is a job that never finishes; the run
    # form is what a loop and a workflow can both call.
    scripts = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["scripts"]

    assert scripts["test:run"] == "vitest run"


def test_a_workflow_runs_the_frontend_tests():
    assert WORKFLOW.exists(), "no workflow runs the frontend tests"
    assert RUN_TESTS in _workflow_text(), "the frontend workflow does not run the tests"


def test_the_workflow_installs_dependencies_before_running_them():
    text = _workflow_text()

    assert text.index(INSTALL) < text.index(RUN_TESTS), (
        "the frontend workflow runs tests before installing"
    )


def test_the_workflow_triggers_on_a_frontend_change():
    # Once under `push`, once under `pull_request`. A workflow that only fires
    # on one of them is a suite a pull request can walk straight past.
    assert _workflow_text().count("'src/App/**'") >= 2, (
        "a frontend change does not trigger the frontend tests on both events"
    )


def test_the_contract_between_the_two_ends_is_asserted_somewhere():
    # `transparency.test.ts` hand-writes the payloads it expects, so it cannot
    # notice a rename on the backend. `test_transparency_contract.py` is what
    # spans that seam.
    contract = Path(__file__).with_name("test_transparency_contract.py")

    assert contract.exists(), (
        "nothing asserts that the backend's transparency payloads and the "
        "browser's parsers still agree"
    )


def test_the_mocked_unlock_contract_is_asserted_somewhere():
    # The same seam for the **Personal answer** (#27). A card that fails to
    # render says nothing at the moment the presenter has just told the room the
    # sign-in changed something, which turns the closing beat into its opposite.
    contract = Path(__file__).with_name("test_personal_answer_contract.py")

    assert contract.exists(), (
        "nothing asserts that the backend's personal answer and the browser's "
        "parser still agree"
    )


def test_the_reviewable_plan_contract_is_asserted_somewhere():
    contract = Path(__file__).with_name("test_plan_approval_contract.py")

    assert contract.exists(), (
        "nothing asserts that Reviewable-plan person steps survive the backend-to-browser seam"
    )


def test_a_change_to_either_end_of_the_contract_runs_the_contract_test():
    # The contract test runs in `test.yml`, which triggers on Python paths — so
    # a backend rename runs it. A *frontend* rename would not have, because
    # `frontend-tests.yml` runs vitest alone and vitest cannot see the backend.
    # These two files are therefore named in `test.yml` explicitly, and only
    # these two: widening it to `src/App/**` would run the backend suite for a
    # CSS edit, which is the reason the two workflows are separate at all.
    text = (REPO_ROOT / ".github" / "workflows" / "test.yml").read_text(
        encoding="utf-8"
    )

    # `ticket.ts` (#22) is here for exactly the same reason as `transparency.ts`
    # — `test_ticket_contract.py` is the only thing that spans the socket for
    # the Simulated ticket, and the vitest suite hand-writes its payloads.
    # `rehearsedReply.ts` (#26) is here for the third time for the same
    # reason: `test_store_pack.py` is the only thing that reads the browser's
    # reader and the authored pack together, and vitest cannot see the pack.
    # `personalAnswer.ts` and `signedInDevice.ts` (#27) are the fourth:
    # `test_personal_answer_contract.py` spans the socket for the Mocked
    # unlock, and it is also the only thing that checks the browser authors no
    # associate's name of its own.
    for path in (
        "src/App/src/models/transparency.ts",
        "src/App/src/models/ticket.ts",
        "src/App/src/models/enums.tsx",
        "src/App/src/models/rehearsedReply.ts",
        "src/App/src/models/personalAnswer.ts",
        "src/App/src/models/signedInDevice.ts",
        "src/App/src/models/plan.tsx",
        "src/App/src/store/PlanDataService.tsx",
    ):
        assert text.count(f"'{path}'") >= 2, (
            f"a change to {path} does not run the transparency contract test on "
            "both push and pull_request"
        )

    assert "'src/App/**'" not in text, (
        "test.yml triggers on the whole frontend — a CSS edit now runs the "
        "backend suite"
    )


def test_the_frontend_tests_are_a_declared_feedback_loop():
    assert LOOP.exists(), "there is no frontend tests loop script"
    assert RUN_TESTS in LOOP.read_text(encoding="utf-8"), (
        "the frontend tests loop does not run the tests"
    )

    agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "scripts/frontend-tests.sh" in agents_md, (
        "the frontend tests loop is not in the AGENTS.md feedback loops table"
    )


def test_there_are_frontend_tests_to_run():
    tests = list(APP.glob("src/**/*.test.ts")) + list(APP.glob("src/**/*.test.tsx"))

    assert tests, "the frontend test script has nothing to run"
