"""The Stage driver is the validator's second project, not a second suite.

Issue #51, [ADR-016](../../../docs/ADR/016-typescript-playwright-for-the-demo-validator.md).

Same shape and same reason as `test_e2e_wiring.py`: the browser suite needs a
running deployment, so what CI can assert is the *wiring* — read off disk as
text, with comments stripped so a rule named only in prose cannot satisfy it.

What these defend is the difference between a stage driver and a second
description of the walkthrough:

- The driver is a `projects` entry over the **same** `testDir`, headed and
  paced. Two suites would be two things to keep true, and they would disagree.
- Choosing it is **one switch on the loop script**. A driver that needs a spec
  edited is a driver nobody reaches for at 11:40 on the morning.
- The **recording** is collected into a predictable place by a reporter that
  reads the run, so it covers every beat that existed when it was produced —
  and only a run in which every beat passed replaces it. A fallback recording
  of a broken demonstration is worse than no fallback at all.
- Dropping the driver leaves the validator working. It is presenter-facing and
  the first thing to cut.
"""

from pathlib import Path
import os
import re
import shutil
import subprocess

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E = REPO_ROOT / "e2e"
LOOP = REPO_ROOT / "scripts" / "e2e-tests.sh"
CONFIG = E2E / "playwright.config.ts"
STAGE = E2E / "stage.ts"
REPORTER = E2E / "reporters" / "walkthrough.ts"
SPECS = E2E / "specs"
DOC = REPO_ROOT / "docs" / "stage-driver.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(path: Path) -> str:
    """A TypeScript or shell file's code, with its comments stripped."""
    source = re.sub(r"/\*.*?\*/", "", _text(path), flags=re.DOTALL)
    source = re.sub(r"^\s*//.*$", "", source, flags=re.MULTILINE)
    return re.sub(r"^\s*#(?!!).*$", "", source, flags=re.MULTILINE)


def test_the_driver_is_a_project_over_the_validators_specs():
    config = _code(CONFIG)

    assert "name: 'stage'" in config, "no Stage driver project"
    assert "name: 'validator'" in config, (
        "the validator project is gone: dropping the driver must leave it working"
    )
    assert config.count("testDir") == 1, (
        "more than one testDir: the walkthrough is described in two places"
    )


def test_the_driver_is_headed_and_paced():
    config = _code(CONFIG)
    stage = _code(STAGE)

    assert "headless: false" in config, "the Stage driver is not headed"
    assert "slowMo" in config, "the Stage driver has no pacing to narrate over"
    assert "PACE_MS" in stage, (
        "the pace is not adjustable: a rehearsal that runs too fast to narrate "
        "over is a rehearsal of nothing"
    )


def _run_loop(tmp_path, *args, env_extra=None):
    """Run the loop script with a stub toolchain and return the argv it built.

    The script's job is to turn switches into a Playwright command line, so the
    test asks it for one rather than reading the source and believing it. `npx`,
    `npm` and `az` are stubbed onto PATH — nothing here installs a browser or
    dials a subscription — and the stub records each invocation.
    """
    stubs = tmp_path / "bin"
    stubs.mkdir(parents=True)
    log = tmp_path / "invocations"
    for name in ("npx", "npm", "az"):
        stub = stubs / name
        stub.write_text(
            "#!/bin/sh\n"
            f'printf "%s|%s|%s\\n" "{name}" "$E2E_TARGET" "$*" >> "{log}"\n',
            encoding="utf-8",
        )
        stub.chmod(0o755)

    env = {
        **os.environ,
        "PATH": f"{stubs}:{os.environ['PATH']}",
        "E2E_BASE_URL": "https://example.invalid",
        **(env_extra or {}),
    }
    completed = subprocess.run(
        ["bash", str(LOOP), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    runs = [line.split("|") for line in lines]
    tests = [
        run for run in runs
        if run[0] == "npx" and run[2].startswith("playwright test")
    ]
    assert tests, f"the loop never ran the suite: {runs}"
    tool, target, argv = tests[-1]
    return tool, target, argv.removeprefix("playwright ")


def test_the_switch_selects_the_driver_and_the_default_selects_the_validator(tmp_path):
    _, _, driver = _run_loop(tmp_path / "stage", "--stage")
    assert "--project stage" in driver, driver

    _, _, default = _run_loop(tmp_path / "default")
    assert "--project validator" in default, (
        "an unattended run must not open a browser window on somebody's screen"
    )


def test_the_driver_runs_against_either_target(tmp_path):
    # The switch and the target compose: neither shadows the other.
    _, deployed, argv = _run_loop(tmp_path / "deployed", "--stage")
    assert deployed == "deployed" and "--project stage" in argv

    _, local, argv = _run_loop(tmp_path / "local", "--stage", "--target", "local")
    assert local == "local", "--stage swallowed the target"
    assert "--project stage" in argv

    _, joined, argv = _run_loop(tmp_path / "joined", "--target=local", "--stage")
    assert joined == "local" and "--project stage" in argv


def test_a_project_of_the_callers_own_is_not_doubled(tmp_path):
    # Two `--project` flags is a union in Playwright, not an override: both
    # projects run, every beat is recorded twice, and the recording is refused.
    _, _, argv = _run_loop(
        tmp_path / "own", "--stage", "--", "--project=validator", "--list"
    )
    assert "--project" not in argv.split(), argv
    assert "--project=validator" in argv


def test_choosing_the_driver_edits_no_spec_file():
    for spec in SPECS.glob("*.spec.ts"):
        body = _code(spec)
        assert "headless" not in body and "slowMo" not in body, (
            f"{spec.name} carries the driver's own settings: selecting the "
            "driver would mean editing a spec"
        )


def test_the_recording_lands_somewhere_predictable():
    config = _code(CONFIG)
    reporter = _code(REPORTER)

    assert "walkthrough" in config, (
        "no reporter collects the walkthrough recording"
    )
    assert "artifacts/walkthrough" in reporter, (
        "the recording has no predictable place to be found in"
    )
    assert ".html" in reporter, (
        "the recording is not playable without the repository: no player page "
        "is written beside the videos"
    )


def test_the_recording_is_built_from_the_run_and_not_from_a_roster():
    reporter = _code(REPORTER)

    # Every beat, in the order it ran, taken from the run itself. A roster in
    # the reporter silently stops covering the beat added after it was written.
    body = re.search(
        r"onTestEnd\(.*?\n    \}", reporter, flags=re.DOTALL
    )
    assert body, "the reporter does not observe the tests"
    assert "attachments" in body.group(0), (
        "onTestEnd does not read the test's attachments, so it collects no video"
    )
    assert "push" in body.group(0), (
        "onTestEnd records nothing, so the recording covers whatever the "
        "reporter happened to be told elsewhere"
    )
    for spec in SPECS.glob("*.spec.ts"):
        stem = spec.name.removesuffix(".spec.ts")
        assert stem not in reporter, (
            f"the reporter names {spec.name}: a recording built from a list "
            "stops covering the beat added after the list was written"
        )


def test_a_red_beat_cannot_reach_the_recording():
    reporter = _code(REPORTER)

    assert "beat.status !== 'passed'" in reporter, (
        "the reporter does not read the beats' own outcome; FullResult.status "
        "is 'passed' for a run whose beats were all skipped"
    )
    # The refusal is decided before anything is moved, so a red run cannot get
    # half way through replacing the fallback and stop.
    assert reporter.index("whyNotRecorded(result)") < reporter.index("renameSync(staging, WALKTHROUGH_DIR)"), (
        "the recording is written before the run is judged"
    )
    assert "existsSync(WALKTHROUGH_DIR)" in reporter, (
        "the recording being replaced is deleted rather than moved aside, so a "
        "failed swap leaves no fallback at all"
    )


def test_a_filtered_run_cannot_replace_the_recording():
    """Exercised, not read: `filteredBy` is the one piece here with logic.

    Runs under `node --experimental-strip-types`, and skips where there is no
    node — the CI-tooling loop is Python and its runner need not carry one. The
    positional cases are the ones that matter: every bare argument to
    `playwright test` is a file-path regex, so `cross-platform` narrows a run as
    surely as `--grep` does, and a recording made from it would be a subset
    wearing the walkthrough's name.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("no node on PATH")

    probe = """
    import { filteredBy } from './reporters/walkthrough.ts';
    const cases = process.argv.slice(2).map((c) => JSON.parse(c));
    console.log(JSON.stringify(cases.map((c) => filteredBy(c))));
    """
    cases = [
        ["node", "playwright", "test", "--project", "stage"],
        ["node", "playwright", "test", "--project", "stage", "--headed", "-j", "1"],
        ["node", "playwright", "test", "--project", "stage", "--grep", "hop"],
        ["node", "playwright", "test", "--project=validator", "cross-platform"],
        ["node", "playwright", "test", "specs/cross-platform.spec.ts"],
        ["node", "playwright", "test", "--last-failed"],
        ["node", "playwright", "test", "--shard=1/2"],
    ]
    completed = subprocess.run(
        [node, "--experimental-strip-types", "--input-type=module", "-", *[
            __import__("json").dumps(case) for case in cases
        ]],
        input=probe,
        cwd=E2E,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    verdicts = __import__("json").loads(completed.stdout.strip().splitlines()[-1])

    assert verdicts[0] is None, "an unfiltered run was reported as filtered"
    assert verdicts[1] is None, (
        "a flag's own value was mistaken for a filter, so a complete "
        "walkthrough would never be recorded"
    )
    assert verdicts[2:] == ["--grep", "cross-platform", "specs/cross-platform.spec.ts",
                            "--last-failed", "--shard=1/2"], verdicts


def test_the_driver_is_written_down():
    assert DOC.exists(), "the Stage driver has no record"

    context = _text(REPO_ROOT / "CONTEXT.md")
    assert "scripts/e2e-tests.sh --stage" in context, (
        "CONTEXT.md's Stage driver entry does not say how to run it"
    )
