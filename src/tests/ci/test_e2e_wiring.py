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

    assert "video: 'on'" in config, "video is not recorded on passing runs"
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
