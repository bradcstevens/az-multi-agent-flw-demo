# Copyright (c) Microsoft. All rights reserved.
"""Tests for api/router.py.

These tests import the *real* router module and patch its collaborators at the
module level (never via sys.modules), so they do not pollute the shared
interpreter state for other test files that import the same real modules.
"""

import contextlib
import os
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure flat backend imports (models.messages etc.) inside router resolve.
_backend_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
)
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)


def _import_router():
    """Import the real router module despite shared-process mock pollution.

    Earlier-collected tests (e.g. agents/) replace flat modules such as
    ``common.database`` with bare ``Mock()`` objects in ``sys.modules``. Those
    are not packages, so the router's flat imports would fail. We install proper
    package stubs for the flat namespaces the router walks and ``MagicMock``
    stand-ins for its heavy leaf dependencies, letting the lightweight message
    model modules import for real (so FastAPI request/response validation uses
    the genuine dataclasses/pydantic models). Afterwards ``sys.modules`` is
    restored to its exact prior state so no other test file is affected. The
    router's collaborators are patched per-test.
    """
    def _realpkg(name):
        module = ModuleType(name)
        module.__path__ = [os.path.join(_backend_path, *name.split("."))]
        sys.modules[name] = module

    packages = [
        "common", "common.models", "common.config", "common.database",
        "common.utils", "orchestration", "orchestration.helper", "services",
        "auth", "models",
    ]
    heavy_leaves = [
        "common.config.app_config", "common.database.database_factory",
        "common.utils.event_utils", "common.utils.team_utils",
        "orchestration.connection_config", "orchestration.orchestration_manager",
        "services.plan_service", "services.team_service", "auth.auth_utils",
    ]
    # Leaf modules that MUST load for real so FastAPI sees genuine model classes.
    force_real = ["common.models.messages", "models.messages", "models.plan_models"]
    snapshot = dict(sys.modules)
    try:
        for pkg in packages:
            _realpkg(pkg)
        for leaf in heavy_leaves:
            sys.modules[leaf] = MagicMock()
        for name in force_real:
            sys.modules.pop(name, None)
        import backend.api.router as router  # noqa: F401
        from fastapi import FastAPI

        # Build the app while the real message-model modules are importable, so
        # FastAPI resolves the route signatures against the genuine models.
        app = FastAPI()
        app.include_router(router.app_router)
        return router, app
    finally:
        router_mod_obj = sys.modules.get("backend.api.router")
        for key in list(sys.modules):
            if key not in snapshot and not key.startswith("backend"):
                del sys.modules[key]
        for key, value in snapshot.items():
            sys.modules[key] = value
        if router_mod_obj is not None:
            sys.modules["backend.api.router"] = router_mod_obj


router_mod, _app = _import_router()
from fastapi.testclient import TestClient  # noqa: E402

from guardrail.corpus import (  # noqa: E402
    PERSONAL_INTENT_ANCHORS,
    STORE_SCOPE_ANCHORS,
)
from guardrail.gate import IdentityBoundaryGate  # noqa: E402
from guardrail.refusal import IDENTITY_BOUNDARY_REFUSAL  # noqa: E402
from sop.citation import Citation  # noqa: E402
from sop.direct_line import SopAnswer  # noqa: E402


class StubEmbedder:
    """Canned two-dimensional embeddings for the Identity boundary gate.

    The gate under test is the *real* one — the real keyword fast path, the
    real Two-class margin, the real fail-closed rule — so only the embedding
    deployment is stood in for. Anchors point along their own axis and any
    other text is store-shaped unless a test says otherwise, which makes the
    default verdict "admitted" and keeps every pre-existing router test honest.
    """

    def __init__(self):
        self.personal_texts = set()

    async def __call__(self, texts):
        return [self._vector(text) for text in texts]

    def _vector(self, text):
        if text in PERSONAL_INTENT_ANCHORS or text in self.personal_texts:
            return [1.0, 0.0]
        if text in STORE_SCOPE_ANCHORS:
            return [0.0, 1.0]
        return [0.05, 1.0]


# ---------------------------------------------------------------------------
# Fixture: TestClient with all collaborators mocked
# ---------------------------------------------------------------------------
@pytest.fixture
def rt(monkeypatch):
    """Patch every collaborator referenced from the router namespace."""
    store = MagicMock()
    store.get_plan_by_plan_id = AsyncMock(return_value=None)
    store.get_current_team = AsyncMock(return_value=None)
    store.get_team_by_id = AsyncMock(return_value=MagicMock())
    store.get_plan = AsyncMock(return_value=None)
    store.get_agent_messages = AsyncMock(return_value=[])
    store.get_all_plans_by_team_id_status = AsyncMock(return_value=[])
    store.delete_current_team = AsyncMock()
    store.add_plan = AsyncMock()

    # The generic CRUD the memory container exposes, faked well enough that a
    # session-state record genuinely round-trips (issue #20). Keyed by
    # ``(id, partition key)`` the way Cosmos keys it, so a record written under
    # the wrong partition is invisible to a read.
    session_documents = {}

    async def _get_item_by_id(item_id, partition_key, model_class):
        document = session_documents.get((item_id, partition_key))
        if document is None:
            return None
        return model_class.model_validate(document)

    async def _update_item(item):
        session_documents[(item.id, item.session_id)] = item.model_dump(mode="json")

    store.get_item_by_id = AsyncMock(side_effect=_get_item_by_id)
    store.update_item = AsyncMock(side_effect=_update_item)

    database_factory = MagicMock()
    database_factory.get_database = AsyncMock(return_value=store)

    team_service = MagicMock()
    team_service.get_team_configuration = AsyncMock(return_value=None)
    team_service.handle_team_selection = AsyncMock(return_value=MagicMock())
    team_service.get_all_team_configurations = AsyncMock(return_value=[])
    team_service.delete_team_configuration = AsyncMock(return_value=True)
    team_service.validate_team_models = AsyncMock(return_value=(True, []))
    team_service.validate_team_search_indexes = AsyncMock(return_value=(True, []))
    team_service.validate_and_parse_team_config = AsyncMock(return_value=MagicMock())
    team_service.save_team_configuration = AsyncMock(return_value="team-123")
    team_service_cls = MagicMock(return_value=team_service)

    plan_service = MagicMock()
    plan_service.handle_plan_approval = AsyncMock(return_value=True)
    plan_service.handle_human_clarification = AsyncMock(return_value=True)
    plan_service.handle_agent_messages = AsyncMock(return_value=True)

    orchestration_manager = MagicMock()
    orchestration_manager.get_current_or_new_orchestration = AsyncMock()
    orchestration_manager.return_value.run_orchestration = AsyncMock()

    connection_config = MagicMock()
    connection_config.send_status_update_async = AsyncMock()
    connection_config.close_connection = AsyncMock()
    connection_config.add_connection = MagicMock()
    connection_config.wait_for_clarification = AsyncMock(return_value="the answer")

    orchestration_config = MagicMock()
    orchestration_config.wait_for_clarification = AsyncMock(return_value="the answer")
    orchestration_config.approvals = {}
    orchestration_config.clarifications = {}
    orchestration_config.plans = {}
    orchestration_config.active_tasks = {}
    orchestration_config.get_current_orchestration = MagicMock(return_value=None)
    orchestration_config.set_approval_result = MagicMock()
    orchestration_config.set_clarification_result = MagicMock()
    orchestration_config.set_clarification_pending = MagicMock()

    team_config = MagicMock()

    find_first_available_team = AsyncMock(return_value="team-abc")
    rai_success = AsyncMock(return_value=True)
    rai_validate_team_config = AsyncMock(return_value=(True, None))
    get_user = MagicMock(return_value={"user_principal_id": "user-1"})

    embedder = StubEmbedder()
    gate = IdentityBoundaryGate(embed=embedder)

    # The Copilot Studio SOP agent, stood in for at the client's own seam
    # (issue #18). Real `SopAnswer` and real `Citation` — only the network is
    # absent, so the route is exercised against the genuine shapes.
    sop = MagicMock()
    sop.ask = AsyncMock(
        return_value=SopAnswer(
            text="1. Count the drawer.",
            citations=[
                Citation(
                    position=1,
                    name="SOP-102 Store Closing Procedure.docx",
                    abstract="SOP-102 Store Closing Procedure.docx",
                    text="<h1>Store Closing Procedure</h1> body",
                )
            ],
            conversation_id="conv-1",
        )
    )

    monkeypatch.setattr(router_mod, "get_authenticated_user_details", get_user)
    monkeypatch.setattr(router_mod, "identity_boundary_gate", lambda: gate)
    monkeypatch.setattr(router_mod, "DatabaseFactory", database_factory)
    monkeypatch.setattr(router_mod, "TeamService", team_service_cls)
    monkeypatch.setattr(router_mod, "PlanService", plan_service)
    monkeypatch.setattr(router_mod, "OrchestrationManager", orchestration_manager)
    monkeypatch.setattr(router_mod, "connection_config", connection_config)
    monkeypatch.setattr(router_mod, "orchestration_config", orchestration_config)
    monkeypatch.setattr(router_mod, "team_config", team_config)
    monkeypatch.setattr(router_mod, "track_event_if_configured", MagicMock())
    monkeypatch.setattr(
        router_mod, "find_first_available_team", find_first_available_team
    )
    monkeypatch.setattr(router_mod, "rai_success", rai_success)
    monkeypatch.setattr(router_mod, "rai_validate_team_config", rai_validate_team_config)

    app = _app
    client = TestClient(app)

    return SimpleNamespace(
        client=client,
        store=store,
        session_documents=session_documents,
        database_factory=database_factory,
        team_service=team_service,
        team_service_cls=team_service_cls,
        plan_service=plan_service,
        orchestration_manager=orchestration_manager,
        connection_config=connection_config,
        orchestration_config=orchestration_config,
        team_config=team_config,
        find_first_available_team=find_first_available_team,
        rai_success=rai_success,
        rai_validate_team_config=rai_validate_team_config,
        get_user=get_user,
        gate=gate,
        embedder=embedder,
        sop=sop,
    )


def _no_user(rt):
    rt.get_user.return_value = {"user_principal_id": None}


# ---------------------------------------------------------------------------
# /init_team
# ---------------------------------------------------------------------------
class TestInitTeam:
    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.get("/api/v4/init_team")
        assert resp.status_code == 400

    def test_no_teams_configured(self, rt):
        rt.find_first_available_team.return_value = None
        rt.store.get_current_team.return_value = None
        resp = rt.client.get("/api/v4/init_team")
        assert resp.status_code == 200
        body = resp.json()
        assert body["requires_team_upload"] is True

    def test_first_available_team_used(self, rt):
        rt.find_first_available_team.return_value = "team-abc"
        rt.store.get_current_team.return_value = None
        selected = MagicMock()
        selected.team_id = "team-abc"
        rt.team_service.handle_team_selection.return_value = selected
        team_conf = MagicMock()
        rt.team_service.get_team_configuration.return_value = team_conf
        resp = rt.client.get("/api/v4/init_team")
        assert resp.status_code == 200
        assert resp.json()["status"] == "Request started successfully"

    def test_current_team_used(self, rt):
        current = MagicMock()
        current.team_id = "team-current"
        rt.store.get_current_team.return_value = current
        rt.team_service.get_team_configuration.return_value = MagicMock()
        resp = rt.client.get("/api/v4/init_team")
        assert resp.status_code == 200
        assert resp.json()["team_id"] == "team-current"

    def test_team_configuration_missing_clears(self, rt):
        current = MagicMock()
        current.team_id = "team-current"
        rt.store.get_current_team.return_value = current
        rt.team_service.get_team_configuration.return_value = None
        resp = rt.client.get("/api/v4/init_team")
        assert resp.status_code == 200
        assert resp.json()["requires_team_upload"] is True
        rt.store.delete_current_team.assert_awaited()

    def test_exception_returns_400(self, rt):
        rt.database_factory.get_database = AsyncMock(side_effect=Exception("boom"))
        resp = rt.client.get("/api/v4/init_team")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /process_request
# ---------------------------------------------------------------------------
class TestProcessRequest:
    def _payload(self):
        return {"session_id": "sess-1", "description": "do the thing"}

    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.post("/api/v4/process_request", json=self._payload())
        assert resp.status_code == 400

    def test_team_not_found(self, rt):
        rt.store.get_current_team.return_value = None
        rt.store.get_team_by_id.return_value = None
        resp = rt.client.post("/api/v4/process_request", json=self._payload())
        assert resp.status_code == 400

    def test_rai_failure(self, rt):
        rt.store.get_team_by_id.return_value = MagicMock()
        rt.rai_success.return_value = False
        resp = rt.client.post("/api/v4/process_request", json=self._payload())
        assert resp.status_code == 400

    def test_success(self, rt):
        team = MagicMock()
        rt.store.get_team_by_id.return_value = team
        current = MagicMock()
        current.team_id = "team-x"
        rt.store.get_current_team.return_value = current
        rt.rai_success.return_value = True
        resp = rt.client.post("/api/v4/process_request", json=self._payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "Request started successfully"
        assert body["plan_id"]

    def test_success_generates_session_id(self, rt):
        rt.store.get_team_by_id.return_value = MagicMock()
        rt.rai_success.return_value = True
        resp = rt.client.post(
            "/api/v4/process_request", json={"session_id": "", "description": "x"}
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"]


# ---------------------------------------------------------------------------
# /process_request — the Identity boundary gate (issue #14, ADR-014)
# ---------------------------------------------------------------------------
class TestTheIdentityBoundaryGate:
    """The centerpiece, driven through real HTTP against the real gate.

    Only the embedding deployment is stood in for; the keyword fast path, the
    Two-class margin and the fail-closed rule are all the production code.
    """

    PERSONAL = "my name is Tanya, how much PTO do I have?"
    STORE = "How do I close the store?"

    def _post(self, rt, description):
        return rt.client.post(
            "/api/v4/process_request",
            json={"session_id": "sess-1", "description": description},
        )

    def test_a_personal_question_is_refused_as_a_policy_block(self, rt):
        resp = self._post(rt, self.PERSONAL)

        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["kind"] == "policy_block"
        assert detail["code"] == "identity_boundary"
        assert detail["message"] == IDENTITY_BOUNDARY_REFUSAL

    def test_the_orchestration_manager_is_never_invoked(self, rt):
        """"No agent ran, no tokens spent" is the requirement, so assert the
        non-call rather than the refusal — the demo's cost claim rests on it."""
        self._post(rt, self.PERSONAL)

        rt.orchestration_manager.assert_not_called()
        rt.orchestration_manager.return_value.run_orchestration.assert_not_awaited()

    def test_the_safety_check_agent_is_never_created_either(self, rt):
        """The gate runs *before* `rai_success`, which instantiates an agent.

        Placing it after would have spent a model call on every refusal and
        quietly falsified "the guardrail costs nothing".
        """
        self._post(rt, self.PERSONAL)

        rt.rai_success.assert_not_awaited()

    def test_no_plan_is_persisted_for_a_refused_request(self, rt):
        self._post(rt, self.PERSONAL)

        rt.store.add_plan.assert_not_awaited()

    def test_it_refuses_before_the_team_is_even_resolved(self, rt):
        """Ordering, asserted through a failure that would otherwise win.

        A missing team is a 400. If this returns 403 the gate genuinely ran
        first, which is what "before the lane router and before orchestration"
        has to mean at the top of the request path.
        """
        rt.store.get_current_team.return_value = None
        rt.store.get_team_by_id.return_value = None

        assert self._post(rt, self.PERSONAL).status_code == 403

    def test_a_store_level_question_is_unaffected(self, rt):
        """The guardrail must not make the tool useless."""
        resp = self._post(rt, self.STORE)

        assert resp.status_code == 200
        rt.orchestration_manager.assert_called()

    def test_a_paraphrase_with_no_personal_vocabulary_is_still_refused(self, rt):
        """The similarity tier, exercised through the endpoint."""
        paraphrase = "Am I working tomorrow evening?"
        rt.embedder.personal_texts.add(paraphrase)

        assert self._post(rt, paraphrase).status_code == 403

    def test_a_signed_in_identity_is_admitted(self, rt):
        """The mocked unlock: same question, same gate, different identity.

        The name is written into server-side session state (#20) exactly as the
        sign-in beat (#27) will write it, and the gate reads it back through
        that one seam — which is ADR-014's claim that the unlock is a
        *parameter* of the gate and not a second gate.
        """
        rt.client.patch(
            "/api/v4/session_state/sess-1",
            json={"identity": {"display_name": "Tanya Reyes"}},
        )

        resp = self._post(rt, self.PERSONAL)

        assert resp.status_code == 200
        rt.orchestration_manager.assert_called()

    def test_a_gate_that_cannot_score_refuses(self, rt, monkeypatch):
        """Fail closed all the way out to the HTTP response."""
        async def broken(_texts):
            raise RuntimeError("the embedding deployment is unreachable")

        monkeypatch.setattr(rt.gate, "_embed", broken)

        assert self._post(rt, self.STORE).status_code == 403


# ---------------------------------------------------------------------------
# /process_request — the lane router and the Workflow cache (issues #15 and
# #16, ADR-013)
# ---------------------------------------------------------------------------
class TestPerRequestPlanReview:
    """The Lane a request takes reaches the orchestration call as Plan review.

    The Fast lane is the same orchestration path with the approval gate off,
    not a second path — so the only thing to observe here is which value the
    orchestration call was handed. The request declares a **Lane**; the
    endpoint is where the lane router maps it onto Plan review, which is why
    this is the seam ADR-013 names for lane behaviour.
    """

    def _post(self, rt, **body):
        rt.store.get_team_by_id.return_value = MagicMock()
        rt.rai_success.return_value = True
        payload = {"session_id": "sess-1", "description": "how do I close the store?"}
        payload.update(body)
        return rt.client.post("/api/v4/process_request", json=payload)

    def _plan_review_passed(self, rt):
        return (
            rt.orchestration_manager
            .get_current_or_new_orchestration
            .call_args.kwargs["plan_review"]
        )

    def _eagerly_built_workflow(self, rt, plan_review=True):
        """What /init_team leaves in the Workflow cache before any task.

        The manager is mocked, so it is wired here to do what the real one does
        on a rebuild — install the new Workflow in the cache — otherwise the
        stale one would still be installed at the end of a "rebuild" and the
        test could not tell the difference.
        """
        workflow = MagicMock()
        workflow._terminated = False
        workflow._is_running = False
        workflow._team_id = None
        workflow._plan_review = plan_review
        cache = {"current": workflow}
        rt.orchestration_config.get_current_orchestration.side_effect = (
            lambda _user_id: cache["current"]
        )

        async def rebuild(**kwargs):
            rebuilt = MagicMock()
            rebuilt._terminated = False
            rebuilt._is_running = False
            # None matches the team_id the router resolves for this fixture, so
            # the team term cannot mask the lane term being tested.
            rebuilt._team_id = None
            rebuilt._plan_review = kwargs["plan_review"]
            cache["current"] = rebuilt
            return rebuilt

        rt.orchestration_manager.get_current_or_new_orchestration.side_effect = rebuild
        return cache

    def test_a_deliberate_lane_request_keeps_the_approval_gate(self, rt):
        assert self._post(rt, lane="deliberate").status_code == 200
        assert self._plan_review_passed(rt) is True

    def test_a_fast_lane_request_turns_the_approval_gate_off(self, rt):
        assert self._post(rt, lane="fast").status_code == 200
        assert self._plan_review_passed(rt) is False

    def test_free_typed_input_falls_back_to_the_keyword_selection(self, rt):
        """No declared lane at all — the fixture's description is an SOP lookup.

        Asserting Fast here is what proves the keyword fallback is wired into
        the request path rather than merely unit-tested: a request that
        declares nothing would otherwise take the Deliberate default.
        """
        assert self._post(rt).status_code == 200
        assert self._plan_review_passed(rt) is False

    def test_free_typed_escalation_keeps_the_approval_gate(self, rt):
        resp = self._post(rt, description="I can't fix it, please escalate this")

        assert resp.status_code == 200
        assert self._plan_review_passed(rt) is True

    def test_an_unparseable_lane_fails_open_to_the_deliberate_lane(self, rt):
        """A router failure never becomes a policy failure on stage.

        The description is a plain Fast lane lookup, so the keyword fallback
        would say Fast. A corrupt declaration must outrank it.
        """
        assert self._post(rt, lane="quick").status_code == 200
        assert self._plan_review_passed(rt) is True

    def test_a_lane_that_is_not_even_a_string_is_rejected_by_the_schema(self, rt):
        """Where the fail-open rule stops, and why that is safe.

        Fail open covers an unreadable *lane* — a string that is not one of the
        two. A lane that is not a string at all is a malformed request, and the
        schema refuses it before the router is reached. That is not a lane
        decision going the wrong way: nothing is routed, no plan is created and
        no orchestration is built, so the approval gate cannot be lost.
        """
        assert self._post(rt, lane=7).status_code == 422
        rt.orchestration_manager.get_current_or_new_orchestration.assert_not_awaited()

    def test_the_lane_taken_comes_back_on_the_response(self, rt):
        """Surfaced as a feature, not hidden as an implementation detail.

        The lane *taken* is the router's output, not the client's declaration,
        so free-typed input is the case worth asserting: the client cannot
        know it without being told.
        """
        assert self._post(rt).json()["lane"] == "fast"
        assert self._post(rt, lane="deliberate").json()["lane"] == "deliberate"

    def test_the_first_request_after_a_page_load_is_not_served_the_eager_workflow(
        self, rt
    ):
        """The Workflow cache fix, at the endpoint.

        /init_team eagerly builds a Workflow with Plan review on before any
        task is submitted. Without the fix the very first Fast lane request
        reuses it and silently runs in the Deliberate lane.
        """
        cache = self._eagerly_built_workflow(rt, plan_review=True)
        eager = cache["current"]

        assert self._post(rt, lane="fast").status_code == 200

        rt.orchestration_manager.get_current_or_new_orchestration.assert_awaited()
        assert self._plan_review_passed(rt) is False
        # The stale Workflow is gone from the cache, replaced by a Fast lane one
        assert cache["current"] is not eager
        assert cache["current"]._plan_review is False

    def test_a_workflow_already_built_for_this_lane_is_reused(self, rt):
        """The complement: matching lane, matching team, nothing to rebuild.

        Together with the test above this isolates the Plan review term — the
        two differ in nothing but the lane the cached Workflow was built for.
        """
        cache = self._eagerly_built_workflow(rt, plan_review=False)
        cached = cache["current"]

        assert self._post(rt, lane="fast").status_code == 200

        rt.orchestration_manager.get_current_or_new_orchestration.assert_not_awaited()
        assert cache["current"] is cached


# ---------------------------------------------------------------------------
# /session_state — server-side session state (issue #20)
# ---------------------------------------------------------------------------
class TestSessionState:
    """The route, driven through real HTTP against the faked memory container.

    Session state is held server-side precisely so a mid-demo browser reload
    does not lose it, so every assertion here is a second request standing in
    for the reload: nothing about the first request's client survives it.
    """

    def _get(self, rt, session_id="sess-1"):
        return rt.client.get(f"/api/v4/session_state/{session_id}")

    def _patch(self, rt, body, session_id="sess-1"):
        return rt.client.patch(f"/api/v4/session_state/{session_id}", json=body)

    def test_no_user(self, rt):
        _no_user(rt)
        assert self._get(rt).status_code == 400

    def test_no_user_cannot_write_either(self, rt):
        _no_user(rt)
        assert self._patch(rt, {"lane": "fast"}).status_code == 400

    def test_a_session_with_no_record_reads_back_the_opening_state(self, rt):
        """Absent is not an error — it is the state the demo opens in."""
        resp = self._get(rt)

        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "sess-1"
        assert body["identity"]["display_name"] is None
        assert body["lane"] is None

    def test_a_written_identity_survives_the_reload(self, rt):
        assert self._patch(rt, {"identity": {"display_name": "Tanya"}}).status_code == 200

        assert self._get(rt).json()["identity"]["display_name"] == "Tanya"

    def test_a_written_lane_survives_the_reload(self, rt):
        self._patch(rt, {"lane": "fast"})

        assert self._get(rt).json()["lane"] == "fast"

    def test_writing_one_field_leaves_the_other_alone(self, rt):
        """Two surfaces write this record and neither may erase the other."""
        self._patch(rt, {"identity": {"display_name": "Tanya"}})
        self._patch(rt, {"lane": "fast"})

        body = self._get(rt).json()
        assert body["identity"]["display_name"] == "Tanya"
        assert body["lane"] == "fast"

    def test_signing_out_returns_to_the_anonymous_state(self, rt):
        """An explicit null clears; it is a write, not the absence of one."""
        self._patch(rt, {"identity": {"display_name": "Tanya"}})
        self._patch(rt, {"identity": None})

        assert self._get(rt).json()["identity"]["display_name"] is None

    def test_one_session_cannot_read_another_sessions_state(self, rt):
        """The record is partitioned by session, observed through the route."""
        self._patch(rt, {"identity": {"display_name": "Tanya"}})

        other = self._get(rt, session_id="sess-2").json()
        assert other["identity"]["display_name"] is None

    def test_one_user_cannot_read_another_users_session_state(self, rt):
        """Records in this container carry their owner and reads are scoped by
        it, so a session identifier alone does not unlock somebody else's
        session — the gate would otherwise admit on a borrowed record."""
        self._patch(rt, {"identity": {"display_name": "Tanya"}})
        rt.get_user.return_value = {"user_principal_id": "user-2"}

        assert self._get(rt).json()["identity"]["display_name"] is None

    def test_the_record_is_discriminated_by_data_type(self, rt):
        self._patch(rt, {"lane": "fast"})

        document = next(iter(rt.session_documents.values()))
        assert document["data_type"] == "session_state"

    def test_an_unreachable_container_is_an_error_on_this_route(self, rt):
        """Unlike the gate, a read that failed has no safe answer to fall back
        on here — the caller asked for the state, so say it could not be had."""
        rt.database_factory.get_database = AsyncMock(side_effect=Exception("boom"))

        assert self._get(rt).status_code == 500


# ---------------------------------------------------------------------------
# /process_request — reading and writing session state (issue #20)
# ---------------------------------------------------------------------------
class TestProcessRequestUsesSessionState:
    PERSONAL = "my name is Tanya, how much PTO do I have?"

    def _post(self, rt, description="how do I close the store?", **body):
        rt.store.get_team_by_id.return_value = MagicMock()
        rt.rai_success.return_value = True
        payload = {"session_id": "sess-1", "description": description}
        payload.update(body)
        return rt.client.post("/api/v4/process_request", json=payload)

    def test_the_lane_taken_is_recorded_for_a_reloaded_page(self, rt):
        """The lane taken is the router's output, so a reloaded plan page can
        only get it from the server. Recording it here is what makes the badge
        survive a reload rather than vanish with the router state."""
        assert self._post(rt, lane="deliberate").status_code == 200

        assert rt.client.get("/api/v4/session_state/sess-1").json()["lane"] == "deliberate"

    def test_an_anonymous_session_still_refuses_a_personal_question(self, rt):
        """The record exists now, and its default must still be the refusing
        state — nobody has signed in."""
        assert self._post(rt, description=self.PERSONAL).status_code == 403

    def test_a_name_in_another_session_does_not_unlock_this_one(self, rt):
        """Signing in on one device is not signing in on the shared one."""
        rt.client.patch(
            "/api/v4/session_state/sess-other",
            json={"identity": {"display_name": "Tanya Reyes"}},
        )

        assert self._post(rt, description=self.PERSONAL).status_code == 403

    def test_an_unreadable_record_refuses_rather_than_admits(self, rt):
        """Fail-closed, at the seam where the gate meets the container.

        A read that raises must resolve to the anonymous identity — the
        refusing one. Admitting on a Cosmos outage would turn an infrastructure
        failure into a governance failure on stage.
        """
        rt.client.patch(
            "/api/v4/session_state/sess-1",
            json={"identity": {"display_name": "Tanya Reyes"}},
        )
        rt.store.get_item_by_id = AsyncMock(side_effect=Exception("cosmos is down"))

        assert self._post(rt, description=self.PERSONAL).status_code == 403

    def test_a_failed_lane_recording_does_not_fail_the_request(self, rt):
        """Recording the lane is best-effort: a badge that cannot be restored
        after a reload is not a reason to refuse to start the request."""
        rt.store.update_item = AsyncMock(side_effect=Exception("cosmos is down"))

        assert self._post(rt, lane="fast").status_code == 200


# ---------------------------------------------------------------------------
# /plan_approval
# ---------------------------------------------------------------------------
class TestPlanApproval:
    def _payload(self, **kw):
        data = {"m_plan_id": "m-1", "approved": True, "plan_id": "p-1", "feedback": "ok"}
        data.update(kw)
        return data

    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.post("/api/v4/plan_approval", json=self._payload())
        assert resp.status_code == 401

    def test_approved_recorded(self, rt):
        rt.orchestration_config.approvals = {"m-1": True}
        plan = MagicMock()
        plan.session_id = "sess-1"
        rt.store.get_plan_by_plan_id.return_value = plan
        resp = rt.client.post("/api/v4/plan_approval", json=self._payload())
        assert resp.status_code == 200
        assert resp.json()["status"] == "approval recorded"
        rt.orchestration_config.set_approval_result.assert_called_once()

    def test_rejected_recorded(self, rt):
        rt.orchestration_config.approvals = {"m-1": True}
        rt.store.get_plan_by_plan_id.return_value = None
        resp = rt.client.post(
            "/api/v4/plan_approval", json=self._payload(approved=False)
        )
        assert resp.status_code == 200

    def test_no_active_plan(self, rt):
        # The 404 raised in the else-branch is caught by the surrounding
        # `except Exception` block and surfaced as a 500 by the endpoint.
        rt.orchestration_config.approvals = {}
        resp = rt.client.post("/api/v4/plan_approval", json=self._payload())
        assert resp.status_code == 500

    def test_plan_service_value_error(self, rt):
        rt.orchestration_config.approvals = {"m-1": True}
        rt.plan_service.handle_plan_approval = AsyncMock(side_effect=ValueError("bad"))
        resp = rt.client.post("/api/v4/plan_approval", json=self._payload())
        assert resp.status_code == 200

    def test_plan_service_generic_error(self, rt):
        rt.orchestration_config.approvals = {"m-1": True}
        rt.plan_service.handle_plan_approval = AsyncMock(side_effect=Exception("boom"))
        resp = rt.client.post("/api/v4/plan_approval", json=self._payload())
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /clarification/ask
# ---------------------------------------------------------------------------
class TestClarificationAsk:
    def test_missing_fields(self, rt):
        resp = rt.client.post("/api/v4/clarification/ask", json={"question": ""})
        assert resp.status_code == 400

    def test_success(self, rt):
        rt.orchestration_config.wait_for_clarification.return_value = "answer!"
        resp = rt.client.post(
            "/api/v4/clarification/ask",
            json={"question": "why?", "user_id": "user-1"},
        )
        assert resp.status_code == 200
        assert resp.json()["answer"] == "answer!"

    def test_timeout(self, rt):
        import asyncio

        rt.orchestration_config.wait_for_clarification = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        resp = rt.client.post(
            "/api/v4/clarification/ask",
            json={"question": "why?", "user_id": "user-1"},
        )
        assert resp.status_code == 200
        assert resp.json()["answer"] == ""

    def test_generic_error(self, rt):
        rt.orchestration_config.wait_for_clarification = AsyncMock(
            side_effect=Exception("boom")
        )
        resp = rt.client.post(
            "/api/v4/clarification/ask",
            json={"question": "why?", "user_id": "user-1"},
        )
        assert resp.status_code == 200
        assert resp.json()["answer"] == ""


# ---------------------------------------------------------------------------
# /user_clarification
# ---------------------------------------------------------------------------
class TestUserClarification:
    def _payload(self, **kw):
        data = {"request_id": "r-1", "answer": "my answer", "plan_id": "p-1"}
        data.update(kw)
        return data

    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.post("/api/v4/user_clarification", json=self._payload())
        assert resp.status_code == 401

    def test_team_not_found(self, rt):
        rt.store.get_team_by_id.return_value = None
        resp = rt.client.post("/api/v4/user_clarification", json=self._payload())
        assert resp.status_code == 400

    def test_rai_failure(self, rt):
        rt.store.get_team_by_id.return_value = MagicMock()
        rt.rai_success.return_value = False
        resp = rt.client.post("/api/v4/user_clarification", json=self._payload())
        assert resp.status_code == 400

    def test_success(self, rt):
        rt.store.get_team_by_id.return_value = MagicMock()
        rt.rai_success.return_value = True
        rt.orchestration_config.clarifications = {"r-1": True}
        resp = rt.client.post("/api/v4/user_clarification", json=self._payload())
        assert resp.status_code == 200
        assert resp.json()["status"] == "clarification recorded"

    def test_no_active_clarification(self, rt):
        rt.store.get_team_by_id.return_value = MagicMock()
        rt.rai_success.return_value = True
        rt.orchestration_config.clarifications = {}
        resp = rt.client.post("/api/v4/user_clarification", json=self._payload())
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /agent_message
# ---------------------------------------------------------------------------
class TestAgentMessage:
    def _payload(self, **kw):
        data = {
            "plan_id": "p-1",
            "agent": "My Agent",
            "content": "hello",
            "agent_type": "AI_Agent",
        }
        data.update(kw)
        return data

    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.post("/api/v4/agent_message", json=self._payload())
        assert resp.status_code == 401

    def test_success(self, rt):
        plan = MagicMock()
        plan.session_id = "sess-1"
        rt.store.get_plan_by_plan_id.return_value = plan
        resp = rt.client.post("/api/v4/agent_message", json=self._payload())
        assert resp.status_code == 200
        assert resp.json()["status"] == "message recorded"

    def test_plan_service_error(self, rt):
        rt.plan_service.handle_agent_messages = AsyncMock(side_effect=Exception("boom"))
        resp = rt.client.post("/api/v4/agent_message", json=self._payload())
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /upload_team_config
# ---------------------------------------------------------------------------
class TestUploadTeamConfig:
    def _file(self, content=b'{"name": "t", "status": "active"}', name="team.json"):
        return {"file": (name, content, "application/json")}

    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.post("/api/v4/upload_team_config", files=self._file())
        assert resp.status_code == 400

    def test_non_json_file(self, rt):
        resp = rt.client.post(
            "/api/v4/upload_team_config", files=self._file(name="team.txt")
        )
        assert resp.status_code == 400

    def test_invalid_json(self, rt):
        resp = rt.client.post(
            "/api/v4/upload_team_config", files=self._file(content=b"not json")
        )
        assert resp.status_code == 400

    def test_rai_validation_failure(self, rt):
        rt.rai_validate_team_config.return_value = (False, "unsafe content")
        resp = rt.client.post("/api/v4/upload_team_config", files=self._file())
        assert resp.status_code == 400

    def test_model_validation_failure(self, rt):
        rt.rai_validate_team_config.return_value = (True, None)
        rt.team_service.validate_team_models.return_value = (False, ["gpt-4"])
        resp = rt.client.post("/api/v4/upload_team_config", files=self._file())
        assert resp.status_code == 400

    def test_search_validation_failure(self, rt):
        rt.rai_validate_team_config.return_value = (True, None)
        rt.team_service.validate_team_models.return_value = (True, [])
        rt.team_service.validate_team_search_indexes.return_value = (False, ["idx err"])
        resp = rt.client.post("/api/v4/upload_team_config", files=self._file())
        assert resp.status_code == 400

    def test_success(self, rt):
        rt.rai_validate_team_config.return_value = (True, None)
        rt.team_service.validate_team_models.return_value = (True, [])
        rt.team_service.validate_team_search_indexes.return_value = (True, [])
        team_conf = MagicMock()
        team_conf.agents = [1]
        team_conf.starting_tasks = [1]
        team_conf.name = "MyTeam"
        team_conf.model_dump.return_value = {"name": "MyTeam"}
        rt.team_service.validate_and_parse_team_config.return_value = team_conf
        rt.team_service.save_team_configuration.return_value = "team-999"
        resp = rt.client.post("/api/v4/upload_team_config", files=self._file())
        assert resp.status_code == 200
        assert resp.json()["team_id"] == "team-999"

    def test_success_with_team_id(self, rt):
        rt.team_service.validate_team_models.return_value = (True, [])
        rt.team_service.validate_team_search_indexes.return_value = (True, [])
        team_conf = MagicMock()
        team_conf.agents = []
        team_conf.starting_tasks = []
        team_conf.name = "MyTeam"
        team_conf.model_dump.return_value = {"name": "MyTeam"}
        rt.team_service.validate_and_parse_team_config.return_value = team_conf
        rt.team_service.save_team_configuration.return_value = "given-id"
        resp = rt.client.post(
            "/api/v4/upload_team_config?team_id=given-id", files=self._file()
        )
        assert resp.status_code == 200

    def test_parse_value_error(self, rt):
        rt.team_service.validate_team_models.return_value = (True, [])
        rt.team_service.validate_team_search_indexes.return_value = (True, [])
        rt.team_service.validate_and_parse_team_config = AsyncMock(
            side_effect=ValueError("bad config")
        )
        resp = rt.client.post("/api/v4/upload_team_config", files=self._file())
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /team_configs (GET all)
# ---------------------------------------------------------------------------
class TestGetTeamConfigs:
    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.get("/api/v4/team_configs")
        assert resp.status_code == 401

    def test_success(self, rt):
        c = MagicMock()
        c.model_dump.return_value = {"id": "1"}
        rt.team_service.get_all_team_configurations.return_value = [c]
        resp = rt.client.get("/api/v4/team_configs")
        assert resp.status_code == 200
        assert resp.json() == [{"id": "1"}]

    def test_error(self, rt):
        rt.team_service.get_all_team_configurations = AsyncMock(
            side_effect=Exception("boom")
        )
        resp = rt.client.get("/api/v4/team_configs")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# /team_configs/{team_id}
# ---------------------------------------------------------------------------
class TestGetTeamConfigById:
    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.get("/api/v4/team_configs/t1")
        assert resp.status_code == 401

    def test_not_found(self, rt):
        rt.team_service.get_team_configuration.return_value = None
        resp = rt.client.get("/api/v4/team_configs/t1")
        assert resp.status_code == 404

    def test_success(self, rt):
        conf = MagicMock()
        conf.model_dump.return_value = {"id": "t1"}
        rt.team_service.get_team_configuration.return_value = conf
        resp = rt.client.get("/api/v4/team_configs/t1")
        assert resp.status_code == 200
        assert resp.json() == {"id": "t1"}

    def test_error(self, rt):
        rt.team_service.get_team_configuration = AsyncMock(
            side_effect=Exception("boom")
        )
        resp = rt.client.get("/api/v4/team_configs/t1")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /team_configs/{team_id}
# ---------------------------------------------------------------------------
class TestDeleteTeamConfig:
    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.delete("/api/v4/team_configs/t1")
        assert resp.status_code == 401

    def test_not_found(self, rt):
        rt.team_service.delete_team_configuration.return_value = False
        resp = rt.client.delete("/api/v4/team_configs/t1")
        assert resp.status_code == 404

    def test_success(self, rt):
        rt.team_service.delete_team_configuration.return_value = True
        resp = rt.client.delete("/api/v4/team_configs/t1")
        assert resp.status_code == 200
        assert resp.json()["team_id"] == "t1"

    def test_error(self, rt):
        rt.team_service.delete_team_configuration = AsyncMock(
            side_effect=Exception("boom")
        )
        resp = rt.client.delete("/api/v4/team_configs/t1")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# /select_team
# ---------------------------------------------------------------------------
class TestSelectTeam:
    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.post("/api/v4/select_team", json={"team_id": "t1"})
        assert resp.status_code == 401

    def test_missing_team_id(self, rt):
        resp = rt.client.post("/api/v4/select_team", json={"team_id": ""})
        assert resp.status_code == 400

    def test_team_not_found(self, rt):
        rt.team_service.get_team_configuration.return_value = None
        resp = rt.client.post("/api/v4/select_team", json={"team_id": "t1"})
        assert resp.status_code == 404

    def test_selection_failed(self, rt):
        conf = MagicMock()
        conf.name = "TeamA"
        rt.team_service.get_team_configuration.return_value = conf
        rt.team_service.handle_team_selection.return_value = None
        resp = rt.client.post("/api/v4/select_team", json={"team_id": "t1"})
        assert resp.status_code == 404

    def test_success(self, rt):
        conf = MagicMock()
        conf.name = "TeamA"
        conf.agents = [1, 2]
        conf.description = "desc"
        rt.team_service.get_team_configuration.return_value = conf
        rt.team_service.handle_team_selection.return_value = MagicMock()
        resp = rt.client.post("/api/v4/select_team", json={"team_id": "t1"})
        assert resp.status_code == 200
        assert resp.json()["team_id"] == "t1"

    def test_error(self, rt):
        rt.team_service.get_team_configuration = AsyncMock(
            side_effect=Exception("boom")
        )
        resp = rt.client.post("/api/v4/select_team", json={"team_id": "t1"})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# /plans
# ---------------------------------------------------------------------------
class TestGetPlans:
    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.get("/api/v4/plans")
        assert resp.status_code == 400

    def test_no_current_team(self, rt):
        rt.store.get_current_team.return_value = None
        resp = rt.client.get("/api/v4/plans")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_success(self, rt):
        current = MagicMock()
        current.team_id = "t1"
        rt.store.get_current_team.return_value = current
        rt.store.get_all_plans_by_team_id_status.return_value = []
        resp = rt.client.get("/api/v4/plans")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /plan
# ---------------------------------------------------------------------------
class TestGetPlanById:
    def test_no_user(self, rt):
        _no_user(rt)
        resp = rt.client.get("/api/v4/plan?plan_id=p1")
        assert resp.status_code == 400

    def test_no_plan_id(self, rt):
        resp = rt.client.get("/api/v4/plan")
        assert resp.status_code == 500

    def test_plan_not_found(self, rt):
        rt.store.get_plan_by_plan_id.return_value = None
        resp = rt.client.get("/api/v4/plan?plan_id=p1")
        assert resp.status_code == 500

    def test_success(self, rt):
        plan = MagicMock()
        plan.session_id = "sess-1"
        plan.team_id = "t1"
        plan.plan_id = "p1"
        plan.m_plan = {"x": 1}
        plan.streaming_message = "streaming"
        rt.store.get_plan_by_plan_id.return_value = plan
        rt.store.get_team_by_id.return_value = MagicMock()
        rt.store.get_agent_messages.return_value = []
        resp = rt.client.get("/api/v4/plan?plan_id=p1")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /images/{blob_name}
# ---------------------------------------------------------------------------
class TestGetGeneratedImage:
    def test_storage_not_configured(self, rt, monkeypatch):
        cfg = MagicMock()
        cfg.AZURE_STORAGE_BLOB_URL = ""
        monkeypatch.setattr(router_mod, "config", cfg)
        resp = rt.client.get("/api/v4/images/pic.png")
        assert resp.status_code == 503

    def test_invalid_name(self, rt, monkeypatch):
        cfg = MagicMock()
        cfg.AZURE_STORAGE_BLOB_URL = "https://blob"
        cfg.AZURE_STORAGE_IMAGES_CONTAINER = "images"
        monkeypatch.setattr(router_mod, "config", cfg)
        resp = rt.client.get("/api/v4/images/evil!.png")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# WebSocket /socket/{process_id}
# ---------------------------------------------------------------------------
class TestWebSocket:
    def test_connect_and_disconnect(self, rt):
        plan = MagicMock()
        plan.session_id = "sess-1"
        rt.store.get_plan_by_plan_id.return_value = plan
        with rt.client.websocket_connect(
            "/api/v4/socket/proc-1?user_id=user-1"
        ) as ws:
            ws.send_text("hello")
        rt.connection_config.add_connection.assert_called_once()

    def test_connect_default_user(self, rt):
        rt.store.get_plan_by_plan_id.return_value = None
        with contextlib.suppress(Exception):
            with rt.client.websocket_connect("/api/v4/socket/proc-2") as ws:
                ws.close()


# ---------------------------------------------------------------------------
# /sop/ask — the bridge the SOP MCP tool calls back on (issue #18)
# ---------------------------------------------------------------------------
class TestSopAsk:
    """The MCP container has no Direct Line client of its own.

    It ships only its own directory and `httpx`, so the client lives in the
    backend and the tool calls back over HTTP — the pattern `ask_user` already
    uses. This route is that bridge, and it is where the citation crosses from
    Copilot Studio into the shape the Grounding panel reads.
    """

    def _post(self, rt, question="How do I close the store?"):
        return rt.client.post("/api/v4/sop/ask", json={"question": question})

    def test_a_question_returns_the_agents_answer(self, rt, monkeypatch):
        monkeypatch.setattr(router_mod, "sop_client", lambda: rt.sop)

        resp = self._post(rt)

        assert resp.status_code == 200
        assert resp.json()["text"] == "1. Count the drawer."

    def test_an_empty_question_is_rejected(self, rt, monkeypatch):
        monkeypatch.setattr(router_mod, "sop_client", lambda: rt.sop)

        assert self._post(rt, question="  ").status_code == 400

    def test_the_citation_crosses_with_a_name_and_a_snippet(self, rt, monkeypatch):
        """An absent URL is expected, not a fault — ADR-011's prediction,
        confirmed live in #17. Name plus snippet is the whole rendering."""
        monkeypatch.setattr(router_mod, "sop_client", lambda: rt.sop)

        (citation,) = self._post(rt).json()["citations"]

        assert citation["name"] == "SOP-102 Store Closing Procedure.docx"
        assert citation["snippet"] == "Store Closing Procedure body"
        assert citation["url"] is None

    def test_the_answer_names_the_platform_and_the_source(self, rt, monkeypatch):
        """R6's claim is which *platform* answered, and the SOP corpus lives in
        Dataverse — never SharePoint (ADR-012)."""
        monkeypatch.setattr(router_mod, "sop_client", lambda: rt.sop)

        body = self._post(rt).json()

        assert body["platform"] == "Copilot Studio"
        assert body["source"] == "Dataverse"

    def test_an_unconfigured_agent_is_the_fixed_failure_not_a_traceback(
        self, rt, monkeypatch
    ):
        """No agent configured must never become an answer from somewhere
        else: the tool gets the fixed failure message and says so."""
        def _unconfigured():
            raise ValueError("COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT is not configured")

        monkeypatch.setattr(router_mod, "sop_client", _unconfigured)

        body = self._post(rt).json()

        assert body["failed"] is True
        assert body["text"] == router_mod.DIRECT_LINE_FAILURE
        assert body["citations"] == []
