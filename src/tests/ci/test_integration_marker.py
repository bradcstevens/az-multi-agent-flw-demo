"""The `integration` marker is deselected everywhere tests run unattended.

The Guardrail corpus (#13) and the agent-template suite score against live
Azure. Both carry the `integration` marker the repo declares in
`pyproject.toml`, and both must stay out of the Backend tests loop and
`test.yml` — an unattended run has no subscription, and a suite that silently
skipped would report green without having asked anything.

These are CI-tooling tests: the subject is the repository's own tooling, read
from disk.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_TESTS_LOOP = REPO_ROOT / "scripts" / "backend-tests.sh"
TEST_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"

DESELECTION = re.compile(r"""-m\s+["']not integration["']""")
PYTEST_INVOCATION = re.compile(r"^\s*(?:\"\$VENV_PYTHON\"|python) -m pytest .*$", re.MULTILINE)


def _pytest_invocations(script: Path) -> list[str]:
    """Every pytest command line in a script, joined across line continuations."""
    text = script.read_text(encoding="utf-8").replace("\\\n", " ")
    return [line.strip() for line in PYTEST_INVOCATION.findall(text)]


def test_the_marker_is_declared_so_it_can_be_deselected():
    assert "integration: marks tests as requiring a live Azure" in (
        PYPROJECT.read_text(encoding="utf-8")
    )


def test_the_backend_tests_loop_deselects_the_integration_marker():
    invocations = _pytest_invocations(BACKEND_TESTS_LOOP)

    assert invocations, "no pytest invocation found in the Backend tests loop"
    for invocation in invocations:
        assert DESELECTION.search(invocation), (
            f"Backend tests loop runs live-Azure tests: {invocation}"
        )


def test_the_test_workflow_deselects_the_integration_marker():
    invocations = _pytest_invocations(TEST_WORKFLOW)
    backend = [line for line in invocations if "src/tests/backend" in line]

    assert backend, "no backend pytest invocation found in test.yml"
    for invocation in backend:
        assert DESELECTION.search(invocation), (
            f"test.yml runs live-Azure tests: {invocation}"
        )
