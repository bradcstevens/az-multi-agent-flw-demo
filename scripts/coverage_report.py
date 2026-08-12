#!/usr/bin/env python3
"""Advisory coverage report — reads a Cobertura ``coverage.xml`` and prints the
overall line rate against a threshold.

The threshold is advisory by decision (issue #10). A run below it emits a GitHub
Actions warning annotation and still exits zero, so coverage never blocks a
build; only a missing or unreadable report is an error, because that means the
test run itself did not produce the number.

Used by both `.github/workflows/test.yml` and the feedback-loop scripts in this
directory, so CI and a local loop report the same number the same way.
"""

import sys
import xml.etree.ElementTree as ET

ADVISORY_THRESHOLD = 80.0

DEFAULT_REPORT = "coverage.xml"


def read_line_rate(report_path):
    """Return the overall line coverage of a Cobertura report as a percentage."""
    root = ET.parse(report_path).getroot()
    return float(root.attrib.get("line-rate", 0)) * 100


def format_report(coverage, threshold=ADVISORY_THRESHOLD):
    """Return the report line for a coverage percentage. Pure."""
    if coverage < threshold:
        return (
            f"::warning::Coverage is below the advisory {threshold:g}% "
            f"threshold. Current: {coverage:.2f}%"
        )
    return f"Coverage threshold met: {coverage:.2f}% >= {threshold:g}%"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    report_path = argv[0] if argv else DEFAULT_REPORT

    try:
        coverage = read_line_rate(report_path)
    except (OSError, ET.ParseError) as exc:
        print(f"::error::coverage.xml not readable at {report_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Overall coverage: {coverage:.2f}%")
    print(format_report(coverage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
