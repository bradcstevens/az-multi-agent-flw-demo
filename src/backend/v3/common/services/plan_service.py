import logging
from typing import Dict, Any, Optional
from common.database.database_factory import DatabaseFactory
from common.database.database_base import DatabaseBase
import v3.models.messages as messages
from v3.config.settings import orchestration_config
from common.utils.event_utils import track_event_if_configured

logger = logging.getLogger(__name__)

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
            if hasattr(mplan, "plan_id"):
                print(
                    "Updated orchestration config:",
                    orchestration_config.plans[human_feedback.m_plan_id],
                )
                mplan.plan_id = human_feedback.plan_id
                orchestration_config.plans[human_feedback.m_plan_id] = mplan
                memory_store = await DatabaseFactory.get_database(user_id=user_id)
                plan = await memory_store.get_plan(human_feedback.plan_id)
                if plan:
                    print("Retrieved plan from memory store:", plan)
                    
                    
                else:
                    print("Plan not found in memory store.")
                    return False

        except Exception as e:
            print(f"Error processing plan approval: {e}")
            return False
        return True

    @staticmethod
    async def handle_agent_messages(standard_message: messages.AgentMessage) -> bool:
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
    async def handle_human_clarification(standard_message: messages.AgentMessage) -> bool:
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
