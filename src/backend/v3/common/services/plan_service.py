import logging
from typing import Dict, Any, Optional
from common.database.database_factory import DatabaseFactory
from common.database.database_base import DatabaseBase
import v3.models.messages as messages
from common.models.messages_kernel import PlanStatus
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
    async def handle_agent_messages(standard_message: messages.AgentMessage, user_id: str) -> bool:
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
        return True
