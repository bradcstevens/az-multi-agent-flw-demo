# Copyright (c) Microsoft. All rights reserved.
"""Messages from the backend to the frontend via WebSocket."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List

from common.models.messages import AgentMessageType
from models.plan_models import MPlan, PlanStatus

# ---------------------------------------------------------------------------
# Dataclass message payloads
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AgentMessage:
    """Message from the backend to the frontend via WebSocket."""
    agent_name: str
    timestamp: str
    content: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentStreamStart:
    """Start of a streaming message."""
    agent_name: str


@dataclass(slots=True)
class AgentStreamEnd:
    """End of a streaming message."""
    agent_name: str


@dataclass(slots=True)
class AgentMessageStreaming:
    """Streaming chunk from an agent."""
    agent_name: str
    content: str
    is_final: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentToolMessage:
    """Message representing that an agent produced one or more tool calls."""
    agent_name: str
    tool_calls: List["AgentToolCall"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentToolCall:
    """A single tool invocation."""
    tool_name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlanApprovalRequest:
    """Request for plan approval from the frontend."""
    plan: MPlan
    status: PlanStatus
    context: dict | None = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the Reviewable plan as structured data for the browser."""
        return {
            "plan": self.plan.model_dump(mode="json"),
            "status": getattr(self.status, "value", self.status),
            "context": self.context,
        }


@dataclass(slots=True)
class PlanApprovalResponse:
    """Response for plan approval from the frontend."""
    m_plan_id: str
    approved: bool
    feedback: str | None = None
    plan_id: str | None = None


@dataclass(slots=True)
class ReplanApprovalRequest:
    """Request for replan approval from the frontend."""
    new_plan: MPlan
    reason: str
    context: dict | None = None


@dataclass(slots=True)
class ReplanApprovalResponse:
    """Response for replan approval from the frontend."""
    plan_id: str
    approved: bool
    feedback: str | None = None


@dataclass(slots=True)
class UserClarificationRequest:
    """Request for user clarification from the frontend."""
    question: str
    request_id: str


@dataclass(slots=True)
class UserClarificationResponse:
    """Response for user clarification from the frontend."""
    request_id: str
    answer: str = ""
    plan_id: str = ""
    m_plan_id: str = ""


@dataclass(slots=True)
class TimeoutNotification:
    """Notification about a timeout (approval or clarification)."""
    timeout_type: str          # "approval" or "clarification"
    request_id: str            # plan_id or request_id
    message: str               # description
    timestamp: float           # epoch time
    timeout_duration: float    # seconds waited

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timeout_type": self.timeout_type,
            "request_id": self.request_id,
            "message": self.message,
            "timestamp": self.timestamp,
            "timeout_duration": self.timeout_duration,
        }


# The three transparency payloads (issue #23) — SourceUsed, TokenUsage and
# PresenterAlert — live in ``transparency/payloads.py``, with the package that
# decides what each may claim, the way ``Citation`` lives in ``sop/``. Only
# their ``WebsocketMessageType`` members are here, because the transport is
# this file's business.


class WebsocketMessageType(str, Enum):
    """Types of WebSocket messages sent over the WebSocket connection."""
    SYSTEM_MESSAGE = "system_message"
    AGENT_MESSAGE = "agent_message"
    AGENT_STREAM_START = "agent_stream_start"
    AGENT_STREAM_END = "agent_stream_end"
    AGENT_MESSAGE_STREAMING = "agent_message_streaming"
    AGENT_TOOL_MESSAGE = "agent_tool_message"
    PLAN_APPROVAL_REQUEST = "plan_approval_request"
    PLAN_APPROVAL_RESPONSE = "plan_approval_response"
    REPLAN_APPROVAL_REQUEST = "replan_approval_request"
    REPLAN_APPROVAL_RESPONSE = "replan_approval_response"
    USER_CLARIFICATION_REQUEST = "user_clarification_request"
    USER_CLARIFICATION_RESPONSE = "user_clarification_response"
    FINAL_RESULT_MESSAGE = "final_result_message"
    TIMEOUT_NOTIFICATION = "timeout_notification"
    ERROR_MESSAGE = "error_message"
    PING = "ping"
    # The three transparency signals (issue #23). They share this enum and this
    # socket rather than a channel of their own — the frontend already
    # subscribes here, and a second transport is a second thing to fail on
    # stage.
    SOURCE_USED = "source_used"
    TOKEN_USAGE = "token_usage"
    PRESENTER_ALERT = "presenter_alert"
    # The Simulated ticket (issue #22), pushed from the plan-approval seam
    # rather than by an agent — the approval **is** the confirmation, so the
    # card is emitted by the thing that submitted the ticket. Its shape lives
    # in ``escalation/payloads.py`` for the same reason the three above live in
    # ``transparency/``.
    TICKET_RAISED = "ticket_raised"


@dataclass(slots=True)
class AgentMessageResponse:
    """Response message representing an agent's contribution to a plan (stream or final)."""
    plan_id: str
    agent: str
    content: str
    agent_type: AgentMessageType
    is_final: bool = False
    raw_data: str | None = None
    streaming_message: str | None = None
    steps: List[Any] = field(default_factory=list)
    next_steps: List[Any] = field(default_factory=list)
