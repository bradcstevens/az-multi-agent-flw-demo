"""Check the store assistant's content pack — offline, and against a deployment.

Two commands, and the split is the point.

``verify`` is pure and runs anywhere: the pack's own invariants, the ones the
CI-tooling tests assert continuously.

``roster`` is the one the deploy path runs **after** the upload, and it exists
because of how ``AgentFactory.get_agents`` fails. An agent whose
``deployment_name`` is not in the ``SUPPORTED_MODELS`` allowlist is skipped with
a ``logger.warning`` and nothing else: the upload returned 200, the team is in
Cosmos, the surface shows the assistant, and the cast is quietly one member
short. Nobody reads a container's warnings during a rehearsal. So the roster is
read back out of the deployment and compared with the roster that was authored.

Deliberately stdlib-only. It runs inside the post-deploy script's throwaway
virtualenv, and a check that cannot run because its dependency is missing is a
check that reports nothing at the moment it is most needed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Sequence

from store_pack import content as content_mod
from store_pack import pack as pack_mod
from store_pack import roster as roster_mod

REPO_ROOT = Path(__file__).resolve().parents[2]
ANONYMOUS_PRINCIPAL = "00000000-0000-0000-0000-000000000000"


def _fail(problems: Sequence[str]) -> int:
    for problem in problems:
        print(f"FAIL: {problem}")
    print(f"\n{len(problems)} problem(s).")
    return 1


def verify(argv: argparse.Namespace) -> int:
    """The pack's own invariants, with no deployment in sight."""
    problems: List[str] = []
    store = pack_mod.load_pack(REPO_ROOT)

    if not pack_mod.is_hex_uuid(store.team.get("team_id", "")):
        problems.append(
            f"team_id {store.team.get('team_id')!r} is not a hex-only UUID, so the "
            "surface will not recognise it"
        )

    skipped = roster_mod.silently_skipped(store.team, roster_mod.SUPPORTED_MODELS)
    if skipped:
        problems.append(
            "these agents name a model outside the allowlist and would be "
            f"skipped with only a warning: {', '.join(skipped)}"
        )

    assignment = roster_mod.model_assignment(store.team)
    if assignment != roster_mod.INTENDED_MODELS:
        problems.append(
            f"model assignment is {assignment}, intended {roster_mod.INTENDED_MODELS}"
        )

    seeded = pack_mod.seeded_knowledge_base_names(REPO_ROOT)
    for kb_name in store.knowledge_base_names:
        if kb_name not in seeded:
            problems.append(
                f"knowledge base {kb_name!r} is named by the roster but is not "
                "registered in seed_knowledge_bases.py, so nothing creates it"
            )

    absent_terms = pack_mod.honest_miss_absent_terms(REPO_ROOT)
    for path in store.all_documents():
        text = path.read_text(encoding="utf-8").lower()
        for term in absent_terms:
            if term.lower() in text:
                problems.append(
                    f"{path.name} covers {term!r}, which the SOP corpus keeps out so "
                    "the rehearsed honest miss stays a miss"
                )
        try:
            content_mod.parse_document(path)
        except content_mod.ContentError as exc:
            problems.append(str(exc))

    if argv.search_indexes is not None:
        existing = [name for name in argv.search_indexes.split(",") if name]
        for index_name in roster_mod.missing_indexes(store, existing):
            problems.append(
                f"search index {index_name!r} does not exist yet; an agent grounded "
                "on nothing improvises"
            )

    if problems:
        return _fail(problems)

    print(f"Pack OK: {store.team['name']} ({store.team['team_id']})")
    print(f"  agents:          {', '.join(sorted(assignment))}")
    print(f"  models:          {json.dumps(assignment, sort_keys=True)}")
    print(f"  knowledge bases: {', '.join(store.knowledge_base_names) or 'none'}")
    print(f"  indexes:         {', '.join(store.index_names) or 'none'}")
    print(f"  documents:       {len(store.all_documents())}")
    return 0


def _get_team(backend_url: str, team_id: str, principal_id: str) -> Optional[dict]:
    url = f"{backend_url.rstrip('/')}/api/v4/team_configs/{team_id}"
    request = urllib.request.Request(
        url, headers={"x-ms-client-principal-id": principal_id}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"FAIL: {url} returned {exc.code}")
        return None
    except Exception as exc:  # pragma: no cover - network shapes vary
        print(f"FAIL: could not reach {url}: {exc}")
        return None


def check_roster(uploaded: dict, authored: dict, supported_models: Sequence[str]):
    """Compare the roster a deployment holds with the roster that was authored.

    Pure, so the comparison is unit-testable without a deployment; the HTTP
    call above is the only part that is not.
    """
    problems: List[str] = []

    authored_names = [agent.get("name") for agent in authored.get("agents", [])]
    uploaded_names = [agent.get("name") for agent in uploaded.get("agents", [])]

    for name in authored_names:
        if name not in uploaded_names:
            problems.append(f"agent {name!r} was authored but is not in the deployment")
    for name in uploaded_names:
        if name not in authored_names:
            problems.append(f"agent {name!r} is in the deployment but was not authored")

    for name in roster_mod.silently_skipped(uploaded, supported_models):
        problems.append(
            f"agent {name!r} names a model outside {list(supported_models)} — the "
            "agent factory will skip it with only a warning and the roster will be "
            "one agent short at run time"
        )

    authored_models = roster_mod.model_assignment(authored)
    uploaded_models = roster_mod.model_assignment(uploaded)
    for name, model in authored_models.items():
        if name in uploaded_models and uploaded_models[name] != model:
            problems.append(
                f"agent {name!r} was authored on {model!r} but the deployment has "
                f"{uploaded_models[name]!r}"
            )

    return problems


def roster(argv: argparse.Namespace) -> int:
    store = pack_mod.load_pack(REPO_ROOT)
    team_id = store.team["team_id"]

    supported = (
        [name for name in argv.supported_models.split(",") if name]
        if argv.supported_models
        else _supported_from_env()
    )

    uploaded = _get_team(argv.backend_url, team_id, argv.user_principal_id)
    if uploaded is None:
        return _fail(
            [
                f"the store assistant's team configuration ({team_id}) could not be "
                "read back from the deployment, so the surface will report that the "
                "assistant is not loaded"
            ]
        )

    problems = check_roster(uploaded, store.team, supported)
    if problems:
        return _fail(problems)

    print(f"Roster OK: {uploaded.get('name')} ({team_id})")
    for agent in uploaded.get("agents", []):
        print(f"  {agent.get('name')} on {agent.get('deployment_name')}")
    return 0


def _supported_from_env() -> List[str]:
    raw = os.environ.get("SUPPORTED_MODELS", "")
    if not raw:
        return list(roster_mod.SUPPORTED_MODELS)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return list(roster_mod.SUPPORTED_MODELS)
    return [str(name) for name in parsed]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="store_pack", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    verify_parser = sub.add_parser("verify", help="check the authored pack, offline")
    verify_parser.add_argument(
        "--search-indexes",
        default=None,
        help="comma-separated indexes that exist, to check the pack's against",
    )
    verify_parser.set_defaults(handler=verify)

    roster_parser = sub.add_parser(
        "roster", help="check the uploaded roster against the authored one"
    )
    roster_parser.add_argument("--backend-url", required=True)
    roster_parser.add_argument("--user-principal-id", default=ANONYMOUS_PRINCIPAL)
    roster_parser.add_argument("--supported-models", default=None)
    roster_parser.set_defaults(handler=roster)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
