"""The Lane itself (issue #16, ADR-013).

A Lane is a domain term with exactly one mechanical consequence: which value
the orchestration builder's approval gate is built with. Parsing is separate
from that mapping because a declared lane arrives as an unvalidated string from
a team definition, and an unparseable one must fail open rather than raise.
"""

import pytest

from lane.lane import Lane, parse_lane


class TestTheMapping:
    """Lane maps to Plan review, and it is the only thing a Lane decides."""

    def test_the_fast_lane_turns_the_approval_gate_off(self):
        assert Lane.FAST.plan_review is False

    def test_the_deliberate_lane_keeps_the_approval_gate(self):
        assert Lane.DELIBERATE.plan_review is True


class TestParsingADeclaredLane:
    @pytest.mark.parametrize(
        "declared,expected",
        [
            ("fast", Lane.FAST),
            ("deliberate", Lane.DELIBERATE),
            ("Fast", Lane.FAST),
            ("  DELIBERATE  ", Lane.DELIBERATE),
        ],
    )
    def test_a_declared_lane_parses(self, declared, expected):
        """Case and surrounding whitespace are authoring noise, not intent."""
        assert parse_lane(declared) is expected

    @pytest.mark.parametrize("declared", [None, "", "   ", "quick", "fast lane", 7])
    def test_anything_else_is_unparseable(self, declared):
        """Total: any input at all, a Lane or None out, never an exception.

        Returning None rather than a Lane keeps the fail-open decision in the
        router, where the reason for it is written down, instead of hiding a
        policy default inside a parser.
        """
        assert parse_lane(declared) is None
