"""The two ends agree about Chat deletion (#75, ADR-026).

The fifth crossing of the seam ``test_transparency_contract.py``,
``test_ticket_contract.py`` and ``test_personal_answer_contract.py`` span, and
for the same reason: the backend decides, the browser decides again, and nothing
at runtime reconciles the two.

It has to be decided twice. The row has to know whether to offer the delete
*before* any request is made — a menu that offers what the route will refuse is
the surface claiming an action it does not have — and the route has to refuse
whatever the row offered, because a browser is not an authorization boundary.
Two copies of one rule is the shape that drifts, so this file is what keeps them
honest:

* the same three **settled** states, so a row offers exactly what the route
  takes;
* the same sentence for *why a running chat is kept*, so the reason the
  associate reads on the menu is the reason the 409 gives;
* the same path, so the delete reaches the route at all.

The backend half is **imported** — ``chat/deletion.py`` imports nothing but
``dataclasses``, ``enum`` and the message models — so the rule comes from the
module rather than from a regex over it. The frontend half is read as text;
there is no TypeScript runtime in this suite.
"""

import re
from pathlib import Path

from chat.deletion import SETTLED_STATUSES, STILL_RUNNING_DETAIL

REPO_ROOT = Path(__file__).resolve().parents[3]
DELETION = REPO_ROOT / "src" / "App" / "src" / "models" / "chatDeletion.ts"
API_SERVICE = REPO_ROOT / "src" / "App" / "src" / "api" / "apiService.tsx"
ROUTER = REPO_ROOT / "src" / "backend" / "api" / "router.py"

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//[^\n]*")


def _code_only(path: Path) -> str:
    """The source with its comments removed.

    Every assertion below is about what the code *does*, and these files are
    heavily commented — a rule stated only in prose would otherwise satisfy a
    check while nothing read it.
    """
    source = path.read_text(encoding="utf-8")
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", source))


def _settled_statuses_in_browser() -> set:
    """The states the row treats as safe to delete."""
    source = _code_only(DELETION)
    declaration = re.search(
        r"SETTLED_STATUSES[^=]*=\s*new Set<string>\(\[(.*?)\]\)", source, re.S
    )
    assert declaration, "chatDeletion.ts no longer declares SETTLED_STATUSES"

    return set(re.findall(r"PlanStatus\.(\w+)", declaration.group(1)))


def test_both_ends_call_the_same_three_states_settled():
    # `PlanStatus.COMPLETED` in the browser is `completed` on the wire; the
    # enum member names are upper-cased spellings of the backend's values.
    browser = {name.lower() for name in _settled_statuses_in_browser()}

    assert browser == set(SETTLED_STATUSES)


def test_a_running_chat_is_refused_in_the_same_words_at_both_ends():
    # The row says this while it refuses to offer the delete; the route says it
    # in the 409 when something asks anyway. Two sentences here would have the
    # surface explaining itself twice and differently.
    source = _code_only(DELETION)
    reason = re.search(
        r"STILL_RUNNING_REASON\s*(?::\s*string\s*)?=\s*(.*?);", source, re.S
    )
    assert reason, "chatDeletion.ts no longer declares STILL_RUNNING_REASON"

    said = "".join(re.findall(r"'([^']*)'", reason.group(1)))
    assert said == STILL_RUNNING_DETAIL


def test_the_browser_deletes_a_chat_at_the_route_the_backend_serves():
    router = ROUTER.read_text(encoding="utf-8")

    prefix = re.search(r'prefix="(/[^"]+)"', router)
    assert prefix, "router.py no longer declares its prefix"

    served = re.search(r'@app_router\.delete\("(/[^"]+)/\{session_id\}"\)', router)
    assert served, "router.py no longer serves a session-scoped chat delete"

    called = re.search(r"CHATS:\s*'(/[^']+)'", _code_only(API_SERVICE))
    assert called, "apiService no longer names a CHATS endpoint"

    # The browser's base URL already carries `/api`; the version and the
    # collection are what has to match.
    assert prefix.group(1) + served.group(1) == "/api" + called.group(1)


def test_the_browser_deletes_a_chat_by_its_session():
    # Chat deletion is session-scoped (ADR-026). A delete that sent the plan id
    # a row carries to open with would take one turn of the conversation and
    # leave the rest of it in Cosmos — and would 404 rather than say so.
    source = _code_only(API_SERVICE)
    call = re.search(r"async deleteChat\((.*?)\n    \}", source, re.S)
    assert call, "apiService no longer offers deleteChat"

    assert "sessionId: string" in call.group(1)
    assert "planId" not in call.group(1)


def test_the_single_plan_primitive_has_no_caller_left():
    # ADR-026 left `delete_plan_by_plan_id` alone: it takes one document, is
    # not scoped by `user_id`, and returns `True` even when it deleted nothing.
    # Reached as Chat deletion it would leave a partial chat behind — the
    # transcript, the troubleshooting record and the ticket all outliving the
    # plan — and would let anyone who knows an id delete another user's record.
    #
    # Its one caller was the verdict path, where disagreeing with a plan
    # destroyed it. #108 replaced that with the framework's revise path, so the
    # primitive now has no caller at all and the destroying path is unreachable
    # rather than merely unused.
    #
    # Counted as calls, not as mentions: `router.py` names it in prose,
    # explaining why it is *not* what the delete route reaches for.
    backend = REPO_ROOT / "src" / "backend"
    callers = [
        source.relative_to(REPO_ROOT).as_posix()
        for source in backend.rglob("*.py")
        if re.search(r"\.delete_plan_by_plan_id\(", source.read_text(encoding="utf-8"))
    ]

    assert callers == []


def test_the_hide_feature_is_gone_rather_than_standing_beside_the_delete():
    # ADR-026 supersedes ADR-022. Two controls, one of which quietly leaves the
    # record behind, is the ambiguity the delete label exists to remove.
    models = REPO_ROOT / "src" / "App" / "src" / "models"
    hooks = REPO_ROOT / "src" / "App" / "src" / "hooks"

    assert not (models / "hiddenCompletedTasks.ts").exists()
    assert not (models / "hiddenCompletedTasks.test.ts").exists()
    assert not (hooks / "useHiddenCompletedTasks.tsx").exists()
