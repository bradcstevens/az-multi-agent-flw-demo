# Copyright (c) Microsoft. All rights reserved.
"""Tests for services/plan_service.py."""

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src/backend to sys.path so flat imports inside plan_service resolve
_backend_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend')
)
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

# Mock Azure modules
sys.modules.setdefault('azure', MagicMock())
sys.modules.setdefault('azure.ai', MagicMock())
sys.modules.setdefault('azure.ai.projects', MagicMock())
sys.modules.setdefault('azure.ai.projects.aio', MagicMock())

# Mock common modules
mock_config_module = MagicMock()
mock_config = MagicMock()
mock_config.DATABASE_TYPE = 'memory'
mock_config_module.config = mock_config
sys.modules['common.config.app_config'] = mock_config_module

mock_database_factory = MagicMock()
sys.modules['common.database.database_factory'] = mock_database_factory

mock_event_utils = MagicMock()
sys.modules['common.utils.event_utils'] = mock_event_utils

# Create mock common.models.messages with enums
class MockAgentType:
    HUMAN = MagicMock()
    HUMAN.value = "Human_Agent"

class MockAgentMessageType:
    HUMAN_AGENT = "Human_Agent"
    AI_AGENT = "AI_Agent"

class MockPlanStatus:
    approved = "approved"
    completed = "completed"
    rejected = "rejected"

class MockAgentMessageData:
    def __init__(self, plan_id, user_id, m_plan_id, agent, agent_type, content, raw_data, steps, next_steps):
        self.plan_id = plan_id
        self.user_id = user_id
        self.m_plan_id = m_plan_id
        self.agent = agent
        self.agent_type = agent_type
        self.content = content
        self.raw_data = raw_data
        self.steps = steps
        self.next_steps = next_steps

mock_messages_common = MagicMock()
mock_messages_common.AgentType = MockAgentType
mock_messages_common.AgentMessageType = MockAgentMessageType
mock_messages_common.PlanStatus = MockPlanStatus
mock_messages_common.AgentMessageData = MockAgentMessageData
sys.modules['common.models.messages'] = mock_messages_common

# Mock models.messages (flat import used by plan_service after migration)
mock_v_messages = MagicMock()
sys.modules['models'] = MagicMock()
sys.modules['models.messages'] = mock_v_messages

# Mock orchestration.connection_config
mock_orchestration_config = MagicMock()
mock_orchestration_config.plans = {}
mock_orchestration_module = MagicMock()
mock_orchestration_module.orchestration_config = mock_orchestration_config
sys.modules['orchestration'] = MagicMock()
sys.modules['orchestration.connection_config'] = mock_orchestration_module

# The revision lineage is pure — no I/O, no framework — so plan_service reads
# the real one. Mocking it would leave the send-back path asserting a MagicMock
# instead of the numbers the Plan record ends up carrying.
import backend.orchestration.plan_revision as plan_revision_module  # noqa: E402
sys.modules['orchestration.plan_revision'] = plan_revision_module

import backend.services.plan_service as plan_service_module
from backend.services.plan_service import (
    PlanService, build_agent_message_from_agent_message_response,
    build_agent_message_from_user_clarification)
from chat.echo import (  # noqa: E402  (pure: dataclasses and an enum)
    EchoOutcome,
    MessageEchoed,
)

# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

@dataclass
class MockUserClarificationResponse:
    plan_id: str = ""
    m_plan_id: str = ""
    answer: str = ""


@dataclass
class MockAgentMessageResponse:
    plan_id: str = ""
    user_id: str = ""
    m_plan_id: str = ""
    agent: str = ""
    agent_name: str = ""
    source: str = ""
    agent_type: Any = None
    content: str = ""
    text: str = ""
    raw_data: Any = None
    steps: List = None
    next_steps: List = None
    streaming_message: str = ""


@dataclass
class MockPlanApprovalResponse:
    plan_id: str = ""
    m_plan_id: str = ""
    approved: bool = True
    feedback: str = ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUtilityFunctions:
    def test_build_agent_message_from_user_clarification_basic(self):
        feedback = MockUserClarificationResponse(
            plan_id="test-plan-123",
            m_plan_id="test-m-plan-456",
            answer="This is my clarification"
        )
        result = build_agent_message_from_user_clarification(feedback, "test-user-789")
        assert result.plan_id == "test-plan-123"
        assert result.user_id == "test-user-789"
        assert result.m_plan_id == "test-m-plan-456"
        assert result.agent == "Human_Agent"
        assert result.content == "This is my clarification"
        assert result.steps == []
        assert result.next_steps == []

    def test_build_agent_message_from_user_clarification_empty_fields(self):
        feedback = MockUserClarificationResponse(plan_id=None, m_plan_id=None, answer=None)
        result = build_agent_message_from_user_clarification(feedback, "test-user")
        assert result.plan_id == ""
        assert result.user_id == "test-user"
        assert result.m_plan_id is None
        assert result.content == ""

    def test_build_agent_message_from_user_clarification_raw_data_serialization(self):
        feedback = MockUserClarificationResponse(plan_id="test-plan", answer="test answer")
        result = build_agent_message_from_user_clarification(feedback, "test-user")
        raw_data = json.loads(result.raw_data)
        assert raw_data["plan_id"] == "test-plan"
        assert raw_data["answer"] == "test answer"

    def test_build_agent_message_from_agent_message_response_basic(self):
        response = MockAgentMessageResponse(
            plan_id="test-plan-123",
            user_id="response-user",
            agent="TestAgent",
            content="Agent response content",
            steps=["step1", "step2"],
            next_steps=["next1"]
        )
        result = build_agent_message_from_agent_message_response(response, "fallback-user")
        assert result.plan_id == "test-plan-123"
        assert result.user_id == "response-user"
        assert result.agent == "TestAgent"
        assert result.content == "Agent response content"
        assert result.steps == ["step1", "step2"]
        assert result.next_steps == ["next1"]

    def test_build_agent_message_from_agent_message_response_fallbacks(self):
        response = MockAgentMessageResponse(
            plan_id="",
            user_id="",
            agent="",
            agent_name="NamedAgent",
            text="Text content",
            steps=None,
            next_steps=None
        )
        result = build_agent_message_from_agent_message_response(response, "fallback-user")
        assert result.user_id == "fallback-user"
        assert result.agent == "NamedAgent"
        assert result.content == "Text content"
        assert result.steps == []
        assert result.next_steps == []

    def test_build_agent_message_from_agent_message_response_agent_type_inference(self):
        response_human = MockAgentMessageResponse(agent_type="human_agent")
        result = build_agent_message_from_agent_message_response(response_human, "user")
        assert result.agent_type == MockAgentMessageType.HUMAN_AGENT

        response_ai = MockAgentMessageResponse(agent_type="unknown")
        result = build_agent_message_from_agent_message_response(response_ai, "user")
        assert result.agent_type == MockAgentMessageType.AI_AGENT

    def test_build_agent_message_from_agent_message_response_raw_data_dict(self):
        response = MockAgentMessageResponse(raw_data={"test": "data"})
        result = build_agent_message_from_agent_message_response(response, "user")
        assert '"test": "data"' in result.raw_data

    def test_build_agent_message_from_agent_message_response_raw_data_none(self):
        response = MockAgentMessageResponse(raw_data=None, content="test")
        result = build_agent_message_from_agent_message_response(response, "user")
        assert isinstance(result.raw_data, str)

    def test_build_agent_message_from_agent_message_response_source_fallback(self):
        response = MockAgentMessageResponse(agent="", agent_name="", source="SourceAgent")
        result = build_agent_message_from_agent_message_response(response, "user")
        assert result.agent == "SourceAgent"


class TestPlanService:
    @pytest.mark.asyncio
    async def test_handle_plan_approval_success(self):
        mock_approval = MockPlanApprovalResponse(
            plan_id="test-plan-123",
            m_plan_id="test-m-plan-456",
            approved=True,
            feedback="Looks good!"
        )
        mock_mplan = MagicMock()
        mock_mplan.plan_id = None
        mock_mplan.team_id = None
        mock_mplan.model_dump.return_value = {"test": "data"}
        mock_orchestration_config.plans = {"test-m-plan-456": mock_mplan}

        mock_db = MagicMock()
        mock_plan = MagicMock()
        mock_plan.team_id = "test-team"
        mock_db.get_plan = AsyncMock(return_value=mock_plan)
        mock_db.update_plan = AsyncMock()
        mock_database_factory.DatabaseFactory.get_database = AsyncMock(return_value=mock_db)

        with patch.object(plan_service_module, 'orchestration_config', mock_orchestration_config):
            result = await PlanService.handle_plan_approval(mock_approval, "test-user")

        assert result is True
        assert mock_mplan.plan_id == "test-plan-123"
        assert mock_plan.overall_status == MockPlanStatus.approved
        mock_db.update_plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_plan_send_back_records_the_revision_lineage(self):
        # Sending a plan back is not a rejection: the Plan record survives and
        # carries which revision was asked for and what asked for it (#108).
        mock_approval = MockPlanApprovalResponse(
            plan_id="test-plan-123",
            m_plan_id="test-m-plan-456",
            approved=False,
            feedback="Ask Marcus instead.",
        )
        mock_mplan = MagicMock()
        mock_mplan.plan_id = "existing-plan-id"
        mock_orchestration_config.plans = {"test-m-plan-456": mock_mplan}

        mock_db = MagicMock()
        mock_plan = MagicMock()
        mock_plan.revision = 1
        mock_plan.revision_feedback = []
        mock_db.get_plan = AsyncMock(return_value=mock_plan)
        mock_db.update_plan = AsyncMock()
        mock_db.delete_plan_by_plan_id = AsyncMock()
        mock_database_factory.DatabaseFactory.get_database = AsyncMock(return_value=mock_db)

        with patch.object(plan_service_module, 'orchestration_config', mock_orchestration_config):
            result = await PlanService.handle_plan_approval(mock_approval, "test-user")

        assert result is True
        assert mock_plan.revision == 2
        assert mock_plan.revision_feedback == ["Ask Marcus instead."]
        mock_db.update_plan.assert_called_once_with(mock_plan)
        mock_db.delete_plan_by_plan_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_second_send_back_appends_rather_than_replaces(self):
        mock_approval = MockPlanApprovalResponse(
            plan_id="test-plan-123",
            m_plan_id="test-m-plan-456",
            approved=False,
            feedback="Actually, ask Dana.",
        )
        mock_orchestration_config.plans = {"test-m-plan-456": MagicMock()}

        mock_db = MagicMock()
        mock_plan = MagicMock()
        mock_plan.revision = 2
        mock_plan.revision_feedback = ["Ask Marcus instead."]
        mock_db.get_plan = AsyncMock(return_value=mock_plan)
        mock_db.update_plan = AsyncMock()
        mock_database_factory.DatabaseFactory.get_database = AsyncMock(return_value=mock_db)

        with patch.object(plan_service_module, 'orchestration_config', mock_orchestration_config):
            result = await PlanService.handle_plan_approval(mock_approval, "test-user")

        assert result is True
        assert mock_plan.revision == 3
        assert mock_plan.revision_feedback == [
            "Ask Marcus instead.",
            "Actually, ask Dana.",
        ]

    @pytest.mark.asyncio
    async def test_handle_plan_approval_no_orchestration_config(self):
        mock_approval = MockPlanApprovalResponse()
        with patch.object(plan_service_module, 'orchestration_config', None):
            result = await PlanService.handle_plan_approval(mock_approval, "user")
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_plan_approval_plan_not_found(self):
        mock_approval = MockPlanApprovalResponse(
            plan_id="missing-plan",
            m_plan_id="test-m-plan",
            approved=True
        )
        mock_mplan = MagicMock()
        mock_mplan.plan_id = None
        mock_orchestration_config.plans = {"test-m-plan": mock_mplan}

        mock_db = MagicMock()
        mock_db.get_plan = AsyncMock(return_value=None)
        mock_database_factory.DatabaseFactory.get_database = AsyncMock(return_value=mock_db)

        with patch.object(plan_service_module, 'orchestration_config', mock_orchestration_config):
            result = await PlanService.handle_plan_approval(mock_approval, "user")

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_plan_approval_exception(self):
        mock_approval = MockPlanApprovalResponse(m_plan_id="nonexistent")
        mock_orchestration_config.plans = {}
        with patch.object(plan_service_module, 'orchestration_config', mock_orchestration_config):
            result = await PlanService.handle_plan_approval(mock_approval, "user")
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_agent_messages_success(self):
        mock_message = MockAgentMessageResponse(
            plan_id="test-plan",
            agent="TestAgent",
            content="Agent message content",
        )
        mock_db = MagicMock()
        mock_db.add_agent_message = AsyncMock()
        mock_database_factory.DatabaseFactory.get_database = AsyncMock(return_value=mock_db)

        result = await PlanService.handle_agent_messages(mock_message, "test-user")

        assert result.persisted is True
        mock_db.add_agent_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_agent_messages_final_message(self):
        mock_message = MockAgentMessageResponse(
            plan_id="test-plan",
            agent="TestAgent",
            content="Final message",
            streaming_message="Stream completed",
        )
        mock_db = MagicMock()
        mock_db.add_agent_message = AsyncMock()
        mock_db.record_streaming_message = AsyncMock(
            return_value=MessageEchoed(EchoOutcome.recorded)
        )
        mock_database_factory.DatabaseFactory.get_database = AsyncMock(return_value=mock_db)

        result = await PlanService.handle_agent_messages(mock_message, "test-user")

        assert result.persisted is True
        mock_db.record_streaming_message.assert_awaited_once_with(
            "test-plan", "Stream completed"
        )

    @pytest.mark.asyncio
    async def test_handle_agent_messages_exception(self):
        mock_message = MockAgentMessageResponse()
        mock_database_factory.DatabaseFactory.get_database = AsyncMock(
            side_effect=Exception("Database error")
        )
        result = await PlanService.handle_agent_messages(mock_message, "user")
        assert result.store_failed is True

    @pytest.mark.asyncio
    async def test_handle_human_clarification_success(self):
        mock_clarification = MockUserClarificationResponse(
            plan_id="test-plan",
            answer="This is my clarification"
        )
        mock_db = MagicMock()
        mock_db.add_agent_message = AsyncMock()
        mock_database_factory.DatabaseFactory.get_database = AsyncMock(return_value=mock_db)

        result = await PlanService.handle_human_clarification(mock_clarification, "test-user")

        assert result is True
        mock_db.add_agent_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_human_clarification_exception(self):
        mock_clarification = MockUserClarificationResponse()
        mock_database_factory.DatabaseFactory.get_database = AsyncMock(
            side_effect=Exception("Database error")
        )
        result = await PlanService.handle_human_clarification(mock_clarification, "user")
        assert result is False

    @pytest.mark.asyncio
    async def test_static_method_properties(self):
        mock_approval = MockPlanApprovalResponse(approved=False)
        with patch.object(plan_service_module, 'orchestration_config', None):
            result = await PlanService.handle_plan_approval(mock_approval, "user")
        assert result is False

    def test_logging_integration(self):
        logger = logging.getLogger('backend.services.plan_service')
        assert logger is not None


# ---------------------------------------------------------------------------
# The echo records what was said, and decides nothing (#158, ADR-043 §7)
# ---------------------------------------------------------------------------
class TestTheEchoStopsDecidingWhetherTheTurnEnded:
    """One fact, one writer.

    The browser echoing an agent message back was the only writer of a
    **Settled status** anywhere in the system, off one branch of one handler.
    #157 gave that fact a writer that is present when the turn ends; this
    handler keeping it as well would be two writers of one fact, which is how
    they come to disagree.

    So the transcript and the streaming message still land here, and
    `overall_status` never does. The streamed reply goes through the store's own
    `record_streaming_message`, which is the seam that can tell a **Plan
    record** that has gone from one it could not read — the distinction the old
    `get_plan`-and-upsert could not make, because the read behind it answers an
    outage with an empty result.
    """

    def _store(self, streamed=None):
        store = MagicMock()
        store.add_agent_message = AsyncMock()
        store.record_streaming_message = AsyncMock(
            return_value=streamed
            if streamed is not None
            else MessageEchoed(EchoOutcome.recorded)
        )
        mock_database_factory.DatabaseFactory.get_database = AsyncMock(
            return_value=store
        )
        return store

    def _message(self, **kw):
        data = dict(plan_id="p-1", agent="TestAgent", content="hi")
        data.update(kw)
        return MockAgentMessageResponse(**data)

    @pytest.mark.asyncio
    async def test_the_handler_writes_no_status_at_all(self):
        # The route to a **Settled status** is the settle-write, and this
        # handler having a second one is the defect #158 removed. Asserted as
        # an absence against the store: no Plan record write of any kind
        # leaves here.
        store = self._store()

        await PlanService.handle_agent_messages(
            self._message(streaming_message="the streamed answer"), "user-1"
        )

        store.update_plan.assert_not_called()
        store.settle_turn.assert_not_called()

    @pytest.mark.asyncio
    async def test_the_streamed_reply_still_reaches_the_record(self):
        # The narrowing's other half: nothing else persists this, so removing
        # it along with the verdict would lose the streamed reply on reload.
        store = self._store()

        result = await PlanService.handle_agent_messages(
            self._message(streaming_message="what it said"), "user-1"
        )

        store.record_streaming_message.assert_awaited_once_with(
            "p-1", "what it said"
        )
        assert result.persisted is True

    @pytest.mark.asyncio
    async def test_the_transcript_reaches_the_record(self):
        store = self._store()

        await PlanService.handle_agent_messages(self._message(), "user-1")

        store.add_agent_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_message_with_no_streamed_reply_touches_no_plan_record(self):
        # Every message before the last one. The browser sends an empty
        # streamed reply on each of them, and writing that was a no-op — so
        # this keeps a Cosmos round trip off every streamed line.
        store = self._store()

        result = await PlanService.handle_agent_messages(self._message(), "user-1")

        store.record_streaming_message.assert_not_awaited()
        assert result.persisted is True

    @pytest.mark.asyncio
    async def test_the_store_decides_whether_the_record_was_there(self):
        # Told apart at the seam that can tell, and reported unchanged: this
        # handler neither invents `no_such_plan_record` nor upgrades it to a failure.
        store = self._store(MessageEchoed(EchoOutcome.no_such_plan_record))

        result = await PlanService.handle_agent_messages(
            self._message(streaming_message="what it said"), "user-1"
        )

        assert result.outcome is EchoOutcome.no_such_plan_record
        assert result.store_failed is False
        assert result.persisted is False
        assert store.record_streaming_message.await_count == 1

    @pytest.mark.asyncio
    async def test_a_transcript_that_did_not_land_is_reported_as_a_failure(self):
        store = self._store()
        store.add_agent_message = AsyncMock(side_effect=RuntimeError("Cosmos is down"))

        result = await PlanService.handle_agent_messages(self._message(), "user-1")

        assert result.store_failed is True
        assert result.persisted is False

    @pytest.mark.asyncio
    async def test_a_transcript_that_did_not_land_stops_there(self):
        # No point asking the store to hold a streamed reply for a turn whose
        # transcript it just refused.
        store = self._store()
        store.add_agent_message = AsyncMock(side_effect=RuntimeError("Cosmos is down"))

        await PlanService.handle_agent_messages(
            self._message(streaming_message="what it said"), "user-1"
        )

        store.record_streaming_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_streamed_reply_the_store_refused_is_reported_as_a_failure(self):
        self._store(MessageEchoed(EchoOutcome.refused))

        result = await PlanService.handle_agent_messages(
            self._message(streaming_message="what it said"), "user-1"
        )

        assert result.store_failed is True

    @pytest.mark.asyncio
    async def test_a_store_that_raised_is_reported_as_a_failure(self):
        # `record_streaming_message` reports rather than raises, but a caller
        # that trusted that and was wrong would answer 200 to an exception.
        store = self._store()
        store.record_streaming_message = AsyncMock(
            side_effect=RuntimeError("Cosmos is down")
        )

        result = await PlanService.handle_agent_messages(
            self._message(streaming_message="what it said"), "user-1"
        )

        assert result.store_failed is True

    @pytest.mark.asyncio
    async def test_nothing_in_the_handler_writes_a_settled_status(self):
        # The read a reviewer would do, made mechanical: #157's writer is the
        # one that settles a turn, and a second one reappearing here is the
        # defect this ticket removed coming back.
        source = Path(plan_service_module.__file__).read_text(encoding="utf-8")

        assert "PlanStatus.completed" not in source
        assert "PlanStatus.failed" not in source
        assert "PlanStatus.canceled" not in source
