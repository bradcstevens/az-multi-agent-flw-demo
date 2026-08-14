#!/usr/bin/env python3
"""Check: is the deployed surface the demonstration, or the accelerator?

`check-deployed-environment.sh` proves the infrastructure — the regions, the
model roster, three application hosts running an image from **our** registry.
All of that was true of `macae-flw-v1` on 2026-08-13 while the Container Apps
were running images built 42 commits earlier, because an image's *provenance*
is not its *currency*: the served page title read `Multi-Agent - Custom
Automation Engine`, `COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT` had never been
set, and every declared feedback loop was green because every loop runs against
fakes. See docs/preflight/deployed-surface.md.

So this check reads the running deployment the way the presenter will: the page
the frontend serves, the team configuration the backend hands back, the setting
the SOP tool needs, and one real procedure question.

`evaluate` is pure: it takes what the deployment answered and returns a
`Verdict`. The live HTTP and `az` reads, and the probe, are in `main`.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

RESOURCE_GROUP = "rg-macae-flw-v1"
BACKEND_CONTAINER_APP = "ca-macaeflwv1flrpd"
FRONTEND_CONTAINER_APP = "app-macaeflwv1flrpd"

# The setting the Copilot Studio SOP agent is reached through. Tenant-specific,
# so a bicep parameter rather than something the deployment creates — and unset,
# the SOP tool answers with its fixed failure message instead of a procedure.
TOKEN_ENDPOINT_SETTING = "COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT"

# The demonstration opens anonymous on a shared store device, so the read
# presents the same principal the presenter will. The team the backend is
# asked for is the authored one, read from the pack — never a copy kept
# here, which would ask for a team the repository has since renumbered.
ANONYMOUS_PRINCIPAL = "00000000-0000-0000-0000-000000000000"

# The two facts the Grounding panel is a claim about. They live in
# `src/backend/sop/provenance.py`; repeated here because this check runs
# with nothing but `python3` on PATH and must not import the backend.
SOP_PLATFORM = "Copilot Studio"
SOP_SOURCE = "Dataverse"

TITLE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


class Expected:
    """What this repository authored, read out of the repository."""

    def __init__(self, assistant, team_id, quick_tasks, documents=(),
                 require_all_agents=None):
        self.assistant = assistant
        self.team_id = team_id
        self.quick_tasks = tuple(quick_tasks)
        self.documents = tuple(documents)
        self.require_all_agents = require_all_agents


class Check:
    """One named expectation and whether the deployed surface meets it."""

    def __init__(self, name, ok, detail):
        self.name = name
        self.ok = ok
        self.detail = detail


class Verdict:
    """The outcome of every check, and whether they all passed."""

    def __init__(self, checks):
        self.checks = checks

    @property
    def ok(self):
        return all(check.ok for check in self.checks)

    def check(self, name):
        """Return the named `Check`."""
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)


def evaluate(observed, expected):
    """Return the `Verdict` for a deployment's own answers. Pure."""
    return Verdict(
        [
            _store_surface_check(observed.get("title"), expected),
            _quick_tasks_check(observed.get("team"), expected),
            _mandatory_agents_check(observed.get("team"), expected),
            _direct_line_endpoint_check(observed.get("tokenEndpoint")),
        ]
    )


def _store_surface_check(title, expected):
    """The served page title is the deployed build's identity.

    Nothing sets the document title at run time, so it is whatever
    `src/App/index.html` said in the image that is running. That makes it the
    cheapest honest answer to "is this the build we think it is" available
    without a commit stamp — and it is the string that gave the drift away.
    """
    if not title:
        return Check(
            "store-surface",
            False,
            "the deployed frontend served no page title — a cold or failed "
            "revision is not a surface",
        )
    if title.strip() != expected.assistant:
        return Check(
            "store-surface",
            False,
            f"the deployed frontend serves {title.strip()!r}, not "
            f"{expected.assistant!r} — the running image predates the rebrand",
        )
    return Check(
        "store-surface",
        True,
        f"the deployed frontend serves {expected.assistant!r}",
    )


def _quick_tasks_check(team, expected):
    """The Quick Tasks live in Cosmos, not in the image.

    So a deployment can be running the current build and still have no
    assistant on it: the store pack is uploaded by `post_deploy.sh`, and a
    re-provision does not re-seed it. Each task's **declared lane** is checked
    too — a task that arrives without one falls to the keyword router, and the
    escalation beat then runs without the approval gate that raises its ticket.
    """
    if not team:
        return Check(
            "quick-tasks",
            False,
            f"the backend does not hold team {expected.team_id} — the surface "
            "will report that the assistant is not loaded",
        )
    if team.get("team_id") != expected.team_id:
        return Check(
            "quick-tasks",
            False,
            f"the backend answered with team {team.get('team_id')}, not "
            f"{expected.team_id} — the surface recognises the authored "
            "identifier and will show none of these tasks",
        )
    declared = {
        task.get("id"): task.get("lane")
        for task in team.get("starting_tasks") or []
    }
    problems = []
    for identifier, lane in expected.quick_tasks:
        if identifier not in declared:
            problems.append(f"{identifier} is not on the deployed surface")
        elif declared[identifier] != lane:
            problems.append(
                f"{identifier} declares lane {declared[identifier]!r}, "
                f"not {lane!r}"
            )
    if problems:
        return Check("quick-tasks", False, "; ".join(problems))
    return Check(
        "quick-tasks",
        True,
        f"all {len(expected.quick_tasks)} Quick Tasks are on the deployed "
        "surface, each declaring the lane it was authored with",
    )


def _mandatory_agents_check(team, expected):
    """Whether the deployed team still lets one agent answer alone.

    This asks the same endpoint `_quick_tasks_check` does, but it is a
    different failure and deserves its own row: the tasks can all be present
    and correct while the opening beat still comes back as a clarifying
    question, because `require_all_agents` puts every store specialist into a
    plan that needs one lookup and the Troubleshooting Agent's job is to ask
    what you already tried (#54).

    It is checked on the deployed surface rather than trusted from the pack
    because a default team cannot be deleted: `delete_team` refuses, and the
    post-provision upload warns and writes a *second* document under a new
    partition key. Six of them were live when this check was written, five
    predating the flag and defaulting it back to on. `get_team` now orders
    newest-first, and this is the row that notices if that ever stops working.
    """
    if expected.require_all_agents is None or not team:
        return Check(
            "mandatory-agents",
            True,
            "not checked — the pack does not pin the flag"
            if team else "not checked — no team to read it from",
        )
    observed = team.get("require_all_agents")
    if observed is None:
        return Check(
            "mandatory-agents",
            False,
            "the deployed team declares no require_all_agents — it predates "
            "the field and the backend will default it to on, putting every "
            "store specialist into the opening question's plan",
        )
    if bool(observed) != bool(expected.require_all_agents):
        return Check(
            "mandatory-agents",
            False,
            f"the deployed team reports require_all_agents={observed!r}, but "
            f"this repository authored {expected.require_all_agents!r} — the "
            "deployment is reading a team document older than the pack",
        )
    return Check(
        "mandatory-agents",
        True,
        f"the deployed team reports require_all_agents="
        f"{expected.require_all_agents!r}, as authored — one agent may answer "
        "the opening question alone",
    )


def _direct_line_endpoint_check(endpoint):
    """The setting the Copilot Studio SOP agent is reached through.

    Two ways to be wrong, and both present on stage as the fixed failure
    message: unset, which is how this deployment shipped for weeks; and set to
    a URL somebody assembled from the default Direct Line hostname, which
    ADR-011 rules out because the token endpoint is whatever
    `PvaGetDirectLineEndpoint` returned for *this* environment's region.
    """
    if not endpoint:
        return Check(
            "direct-line-endpoint",
            False,
            f"{TOKEN_ENDPOINT_SETTING} is not set on the backend Container App "
            "— the SOP tool answers with its fixed failure message",
        )
    if "directline.botframework.com" in endpoint:
        return Check(
            "direct-line-endpoint",
            False,
            f"{TOKEN_ENDPOINT_SETTING} was assembled from the default Direct "
            "Line hostname; ADR-011 takes it from PvaGetDirectLineEndpoint",
        )
    return Check(
        "direct-line-endpoint",
        True,
        f"{TOKEN_ENDPOINT_SETTING} is set to {endpoint.split('?')[0]}",
    )


def direct_sop_answer_check(reply, expected):
    """Return the `Check` for one real procedure question. Pure.

    **Named for what it asks, because it asks the easier question** (#54). This
    probe puts the corpus's *own wording* to `/api/v4/sop/ask` directly, with no
    orchestrator in front of it. The presenter's tap does not: the Foundry
    orchestrator writes the tool call, and it hands
    ``search_store_procedures`` whatever it rephrased the question into. Two
    runs in eight came back as the honest miss for that reason while this check
    was green on every attempt over the same afternoon — the check and the
    browser were asking different questions of the same agent, and only the
    browser was asking the presenter's.

    A name like `grounded-answer` cannot say that. It reads as *the grounded
    answer works*, which is the claim only the **Demo validator** can make, so
    the name says `direct` and every detail below says it again. What is proved
    here is the **agent, its index and the hop** — everything except the
    routing.

    What is graded is the provenance and the citations, never the prose: a
    fluent answer is precisely what an ungrounded fallback produces. An unasked
    question is reported as unproven and fails, because a run that gathered no
    evidence must not report the cross-platform hop as working.
    """
    if not reply:
        return Check(
            "direct-sop-answer",
            False,
            "no procedure question was asked — an unprobed SOP agent is not a "
            "reachable one (drop --no-probe)",
        )
    problems = []
    if reply.get("failed"):
        problems.append(
            "the backend returned the fixed Direct Line failure message"
        )
    if not reply.get("citations"):
        problems.append("the answer carried no citations")
    if reply.get("platform") != SOP_PLATFORM or reply.get("source") != SOP_SOURCE:
        problems.append(
            f"the answer claims {reply.get('platform')!r}/{reply.get('source')!r}, "
            f"not {SOP_PLATFORM!r}/{SOP_SOURCE!r}"
        )
    # The token endpoint check accepts any endpoint that is not the assembled
    # Direct Line hostname, so a second Dataverse-grounded agent in the same
    # tenant would answer and cite something. The citation naming a document
    # out of `content/sop/` is what ties the answer back to the corpus this
    # repository uploaded.
    for name in reply.get("citations") or []:
        if expected.documents and name not in expected.documents:
            problems.append(
                f"the answer cites {name!r}, which this repository did not "
                "author — the agent that answered is grounded in another corpus"
            )
    if problems:
        return Check("direct-sop-answer", False, "; ".join(problems))
    return Check(
        "direct-sop-answer",
        True,
        f"{reply.get('question')!r} — the corpus's own wording, asked "
        f"directly with no orchestrator in front of it — was answered from "
        f"{SOP_SOURCE} through {SOP_PLATFORM}, citing "
        f"{', '.join(reply['citations'])}. This is the easier question: the "
        "orchestrator rephrases it, and the rehearsed beat is proved by "
        "scripts/sop-rehearsal.sh, not here (#54)",
    )


def format_report(verdict, expected):
    """Return the human-readable report for a `Verdict`. Pure.

    The consequence line is derived, not asserted: "the walkthrough is
    shippable" is a claim about a real question having been answered from
    Dataverse, so a run that only read the control plane reports it as unproven
    rather than the surface as ready.

    And even a fully green run does not claim the walkthrough works. Every
    check here asks the deployment a question the presenter never asks; the one
    that comes closest asks it in the corpus's own words, past the orchestrator
    that rephrases it. That gap is #54, and the consequence line names the loop
    that closes it rather than leaving a reader to infer it from a row of
    PASSes.
    """
    checks = list(verdict.checks)
    if not any(check.name == "direct-sop-answer" for check in checks):
        checks.append(direct_sop_answer_check(None, expected))
    lines = [
        f"  {'PASS' if c.ok else 'FAIL'}  {c.name}: {c.detail}" for c in checks
    ]
    ready = all(check.ok for check in checks)
    lines.append(
        "  ----  the walkthrough (#46, #47): "
        + ("the direct SOP probe passed — it asked the corpus's own wording "
           "and the orchestrator does not, so this is not the beat. Run "
           "scripts/sop-rehearsal.sh to prove the routing (#54)" if ready
           else "blocked on the failures above")
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# What this repository authored. Read out of the repository, never pinned here:
# a check carrying its own copy of the surface's strings passes a rebrand it
# never saw (the ADR-019 lesson).
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SURFACE_MODULE = os.path.join(
    REPO_ROOT, "src", "App", "src", "models", "storeSurface.ts")
STORE_PACK = os.path.join(
    REPO_ROOT, "content_packs", "store_assistant", "agent_teams",
    "store_assistant.json")
SOP_CORPUS = os.path.join(REPO_ROOT, "content", "sop", "docx")
SOP_MANIFEST = os.path.join(REPO_ROOT, "content", "sop", "corpus.toml")


def rehearsed_question(manifest=SOP_MANIFEST):
    """The question the walkthrough opens with, from the corpus that answers it.

    Never pinned here. `[rehearsed_hit]` names the question *and* the SOP-NNN
    that answers it precisely so that renaming the document away goes red
    instead of quietly becoming an honest miss, and a check carrying its own
    copy of the question asks one the corpus no longer guarantees.

    Read **section-scoped**, exactly as `e2e/authored.ts` reads it and for the
    same reason: `question` is a key under both `[rehearsed_hit]` and
    `[honest_miss]`, so a whole-file match would probe the deployment with the
    question the corpus deliberately cannot answer and report a working agent
    as broken.
    """
    with open(manifest, encoding="utf-8") as handle:
        source = handle.read()
    start = source.find("[rehearsed_hit]")
    if start < 0:
        raise RuntimeError(f"{manifest} has no [rehearsed_hit] section")
    section = source[start + len("[rehearsed_hit]"):]
    end = re.search(r"^\[", section, re.MULTILINE)
    if end:
        section = section[: end.start()]
    match = re.search(r'^question\s*=\s*"([^"]*)"', section, re.MULTILINE)
    if not match:
        raise RuntimeError(f"{manifest} names no rehearsed question")
    return match.group(1)


def authored_expectation(surface=SURFACE_MODULE, pack=STORE_PACK,
                         corpus=SOP_CORPUS):
    """Return the `Expected` this repository authored."""
    with open(pack, encoding="utf-8") as handle:
        team = json.load(handle)
    return Expected(
        assistant=_typescript_constant(surface, "ASSISTANT_NAME"),
        team_id=team["team_id"],
        quick_tasks=tuple(
            (task["id"], task.get("lane"))
            for task in team.get("starting_tasks") or []
        ),
        documents=tuple(sorted(
            name for name in os.listdir(corpus) if name.endswith(".docx")
        )) if os.path.isdir(corpus) else (),
        require_all_agents=team.get("require_all_agents"),
    )


def _typescript_constant(module, name):
    """Read one exported string constant out of the surface's own module."""
    with open(module, encoding="utf-8") as handle:
        match = re.search(
            rf"export const {name} = '([^']*)'", handle.read())
    if not match:
        raise RuntimeError(f"{name} is not exported by {module}")
    return match.group(1)


# ---------------------------------------------------------------------------
# Live reads. Everything above this line is pure.
# ---------------------------------------------------------------------------


def _az(*args):
    """Run an `az` command and return its parsed JSON output."""
    result = subprocess.run(
        ["az", *args, "-o", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"az {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout or "null")


def _get(url, body=None, timeout=180):
    """One request, returning the parsed body or None if it did not answer."""
    headers = {"x-ms-client-principal-id": ANONYMOUS_PRINCIPAL}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (urllib.error.URLError, OSError):
        return None


def read_surface(resource_group, backend_app, frontend_app, team_id):
    """Read the running deployment into the shape `evaluate` expects."""
    backend = _fqdn(resource_group, backend_app)
    frontend = _fqdn(resource_group, frontend_app)
    settings = _az(
        "containerapp", "show",
        "-g", resource_group, "-n", backend_app,
        "--query", "properties.template.containers[0].env",
    ) or []
    page = _get(f"https://{frontend}/", timeout=90) if frontend else None
    title = None
    if page:
        found = TITLE.search(page)
        title = found.group(1) if found else None
    team = None
    if backend:
        raw = _get(
            f"https://{backend}/api/v4/team_configs/{team_id}", timeout=90)
        if raw:
            team = json.loads(raw)
    return {
        "backendUrl": f"https://{backend}" if backend else None,
        "title": title,
        "team": team,
        "tokenEndpoint": next(
            (setting.get("value") for setting in settings
             if setting.get("name") == TOKEN_ENDPOINT_SETTING),
            None,
        ),
    }


def _fqdn(resource_group, app):
    return _az(
        "containerapp", "show",
        "-g", resource_group, "-n", app,
        "--query", "properties.configuration.ingress.fqdn",
    )


def ask_procedure_question(backend_url, question):
    """Ask one procedure question through the deployed backend. Returns a reply.

    Deliberately through `/api/v4/sop/ask` rather than the MCP tool: this is the
    exact path the tool takes, and going through the orchestrator would make a
    failure here indistinguishable from a routing decision.
    """
    if not backend_url:
        return None
    raw = _get(f"{backend_url}/api/v4/sop/ask", body={"question": question})
    if not raw:
        return None
    reply = json.loads(raw)
    return {
        "question": question,
        "failed": reply.get("failed"),
        "platform": reply.get("platform"),
        "source": reply.get("source"),
        "citations": [
            citation.get("name") for citation in reply.get("citations") or []
        ],
        "text": reply.get("text"),
    }


def main(argv=None, read=None, ask=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-group", default=RESOURCE_GROUP)
    parser.add_argument("--backend-app", default=BACKEND_CONTAINER_APP)
    parser.add_argument("--frontend-app", default=FRONTEND_CONTAINER_APP)
    parser.add_argument(
        "--question",
        default=None,
        help="the procedure question to ask the deployed SOP tool. Defaults "
             "to the corpus manifest's own [rehearsed_hit] question — the "
             "easier question, which the orchestrator does not ask (#54).",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="skip the one live procedure question. It is then reported as "
             "unproven rather than as working, and the run exits non-zero: an "
             "unasked question is no evidence that the SOP agent is reachable.",
    )
    args = parser.parse_args(argv)

    expected = authored_expectation()
    reader = read or read_surface
    observed = reader(
        args.resource_group, args.backend_app, args.frontend_app,
        expected.team_id,
    )
    verdict = evaluate(observed, expected)
    if args.no_probe:
        verdict.checks.append(direct_sop_answer_check(None, expected))
    else:
        asker = ask or ask_procedure_question
        verdict.checks.append(
            direct_sop_answer_check(
                asker(observed.get("backendUrl"),
                      args.question or rehearsed_question()), expected))

    print(f"Deployed surface: {args.resource_group}")
    print(format_report(verdict, expected))
    return 0 if verdict.ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
