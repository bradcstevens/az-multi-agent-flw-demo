"""Tests for the advisory coverage report used by the feedback loops and CI.

The report is advisory by decision (issue #10): this build adds substantial demo
scaffolding to the two largest backend files, and the coverage configuration
counts test files themselves toward the total, so a blocking gate would buy
noise rather than confidence. These tests are the standing proof of that — a
deliberately low coverage report must still exit zero.
"""

import subprocess
import sys
from pathlib import Path

from coverage_report import main

REPO_ROOT = Path(__file__).resolve().parents[3]
COVERAGE_REPORT = REPO_ROOT / "scripts" / "coverage_report.py"


def write_coverage_xml(path, line_rate):
    path.write_text(
        f'<?xml version="1.0" ?>\n'
        f'<coverage line-rate="{line_rate}" branch-rate="0" version="7.0">'
        f"<packages/></coverage>\n",
        encoding="utf-8",
    )
    return path


def test_given_deliberately_low_coverage_when_reported_then_exits_zero(tmp_path, capsys):
    report = write_coverage_xml(tmp_path / "coverage.xml", 0.12)

    exit_code = main([str(report)])

    assert exit_code == 0
    assert "::warning::" in capsys.readouterr().out


def test_given_coverage_above_the_threshold_when_reported_then_no_warning(tmp_path, capsys):
    report = write_coverage_xml(tmp_path / "coverage.xml", 0.86)

    exit_code = main([str(report)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "::warning::" not in out
    assert "Coverage threshold met" in out


def test_given_no_report_when_reported_then_errors(tmp_path, capsys):
    exit_code = main([str(tmp_path / "coverage.xml")])

    assert exit_code == 1
    assert "::error::" in capsys.readouterr().err


def test_given_deliberately_low_coverage_when_run_as_ci_runs_it_then_the_step_succeeds(tmp_path):
    """The end-to-end demonstration issue #10 asks for.

    CI invokes this as a shell step, so the advisory decision only holds if the
    *process* exits zero. 12% is far enough below the threshold that no rounding
    or reconfiguration could make this pass by accident.
    """
    report = write_coverage_xml(tmp_path / "coverage.xml", 0.12)

    result = subprocess.run(
        [sys.executable, str(COVERAGE_REPORT), str(report)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Overall coverage: 12.00%" in result.stdout
    assert "::warning::" in result.stdout
