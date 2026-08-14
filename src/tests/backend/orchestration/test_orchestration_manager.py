"""Unit tests for orchestration_manager module.

Tests OrchestrationManager:
- init_orchestration() — builds MagenticBuilder workflow
- get_current_or_new_orchestration() — lifecycle management
- run_orchestration() — event stream processing with plan review
- _process_event_stream() — event dispatch
"""

import json
import logging
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Set up required environment variables before any imports
os.environ.update({
    'APPLICATIONINSIGHTS_CONNECTION_STRING': 'InstrumentationKey=test-key',
    'APP_ENV': 'dev',
    'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com/',
    'AZURE_OPENAI_API_KEY': 'test_key',
    'AZURE_OPENAI_DEPLOYMENT_NAME': 'test_deployment',
    'AZURE_AI_SUBSCRIPTION_ID': 'test_subscription_id',
    'AZURE_AI_RESOURCE_GROUP': 'test_resource_group',
    'AZURE_AI_PROJECT_NAME': 'test_project_name',
    'AZURE_AI_AGENT_ENDPOINT': 'https://test.agent.azure.com/',
    'AZURE_AI_PROJECT_ENDPOINT': 'https://test.project.azure.com/',
    'COSMOSDB_ENDPOINT': 'https://test.documents.azure.com:443/',
    'COSMOSDB_DATABASE': 'test_database',
    'COSMOSDB_CONTAINER': 'test_container',
    'AZURE_CLIENT_ID': 'test_client_id',
    'AZURE_TENANT_ID': 'test_tenant_id',
    'AZURE_OPENAI_RAI_DEPLOYMENT_NAME': 'test_rai_deployment',
})

# Mock external Azure dependencies
sys.modules['azure'] = Mock()
sys.modules['azure.ai'] = Mock()
sys.modules['azure.ai.agents'] = Mock()
sys.modules['azure.ai.agents.aio'] = Mock(AgentsClient=Mock)
sys.modules['azure.ai.projects'] = Mock()
sys.modules['azure.ai.projects.aio'] = Mock(AIProjectClient=Mock)
sys.modules['azure.ai.projects.models'] = Mock(MCPTool=Mock)
sys.modules['azure.ai.projects.models._models'] = Mock()
sys.modules['azure.ai.projects._client'] = Mock()
sys.modules['azure.ai.projects.operations'] = Mock()
sys.modules['azure.ai.projects.operations._patch'] = Mock()
sys.modules['azure.ai.projects.operations._patch_datasets'] = Mock()
sys.modules['azure.search'] = Mock()
sys.modules['azure.search.documents'] = Mock()
sys.modules['azure.search.documents.indexes'] = Mock()
sys.modules['azure.core'] = Mock()
sys.modules['azure.core.exceptions'] = Mock()
sys.modules['azure.identity'] = Mock()
sys.modules['azure.identity.aio'] = Mock()
sys.modules['azure.cosmos'] = Mock(CosmosClient=Mock)


# ---------------------------------------------------------------------------
# Lightweight mock types for agent_framework
# ---------------------------------------------------------------------------
class MockMessage:
    """Mock Message returned by executor_completed events."""
    def __init__(self, text="Mock message", contents=None):
        self.text = text
        self.contents = contents or []


class MockAgentResponseUpdate:
    """Mock AgentResponseUpdate for streaming output events."""
    def __init__(self, text="streaming chunk"):
        self.text = text


class MockMagenticPlanReviewRequest:
    """Mock MagenticPlanReviewRequest."""
    def __init__(self):
        self.plan = Mock()  # _MagenticTaskLedger
        self._approved_response = Mock()

    def approve(self):
        return self._approved_response

    def revise(self, feedback):
        return Mock()


class MockMagenticOrchestratorEvent:
    """Mock MagenticOrchestratorEvent."""
    def __init__(self):
        self.event_type = Mock()
        self.event_type.value = "plan_created"


class MockInMemoryCheckpointStorage:
    pass


class MockAgent:
    """Mock agent with typical attributes."""
    def __init__(self, agent_name=None, name=None, has_inner_agent=False):
        if agent_name:
            self.agent_name = agent_name
        if name:
            self.name = name
        if has_inner_agent:
            self._agent = Mock()
        self.close = AsyncMock()


def _make_event(event_type, data=None, executor_id=None, request_id=None):
    """Factory for workflow events."""
    event = Mock()
    event.type = event_type
    event.data = data
    event.executor_id = executor_id
    event.request_id = request_id
    return event


async def _async_iter(items):
    """Helper: convert a list into an async iterator."""
    for item in items:
        yield item


def _make_workflow_mock(run_return=None, executors=None):
    """Create a properly configured workflow Mock."""
    wf = Mock()
    wf._executors = executors or {}
    wf.executors = executors or {}
    wf._terminated = False
    wf._participants = {}
    if run_return is not None:
        wf.run = Mock(return_value=run_return)
    return wf


# ---------------------------------------------------------------------------
# agent_framework mocks
# ---------------------------------------------------------------------------
mock_magentic_builder = Mock()
mock_magentic_builder.return_value.build.return_value = Mock()

af_mock = Mock()
af_mock.Agent = Mock(return_value=Mock())
af_mock.AgentResponse = Mock
af_mock.AgentResponseUpdate = MockAgentResponseUpdate
af_mock.InMemoryCheckpointStorage = MockInMemoryCheckpointStorage
af_mock.Message = MockMessage
af_mock.WorkflowEvent = Mock

af_orch_mock = Mock()
af_orch_mock.MagenticBuilder = mock_magentic_builder
af_orch_mock.MagenticOrchestratorEvent = MockMagenticOrchestratorEvent
af_orch_mock.MagenticOrchestratorEventType = Mock
af_orch_mock.MagenticPlanReviewRequest = MockMagenticPlanReviewRequest

sys.modules['agent_framework'] = af_mock
sys.modules['agent_framework.orchestrations'] = af_orch_mock
sys.modules['agent_framework_foundry'] = Mock(FoundryChatClient=Mock())
sys.modules['agent_framework_orchestrations'] = af_orch_mock
sys.modules['agent_framework_orchestrations._magentic'] = Mock()
sys.modules['agent_framework_azure_ai_search'] = Mock()

# ---------------------------------------------------------------------------
# Application module mocks
# ---------------------------------------------------------------------------
mock_config = Mock()
mock_config.get_azure_credential.return_value = Mock()
mock_config.AZURE_CLIENT_ID = 'test_client_id'
mock_config.AZURE_AI_PROJECT_ENDPOINT = 'https://test.project.azure.com/'

sys.modules['common'] = Mock()
sys.modules['common.config'] = Mock()
sys.modules['common.config.app_config'] = Mock(config=mock_config)
sys.modules['common.models'] = Mock()

# Register the real markdown_utils so the orchestrator uses genuine table logic, not a Mock (Bug 47810).
import importlib.util as _ilu  # noqa: E402

_md_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "backend",
    "common", "utils", "markdown_utils.py",
)
_md_spec = _ilu.spec_from_file_location("common.utils.markdown_utils", _md_path)
_markdown_utils = _ilu.module_from_spec(_md_spec)
_md_spec.loader.exec_module(_markdown_utils)
sys.modules['common.utils'] = Mock()
sys.modules['common.utils.markdown_utils'] = _markdown_utils


def _real_websocket_message_type(member: str) -> str:
    """One ``WebsocketMessageType`` member's value, read out of the real file.

    ``models.messages`` is mocked wholesale here because it drags the plan
    models in, so a mock enum has to restate the members the manager uses. A
    restated member is a member that cannot go wrong; this reads the source of
    truth with the source's own parser and fails loudly if the member is gone.
    """
    import ast

    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "backend",
        "models", "messages.py",
    )
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "WebsocketMessageType":
            for statement in node.body:
                if (
                    isinstance(statement, ast.Assign)
                    and isinstance(statement.targets[0], ast.Name)
                    and statement.targets[0].id == member
                ):
                    return ast.literal_eval(statement.value)
    raise AssertionError(f"WebsocketMessageType.{member} no longer exists")


class MockTeamConfiguration:
    def __init__(self, name="TestTeam", deployment_name="test_deployment", team_id="test-team-id"):
        self.name = name
        self.deployment_name = deployment_name
        self.team_id = team_id
        self.id = team_id


class MockDatabaseBase:
    pass


sys.modules['common.models.messages'] = Mock(TeamConfiguration=MockTeamConfiguration)
sys.modules['common.database'] = Mock()
sys.modules['common.database.database_base'] = Mock(DatabaseBase=MockDatabaseBase)


class MockTeamService:
    def __init__(self):
        self.memory_context = MockDatabaseBase()


sys.modules['services'] = Mock()
sys.modules['services.team_service'] = Mock(TeamService=MockTeamService)

sys.modules['callbacks.response_handlers'] = Mock(
    agent_response_callback=Mock(),
    streaming_agent_response_callback=AsyncMock(),
    # Real, because the Token meter's attribution is this function's output and
    # a Mock display name would let a broken attribution pass (issue #23).
    format_agent_display_name=lambda raw: raw.replace("_", " ").title(),
)

# ---- Mock orchestration.connection_config ----
mock_connection_config = Mock()
mock_connection_config.send_status_update_async = AsyncMock()

mock_orchestration_config = Mock()
mock_orchestration_config.max_rounds = 10
mock_orchestration_config.orchestrations = {}
mock_orchestration_config.plans = {}
mock_orchestration_config.get_current_orchestration = Mock(return_value=None)
mock_orchestration_config.set_approval_pending = Mock()

sys.modules['orchestration.connection_config'] = Mock(
    connection_config=mock_connection_config,
    orchestration_config=mock_orchestration_config,
)

# ---- Mock models.messages ----
class MockWebsocketMessageType:
    FINAL_RESULT_MESSAGE = "final_result_message"
    PLAN_APPROVAL_REQUEST = "plan_approval_request"
    PLAN_APPROVAL_RESPONSE = "plan_approval_response"
    AGENT_MESSAGE_STREAMING = "agent_message_streaming"
    TOKEN_USAGE = "token_usage"
    USER_CLARIFICATION_REQUEST = "user_clarification_request"
    # Read out of the real enum rather than restated (issue #22). A member
    # written here by hand agrees with itself forever: the manager would go on
    # pushing a message type the backend had renamed, and the card would go
    # dark on stage with every test green.
    TICKET_RAISED = _real_websocket_message_type("TICKET_RAISED")


class MockAgentMessageStreaming:
    def __init__(self, agent_name="", content="", is_final=False):
        self.agent_name = agent_name
        self.content = content
        self.is_final = is_final


class MockPlanApprovalRequest:
    def __init__(self, plan=None, status="PENDING_APPROVAL", context=None):
        self.plan = plan
        self.status = status
        self.context = context or {}


class MockPlanApprovalResponse:
    def __init__(self, approved=True, m_plan_id=None):
        self.approved = approved
        self.m_plan_id = m_plan_id


mock_messages_module = Mock()
mock_messages_module.WebsocketMessageType = MockWebsocketMessageType
mock_messages_module.AgentMessageStreaming = MockAgentMessageStreaming
mock_messages_module.PlanApprovalRequest = MockPlanApprovalRequest
mock_messages_module.PlanApprovalResponse = MockPlanApprovalResponse
sys.modules['models'] = Mock()
sys.modules['models.messages'] = mock_messages_module

# ---- Mock plan_review_helpers ----
class MockMPlan:
    def __init__(self):
        self.id = "test-plan-id"
        self.user_id = None


mock_convert = Mock(return_value=MockMPlan())
mock_get_prompt_kwargs = Mock(return_value={"task_ledger_plan_prompt": "p"})
mock_wait_approval = AsyncMock(return_value=MockPlanApprovalResponse(approved=True, m_plan_id="test-plan-id"))

sys.modules['orchestration.plan_review_helpers'] = Mock(
    convert_plan_review_to_mplan=mock_convert,
    get_magentic_prompt_kwargs=mock_get_prompt_kwargs,
    wait_for_plan_approval=mock_wait_approval,
)

# ---- Mock agents ----
class MockAgentFactory:
    def __init__(self, team_service=None):
        self.team_service = team_service

    async def get_agents(self, user_id, team_config_input, memory_store):
        agent1 = Mock()
        agent1.agent_name = "TestAgent1"
        agent1._agent = Mock()
        agent1.close = AsyncMock()
        agent2 = Mock()
        agent2.name = "TestAgent2"
        agent2.close = AsyncMock()
        return [agent1, agent2]


sys.modules.setdefault('agents', Mock())
sys.modules['agents.agent_factory'] = Mock(AgentFactory=MockAgentFactory)

# ---- Import module under test ----
from backend.orchestration.orchestration_manager import OrchestrationManager

# Re-bind mocked singletons for convenient assertions
connection_config = sys.modules['orchestration.connection_config'].connection_config
orchestration_config = sys.modules['orchestration.connection_config'].orchestration_config
agent_response_callback = sys.modules['callbacks.response_handlers'].agent_response_callback
streaming_agent_response_callback = sys.modules['callbacks.response_handlers'].streaming_agent_response_callback


# =========================================================================
# init_orchestration
# =========================================================================
class TestInitOrchestration:
    """Test OrchestrationManager.init_orchestration()."""

    def setup_method(self):
        mock_config.get_azure_credential.reset_mock()
        mock_magentic_builder.reset_mock()
        mock_magentic_builder.return_value.build.return_value = Mock()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("plan_review", [True, False])
    async def test_given_valid_args_when_init_then_returns_workflow(self, plan_review):
        """Plan review is a per-request value, not a literal (ADR-013).

        Parametrised over both values rather than deleted: the Deliberate lane
        still needs the gate on, and the Fast lane needs it off.
        """
        # Arrange
        agents = [MockAgent(agent_name="A1", has_inner_agent=True), MockAgent(name="A2")]

        # Act
        workflow = await OrchestrationManager.init_orchestration(
            agents=agents,
            team_config=MockTeamConfiguration(),
            memory_store=MockDatabaseBase(),
            user_id="user-1",
            plan_review=plan_review,
        )

        # Assert
        assert workflow is not None
        mock_config.get_azure_credential.assert_called_once()
        mock_magentic_builder.assert_called_once()
        call_kwargs = mock_magentic_builder.call_args.kwargs
        assert call_kwargs["enable_plan_review"] is plan_review
        assert call_kwargs["output_from"] == "all"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("plan_review", [True, False])
    async def test_given_init_then_workflow_is_tagged_with_team_and_plan_review(
        self, plan_review
    ):
        """The two cache predicates read these tags off the cached Workflow.

        ``_team_id`` was never assigned in production code, so every request
        took the Full workflow rebuild branch (CONTEXT.md, Confirmed findings);
        ``_plan_review`` is what lets a lane change invalidate a cached
        Workflow built for the other lane.
        """
        # Act
        workflow = await OrchestrationManager.init_orchestration(
            agents=[MockAgent(agent_name="A1")],
            team_config=MockTeamConfiguration(team_id="team-xyz"),
            memory_store=MockDatabaseBase(),
            user_id="user-1",
            plan_review=plan_review,
        )

        # Assert
        assert workflow._team_id == "team-xyz"
        assert workflow._plan_review is plan_review

    @pytest.mark.asyncio
    async def test_given_no_user_id_when_init_then_raises_value_error(self):
        with pytest.raises(ValueError, match="user_id is required"):
            await OrchestrationManager.init_orchestration(
                agents=[Mock()],
                team_config=MockTeamConfiguration(),
                memory_store=MockDatabaseBase(),
                user_id=None,
            )

    @pytest.mark.asyncio
    async def test_given_empty_user_id_when_init_then_raises_value_error(self):
        with pytest.raises(ValueError, match="user_id is required"):
            await OrchestrationManager.init_orchestration(
                agents=[Mock()],
                team_config=MockTeamConfiguration(),
                memory_store=MockDatabaseBase(),
                user_id="",
            )

    @pytest.mark.asyncio
    async def test_given_client_failure_when_init_then_propagates(self):
        # Arrange
        with patch('backend.orchestration.orchestration_manager.FoundryChatClient',
                   side_effect=Exception("Client boom")):
            # Act & Assert
            with pytest.raises(Exception, match="Client boom"):
                await OrchestrationManager.init_orchestration(
                    agents=[Mock()],
                    team_config=MockTeamConfiguration(),
                    memory_store=MockDatabaseBase(),
                    user_id="user-1",
                )

    @pytest.mark.asyncio
    async def test_given_agents_with_inner_agent_when_init_then_unwraps(self):
        # Arrange
        inner = Mock()
        outer = Mock()
        outer.agent_name = "Wrapped"
        outer._agent = inner
        outer.user_responses = False

        # Act
        await OrchestrationManager.init_orchestration(
            agents=[outer],
            team_config=MockTeamConfiguration(),
            memory_store=MockDatabaseBase(),
            user_id="user-1",
        )

        # Assert — participants list should contain the inner agent
        call_kwargs = mock_magentic_builder.call_args.kwargs
        assert inner in call_kwargs["participants"]

    @pytest.mark.asyncio
    async def test_given_agent_without_name_when_init_then_assigns_fallback(self):
        # Arrange — agent with neither agent_name nor name
        bare_agent = Mock(spec=[])

        # Act — should not raise
        await OrchestrationManager.init_orchestration(
            agents=[bare_agent],
            team_config=MockTeamConfiguration(),
            memory_store=MockDatabaseBase(),
            user_id="user-1",
        )

        # Assert
        mock_magentic_builder.assert_called_once()


# =========================================================================
# get_current_or_new_orchestration
# =========================================================================
class TestGetCurrentOrNewOrchestration:
    """Test OrchestrationManager.get_current_or_new_orchestration()."""

    def setup_method(self):
        orchestration_config.orchestrations.clear()
        orchestration_config.get_current_orchestration.reset_mock()
        orchestration_config.get_current_orchestration.return_value = None

    @pytest.mark.asyncio
    async def test_given_existing_workflow_when_no_switch_then_returns_it(self):
        """Regression test for the Workflow cache fix (ADR-013).

        The cached Workflow is built the way production builds it — through
        ``init_orchestration`` — rather than hand-tagged by the test. Before
        ``_team_id`` was assigned at build time this took the Full workflow
        rebuild branch, so every request closed and recreated the agent pool.
        """
        # Arrange — a Workflow tagged the way production tags it
        cached = await OrchestrationManager.init_orchestration(
            agents=[MockAgent(agent_name="A1")],
            team_config=MockTeamConfiguration(),
            memory_store=MockDatabaseBase(),
            user_id="user-1",
        )
        cached._terminated = False
        orchestration_config.get_current_orchestration.return_value = cached

        with patch.object(
            OrchestrationManager, 'init_orchestration', new_callable=AsyncMock
        ) as mock_init:
            # Act
            result = await OrchestrationManager.get_current_or_new_orchestration(
                user_id="user-1",
                team_config=MockTeamConfiguration(),
                team_switched=False,
                team_service=MockTeamService(),
            )

            # Assert — reused, not rebuilt
            assert result is cached
            mock_init.assert_not_called()

    @pytest.mark.asyncio
    async def test_given_lane_change_when_called_then_rebuilds(self):
        """A Workflow built for the other lane must not be reused.

        The team-initialisation endpoint eagerly builds a Workflow before any
        task is submitted, so without this the *first* request after a page
        load silently runs in whichever lane that eager build chose.
        """
        # Arrange — cached Workflow built with Plan review on
        cached = await OrchestrationManager.init_orchestration(
            agents=[MockAgent(agent_name="A1")],
            team_config=MockTeamConfiguration(),
            memory_store=MockDatabaseBase(),
            user_id="user-1",
            plan_review=True,
        )
        cached._terminated = False
        cached.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = cached

        with patch.object(
            OrchestrationManager, 'init_orchestration', new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = Mock()

            # Act — a Fast lane request arrives
            await OrchestrationManager.get_current_or_new_orchestration(
                user_id="user-1",
                team_config=MockTeamConfiguration(),
                team_switched=False,
                team_service=MockTeamService(),
                plan_review=False,
            )

            # Assert — rebuilt, and rebuilt for the requested lane
            mock_init.assert_called_once()
            assert mock_init.call_args.kwargs["plan_review"] is False

    @pytest.mark.asyncio
    async def test_given_no_workflow_when_called_then_creates_new(self):
        # Arrange
        orchestration_config.get_current_orchestration.return_value = None

        with patch.object(OrchestrationManager, 'init_orchestration', new_callable=AsyncMock) as mock_init:
            mock_workflow = Mock()
            mock_init.return_value = mock_workflow

            # Act
            await OrchestrationManager.get_current_or_new_orchestration(
                user_id="user-1",
                team_config=MockTeamConfiguration(),
                team_switched=False,
                team_service=MockTeamService(),
            )

            # Assert
            mock_init.assert_called_once()
            assert orchestration_config.orchestrations["user-1"] == mock_workflow

    @pytest.mark.asyncio
    async def test_given_team_switched_when_called_then_closes_old_agents(self):
        # Arrange
        mock_agent = MockAgent(agent_name="OldAgent")
        mock_executor = Mock()
        mock_executor.agent = mock_agent
        mock_old_workflow = Mock()
        mock_old_workflow._participants = {"a1": mock_agent}
        mock_old_workflow.get_executors_list.return_value = [mock_executor]
        mock_old_workflow._user_interaction_ctx = None
        orchestration_config.get_current_orchestration.return_value = mock_old_workflow

        with patch.object(OrchestrationManager, 'init_orchestration', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = Mock()

            # Act
            await OrchestrationManager.get_current_or_new_orchestration(
                user_id="user-1",
                team_config=MockTeamConfiguration(),
                team_switched=True,
                team_service=MockTeamService(),
            )

            # Assert
            mock_agent.close.assert_awaited_once()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_given_terminated_workflow_when_called_then_creates_new(self):
        # Arrange
        mock_old = Mock()
        mock_old._terminated = True
        mock_old._participants = {}
        mock_old.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_old

        with patch.object(OrchestrationManager, 'init_orchestration', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = Mock()

            # Act
            await OrchestrationManager.get_current_or_new_orchestration(
                user_id="user-1",
                team_config=MockTeamConfiguration(),
                team_switched=False,
                team_service=MockTeamService(),
            )

            # Assert
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_given_team_switched_when_closing_then_closes_all_agents(self):
        # Arrange
        agent_a = MockAgent(agent_name="AgentA")
        agent_b = MockAgent(agent_name="AgentB")
        exec_a = Mock()
        exec_a.agent = agent_a
        exec_b = Mock()
        exec_b.agent = agent_b
        mock_old = Mock()
        mock_old._participants = {"a": agent_a, "b": agent_b}
        mock_old.get_executors_list.return_value = [exec_a, exec_b]
        mock_old._user_interaction_ctx = None
        orchestration_config.get_current_orchestration.return_value = mock_old

        with patch.object(OrchestrationManager, 'init_orchestration', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = Mock()

            # Act
            await OrchestrationManager.get_current_or_new_orchestration(
                user_id="user-1",
                team_config=MockTeamConfiguration(),
                team_switched=True,
                team_service=MockTeamService(),
            )

            # Assert — all agents closed
            agent_a.close.assert_awaited_once()
            agent_b.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_given_agent_creation_failure_when_called_then_propagates(self):
        # Arrange
        orchestration_config.get_current_orchestration.return_value = None

        with patch('backend.orchestration.orchestration_manager.AgentFactory') as mock_factory_cls:
            mock_factory = Mock()
            mock_factory.get_agents = AsyncMock(side_effect=Exception("Agent boom"))
            mock_factory_cls.return_value = mock_factory

            # Act & Assert
            with pytest.raises(Exception, match="Agent boom"):
                await OrchestrationManager.get_current_or_new_orchestration(
                    user_id="user-1",
                    team_config=MockTeamConfiguration(),
                    team_switched=False,
                    team_service=MockTeamService(),
                )

    @pytest.mark.asyncio
    async def test_given_init_failure_when_called_then_propagates(self):
        # Arrange
        orchestration_config.get_current_orchestration.return_value = None

        with patch.object(OrchestrationManager, 'init_orchestration', new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = Exception("Init boom")

            # Act & Assert
            with pytest.raises(Exception, match="Init boom"):
                await OrchestrationManager.get_current_or_new_orchestration(
                    user_id="user-1",
                    team_config=MockTeamConfiguration(),
                    team_switched=False,
                    team_service=MockTeamService(),
                )


# =========================================================================
# run_orchestration
# =========================================================================
class TestRunOrchestration:
    """Test OrchestrationManager.run_orchestration() and _process_event_stream()."""

    def setup_method(self):
        orchestration_config.orchestrations.clear()
        orchestration_config.plans.clear()
        orchestration_config.get_current_orchestration.reset_mock()
        orchestration_config.set_approval_pending.reset_mock()
        connection_config.send_status_update_async.reset_mock()
        connection_config.send_status_update_async.side_effect = None
        agent_response_callback.reset_mock()
        streaming_agent_response_callback.reset_mock()
        streaming_agent_response_callback.side_effect = None
        mock_wait_approval.reset_mock()
        mock_wait_approval.return_value = MockPlanApprovalResponse(approved=True, m_plan_id="test-plan-id")
        mock_convert.reset_mock()
        mock_convert.return_value = MockMPlan()

    @pytest.mark.asyncio
    async def test_given_no_workflow_when_run_then_raises_value_error(self):
        # Arrange
        orchestration_config.get_current_orchestration.return_value = None
        manager = OrchestrationManager()

        # Act & Assert
        with pytest.raises(ValueError, match="Orchestration not initialized"):
            await manager.run_orchestration(user_id="user-1", input_task="task")

    @pytest.mark.asyncio
    async def test_given_empty_stream_when_run_then_sends_final_result(self):
        # Arrange
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter([]))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act
        await manager.run_orchestration(user_id="user-1", input_task="do stuff")

        # Assert — final result WebSocket message sent
        connection_config.send_status_update_async.assert_awaited()

    @pytest.mark.asyncio
    async def test_given_executor_completed_when_run_then_captures_final_text(self):
        # Arrange
        final_msg = MockMessage(text="Final answer text")
        events = [
            _make_event("executor_completed", data=[final_msg], executor_id="magentic_orchestrator"),
        ]
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter(events))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act
        await manager.run_orchestration(user_id="user-1", input_task="do stuff")

        # Assert — the final WS message should contain the executor's text
        call_args = connection_config.send_status_update_async.call_args_list[-1]
        sent_message = call_args[0][0]
        assert sent_message["data"]["content"] == "Final answer text"

    @pytest.mark.asyncio
    async def test_given_agent_completed_event_when_run_then_calls_agent_callback(self):
        # Arrange
        agent_msg = MockMessage(text="Agent output")
        events = [
            _make_event("executor_completed", data=[agent_msg], executor_id="hr_agent"),
        ]
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter(events))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act
        await manager.run_orchestration(user_id="user-1", input_task="task")

        # Assert
        agent_response_callback.assert_called_once_with("hr_agent", agent_msg, "user-1")

    @pytest.mark.asyncio
    async def test_given_streaming_output_when_run_then_calls_streaming_callback(self):
        # Arrange
        update = MockAgentResponseUpdate(text="chunk")
        events = [
            _make_event("output", data=update, executor_id="hr_agent"),
        ]
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter(events))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act
        await manager.run_orchestration(user_id="user-1", input_task="task")

        # Assert
        streaming_agent_response_callback.assert_awaited()

    @pytest.mark.asyncio
    async def test_given_orchestrator_streaming_when_run_then_accumulates_chunks(self):
        # Arrange
        update1 = MockAgentResponseUpdate(text="Hello ")
        update2 = MockAgentResponseUpdate(text="world")
        events = [
            _make_event("output", data=update1, executor_id="magentic_orchestrator"),
            _make_event("output", data=update2, executor_id="magentic_orchestrator"),
        ]
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter(events))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act
        await manager.run_orchestration(user_id="user-1", input_task="task")

        # Assert — fallback to joined chunks when no executor_completed
        call_args = connection_config.send_status_update_async.call_args_list[-1]
        sent_message = call_args[0][0]
        assert sent_message["data"]["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_given_new_agent_when_streaming_then_sends_header(self):
        # Arrange
        update = MockAgentResponseUpdate(text="chunk")
        events = [
            _make_event("output", data=update, executor_id="hr_agent"),
        ]
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter(events))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act
        await manager.run_orchestration(user_id="user-1", input_task="task")

        # Assert — header sent for agent switch
        header_calls = [
            c for c in connection_config.send_status_update_async.call_args_list
            if len(c[0]) > 0 and isinstance(c[0][0], MockAgentMessageStreaming)
        ]
        assert len(header_calls) >= 1

    @pytest.mark.asyncio
    async def test_given_orchestrator_event_when_run_then_no_error(self):
        # Arrange
        orch_event = MockMagenticOrchestratorEvent()
        events = [
            _make_event("magentic_orchestrator", data=orch_event),
        ]
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter(events))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act — should not raise
        await manager.run_orchestration(user_id="user-1", input_task="task")

    @pytest.mark.asyncio
    async def test_given_string_input_when_run_then_uses_str(self):
        # Arrange
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter([]))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act
        await manager.run_orchestration(user_id="user-1", input_task="plain string task")

        # Assert — workflow.run was called with the string
        mock_workflow.run.assert_called_once()
        call_args = mock_workflow.run.call_args
        assert call_args[0][0] == "plain string task"

    @pytest.mark.asyncio
    async def test_given_object_input_when_run_then_uses_description(self):
        # Arrange
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter([]))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()
        task = Mock()
        task.description = "object task desc"

        # Act
        await manager.run_orchestration(user_id="user-1", input_task=task)

        # Assert
        call_args = mock_workflow.run.call_args
        assert call_args[0][0] == "object task desc"

    @pytest.mark.asyncio
    async def test_given_workflow_error_when_run_then_sends_error_ws_and_raises(self):
        # Arrange
        mock_workflow = Mock()
        mock_workflow.run = Mock(side_effect=Exception("Workflow boom"))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act & Assert
        with pytest.raises(Exception, match="Workflow boom"):
            await manager.run_orchestration(user_id="user-1", input_task="task")

        # Assert — error status sent
        connection_config.send_status_update_async.assert_awaited()

    @pytest.mark.asyncio
    async def test_given_event_processing_error_when_run_then_continues(self):
        # Arrange
        streaming_agent_response_callback.side_effect = Exception("Callback boom")
        update = MockAgentResponseUpdate(text="x")
        events = [
            _make_event("output", data=update, executor_id="hr_agent"),
        ]
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter(events))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act — should not raise; errors are logged and swallowed
        await manager.run_orchestration(user_id="user-1", input_task="task")


# =========================================================================
# _process_event_stream — plan review
# =========================================================================
class TestProcessEventStreamPlanReview:
    """Test plan review collection within _process_event_stream()."""

    def setup_method(self):
        orchestration_config.plans.clear()
        connection_config.send_status_update_async.reset_mock()
        connection_config.send_status_update_async.side_effect = None

    @pytest.mark.asyncio
    async def test_given_plan_review_event_when_processing_then_returns_collected_requests(self):
        # Arrange
        plan_review = MockMagenticPlanReviewRequest()
        event = _make_event("request_info", data=plan_review, request_id="req-1")

        manager = OrchestrationManager()

        # Act
        result = await manager._process_event_stream(
            _async_iter([event]),
            user_id="user-1",
            final_output_ref=[None],
            orchestrator_chunks=[],
            current_streaming_agent_ref=[None],
        )

        # Assert — returns dict with plan_reviews key
        assert result is not None
        assert "plan_reviews" in result
        assert "req-1" in result["plan_reviews"]
        assert result["plan_reviews"]["req-1"] is plan_review

    @pytest.mark.asyncio
    async def test_given_multiple_plan_reviews_when_processing_then_collects_all(self):
        # Arrange
        review1 = MockMagenticPlanReviewRequest()
        review2 = MockMagenticPlanReviewRequest()
        events = [
            _make_event("request_info", data=review1, request_id="req-1"),
            _make_event("request_info", data=review2, request_id="req-2"),
        ]

        manager = OrchestrationManager()

        # Act
        result = await manager._process_event_stream(
            _async_iter(events),
            user_id="user-1",
            final_output_ref=[None],
            orchestrator_chunks=[],
            current_streaming_agent_ref=[None],
        )

        # Assert
        assert result is not None
        assert "plan_reviews" in result
        assert len(result["plan_reviews"]) == 2
        assert "req-1" in result["plan_reviews"]
        assert "req-2" in result["plan_reviews"]

    @pytest.mark.asyncio
    async def test_given_no_plan_review_when_stream_completes_then_returns_none(self):
        # Arrange
        events = [_make_event("magentic_orchestrator", data=MockMagenticOrchestratorEvent())]
        manager = OrchestrationManager()

        # Act
        result = await manager._process_event_stream(
            _async_iter(events),
            user_id="user-1",
            final_output_ref=[None],
            orchestrator_chunks=[],
            current_streaming_agent_ref=[None],
        )

        # Assert
        assert result is None


# =========================================================================
# run_orchestration — resume loop
# =========================================================================
class TestRunOrchestrationResumeLoop:
    """Test the resume loop in run_orchestration()."""

    def setup_method(self):
        orchestration_config.plans.clear()
        orchestration_config.set_approval_pending.reset_mock()
        connection_config.send_status_update_async.reset_mock()
        connection_config.send_status_update_async.side_effect = None
        mock_wait_approval.reset_mock()
        mock_convert.reset_mock()
        mock_convert.return_value = MockMPlan()

    @pytest.mark.asyncio
    async def test_given_plan_review_then_completion_when_run_then_resumes(self):
        # Arrange — first call returns plan review, second call completes
        plan_review = MockMagenticPlanReviewRequest()
        review_event = _make_event("request_info", data=plan_review, request_id="req-1")
        final_msg = MockMessage(text="Done")
        completion_event = _make_event("executor_completed", data=[final_msg], executor_id="magentic_orchestrator")

        call_count = [0]

        def mock_run(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _async_iter([review_event])
            return _async_iter([completion_event])

        mock_wait_approval.return_value = MockPlanApprovalResponse(approved=True, m_plan_id="test-plan-id")

        mock_workflow = Mock()
        mock_workflow.run = mock_run
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act
        await manager.run_orchestration(user_id="user-1", input_task="task")

        # Assert — workflow.run called twice (initial + resume)
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_given_approval_pending_when_run_then_sets_pending(self):
        # Arrange
        mock_workflow = Mock()
        mock_workflow.run = Mock(return_value=_async_iter([]))
        mock_workflow._executors = {}
        mock_workflow.executors = {}
        mock_workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = mock_workflow
        manager = OrchestrationManager()

        # Act
        await manager.run_orchestration(user_id="user-1", input_task="task")

        # Assert
        orchestration_config.set_approval_pending.assert_called_once()


class TestOrchestrationManagerInit:
    """Test OrchestrationManager constructor."""

    def test_given_new_instance_when_init_then_user_id_is_none(self):
        manager = OrchestrationManager()

        assert manager.user_id is None

    def test_given_new_instance_when_init_then_logger_is_set(self):
        manager = OrchestrationManager()

        assert isinstance(manager.logger, logging.Logger)


# _normalize_markdown_tables (Bug 47810)
from backend.orchestration.orchestration_manager import (  # noqa: E402
    _normalize_markdown_tables,
)
from common.utils.markdown_utils import (  # noqa: E402
    reflow_collapsed_table_line as _reflow_collapsed_table_line,
)


class TestNormalizeMarkdownTables:
    """Test markdown table re-flow for collapsed orchestrator output (Bug 47810)."""

    def test_given_collapsed_table_when_normalized_then_rows_split_to_lines(self):
        collapsed = (
            "| Risk Type | Description | Rating | "
            "|-------|-------|-------| "
            "| Delivery | Undefined timeline | Medium | "
            "| Financial | Fixed budget | High |"
        )

        result = _normalize_markdown_tables(collapsed)

        lines = [ln for ln in result.split("\n") if ln.strip()]
        assert lines == [
            "| Risk Type | Description | Rating |",
            "| ------- | ------- | ------- |",
            "| Delivery | Undefined timeline | Medium |",
            "| Financial | Fixed budget | High |",
        ]

    def test_given_collapsed_table_with_prefix_then_prefix_kept_on_own_line(self):
        collapsed = (
            "Risk Analysis | A | B | |---|---| | 1 | 2 |"
        )

        result = _normalize_markdown_tables(collapsed)

        # Prefix prose separated from the table by a blank line for GFM.
        assert result.startswith("Risk Analysis\n\n| A | B |")

    def test_given_wellformed_table_when_normalized_then_unchanged(self):
        good = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"

        assert _normalize_markdown_tables(good) == good

    def test_given_plain_text_when_normalized_then_unchanged(self):
        text = "Just some text with a - dash and | a pipe."

        assert _normalize_markdown_tables(text) == text

    def test_given_colon_aligned_delimiter_when_normalized_then_alignment_kept(self):
        collapsed = "| A | B | C | |:--|:-:|--:| | 1 | 2 | 3 |"

        result = _normalize_markdown_tables(collapsed)

        assert "| :-- | :-: | --: |" in result

    def test_given_empty_or_none_when_normalized_then_returns_input(self):
        assert _normalize_markdown_tables("") == ""
        assert _normalize_markdown_tables(None) is None

    def test_given_non_table_pipe_line_when_reflowed_then_returns_none(self):
        assert _reflow_collapsed_table_line("a | b | c") is None


# ---------------------------------------------------------------------------
# The Token meter's signal (issue #23)
# ---------------------------------------------------------------------------
class TestTokenUsageEmission:
    """Token accounting is net-new — the MACAE baseline emits none at all.

    Its insertion point is the **executor-completed** branch, which is the one
    place a turn is over and its cost is final.
    """

    def setup_method(self):
        connection_config.send_status_update_async.reset_mock()
        orchestration_config.get_current_orchestration.return_value = None

    def _run(self, events):
        workflow = Mock()
        workflow.run = Mock(return_value=_async_iter(events))
        workflow._executors = {}
        workflow.executors = {}
        workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = workflow
        return OrchestrationManager().run_orchestration(
            user_id="user-1", input_task="task"
        )

    @staticmethod
    def _usage(**counts):
        return Mock(type="usage", usage_details=dict(counts))

    def _token_calls(self):
        return [
            call for call in connection_config.send_status_update_async.call_args_list
            if call.kwargs.get("message_type") == MockWebsocketMessageType.TOKEN_USAGE
        ]

    @pytest.mark.asyncio
    async def test_a_completed_executor_reports_what_its_turn_cost(self):
        message = MockMessage(
            text="Here are the steps.",
            contents=[self._usage(input_token_count=120, output_token_count=45)],
        )

        await self._run([
            _make_event("executor_completed", data=[message], executor_id="shift_tasks_agent"),
        ])

        (call,) = self._token_calls()
        payload = call[0][0]
        assert (payload.input_tokens, payload.output_tokens, payload.total_tokens) == (120, 45, 165)

    @pytest.mark.asyncio
    async def test_the_cost_is_attributed_by_executor_identifier(self):
        """Not by the plan — in the Fast lane plan review is off, so there is no
        plan to read an agent name out of and the meter would go blank on the
        lane the demo spends most of its time in."""
        message = MockMessage(contents=[self._usage(total_token_count=7)])

        await self._run([
            _make_event("executor_completed", data=[message], executor_id="shift_tasks_agent"),
        ])

        (call,) = self._token_calls()
        assert call[0][0].executor_id == "shift_tasks_agent"
        assert call[0][0].agent_name == "Shift Tasks Agent"

    @pytest.mark.asyncio
    async def test_the_orchestrator_is_metered_like_any_other_executor(self):
        """The branch treats the manager no differently: the R7 claim is
        per-agent cost, and a meter that excluded the orchestrator would
        understate the architecture's price to the audience.

        Whether the framework *reports* the manager's usage is a separate
        question and is not verified live — `StandardMagenticManager._complete`
        returns `response.messages[-1]` and drops `AgentResponse.usage_details`
        on the way. The debug line in `_emit_token_usage` is how the first real
        run answers it."""
        message = MockMessage(
            text="Final answer",
            contents=[self._usage(input_token_count=900, output_token_count=100)],
        )

        await self._run([
            _make_event("executor_completed", data=[message], executor_id="magentic_orchestrator"),
        ])

        (call,) = self._token_calls()
        assert call[0][0].executor_id == "magentic_orchestrator"
        assert call[0][0].total_tokens == 1000

    @pytest.mark.asyncio
    async def test_an_event_reporting_no_usage_emits_nothing(self):
        """A zero on the meter says the agent was free. Silence says the
        framework did not report — and only one of those is true."""
        await self._run([
            _make_event("executor_completed", data=[MockMessage()], executor_id="hr_agent"),
        ])

        assert self._token_calls() == []


# ---------------------------------------------------------------------------
# Agent attribution with plan review off (issue #23)
# ---------------------------------------------------------------------------
class TestAttributionWithoutAPlan:
    """The Fast lane runs with **Plan review** off, so there is no plan object.

    Attribution has to come from somewhere that still exists on that lane, and
    the executor identifier is that place — the same place the Token meter
    reads. A panel that read the plan would be blank on the lane the demo
    spends most of its time in.
    """

    def setup_method(self):
        connection_config.send_status_update_async.reset_mock()

    @pytest.mark.asyncio
    async def test_a_streaming_agent_is_named_with_no_plan_in_sight(self):
        workflow = Mock()
        workflow.run = Mock(return_value=_async_iter([
            _make_event("output", data=MockAgentResponseUpdate(text="chunk"),
                        executor_id="shift_tasks_agent"),
        ]))
        workflow._executors = {}
        workflow.executors = {}
        workflow.get_executors_list.return_value = []
        # No plan review request is ever emitted on this stream, and no plan is
        # cached — the Fast lane's actual shape.
        orchestration_config.get_current_orchestration.return_value = workflow

        await OrchestrationManager().run_orchestration(
            user_id="user-1", input_task="what are my shift tasks?"
        )

        headers = [
            call[0][0] for call in connection_config.send_status_update_async.call_args_list
            if isinstance(call[0][0], MockAgentMessageStreaming)
        ]
        assert headers, "no agent header was sent"
        assert "Shift Tasks Agent" in headers[0].content


# ---------------------------------------------------------------------------
# Attempted-steps memory at the clarification seam (issue #21)
# ---------------------------------------------------------------------------
class MockToolApproval:
    """A pending ``request_user_clarification`` approval, as the framework
    hands it over: a function call whose arguments carry the questions."""

    def __init__(self, questions="What have you already tried?"):
        self.function_call = Mock()
        self.function_call.name = "request_user_clarification"
        self.function_call.arguments = json.dumps({"questions": questions})
        self.approved = None

    def to_function_approval_response(self, approved=True):
        self.approved = approved
        return Mock(approved=approved)


class FakeTroubleshootingStore:
    """The store's seam, in a list. Records what was persisted and what note
    was handed back, without a container."""

    def __init__(self, attempted=None, note=""):
        self.attempted = list(attempted or [])
        self.recorded = []
        self._note = note

    async def record(self, session_id, steps, equipment=None):
        self.recorded.append((session_id, list(steps)))
        self.attempted.extend(steps)
        return Mock(attempted=self.attempted)

    async def note(self, session_id):
        return self._note


class TestAttemptedStepsMemory:
    """The associate's answer to *what have you already tried* is persisted
    where it is **received**, not where a model remembers to record it.

    ``_handle_tool_approvals`` is that place: the manager already intercepts
    the answer there before approving the tool, so the record is written on
    every clarification turn whether or not the agent calls anything. The same
    seam hands the record back — the tool body returns exactly what was stored,
    so the agent cannot miss it.
    """

    def setup_method(self):
        connection_config.send_status_update_async.reset_mock()
        orchestration_config.set_clarification_pending.reset_mock()

    async def _approve(self, answer, store, session="s-1"):
        from tools.clarification_tool import _pending_answers

        _pending_answers.clear()
        orchestration_config.wait_for_clarification = AsyncMock(return_value=answer)
        manager = OrchestrationManager()
        with patch.object(
            OrchestrationManager, "_troubleshooting_store",
            AsyncMock(return_value=(store, session) if store else (None, None)),
        ):
            await manager._handle_tool_approvals(
                {"req-1": MockToolApproval()}, user_id="user-1"
            )
        return dict(_pending_answers)

    @pytest.mark.asyncio
    async def test_what_the_associate_says_they_tried_is_persisted(self):
        store = FakeTroubleshootingStore()

        await self._approve("I power cycled it and I checked the water line", store)

        assert store.recorded == [
            ("s-1", ["power cycled it", "checked the water line"])
        ]

    @pytest.mark.asyncio
    async def test_the_record_rides_back_to_the_agent_on_its_own_answer(self):
        """Not fetched by the agent: the tool body returns what was stored
        here, so a turn cannot proceed without having been told."""
        store = FakeTroubleshootingStore(
            note="Do NOT walk them through these again:\n- Power cycled the brewer"
        )

        stored = await self._approve("I checked the water line", store)

        assert any("Power cycled the brewer" in value for value in stored.values())

    @pytest.mark.asyncio
    async def test_the_associates_own_answer_is_still_what_the_agent_reads(self):
        """The note is added to the answer, never instead of it."""
        store = FakeTroubleshootingStore(note="- Power cycled the brewer")

        stored = await self._approve("I checked the water line", store)

        assert all("checked the water line" in value for value in stored.values())

    @pytest.mark.asyncio
    async def test_an_answer_reporting_nothing_records_no_step(self):
        """'Nothing yet' is a reply to the question, not a step. A recorded
        empty step would skip the whole runbook."""
        store = FakeTroubleshootingStore()

        await self._approve("nothing yet", store)

        assert store.recorded == [("s-1", [])]

    @pytest.mark.asyncio
    async def test_no_session_in_flight_leaves_the_answer_exactly_as_given(self):
        """The memory is resolved server-side and refuses to guess. When it
        cannot, the turn still gets its answer."""
        stored = await self._approve("I power cycled it", None)

        assert set(stored.values()) == {"I power cycled it"}

    @pytest.mark.asyncio
    async def test_a_store_that_raises_does_not_cost_the_turn_its_answer(self):
        """The record is memory of one shift; the answer is the associate's.
        An unreachable container costs a repeated step, never the turn."""

        class Broken:
            async def record(self, *_args, **_kwargs):
                raise RuntimeError("cosmos is down")

            async def note(self, *_args, **_kwargs):
                raise RuntimeError("cosmos is down")

        stored = await self._approve("I power cycled it", Broken())

        assert set(stored.values()) == {"I power cycled it"}

    @pytest.mark.asyncio
    async def test_the_tool_call_is_still_approved(self):
        """Everything above rides an existing seam and none of it may change
        what that seam was for."""
        approval = MockToolApproval()
        orchestration_config.wait_for_clarification = AsyncMock(return_value="nothing")
        with patch.object(
            OrchestrationManager, "_troubleshooting_store",
            AsyncMock(return_value=(FakeTroubleshootingStore(), "s-1")),
        ):
            responses = await OrchestrationManager()._handle_tool_approvals(
                {"req-1": approval}, user_id="user-1"
            )

        assert approval.approved is True
        assert set(responses) == {"req-1"}


# ---------------------------------------------------------------------------
# The approval step IS the ticket confirmation (issue #22)
# ---------------------------------------------------------------------------
class MockPlanReview:
    """A pending plan review, as the framework hands it over."""

    def __init__(self):
        self.approved = False

    def approve(self):
        self.approved = True
        return Mock(approved=True)


class FakeTicketStore:
    """The ticket store's seam, without a container."""

    def __init__(self, ticket=None):
        self.ticket = ticket
        self.submitted = []

    async def submit(self, session_id):
        self.submitted.append(session_id)
        return self.ticket


def _submitted_ticket(**overrides):
    fields = {"ticket_id": "SIM-223-0041", "status": "submitted"}
    fields.update(overrides)
    return Mock(fields=fields)


class TestTheApprovalIsTheTicketConfirmation:
    """TKT-001: the associate confirms the ticket once, and the confirmation
    is the approval step.

    So submission is deterministic and rides the seam the approval already
    passes through — the same move the attempted-steps memory makes at the
    clarification seam. A model asked to call a submit tool after approval is a
    second confirmation step that sometimes does not happen; a *tool* that
    submits is a second confirmation step that sometimes happens twice. There
    is no submit tool at all, and this is the only caller.
    """

    def setup_method(self):
        connection_config.send_status_update_async.reset_mock()
        mock_wait_approval.return_value = MockPlanApprovalResponse(
            approved=True, m_plan_id="test-plan-id"
        )

    async def _review(self, store, *, approved=True, session="s-1"):
        mock_wait_approval.return_value = MockPlanApprovalResponse(
            approved=approved, m_plan_id="test-plan-id"
        )
        review = MockPlanReview()
        manager = OrchestrationManager()
        with patch.object(
            OrchestrationManager, "_ticket_store",
            AsyncMock(return_value=(store, session) if store else (None, None)),
        ):
            responses = await manager._handle_plan_reviews(
                {"req-1": review},
                participant_names=["EscalationAgent"],
                task_text="I can't fix it, raise a ticket",
                user_id="user-1",
            )
        return review, responses

    @pytest.mark.asyncio
    async def test_approving_the_plan_submits_the_drafted_ticket(self):
        store = FakeTicketStore(ticket=_submitted_ticket())

        await self._review(store)

        assert store.submitted == ["s-1"]

    @pytest.mark.asyncio
    async def test_rejecting_the_plan_submits_nothing(self):
        """The rejection is the associate correcting the ticket. A ticket
        raised from a rejected plan is the one thing the approval gate exists
        to prevent."""
        store = FakeTicketStore(ticket=_submitted_ticket())

        await self._review(store, approved=False)

        assert store.submitted == []

    @pytest.mark.asyncio
    async def test_a_plan_with_no_drafted_ticket_raises_none(self):
        """Every approved plan on the Deliberate lane reaches this seam and
        most of them are not escalations."""
        store = FakeTicketStore(ticket=None)

        _review, responses = await self._review(store)

        assert responses is not None
        pushed = [
            call for call in connection_config.send_status_update_async.call_args_list
            if call.kwargs.get("message_type") == "ticket_raised"
        ]
        assert pushed == []

    @pytest.mark.asyncio
    async def test_the_confirmed_ticket_reaches_the_surface(self):
        store = FakeTicketStore(ticket=_submitted_ticket())

        await self._review(store)

        pushed = [
            call for call in connection_config.send_status_update_async.call_args_list
            if call.kwargs.get("message_type") == "ticket_raised"
        ]
        assert len(pushed) == 1
        payload = pushed[0].args[0]
        assert payload["ticket_id"] == "SIM-223-0041"
        assert payload["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_the_ticket_is_handed_over_unwrapped_like_every_other_signal(self):
        """`send_status_update_async` puts `{"type", "data"}` on the wire around
        whatever it is given, so a caller that hands it an envelope ships two.

        The three transparency signals hand over their bare payload and this one
        did not, so the Simulated ticket arrived at the browser one envelope
        deeper than `parseRaisedTicket` — a total parser — would read. It
        returned `None` and the card never rendered. The frontend half of the
        same defect is `WebSocketService.handleMessage` (#47); this is the half
        no amount of frontend work can fix, and it was invisible because the
        assertions above read the caller's own envelope rather than the wire.
        """
        store = FakeTicketStore(ticket=_submitted_ticket())

        await self._review(store)

        handed_over = [
            call for call in connection_config.send_status_update_async.call_args_list
            if call.kwargs.get("message_type") == "ticket_raised"
        ][0].args[0]
        assert "data" not in handed_over
        assert "type" not in handed_over

    @pytest.mark.asyncio
    async def test_the_card_carries_the_attempted_steps_it_was_submitted_with(self):
        """The requirement, end to end: what the associate said they tried is
        on the ticket they can see, and nobody re-typed it."""
        store = FakeTicketStore(
            ticket=_submitted_ticket(steps_attempted="Fitted a fresh paper filter")
        )

        await self._review(store)

        pushed = [
            call for call in connection_config.send_status_update_async.call_args_list
            if call.kwargs.get("message_type") == "ticket_raised"
        ][0]
        rows = {row["name"]: row["value"] for row in pushed.args[0]["fields"]}
        assert rows["steps_attempted"] == "Fitted a fresh paper filter"

    @pytest.mark.asyncio
    async def test_an_unresolvable_session_raises_nothing_and_says_nothing(self):
        _review, responses = await self._review(None)

        assert responses is not None
        assert not [
            call for call in connection_config.send_status_update_async.call_args_list
            if call.kwargs.get("message_type") == "ticket_raised"
        ]

    @pytest.mark.asyncio
    async def test_a_failing_ticket_store_does_not_cost_the_approval(self):
        """The plan is approved either way. The ticket degrades to nothing
        raised and nothing claimed — never to a turn that dies after the
        associate already said yes."""
        store = FakeTicketStore()
        store.submit = AsyncMock(side_effect=RuntimeError("container unreachable"))

        review, responses = await self._review(store)

        assert review.approved is True
        assert responses is not None

    @pytest.mark.asyncio
    async def test_the_plan_is_still_approved(self):
        """All of this rides an existing seam and none of it may change what
        that seam was for."""
        review, responses = await self._review(FakeTicketStore(_submitted_ticket()))

        assert review.approved is True
        assert set(responses) == {"req-1"}


# ---------------------------------------------------------------------------
# The draft the approved plan makes is raised when that plan finishes (#50)
# ---------------------------------------------------------------------------
class LateDraftTicketStore:
    """A store whose draft appears *during* execution, not before it.

    Which is the live order: the plan review is presented before the plan runs,
    and the EscalationAgent drafts the ticket while running it. A store that
    already holds a draft when the associate approves is the rarer case — a
    second approval in a conversation that already drafted one.
    """

    def __init__(self, ticket):
        self.ticket = ticket
        self.submitted = []

    async def submit(self, session_id):
        self.submitted.append(session_id)
        return self.ticket if len(self.submitted) > 1 else None


class TestTheDraftMadeWhileThePlanRanIsStillRaised:
    """#50: the approval authorises the ticket the approved plan drafts.

    Asserting the escalation beat through a browser found the card never
    appearing: the only submission seam ran at plan-review time, and at plan
    review time the draft does not exist yet — the plan whose third step is
    "draft a simulated service-incident ticket" has not run. Every unit test
    around the seam passed, because each handed the seam a store that already
    held a draft.

    So the approved run submits again when it finishes. It is the same single
    confirmation: the associate approved a plan that says it will raise a
    ticket, and no second gate is presented. A run nobody approved never
    reaches this call, and a rejected plan never gets there at all.
    """

    def setup_method(self):
        orchestration_config.plans.clear()
        connection_config.send_status_update_async.reset_mock()
        connection_config.send_status_update_async.side_effect = None
        mock_wait_approval.reset_mock()
        mock_convert.reset_mock()
        mock_convert.return_value = MockMPlan()

    def _workflow(self, *streams):
        calls = [0]

        def run(*args, **kwargs):
            calls[0] += 1
            return _async_iter(streams[min(calls[0], len(streams)) - 1])

        workflow = Mock()
        workflow.run = run
        workflow._executors = {}
        workflow.executors = {}
        workflow.get_executors_list.return_value = []
        orchestration_config.get_current_orchestration.return_value = workflow
        return workflow

    async def _run(self, store, *streams, approved=True):
        mock_wait_approval.return_value = MockPlanApprovalResponse(
            approved=approved, m_plan_id="test-plan-id"
        )
        self._workflow(*streams)
        with patch.object(
            OrchestrationManager, "_ticket_store",
            AsyncMock(return_value=(store, "s-1")),
        ):
            await OrchestrationManager().run_orchestration(
                user_id="user-1", input_task="I can't fix it, raise a ticket"
            )

    def _raised(self):
        return [
            call for call in connection_config.send_status_update_async.call_args_list
            if call.kwargs.get("message_type") == "ticket_raised"
        ]

    @pytest.mark.asyncio
    async def test_the_ticket_drafted_while_the_plan_ran_reaches_the_surface(self):
        store = LateDraftTicketStore(_submitted_ticket())
        review = _make_event(
            "request_info", data=MockMagenticPlanReviewRequest(), request_id="req-1"
        )
        done = _make_event(
            "executor_completed",
            data=[MockMessage(text="Ticket raised")],
            executor_id="magentic_orchestrator",
        )

        await self._run(store, [review], [done])

        assert store.submitted == ["s-1", "s-1"]
        assert self._raised()[0].args[0]["ticket_id"] == "SIM-223-0041"

    @pytest.mark.asyncio
    async def test_a_run_nobody_approved_raises_nothing(self):
        """The Fast lane presents no plan review, and the EscalationAgent is in
        the pool for every turn. A ticket raised at the end of a turn nobody
        approved is the unconfirmed submission the gate exists to prevent."""
        store = LateDraftTicketStore(_submitted_ticket())
        done = _make_event(
            "executor_completed",
            data=[MockMessage(text="Try the reset")],
            executor_id="magentic_orchestrator",
        )

        await self._run(store, [done])

        assert store.submitted == []
        assert self._raised() == []

    @pytest.mark.asyncio
    async def test_a_rejected_plan_raises_nothing_at_the_end_either(self):
        store = LateDraftTicketStore(_submitted_ticket())
        review = _make_event(
            "request_info", data=MockMagenticPlanReviewRequest(), request_id="req-1"
        )

        with pytest.raises(RuntimeError, match="cancelled by user"):
            await self._run(store, [review], approved=False)

        assert store.submitted == []
        assert self._raised() == []

    @pytest.mark.asyncio
    async def test_a_ticket_already_raised_in_this_run_is_not_raised_twice(self):
        """The rarer order — a draft that already existed when the associate
        approved — now passes two submissions. ``submit`` is idempotent and
        returns the same ticket both times, so only the card would double.
        One approval puts one ticket on the surface once."""
        store = FakeTicketStore(ticket=_submitted_ticket())
        review = _make_event(
            "request_info", data=MockMagenticPlanReviewRequest(), request_id="req-1"
        )
        done = _make_event(
            "executor_completed",
            data=[MockMessage(text="Ticket raised")],
            executor_id="magentic_orchestrator",
        )

        await self._run(store, [review], [done])

        assert store.submitted == ["s-1", "s-1"]
        assert len(self._raised()) == 1
