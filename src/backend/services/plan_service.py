import json
import logging
from dataclasses import asdict

import models.messages as messages
from chat.echo import EchoOutcome, MessageEchoed
from common.database.database_factory import DatabaseFactory
from common.models.messages import (AgentMessageData, AgentMessageType,
                                    AgentType, PlanStatus)
from common.utils.event_utils import track_event_if_configured
from orchestration.connection_config import orchestration_config
from orchestration.plan_revision import PlanRevision

logger = logging.getLogger(__name__)


def build_agent_message_from_user_clarification(
    human_feedback: messages.UserClarificationResponse, user_id: str
) -> AgentMessageData:
    """
    Convert a UserClarificationResponse (human feedback) into an AgentMessageData.
    """
    # NOTE: AgentMessageType enum currently defines values with trailing commas in messages.py.
    # e.g. HUMAN_AGENT = "Human_Agent",  -> value becomes ('Human_Agent',)
    # Consider fixing that enum (remove trailing commas) so .value is a string.
    return AgentMessageData(
        plan_id=human_feedback.plan_id or "",
        user_id=user_id,
        m_plan_id=human_feedback.m_plan_id or None,
        agent=AgentType.HUMAN.value,  # or simply "Human_Agent"
        agent_type=AgentMessageType.HUMAN_AGENT,  # will serialize per current enum definition
        content=human_feedback.answer or "",
        raw_data=json.dumps(asdict(human_feedback)),
        steps=[],  # intentionally empty
        next_steps=[],  # intentionally empty
    )


def build_agent_message_from_agent_message_response(
    agent_response: messages.AgentMessageResponse,
    user_id: str,
) -> AgentMessageData:
    """
    Convert a messages.AgentMessageResponse into common.models.messages.AgentMessageData.
    This is defensive: it tolerates missing fields and different timestamp formats.
    """
    # Robust timestamp parsing (accepts seconds or ms or missing)

    # Raw data serialization
    raw = getattr(agent_response, "raw_data", None)
    try:
        if raw is None:
            # try asdict if it's a dataclass-like
            try:
                raw_str = json.dumps(asdict(agent_response))
            except Exception:
                raw_str = json.dumps(
                    {
                        k: getattr(agent_response, k)
                        for k in dir(agent_response)
                        if not k.startswith("_")
                    }
                )
        elif isinstance(raw, (dict, list)):
            raw_str = json.dumps(raw)
        else:
            raw_str = str(raw)
    except Exception:
        raw_str = json.dumps({"raw": str(raw)})

    # Steps / next_steps defaulting
    steps = getattr(agent_response, "steps", []) or []
    next_steps = getattr(agent_response, "next_steps", []) or []

    # Agent name and type
    agent_name = (
        getattr(agent_response, "agent", "")
        or getattr(agent_response, "agent_name", "")
        or getattr(agent_response, "source", "")
    )
    # Try to infer agent_type, fallback to AI_AGENT
    agent_type_raw = getattr(agent_response, "agent_type", None)
    if isinstance(agent_type_raw, AgentMessageType):
        agent_type = agent_type_raw
    else:
        # Normalize common strings
        agent_type_str = str(agent_type_raw or "").lower()
        if "human" in agent_type_str:
            agent_type = AgentMessageType.HUMAN_AGENT
        else:
            agent_type = AgentMessageType.AI_AGENT

    # Content
    content = (
        getattr(agent_response, "content", "")
        or getattr(agent_response, "text", "")
        or ""
    )

    # plan_id / user_id fallback
    plan_id_val = getattr(agent_response, "plan_id", "") or ""
    user_id_val = getattr(agent_response, "user_id", "") or user_id

    return AgentMessageData(
        plan_id=plan_id_val,
        user_id=user_id_val,
        m_plan_id=getattr(agent_response, "m_plan_id", ""),
        agent=agent_name,
        agent_type=agent_type,
        content=content,
        raw_data=raw_str,
        steps=list(steps),
        next_steps=list(next_steps),
    )


class PlanService:

    @staticmethod
    async def handle_plan_approval(
        human_feedback: messages.PlanApprovalResponse, user_id: str
    ) -> bool:
        """
        Process a PlanApprovalResponse coming from the client.

        The verdict is binary (#108): ``approved`` settles the plan, and
        anything else is a **send-back** carrying what the associate would
        change. Neither branch removes the Plan record — the row is the
        conversation, not the plan.

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
                    mplan.team_id = plan.team_id  # just to keep consistency
                    orchestration_config.plans[human_feedback.m_plan_id] = mplan
                    if plan:
                        plan.overall_status = PlanStatus.approved
                        plan.m_plan = mplan.model_dump()
                        await memory_store.update_plan(plan)
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
                else:  # the associate sent the plan back
                    # Not a rejection and not a deletion: the Plan record *is*
                    # the conversation (ADR-028), so it survives and records
                    # the revision the associate asked for and what they said
                    # to ask for it (#108). The waiting review does the
                    # replanning; this is only the lineage.
                    plan = await memory_store.get_plan(human_feedback.plan_id)
                    if not plan:
                        print("Plan not found in memory store.")
                        return False
                    revision = PlanRevision.restored(
                        getattr(plan, "revision", None),
                        getattr(plan, "revision_feedback", None),
                    ).sent_back(human_feedback.feedback or "")
                    plan.revision = revision.number
                    plan.revision_feedback = list(revision.feedback)
                    await memory_store.update_plan(plan)
                    track_event_if_configured(
                        "PlanSentBack",
                        {
                            "m_plan_id": human_feedback.m_plan_id,
                            "plan_id": human_feedback.plan_id,
                            "user_id": user_id,
                            "revision": revision.number,
                        },
                    )

        except Exception as e:
            print(f"Error processing plan approval: {e}")
            return False
        return True

    @staticmethod
    async def handle_agent_messages(
        agent_message: messages.AgentMessageResponse, user_id: str
    ) -> MessageEchoed:
        """Record what an agent said — and nothing about whether the turn ended.

        The browser's echo carries the transcript and the streaming message,
        which nothing else persists, so this is a narrowing rather than a
        removal (#158, ADR-043 decision 7). What it no longer carries is a
        verdict: the terminal status of a turn is written by the server that
        ended it, and this handler writing `overall_status` as well made two
        writers of one fact.

        The streaming message is written when the echo carries one, which is
        exactly when it used to be written — the browser sends it on the turn's
        last message and nowhere else — but read off the payload it belongs to
        rather than off a flag beside it.

        Args:
            agent_message: what the agent said, as the browser echoed it back.
            user_id: authenticated user id.

        Returns:
            A `MessageEchoed` saying which writes landed. A store failure is one
            of the three answers rather than a swallowed exception, because the
            route above may not report a write that did not happen.
        """
        agent_msg = build_agent_message_from_agent_message_response(
            agent_message, user_id
        )

        try:
            memory_store = await DatabaseFactory.get_database(user_id=user_id)
            await memory_store.add_agent_message(agent_msg)
        except Exception:
            logger.exception(
                "The agent message for plan '%s' did not reach the store",
                agent_msg.plan_id,
            )
            return MessageEchoed(EchoOutcome.refused)

        streaming_message = getattr(agent_message, "streaming_message", None)
        if not streaming_message:
            return MessageEchoed(EchoOutcome.recorded)

        try:
            plan = await memory_store.get_plan(agent_msg.plan_id)
        except Exception:
            logger.exception(
                "Could not read plan '%s' to store its streaming message",
                agent_msg.plan_id,
            )
            return MessageEchoed(EchoOutcome.refused)

        if plan is None:
            # Ordinary rather than a fault: #108's rejection path deletes the
            # Plan document outright, and a Chat can be deleted between an
            # agent speaking and this echo arriving. Nothing to write to is not
            # a store that refused to write.
            logger.info(
                "No plan '%s' to hold the streaming message — the record has gone",
                agent_msg.plan_id,
            )
            return MessageEchoed(EchoOutcome.no_such_chat)

        plan.streaming_message = streaming_message
        try:
            await memory_store.update_plan(plan)
        except Exception:
            logger.exception(
                "The streaming message for plan '%s' did not reach the store",
                agent_msg.plan_id,
            )
            return MessageEchoed(EchoOutcome.refused)

        return MessageEchoed(EchoOutcome.recorded)

    @staticmethod
    async def handle_human_clarification(
        human_feedback: messages.UserClarificationResponse, user_id: str
    ) -> bool:
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
            agent_msg = build_agent_message_from_user_clarification(
                human_feedback, user_id
            )

            # Persist if your database layer supports it.
            # Look for or implement something like: memory_store.add_agent_message(agent_msg)
            memory_store = await DatabaseFactory.get_database(user_id=user_id)
            await memory_store.add_agent_message(agent_msg)

            return True
        except Exception as e:
            logger.exception(
                "Failed to handle human clarification -> agent message: %s", e
            )
            return False
