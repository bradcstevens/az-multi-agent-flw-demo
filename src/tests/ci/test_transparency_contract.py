"""The two ends of the socket agree about the transparency signals (issue #24).

The backend builds three payloads (#23) and the browser parses them (#24), and
nothing at runtime reconciles the two. The frontend's own suite cannot catch a
rename on the backend: `transparency.test.ts` hand-writes the payloads it
expects, so a field renamed in `payloads.py` leaves all 83 vitest tests green
and the panel silently dark on stage — the failure mode this whole feature is
shaped to avoid, arriving through the one seam the feature's own tests do not
span.

This test spans it, and lives on the **Python** side deliberately: `test.yml`
triggers on Python paths, so a backend contract change runs this. The frontend
workflow triggers on `src/App/**`, so a frontend change runs it too — both
directions of the drift are covered, each by the workflow the change starts.

The backend half is **imported**, not read as text: `payloads.py` imports
nothing but `dataclasses`, so the field names come from the dataclasses
themselves rather than from a regex over their source, and a field renamed in a
way a regex would miss still fails here. The frontend half is read as text —
there is no TypeScript runtime in this suite, and the assertion is only ever
about names.
"""

import re
from dataclasses import fields
from pathlib import Path

from transparency.payloads import PresenterAlert, SourceUsed, TokenUsage

REPO_ROOT = Path(__file__).resolve().parents[3]
PARSERS = REPO_ROOT / "src" / "App" / "src" / "models" / "transparency.ts"
FRONTEND_ENUMS = REPO_ROOT / "src" / "App" / "src" / "models" / "enums.tsx"
BACKEND_MESSAGES = REPO_ROOT / "src" / "backend" / "models" / "messages.py"
ROUTER = REPO_ROOT / "src" / "backend" / "api" / "router.py"

SIGNALS = ("SOURCE_USED", "TOKEN_USAGE", "PRESENTER_ALERT")

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//[^\n]*")
_PY_COMMENT = re.compile(r"#[^\n]*")


def _code_only(source: str, python: bool = False) -> str:
    """The source with its comments removed.

    Every assertion below is about what the code *does*. A field named only in
    a prose comment — and this file's subjects are heavily commented — would
    otherwise satisfy a check while nothing read it.
    """
    stripped = _PY_COMMENT.sub("", source) if python else source
    if not python:
        stripped = _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", source))
    return stripped


def _parsers() -> str:
    return _code_only(PARSERS.read_text(encoding="utf-8"))


def _parser_body(name: str) -> str:
    """One exported parser's body, comments already stripped.

    Scoped to the single function rather than the whole file, because the three
    payloads share field names — `agent_name` is read by two parsers — so a
    whole-file search reports a field as read when the parser that needs it has
    stopped reading it.
    """
    source = _parsers()
    start = source.index(f"export function {name}(")
    rest = source[start:]
    end = rest.index("\n}")
    return rest[:end]


def _websocket_values(source: str, python: bool = False) -> dict[str, str]:
    """The three signals' wire strings, however the file spells an assignment."""
    source = _code_only(source, python=python)
    return {
        name: value
        for name, value in re.findall(
            r"(\w+)\s*[:=]\s*[\"']([a-z_]+)[\"']", source
        )
        if name in SIGNALS
    }


def _read_field(field_name: str, source: str) -> bool:
    """Whether this source reads the field off a payload at all."""
    return f"raw.{field_name}" in source


def test_the_browser_reads_every_field_the_source_used_payload_carries():
    source = _parser_body("parseSourceUsed")

    missing = [f.name for f in fields(SourceUsed) if not _read_field(f.name, source)]

    assert not missing, (
        f"the Grounding panel never reads {missing} — the backend sends it and "
        "the browser cannot see it"
    )


def test_the_browser_reads_every_field_the_token_usage_payload_carries():
    source = _parser_body("parseTokenUsage")

    missing = [f.name for f in fields(TokenUsage) if not _read_field(f.name, source)]

    assert not missing, f"the Token meter never reads {missing}"


def test_the_browser_reads_every_field_the_presenter_alert_payload_carries():
    source = _parser_body("parsePresenterAlert")

    missing = [
        f.name for f in fields(PresenterAlert) if not _read_field(f.name, source)
    ]

    assert not missing, f"the Presenter alert never reads {missing}"


def test_the_citation_fields_the_panel_renders_are_the_ones_the_bridge_sends():
    # Citations are built as plain dicts on the `/sop/ask` reply rather than as
    # a dataclass, so the keys are read back out of the route that builds them
    # rather than written down here — a rename there has to fail this, and a
    # list hard-coded in the test is a list that agrees with itself forever.
    block = re.search(
        r'"citations":\s*\[\s*\{(.*?)\}',
        _code_only(ROUTER.read_text(encoding="utf-8"), python=True),
        re.S,
    )
    assert block, "the /sop/ask reply no longer builds a citations list"
    keys = re.findall(r'"(\w+)":', block.group(1))
    assert keys, "the citation payload has no keys"

    source = _parsers()
    missing = [key for key in keys if not _read_field(key, source)]

    assert not missing, f"the Grounding panel never reads a citation's {missing}"


def test_the_three_signals_ride_the_same_wire_strings_at_both_ends():
    backend = _websocket_values(
        BACKEND_MESSAGES.read_text(encoding="utf-8"), python=True
    )
    frontend = _websocket_values(FRONTEND_ENUMS.read_text(encoding="utf-8"))

    assert set(backend) == set(SIGNALS), (
        f"the backend no longer defines all of {SIGNALS}: {sorted(backend)}"
    )
    assert backend == frontend, (
        "the transparency message types drifted between the backend and the "
        f"browser: backend {backend}, frontend {frontend}"
    )


def test_no_count_is_defaulted_to_zero_on_the_way_in():
    # #23's emission rule, carried across: no usage reported means no event, not
    # a zero, because a zero on the meter reads as *this agent was free* and
    # collides with the guardrail row that proves a refusal costs nothing. Any
    # defaulting operator counts, not just the one the code happens not to use.
    source = _parser_body("parseTokenUsage")

    for field_name in ("input_tokens", "output_tokens", "total_tokens"):
        defaulted = re.search(rf"raw\.{field_name}\s*\)?\s*(\?\?|\|\|)\s*0", source)
        assert not defaulted, (
            f"{field_name} is defaulted to zero, which reinvents the zero the "
            "backend refused to send"
        )
