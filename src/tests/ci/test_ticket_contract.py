"""The two ends of the socket agree about the Simulated ticket (issue #22).

The same seam ``test_transparency_contract.py`` spans, for the same reason and
with the same reasoning: the backend builds a payload, the browser parses it,
and nothing at runtime reconciles the two. `ticket.test.ts` hand-writes the
payload it expects, so a field renamed in ``escalation/payloads.py`` would leave
every vitest test green and the ticket card dark on stage.

Sharper here than for the transparency panels, because of what the card claims.
A panel that goes dark says nothing; a ticket card that fails to appear says
nothing *while the associate has been told a ticket was raised*, and the number
they were told is the part they can read down a telephone.

The backend half is **imported** — ``escalation/payloads.py`` imports nothing
but ``dataclasses`` and its own pure ticket module — so the field names come
from the dataclasses rather than from a regex over their source. The frontend
half is read as text; there is no TypeScript runtime in this suite, and the
assertion is only ever about names.
"""

import re
from dataclasses import fields
from pathlib import Path

from escalation.payloads import TicketField, TicketRaised
from escalation.ticket import FIELD_ORDER

REPO_ROOT = Path(__file__).resolve().parents[3]
PARSERS = REPO_ROOT / "src" / "App" / "src" / "models" / "ticket.ts"
FRONTEND_ENUMS = REPO_ROOT / "src" / "App" / "src" / "models" / "enums.tsx"
BACKEND_MESSAGES = REPO_ROOT / "src" / "backend" / "models" / "messages.py"
TEMPLATE = (
    REPO_ROOT / "content_packs" / "store_assistant" / "datasets" / "operations"
    / "TKT-001 Service Incident Ticket Template.md"
)

SIGNAL = "TICKET_RAISED"

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//[^\n]*")
_PY_COMMENT = re.compile(r"#[^\n]*")


def _code_only(source: str, python: bool = False) -> str:
    """The source with its comments removed.

    Every assertion below is about what the code *does*, and these files are
    heavily commented — a field named only in prose would otherwise satisfy a
    check while nothing read it.
    """
    if python:
        return _PY_COMMENT.sub("", source)
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", source))


def _parsers() -> str:
    return _code_only(PARSERS.read_text(encoding="utf-8"))


def _parser_body(name: str) -> str:
    """One exported parser's body, comments already stripped.

    Scoped to the single function rather than the whole file: the two parsers
    share the word ``name``, so a whole-file search would report a field as
    read after the parser that needs it stopped reading it. That miss slipped a
    mutation past #24's first attempt at this test.
    """
    source = _parsers()
    start = source.index(f"export const {name} = (")
    rest = source[start:]
    end = rest.index("\n};")
    return rest[:end]


def _reads(field_name: str, source: str) -> bool:
    return f"record.{field_name}" in source


def test_the_browser_reads_every_field_the_ticket_payload_carries():
    source = _parser_body("parseRaisedTicket")

    missing = [
        f.name
        for f in fields(TicketRaised)
        if not _reads(f.name, source)
    ]

    assert not missing, (
        f"the ticket card never reads {missing} — the backend sends it and the "
        "browser cannot see it"
    )


def test_the_browser_reads_every_field_one_ticket_row_carries():
    source = _parser_body("parseTicketField")

    missing = [f.name for f in fields(TicketField) if not _reads(f.name, source)]

    assert not missing, f"a ticket row's {missing} is never read"


def test_the_ticket_rides_the_same_wire_string_at_both_ends():
    def value(source: str, python: bool = False) -> str | None:
        found = re.search(
            rf"{SIGNAL}\s*[:=]\s*[\"']([a-z_]+)[\"']",
            _code_only(source, python=python),
        )
        return found.group(1) if found else None

    backend = value(BACKEND_MESSAGES.read_text(encoding="utf-8"), python=True)
    frontend = value(FRONTEND_ENUMS.read_text(encoding="utf-8"))

    assert backend, "the backend no longer defines TICKET_RAISED"
    assert backend == frontend, (
        "the ticket message type drifted between the backend and the browser: "
        f"backend {backend!r}, frontend {frontend!r}"
    )


def test_the_fields_the_code_fills_are_the_fields_the_template_states():
    # TKT-001 is **content**, authored in the content pack and revisable there;
    # ``FIELD_ORDER`` is the code's reading of it. A field added to the template
    # and not to the code is a row the associate is told about and never sees;
    # a field in the code and not the template is a row nobody authored the
    # rules for. Read out of the template rather than listed here, because a
    # list written in a test agrees with itself forever.
    section = TEMPLATE.read_text(encoding="utf-8").split("## Fields", 1)[1]
    section = section.split("##", 1)[0]
    declared = tuple(re.findall(r"^(\w+):", section, re.M))

    assert declared, "TKT-001 no longer declares its fields"
    assert declared == FIELD_ORDER, (
        "the ticket template and the code that fills it disagree: template "
        f"{declared}, code {FIELD_ORDER}"
    )
