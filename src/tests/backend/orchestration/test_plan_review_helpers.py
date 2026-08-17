"""Unit tests for plan_review_helpers module.

Tests the three public functions:
- get_magentic_prompt_kwargs()
- convert_plan_review_to_mplan()
- wait_for_plan_approval()
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock

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
sys.modules['azure.core'] = Mock()
sys.modules['azure.core.exceptions'] = Mock()
sys.modules['azure.identity'] = Mock()
sys.modules['azure.identity.aio'] = Mock()
sys.modules['azure.cosmos'] = Mock(CosmosClient=Mock)

# ---- Mock agent_framework prompt constants ----
ORCHESTRATOR_FINAL_ANSWER_PROMPT = "Final answer prompt"
ORCHESTRATOR_TASK_LEDGER_PLAN_PROMPT = "Task ledger plan prompt"
ORCHESTRATOR_TASK_LEDGER_PLAN_UPDATE_PROMPT = "Task ledger plan update prompt"
ORCHESTRATOR_TASK_LEDGER_FACTS_PROMPT = "Task ledger facts prompt"
ORCHESTRATOR_PROGRESS_LEDGER_PROMPT = "Progress ledger prompt"

sys.modules['agent_framework'] = Mock()
sys.modules['agent_framework_orchestrations'] = Mock()
sys.modules['agent_framework_orchestrations._magentic'] = Mock(
    ORCHESTRATOR_FINAL_ANSWER_PROMPT=ORCHESTRATOR_FINAL_ANSWER_PROMPT,
    ORCHESTRATOR_TASK_LEDGER_PLAN_PROMPT=ORCHESTRATOR_TASK_LEDGER_PLAN_PROMPT,
    ORCHESTRATOR_TASK_LEDGER_PLAN_UPDATE_PROMPT=ORCHESTRATOR_TASK_LEDGER_PLAN_UPDATE_PROMPT,
    ORCHESTRATOR_TASK_LEDGER_FACTS_PROMPT=ORCHESTRATOR_TASK_LEDGER_FACTS_PROMPT,
    ORCHESTRATOR_PROGRESS_LEDGER_PROMPT=ORCHESTRATOR_PROGRESS_LEDGER_PROMPT,
)

# ---- Mock models.messages ----
class MockWebsocketMessageType:
    PLAN_APPROVAL_REQUEST = "plan_approval_request"
    PLAN_APPROVAL_RESPONSE = "plan_approval_response"
    FINAL_RESULT_MESSAGE = "final_result_message"
    TIMEOUT_NOTIFICATION = "timeout_notification"


class MockPlanApprovalResponse:
    def __init__(self, approved=True, m_plan_id=None, feedback=None):
        self.approved = approved
        self.m_plan_id = m_plan_id
        self.feedback = feedback


class MockTimeoutNotification:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


mock_messages_module = Mock()
mock_messages_module.WebsocketMessageType = MockWebsocketMessageType
mock_messages_module.PlanApprovalResponse = MockPlanApprovalResponse
mock_messages_module.TimeoutNotification = MockTimeoutNotification
mock_messages_module.PlanApprovalRequest = Mock

mock_models = Mock()
mock_models.messages = mock_messages_module
sys.modules['models'] = mock_models
sys.modules['models.messages'] = mock_messages_module

# ---- Mock orchestration.connection_config ----
mock_connection_config = Mock()
mock_connection_config.send_status_update_async = AsyncMock()

mock_orchestration_config = Mock()
mock_orchestration_config.max_rounds = 10
mock_orchestration_config.default_timeout = 30
mock_orchestration_config.plans = {}
mock_orchestration_config.approvals = {}
mock_orchestration_config.set_approval_pending = Mock()
mock_orchestration_config.wait_for_approval = AsyncMock(return_value=True)
mock_orchestration_config.cleanup_approval = Mock()

sys.modules['orchestration.connection_config'] = Mock(
    connection_config=mock_connection_config,
    orchestration_config=mock_orchestration_config,
)

# ---- Mock models.plan_models ----
class MockMStep:
    def __init__(self, agent="", action="", **kwargs):
        self.agent = agent
        self.action = action
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def model_validate(cls, value):
        return cls(**value)

    def model_dump(self, **_kwargs):
        return {
            "id": getattr(self, "id", None),
            "agent": self.agent,
            "action": self.action,
            "assignee": getattr(self, "assignee", None),
            "waitsOn": getattr(self, "waitsOn", None),
        }


class MockMPlan:
    def __init__(self):
        self.id = "test-plan-id"
        self.user_id = None
        self.steps = []

sys.modules['models.plan_models'] = Mock(MPlan=MockMPlan, MStep=MockMStep)

# ---- Mock plan converter ----
class MockPlanToMPlanConverter:
    @staticmethod
    def convert(plan_text, facts, team, task):
        return MockMPlan()

sys.modules['orchestration.helper.plan_to_mplan_converter'] = Mock(
    PlanToMPlanConverter=MockPlanToMPlanConverter,
)

# ---- Import module under test ----
from backend.orchestration.plan_review_helpers import (
    convert_plan_review_to_mplan, get_magentic_prompt_kwargs,
    mandatory_participants, plans_minimally, wait_for_plan_approval)

# Re-bind mocked singletons for convenient assertions
connection_config = sys.modules['orchestration.connection_config'].connection_config
orchestration_config = sys.modules['orchestration.connection_config'].orchestration_config


# =========================================================================
# get_magentic_prompt_kwargs
# =========================================================================
class TestGetMagenticPromptKwargs:
    """Test get_magentic_prompt_kwargs() prompt customization builder."""

    def test_given_no_user_responses_when_called_then_returns_base_keys(self):
        # Act
        result = get_magentic_prompt_kwargs(has_user_responses=False)

        # Assert
        assert "task_ledger_plan_prompt" in result
        assert "task_ledger_plan_update_prompt" in result
        assert "final_answer_prompt" in result
        assert "task_ledger_facts_prompt" not in result
        # progress_ledger_prompt (completion enforcement) is now always present,
        # so plan-step agents must run even for teams without user_responses.
        assert "progress_ledger_prompt" in result

    def test_given_user_responses_when_called_then_returns_extended_keys(self):
        # Act
        result = get_magentic_prompt_kwargs(has_user_responses=True)

        # Assert
        assert "task_ledger_plan_prompt" in result
        assert "task_ledger_plan_update_prompt" in result
        assert "final_answer_prompt" in result
        assert "task_ledger_facts_prompt" in result
        assert "progress_ledger_prompt" in result

    def test_given_no_user_responses_when_called_then_plan_has_zero_questions_policy(self):
        # Act
        result = get_magentic_prompt_kwargs(has_user_responses=False)

        # Assert
        assert "ZERO QUESTIONS" in result["task_ledger_plan_prompt"]

    def test_given_user_responses_when_called_then_plan_has_work_first_policy(self):
        # Act
        result = get_magentic_prompt_kwargs(has_user_responses=True)

        # Assert
        assert "USER CLARIFICATION POLICY" in result["task_ledger_plan_prompt"]

    def test_given_user_responses_when_called_then_progress_contains_execution_rules(self):
        # Act
        result = get_magentic_prompt_kwargs(has_user_responses=True)

        # Assert
        assert "EXECUTION RULES" in result["progress_ledger_prompt"]
        assert "COMPLETION CHECK" in result["progress_ledger_prompt"]

    def test_given_no_user_responses_when_called_then_progress_still_enforces_completion(self):
        # Act
        result = get_magentic_prompt_kwargs(has_user_responses=False)

        # Assert — completion enforcement applies even without user_responses
        assert "progress_ledger_prompt" in result
        assert "COMPLETION CHECK" in result["progress_ledger_prompt"]
        # User-clarification-only rules must NOT leak in for non-interactive teams
        assert "request_user_clarification" not in result["progress_ledger_prompt"]

    def test_given_participant_names_when_called_then_plan_lists_mandatory_agents(self):
        # Act
        result = get_magentic_prompt_kwargs(
            has_user_responses=False,
            participant_names=["TriageAgent", "ComplianceAgent"],
        )

        # Assert — every listed agent is required to appear in the plan
        plan_prompt = result["task_ledger_plan_prompt"]
        assert "MANDATORY AGENTS" in plan_prompt
        assert "- TriageAgent" in plan_prompt
        assert "- ComplianceAgent" in plan_prompt

    def test_given_no_participant_names_when_called_then_no_mandatory_block(self):
        # Act
        result = get_magentic_prompt_kwargs(has_user_responses=False)

        # Assert
        assert "MANDATORY AGENTS" not in result["task_ledger_plan_prompt"]

    def test_given_minimal_plan_when_called_then_only_relevant_agents_are_planned(self):
        # Dropping MANDATORY AGENTS was necessary and not sufficient (#54).
        # PLAN RULES still said "one step per agent", which a manager reads as
        # a template rather than a ceiling: with the mandatory clause gone it
        # kept planning a step for all three store specialists, and the
        # troubleshooter asked which equipment was blocking closing when
        # nothing was broken. Measured against the deployment, run 1 of 10.
        result = get_magentic_prompt_kwargs(
            has_user_responses=False, minimal_plan=True)

        plan_prompt = result["task_ledger_plan_prompt"]
        assert "MANDATORY AGENTS" not in plan_prompt
        assert "ONLY the agents" in plan_prompt
        assert "one step per agent" not in plan_prompt

    def test_given_no_minimal_plan_when_called_then_one_step_per_agent_stands(self):
        # The accelerator's teams are pipelines and keep the inherited rule.
        result = get_magentic_prompt_kwargs(has_user_responses=False)

        plan_prompt = result["task_ledger_plan_prompt"]
        assert "one step per agent" in plan_prompt
        assert "ONLY the agents" not in plan_prompt

    def test_given_minimal_plan_when_called_then_the_loop_stays_inside_the_plan(self):
        # The clause that survived both earlier fixes (#54). Dropping MANDATORY
        # AGENTS and rewriting PLAN RULES got the plan down to one step, and the
        # troubleshooter was still billed on every sixth run — because the
        # progress ledger's own rule, "prefer a work agent that has NOT yet been
        # invoked", is not scoped to the plan. After the shift-tasks specialist
        # answered, the next round went looking for someone unused.
        result = get_magentic_prompt_kwargs(
            has_user_responses=True, minimal_plan=True)

        progress = result["progress_ledger_prompt"]
        assert "prefer a work agent that has NOT yet been invoked" not in progress
        assert "whose own description covers what the user" in progress
        # And the completion check must not pull one back in behind it: it used
        # to say "select the next uninvoked agent as next_speaker", which is the
        # same instruction wearing a different hat.
        assert "select the next uninvoked agent" not in progress
        assert "not the roster, decides when the work is done" in progress

    def test_given_no_minimal_plan_when_called_then_uninvoked_agents_are_preferred(self):
        # A pipeline team's whole point: an agent that has not run yet is the
        # one the plan is waiting on.
        result = get_magentic_prompt_kwargs(
            has_user_responses=True, participant_names=["TriageAgent"])

        progress = result["progress_ledger_prompt"]
        assert "prefer a work agent that has NOT yet been invoked" in progress
        assert "select the next uninvoked agent" in progress

    def test_given_minimal_plan_when_called_then_the_roster_is_not_the_completion_test(self):
        # The sixth residual (#54). Four clauses had been rewritten in the
        # progress ledger and the plan rules, and the troubleshooter was still
        # billed on a question with nothing broken in it. INVOCATION RULES —
        # in the *plan* prompt, and never conditioned on `minimal_plan` — was
        # still saying the whole assumption in one line: "If an agent has not
        # been invoked yet, the workflow is NOT complete." Not *a plan-step
        # agent*: an agent. On a three-specialist team with a one-step plan
        # that is an instruction to run the other two.
        result = get_magentic_prompt_kwargs(
            has_user_responses=False, minimal_plan=True)

        plan_prompt = result["task_ledger_plan_prompt"]
        assert "If an agent has not been invoked yet" not in plan_prompt
        assert "The plan is the measure of completeness" in plan_prompt

    def test_given_no_minimal_plan_when_called_then_an_uninvoked_agent_is_incomplete(self):
        # Unchanged for a pipeline team, where the clause is what stops the
        # manager finishing before the ComplianceAgent has run.
        result = get_magentic_prompt_kwargs(
            has_user_responses=False, participant_names=["ComplianceAgent"])

        plan_prompt = result["task_ledger_plan_prompt"]
        assert "If an agent has not been invoked yet, the workflow is NOT complete." \
            in plan_prompt

    def test_given_minimal_plan_when_called_then_the_worked_example_is_one_step(self):
        # A rule was already read as a template once — "one step per agent" —
        # and a worked example is a stronger template than a rule (#54). Under
        # `minimal_plan` the only concrete plan the manager was shown was a
        # three-agent, one-step-each plan, directly underneath the paragraph
        # telling it a one-step plan is complete.
        result = get_magentic_prompt_kwargs(
            has_user_responses=False, minimal_plan=True)

        plan_prompt = result["task_ledger_plan_prompt"]
        example = plan_prompt.split("Example plan")[1]
        first_plan = example.split("]")[0]
        assert first_plan.count('{"agent"') == 1, \
            "the first plan the manager is shown must be a one-step plan"
        assert "Add a second step only when" in example
        # And the pipeline example is *gone*, not merely demoted below the
        # one-step one. Counting the first array alone would pass with the old
        # three-agent template restored underneath it, which is the whole of
        # the regression: the manager reads the section, not its first line.
        assert '"MagenticManager", "action": "compile a final onboarding' \
            not in plan_prompt
        assert plan_prompt.count('"HRHelperAgent"') == 2
        assert plan_prompt.count('"TechnicalSupportAgent"') == 1

    def test_given_minimal_plan_when_called_then_scope_policy_names_no_mandatory_rule(self):
        # TEAM SCOPE POLICY told the manager that "the mandatory-inclusion rule
        # below does NOT apply" *when out of scope* — and under `minimal_plan`
        # there is no such rule below. Naming one is how a manager infers that
        # in-scope requests do include every agent, which is the assumption
        # this whole issue is made of (#54).
        result = get_magentic_prompt_kwargs(
            has_user_responses=False, minimal_plan=True)

        plan_prompt = result["task_ledger_plan_prompt"]
        assert "mandatory-inclusion rule" not in plan_prompt
        assert "the PLAN RULES below do NOT apply" in plan_prompt

    def test_given_no_minimal_plan_when_called_then_scope_policy_names_the_mandatory_rule(self):
        # For a pipeline team the rule exists and the exemption must name it.
        result = get_magentic_prompt_kwargs(
            has_user_responses=False, participant_names=["TriageAgent"])

        assert "mandatory-inclusion rule below does NOT apply" \
            in result["task_ledger_plan_prompt"]

    def test_given_no_minimal_plan_when_called_then_the_worked_example_is_the_pipeline_one(self):
        # A pipeline team is shown a pipeline, including the manager's own
        # compile step.
        result = get_magentic_prompt_kwargs(
            has_user_responses=False, participant_names=["TriageAgent"])

        example = result["task_ledger_plan_prompt"].split("Example plan")[1]
        first_plan = example.split("]")[0]
        assert first_plan.count('{"agent"') == 3
        assert "MagenticManager" in first_plan

    def test_given_no_user_responses_when_called_then_final_has_answer_rules(self):
        # Act
        result = get_magentic_prompt_kwargs(has_user_responses=False)

        # Assert
        assert "FINAL ANSWER RULES" in result["final_answer_prompt"]

    def test_given_default_when_called_then_user_responses_is_false(self):
        # Act
        result = get_magentic_prompt_kwargs()

        # Assert
        assert "ZERO QUESTIONS" in result["task_ledger_plan_prompt"]

    def test_given_no_user_responses_when_called_then_plan_prompt_appends_base_prompt(self):
        # Act
        result = get_magentic_prompt_kwargs(has_user_responses=False)

        # Assert — starts with the base prompt constant
        assert result["task_ledger_plan_prompt"].startswith(ORCHESTRATOR_TASK_LEDGER_PLAN_PROMPT)
        assert result["task_ledger_plan_update_prompt"].startswith(ORCHESTRATOR_TASK_LEDGER_PLAN_UPDATE_PROMPT)
        assert result["final_answer_prompt"].startswith(ORCHESTRATOR_FINAL_ANSWER_PROMPT)

    def test_given_user_responses_when_called_then_facts_prompt_appends_base_prompt(self):
        # Act
        result = get_magentic_prompt_kwargs(has_user_responses=True)

        # Assert
        assert result["task_ledger_facts_prompt"].startswith(ORCHESTRATOR_TASK_LEDGER_FACTS_PROMPT)
        assert result["progress_ledger_prompt"].startswith(ORCHESTRATOR_PROGRESS_LEDGER_PROMPT)


# =========================================================================
# convert_plan_review_to_mplan
# =========================================================================
class TestConvertPlanReviewToMplan:
    """Test convert_plan_review_to_mplan() ledger to MPlan conversion."""

    @staticmethod
    def _make_review_request(plan_text="Step plan", facts_text="Some facts"):
        """Build a mock MagenticPlanReviewRequest with nested ledger."""
        inner_plan = Mock()
        inner_plan.text = plan_text

        inner_facts = Mock()
        inner_facts.text = facts_text

        ledger = Mock()
        ledger.plan = inner_plan
        ledger.facts = inner_facts

        request = Mock()
        request.plan = ledger
        return request

    def test_given_valid_ledger_when_called_then_returns_mplan(self):
        # Arrange
        request = self._make_review_request()

        # Act
        result = convert_plan_review_to_mplan(
            request,
            participant_names=["Agent1", "Agent2"],
            task_text="Do something",
            user_id="user-1",
        )

        # Assert
        assert isinstance(result, MockMPlan)
        assert result.user_id == "user-1"

    def test_given_none_ledger_when_called_then_raises_value_error(self):
        # Arrange
        request = Mock()
        request.plan = None

        # Act & Assert
        with pytest.raises(ValueError, match="no plan data"):
            convert_plan_review_to_mplan(
                request,
                participant_names=[],
                task_text="task",
                user_id="user-1",
            )

    def test_given_ledger_missing_plan_attr_when_called_then_falls_to_plain_message_path(self):
        # Arrange — ledger with no .plan attr falls through to plain Message path
        ledger = Mock(spec=[])  # empty spec — no attributes
        ledger.text = "- **Agent1** to do something"
        request = Mock()
        request.plan = ledger

        # Act
        result = convert_plan_review_to_mplan(
            request,
            participant_names=["Agent1"],
            task_text="task",
            user_id="user-1",
        )

        # Assert — gracefully handled via plain-message path
        assert isinstance(result, MockMPlan)

    def test_given_ledger_missing_facts_attr_when_called_then_uses_empty_facts(self):
        # Arrange — ledger with .plan but no .facts uses empty string for facts
        ledger = Mock()
        ledger.plan = Mock()
        ledger.plan.text = "Step plan text"
        del ledger.facts
        request = Mock()
        request.plan = ledger

        # Act
        result = convert_plan_review_to_mplan(
            request,
            participant_names=["Agent1"],
            task_text="task",
            user_id="user-1",
        )

        # Assert — gracefully handled with empty facts
        assert isinstance(result, MockMPlan)


# =========================================================================
# wait_for_plan_approval
# =========================================================================
class TestWaitForPlanApproval:
    """Test wait_for_plan_approval() WebSocket-based approval gate."""

    def setup_method(self):
        """Reset mocks before each test."""
        connection_config.send_status_update_async.reset_mock()
        connection_config.send_status_update_async.side_effect = None
        orchestration_config.set_approval_pending.reset_mock()
        orchestration_config.wait_for_approval.reset_mock()
        orchestration_config.wait_for_approval.return_value = True
        orchestration_config.cleanup_approval.reset_mock()
        orchestration_config.get_plan_feedback.reset_mock()
        orchestration_config.get_plan_feedback.return_value = None

    @pytest.mark.asyncio
    async def test_given_approved_when_waiting_then_returns_approved_response(self):
        # Arrange
        orchestration_config.wait_for_approval.return_value = True

        # Act
        result = await wait_for_plan_approval("plan-1", "user-1")

        # Assert
        assert result is not None
        assert result.approved is True
        assert result.m_plan_id == "plan-1"
        orchestration_config.set_approval_pending.assert_called_with("plan-1")
        orchestration_config.wait_for_approval.assert_awaited_with("plan-1")

    @pytest.mark.asyncio
    async def test_given_rejected_when_waiting_then_returns_rejected_response(self):
        # Arrange
        orchestration_config.wait_for_approval.return_value = False

        # Act
        result = await wait_for_plan_approval("plan-1", "user-1")

        # Assert
        assert result is not None
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_a_plan_sent_back_carries_what_the_associate_would_change(self):
        # The verdict and the feedback arrive together, because the waiting
        # review needs both to call the framework's revise path (#108).
        orchestration_config.wait_for_approval.return_value = False
        orchestration_config.get_plan_feedback.return_value = "Ask Marcus instead."

        result = await wait_for_plan_approval("plan-1", "user-1")

        assert result.approved is False
        assert result.feedback == "Ask Marcus instead."

    @pytest.mark.asyncio
    async def test_given_no_plan_id_when_waiting_then_returns_rejected_response(self):
        # Act
        result = await wait_for_plan_approval(None, "user-1")

        # Assert
        assert result is not None
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_given_empty_plan_id_when_waiting_then_returns_rejected_response(self):
        # Act
        result = await wait_for_plan_approval("", "user-1")

        # Assert
        assert result is not None
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_given_timeout_when_waiting_then_returns_none(self):
        # Arrange
        orchestration_config.wait_for_approval.side_effect = asyncio.TimeoutError()

        # Act
        result = await wait_for_plan_approval("plan-1", "user-1")

        # Assert
        assert result is None
        connection_config.send_status_update_async.assert_awaited_once()
        orchestration_config.cleanup_approval.assert_called_with("plan-1")

    @pytest.mark.asyncio
    async def test_given_timeout_and_ws_error_when_waiting_then_returns_none(self):
        # Arrange
        orchestration_config.wait_for_approval.side_effect = asyncio.TimeoutError()
        connection_config.send_status_update_async.side_effect = Exception("WS down")

        # Act
        result = await wait_for_plan_approval("plan-1", "user-1")

        # Assert
        assert result is None
        orchestration_config.cleanup_approval.assert_called_with("plan-1")

    @pytest.mark.asyncio
    async def test_given_key_error_when_waiting_then_returns_none(self):
        # Arrange
        orchestration_config.wait_for_approval.side_effect = KeyError("missing")

        # Act
        result = await wait_for_plan_approval("plan-1", "user-1")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_given_cancelled_when_waiting_then_returns_none(self):
        # Arrange
        orchestration_config.wait_for_approval.side_effect = asyncio.CancelledError()

        # Act
        result = await wait_for_plan_approval("plan-1", "user-1")

        # Assert
        assert result is None
        orchestration_config.cleanup_approval.assert_called_with("plan-1")

    @pytest.mark.asyncio
    async def test_given_unexpected_error_when_waiting_then_returns_none(self):
        # Arrange
        orchestration_config.wait_for_approval.side_effect = RuntimeError("boom")

        # Act
        result = await wait_for_plan_approval("plan-1", "user-1")

        # Assert
        assert result is None
        orchestration_config.cleanup_approval.assert_called_with("plan-1")


class TestMandatoryInclusionIsOptIn:
    """#54. The clause that forces every agent into every plan is the reason
    the walkthrough's opening beat asks the presenter a question back.

    `MANDATORY AGENTS (CRITICAL — NON-NEGOTIABLE)` was inherited for the
    accelerator's coordinator/compliance teams, where an agent the manager
    silently dropped was the bug. Applied to the store team it turns a
    one-lookup procedure question into a three-specialist conversation: the
    Troubleshooting Agent is *required* to appear, its job is to ask what you
    have already tried, so it asks — and the presenter, who asked "How do I
    close the store?", is asked "What is stopping Store 223 from closing right
    now?" while the answer sits retrieved and cited in the Grounding panel.

    Measured on 2026-08-14 against `rg-macae-flw-v1`, from a validator run
    whose Grounding panel named Copilot Studio, reported Dataverse and cited
    `SOP-102 Store Closing Procedure.docx` — a green hop with a red beat.

    So the clause becomes opt-**out** per team, and the default stays what it
    has always been: every team that has not thought about it keeps the
    inherited behaviour, and only a team that says so gets a manager free to
    plan one step.
    """

    def test_a_team_that_says_nothing_keeps_the_inherited_behaviour(self):
        # The blast radius of this change is meant to be one team. Every
        # accelerator team predates the flag, and a default of "off" would
        # silently drop the agent the clause exists to keep.
        assert mandatory_participants(Mock(spec=[]), ["TriageAgent"]) == [
            "TriageAgent"
        ]

    def test_a_team_that_opts_out_forces_no_agent_into_the_plan(self):
        team = Mock(require_all_agents=False)

        assert mandatory_participants(team, ["TroubleshootingAgent"]) == []

    def test_opting_out_removes_the_clause_from_the_prompt_entirely(self):
        # Not "a shorter list" — the whole block. A MANDATORY AGENTS heading
        # with nothing under it is a prompt the model still reasons about.
        team = Mock(require_all_agents=False)

        result = get_magentic_prompt_kwargs(
            has_user_responses=True,
            participant_names=mandatory_participants(
                team, ["TroubleshootingAgent", "ShiftTasksAgent"]
            ),
        )

        assert "MANDATORY AGENTS" not in result["task_ledger_plan_prompt"]

    def test_opting_out_does_not_touch_the_scope_policy(self):
        """The out-of-scope guard is a different rule and must survive.

        It is what keeps a team answering only what its agents cover, and it
        is the reason a plan can legitimately be one MagenticManager step. If
        opting out of mandatory inclusion also dropped it, the store team would
        start answering questions no agent on it has any knowledge of.
        """
        team = Mock(require_all_agents=False)

        result = get_magentic_prompt_kwargs(
            has_user_responses=True,
            participant_names=mandatory_participants(team, ["ShiftTasksAgent"]),
        )

        assert "TEAM SCOPE POLICY" in result["task_ledger_plan_prompt"]

    def test_the_store_team_is_the_team_that_opts_out(self):
        """Read out of the pack, because that is where it takes effect.

        A flag nothing sets is a flag that fixed nothing, and this is the one
        assertion that ties the mechanism above to the beat below.
        """
        import json
        from pathlib import Path

        pack = Path(__file__).resolve().parents[4] / (
            "content_packs/store_assistant/agent_teams/store_assistant.json")
        team = json.loads(pack.read_text(encoding="utf-8"))

        assert team.get("require_all_agents") is False, (
            "the store team still forces every specialist into every plan; "
            "the rehearsed procedure question will be answered with a "
            "clarifying question from the Troubleshooting Agent"
        )


class TestPlansMinimally:
    """Which teams get a manager free to plan one step.

    Separate from `mandatory_participants` because the two clauses failed
    independently: dropping the mandatory one still left "one step per agent"
    standing, and the store team kept planning all three specialists (#54).
    """

    def test_a_team_that_opts_out_plans_minimally(self):
        assert plans_minimally(
            Mock(require_all_agents=False), ["A", "B"]) is True

    def test_a_team_that_did_not_opt_out_does_not(self):
        assert plans_minimally(
            Mock(require_all_agents=True), ["A", "B"]) is False

    def test_a_team_predating_the_flag_does_not(self):
        # Opt-out, not opt-in: an accelerator team keeps what it was
        # configured under.
        assert plans_minimally(Mock(spec=[]), ["A", "B"]) is False

    def test_a_team_with_no_agents_has_no_plan_to_minimise(self):
        assert plans_minimally(
            Mock(require_all_agents=False), []) is False
