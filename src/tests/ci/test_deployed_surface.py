"""Tests for the deployed-surface check (issue #44).

`deployed-environment` proves the infrastructure: the right regions, the right
models, three application hosts running an image from our own registry. It is
green against a deployment whose Container Apps are running last month's code,
because an image's *provenance* is not its *currency* — which is exactly the
state `macae-flw-v1` was found in, serving the accelerator's own page title
while every declared loop passed.

This check asks the other question: whatever is running, is the surface it
serves **this** demonstration? The seam under test is the pure evaluation —
given what the deployed frontend, backend and Container App actually answered,
`evaluate` decides whether the shipped surface is the authored one. The live
HTTP and `az` reads sit outside it.
"""

from preflight.deployed_surface import Expected, evaluate, grounded_answer_check

EXPECTED = Expected(
    assistant="Circle K Frontline Store Assistant",
    team_id="00000000-0000-0000-0000-000000000223",
    quick_tasks=(
        ("task-223-procedure", "fast"),
        ("task-223-honest-miss", "fast"),
        ("task-223-troubleshooting", "fast"),
        ("task-223-escalation", "deliberate"),
        ("task-223-identity", "fast"),
        ("task-223-shift-tasks", "fast"),
    ),
)

ACCELERATOR_TITLE = "Multi-Agent - Custom Automation Engine"


def observed(**overrides):
    """What a healthy deployment answered, as the live reads return it."""
    base = {
        "title": EXPECTED.assistant,
        "team": {
            "team_id": EXPECTED.team_id,
            "name": EXPECTED.assistant,
            "starting_tasks": [
                {"id": identifier, "lane": lane}
                for identifier, lane in EXPECTED.quick_tasks
            ],
        },
        "tokenEndpoint": (
            "https://powervamg.us-il102.gateway.prod.island.powerapps.com"
            "/api/botmanagement/v1/directline/directlinetoken?botId=b&tenantId=t"
        ),
    }
    base.update(overrides)
    return base


class TestStoreSurface:
    """The page the frontend serves is the store surface, not the accelerator's."""

    def test_the_authored_assistant_name_passes(self):
        verdict = evaluate(observed(), EXPECTED)

        assert verdict.check("store-surface").ok

    def test_the_accelerators_own_title_fails(self):
        # The whole finding in one string: the deployment served
        # `Multi-Agent - Custom Automation Engine` while `src/App/index.html`
        # read `Circle K Frontline Store Assistant` and nothing sets the title
        # at run time, so the served title *is* the deployed build's identity.
        verdict = evaluate(observed(title=ACCELERATOR_TITLE), EXPECTED)

        check = verdict.check("store-surface")
        assert not check.ok
        assert ACCELERATOR_TITLE in check.detail

    def test_a_surface_that_did_not_answer_fails(self):
        # A cold Container App and a wrong build are indistinguishable from a
        # missing title, and both are reasons not to walk on stage.
        verdict = evaluate(observed(title=None), EXPECTED)

        assert not verdict.check("store-surface").ok


class TestQuickTasks:
    """The six taps the presenter drives the walkthrough with are on the surface."""

    def test_every_authored_task_and_its_lane_passes(self):
        verdict = evaluate(observed(), EXPECTED)

        assert verdict.check("quick-tasks").ok

    def test_a_team_the_backend_does_not_hold_fails(self):
        # The store pack lives in Cosmos, not in the image, so a current build
        # and an unseeded deployment look identical from the registry. The
        # surface reports the assistant is not loaded and every beat has to be
        # typed.
        verdict = evaluate(observed(team=None), EXPECTED)

        check = verdict.check("quick-tasks")
        assert not check.ok
        assert EXPECTED.team_id in check.detail

    def test_a_missing_task_fails_and_names_it(self):
        team = observed()["team"]
        team["starting_tasks"] = [
            task for task in team["starting_tasks"]
            if task["id"] != "task-223-escalation"
        ]
        verdict = evaluate(observed(team=team), EXPECTED)

        check = verdict.check("quick-tasks")
        assert not check.ok
        assert "task-223-escalation" in check.detail

    def test_a_task_that_lost_its_declared_lane_fails(self):
        # A Quick Task that declares no lane falls to the keyword router, and
        # the escalation beat quietly runs without its approval gate — which
        # looks like a working demonstration right up to the ticket.
        team = observed()["team"]
        for task in team["starting_tasks"]:
            if task["id"] == "task-223-escalation":
                task["lane"] = "fast"
        verdict = evaluate(observed(team=team), EXPECTED)

        check = verdict.check("quick-tasks")
        assert not check.ok
        assert "deliberate" in check.detail


class TestDirectLineEndpoint:
    """The backend can reach the Copilot Studio SOP agent at all."""

    def test_the_endpoint_pva_returned_passes(self):
        verdict = evaluate(observed(), EXPECTED)

        assert verdict.check("direct-line-endpoint").ok

    def test_an_unset_endpoint_fails(self):
        # The bicep plumbs the setting through unconditionally, so this was
        # never an infrastructure gap — the value was simply never set, and
        # unset the SOP tool answers with its fixed failure message.
        verdict = evaluate(observed(tokenEndpoint=None), EXPECTED)

        check = verdict.check("direct-line-endpoint")
        assert not check.ok
        assert "COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT" in check.detail

    def test_an_endpoint_assembled_from_the_direct_line_hostname_fails(self):
        # ADR-011: the token endpoint comes from the environment's own regional
        # channel settings service and is never assembled from the default
        # Direct Line hostname. A hand-built one is a plausible-looking URL that
        # issues no token, which reads on stage as the agent being down.
        verdict = evaluate(
            observed(
                tokenEndpoint="https://directline.botframework.com/v3/directline/tokens/generate"
            ),
            EXPECTED,
        )

        assert not verdict.check("direct-line-endpoint").ok


def answer(**overrides):
    """What `/api/v4/sop/ask` replied, as the probe reads it."""
    reply = {
        "question": "How do I close the store?",
        "failed": False,
        "platform": "Copilot Studio",
        "source": "Dataverse",
        "citations": ["SOP-102 Store Closing Procedure.docx"],
        "text": "1. At 60 minutes before close, begin the coffee bar shutdown...",
    }
    reply.update(overrides)
    return reply


class TestGroundedAnswer:
    """One real procedure question, all the way to Copilot Studio and back."""

    def test_a_cited_answer_from_dataverse_passes(self):
        check = grounded_answer_check(answer())

        assert check.ok
        assert "SOP-102 Store Closing Procedure.docx" in check.detail

    def test_an_unasked_question_is_unproven_rather_than_passed(self):
        # The centrepiece claim is that the answer came from Dataverse through
        # Copilot Studio. A run that asked nothing has no evidence of that, and
        # reporting it as a pass is how the deployment shipped unreachable in
        # the first place.
        check = grounded_answer_check(None)

        assert not check.ok
        assert "not" in check.detail

    def test_the_fixed_failure_message_fails(self):
        check = grounded_answer_check(answer(failed=True, citations=[]))

        assert not check.ok

    def test_an_uncited_answer_fails(self):
        # There is no fallback to model knowledge by design, but an answer with
        # no citations is exactly what a fallback would look like, and the
        # Grounding panel would have nothing to render.
        check = grounded_answer_check(answer(citations=[]))

        assert not check.ok

    def test_an_answer_from_somewhere_else_fails(self):
        # Platform and source are the two facts the Grounding panel is a claim
        # about. An answer the orchestrator produced itself is a working demo
        # of the wrong thing.
        check = grounded_answer_check(answer(platform="Azure AI Foundry"))

        assert not check.ok
        assert "Copilot Studio" in check.detail
