from dataclasses import Field, asdict
import json
import logging
import time
from typing import Dict, Any, Optional
from common.database.database_factory import DatabaseFactory

from v3.models.models import MPlan
import v3.models.messages as messages
from common.models.messages_kernel import AgentMessageData, AgentMessageType, AgentType, PlanStatus
from v3.config.settings import orchestration_config
from common.utils.event_utils import track_event_if_configured
import uuid
from semantic_kernel.kernel_pydantic import Field

class MPlanExpanded(MPlan):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
logger = logging.getLogger(__name__)
def build_agent_message_from_user_clarification(
    human_feedback: messages.UserClarificationResponse,
    user_id: str
) -> AgentMessageData:
    """
    Convert a UserClarificationResponse (human feedback) into an AgentMessageData.
    """
    # NOTE: AgentMessageType enum currently defines values with trailing commas in messages_kernel.py.
    # e.g. HUMAN_AGENT = "Human_Agent",  -> value becomes ('Human_Agent',)
    # Consider fixing that enum (remove trailing commas) so .value is a string.
    return AgentMessageData(
        plan_id = human_feedback.plan_id or "",
        user_id = user_id,
        m_plan_id = human_feedback.m_plan_id or None,
        agent = AgentType.HUMAN.value,              # or simply "Human_Agent"
        agent_type = AgentMessageType.HUMAN_AGENT,  # will serialize per current enum definition
        content = human_feedback.answer or "",
        raw_data = json.dumps(asdict(human_feedback)),
        steps = [],          # intentionally empty
        next_steps = []      # intentionally empty
    )


class PlanService:

    @staticmethod
    async def handle_plan_approval(human_feedback: messages.PlanApprovalResponse, user_id: str) ->  bool:
        """
        Process a PlanApprovalResponse coming from the client.

        Args:
            feedback: messages.PlanApprovalResponse (contains m_plan_id, plan_id, approved, feedback)
            user_id: authenticated user id

        Returns:
            dict with status and metadata

        Raises:
            ValueError on invalid state
        """
        if orchestration_config is None:
            return False
        try:
            mplan = orchestration_config.plans[human_feedback.m_plan_id]
            memory_store = await DatabaseFactory.get_database(user_id=user_id)
            if hasattr(mplan, "plan_id"):
                print(
                    "Updated orchestration config:",
                    orchestration_config.plans[human_feedback.m_plan_id],
                )
                if human_feedback.approved:
                    plan = await memory_store.get_plan(human_feedback.plan_id)
                    mplan.plan_id = human_feedback.plan_id
                    mplan.team_id = plan.team_id # just to keep consistency 
                    orchestration_config.plans[human_feedback.m_plan_id] = mplan
                    if plan:
                        plan.overall_status = PlanStatus.approved
                        await memory_store.update_plan(plan)
                        await memory_store.add_mplan(mplan)
                        track_event_if_configured(
                            "PlanApproved",
                            {
                                "m_plan_id": human_feedback.m_plan_id,
                                "plan_id": human_feedback.plan_id,
                                "user_id": user_id,
                            },
                        )
                    else:
                        print("Plan not found in memory store.")
                        return False
                else: #reject plan
                    track_event_if_configured(
                            "PlanRejected",
                            {
                                "m_plan_id": human_feedback.m_plan_id,
                                "plan_id": human_feedback.plan_id,
                                "user_id": user_id,
                            },
                        )
                    await memory_store.delete_plan_by_plan_id(human_feedback.plan_id)

        except Exception as e:
            print(f"Error processing plan approval: {e}")
            return False
        return True

    @staticmethod
    async def handle_agent_messages(agent_message: messages.AgentMessageResponse, user_id: str) -> bool:
        """
        Process an AgentMessage coming from the client.

        Args:
            standard_message: messages.AgentMessage (contains relevant message data)
            user_id: authenticated user id

        Returns:
            dict with status and metadata

        Raises:
            ValueError on invalid state
        """
        return True
    
    @staticmethod
    async def handle_human_clarification(human_feedback: messages.UserClarificationResponse, user_id: str) -> bool:
        """
        Process a UserClarificationResponse coming from the client.

        Args:
            human_feedback: messages.UserClarificationResponse (contains relevant message data)
            user_id: authenticated user id

        Returns:
            dict with status and metadata

        Raises:
            ValueError on invalid state
        """
        try:
            agent_msg = build_agent_message_from_user_clarification(human_feedback, user_id)

            # Persist if your database layer supports it.
            # Look for or implement something like: memory_store.add_agent_message(agent_msg)
            memory_store = await DatabaseFactory.get_database(user_id=user_id)
            if hasattr(memory_store, "add_agent_message"):
                await memory_store.add_agent_message(agent_msg)
            else:
                # Fallback: log or ignore if persistence not yet implemented
                logging.debug("add_agent_message not implemented; skipping persistence")

            # Optionally emit over websocket if you have a broadcaster:
            # await websocket_manager.broadcast(WebsocketMessageType.AGENT_MESSAGE, agent_msg.model_dump())

            return True
        except Exception as e:
            logger.exception("Failed to handle human clarification -> agent message: %s", e)
            return False
