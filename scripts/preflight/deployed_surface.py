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

# The two facts the Grounding panel is a claim about. They live in
# `src/backend/sop/provenance.py`; repeated here because this check runs
# with nothing but `python3` on PATH and must not import the backend.
SOP_PLATFORM = "Copilot Studio"
SOP_SOURCE = "Dataverse"

TITLE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


class Expected:
    """What this repository authored, read out of the repository."""

    def __init__(self, assistant, team_id, quick_tasks):
        self.assistant = assistant
        self.team_id = team_id
        self.quick_tasks = tuple(quick_tasks)


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


def grounded_answer_check(reply):
    """Return the `Check` for one real procedure question. Pure.

    The centrepiece beat's whole claim is that the answer arrived from
    Dataverse *through Copilot Studio*, so what is graded is the provenance and
    the citations, never the prose — a fluent answer is precisely what an
    ungrounded fallback produces. An unasked question is reported as unproven
    and fails, because a run that gathered no evidence must not report the
    cross-platform hop as working.
    """
    if not reply:
        return Check(
            "grounded-answer",
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
    if problems:
        return Check("grounded-answer", False, "; ".join(problems))
    return Check(
        "grounded-answer",
        True,
        f"{reply.get('question')!r} was answered from {SOP_SOURCE} through "
        f"{SOP_PLATFORM}, citing {', '.join(reply['citations'])}",
    )
