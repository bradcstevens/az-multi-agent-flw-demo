"""The two ends of the socket agree about the Personal answer (issue #27).

The same seam ``test_transparency_contract.py`` and ``test_ticket_contract.py``
span, for the fourth time and for the same reason: the backend builds a payload,
the browser parses it, and nothing at runtime reconciles the two.
``personalAnswer.test.ts`` hand-writes the payload it expects, so a field renamed
in ``associate/answer.py`` would leave every vitest test green and the closing
beat blank on stage.

Sharper here than for the transparency panels, and for the reason the ticket's
is sharper. A panel that goes dark says nothing. A **Personal answer** that
fails to render says nothing *at the moment the presenter has just told the room
the sign-in changed something* — and the beat's whole content is the delta
between the refusal and this card, so a card that does not arrive turns the
argument into its opposite.

The backend half is **imported** — ``associate/answer.py`` imports nothing but
``dataclasses`` and its own pure records module — so the field names come from
the dataclasses rather than from a regex over their source. The frontend half is
read as text; there is no TypeScript runtime in this suite, and the assertion is
only ever about names.
"""

import re
from dataclasses import fields
from pathlib import Path

from associate.answer import (
    PERSONAL_ANSWER_KIND,
    AnswerFact,
    PersonalAnswer,
    personal_answer_detail,
)
from associate.records import DEMO_ASSOCIATE
from guardrail.refusal import POLICY_BLOCK_KIND

REPO_ROOT = Path(__file__).resolve().parents[3]
PARSER = REPO_ROOT / "src" / "App" / "src" / "models" / "personalAnswer.ts"
POLICY_PARSER = REPO_ROOT / "src" / "App" / "src" / "api" / "policyBlock.ts"

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//[^\n]*")


def _code_only(source: str) -> str:
    """The source with its comments removed.

    Every assertion below is about what the code *does*, and this file is
    heavily commented — a field named only in prose would otherwise satisfy a
    check while nothing read it.
    """
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", source))


def _parser() -> str:
    return _code_only(PARSER.read_text(encoding="utf-8"))


def _parser_body() -> str:
    source = _parser()
    start = source.index("export function parsePersonalAnswer(")
    return source[start:]


def _reads(field_name: str, source: str) -> bool:
    """Whether the parser both names a field *and* does something with it.

    Named twice, deliberately: once where it is destructured off the payload and
    once where it is used. A field destructured and then dropped satisfies a
    bare substring search while the card renders without it — the miss that
    slipped a mutation past #24's first attempt at this test.
    """
    return source.count(field_name) >= 2


def test_the_browser_reads_every_field_the_answer_carries():
    source = _parser_body()

    missing = [f.name for f in fields(PersonalAnswer) if not _reads(f.name, source)]

    assert not missing, (
        f"the personal answer card never reads {missing} — the backend sends it "
        "and the browser cannot see it"
    )


def test_the_browser_reads_every_field_one_fact_carries():
    source = _parser_body()

    missing = [f.name for f in fields(AnswerFact) if not _reads(f.name, source)]

    assert not missing, f"a fact's {missing} is never read"


def test_the_discriminator_is_the_same_string_at_both_ends():
    # The browser switches on `kind`, not on the shape of what arrived, so this
    # one string is the whole of the routing.
    found = re.search(
        r"PERSONAL_ANSWER_KIND\s*=\s*['\"]([a-z_]+)['\"]", _parser()
    )

    assert found, "the browser no longer names the personal answer's kind"
    assert found.group(1) == PERSONAL_ANSWER_KIND, (
        "the personal answer's discriminator drifted between the backend and "
        f"the browser: backend {PERSONAL_ANSWER_KIND!r}, browser "
        f"{found.group(1)!r}"
    )


def test_the_answer_and_the_refusal_are_never_the_same_kind():
    # They are the same beat's two outcomes, they travel the same surface, and
    # one of them is somebody's pay. A shared discriminator would let the
    # browser render a governed refusal as an associate's record.
    browser_policy = re.search(
        r"POLICY_BLOCK_KIND\s*=\s*['\"]([a-z_]+)['\"]",
        _code_only(POLICY_PARSER.read_text(encoding="utf-8")),
    )

    assert browser_policy, "the browser no longer names the policy block's kind"
    assert PERSONAL_ANSWER_KIND != POLICY_BLOCK_KIND
    assert browser_policy.group(1) != PERSONAL_ANSWER_KIND


def test_the_payload_the_backend_sends_carries_the_discriminator():
    # Built by the request path, not hand-written here: a `kind` the payload
    # builder forgets is a card the browser silently refuses to render.
    payload = personal_answer_detail(DEMO_ASSOCIATE)

    assert payload["kind"] == PERSONAL_ANSWER_KIND


def test_the_browser_names_no_associate_of_its_own():
    # The name comes back from the sign-in route and is stored verbatim
    # (`signedInDevice.ts`). A name authored in the browser and a name the
    # **Associate record** is keyed by are two strings free to drift, and the
    # drift's symptom is a header confidently naming somebody the Identity
    # boundary gate will not answer for.
    device = _code_only(
        (REPO_ROOT / "src" / "App" / "src" / "models" / "signedInDevice.ts")
        .read_text(encoding="utf-8")
    )

    first_name = DEMO_ASSOCIATE.display_name.split()[0]
    assert first_name.lower() not in device.lower(), (
        "the browser authors the associate's name — it must only ever store "
        "the one the sign-in route returned"
    )


def test_no_identity_provider_is_involved_on_the_browser_side_either():
    # The beat's plainest requirement, asserted rather than assumed, on the half
    # of the flow the backend's own version of this test cannot see. A later
    # iteration reaching for MSAL here turns this red rather than quietly making
    # the demo's "mocked end to end" claim false.
    app = REPO_ROOT / "src" / "App" / "src"
    forbidden = ("msal", "@azure/identity", "oauth", "openid", "okta", "auth0")

    for path in (
        app / "models" / "signedInDevice.ts",
        app / "models" / "personalAnswer.ts",
        app / "hooks" / "useSignedInDevice.tsx",
        app / "components" / "identity" / "PersonalAnswerCard.tsx",
        app / "components" / "branding" / "StoreIdentity.tsx",
    ):
        source = _code_only(path.read_text(encoding="utf-8")).lower()
        for token in forbidden:
            assert f"'{token}" not in source and f'"{token}' not in source, (
                f"{path.name} reaches for {token} — the sign-in is mocked end "
                "to end"
            )
