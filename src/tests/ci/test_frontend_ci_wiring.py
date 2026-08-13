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
