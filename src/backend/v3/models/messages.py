"""Messages from the backend to the frontend via WebSocket."""

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

from semantic_kernel.kernel_pydantic import Field, KernelBaseModel
from v3.models.models import MPlan, PlanStatus


@dataclass(slots=True)
class AgentMessage:
    """Message from the backend to the frontend via WebSocket."""
    agent_name: str
    timestamp: str
    content: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert the AgentMessage to a dictionary for JSON serialization."""
        return asdict(self)

@dataclass(slots=True)
class AgentStreamStart:
    """Start of a streaming message from the backend to the frontend via WebSocket."""
    agent_name: str

@dataclass(slots=True)
class AgentStreamEnd:
    """End of a streaming message from the backend to the frontend via WebSocket."""
    agent_name: str

@dataclass(slots=True)
class AgentMessageStreaming:
    """Streaming message from the backend to the frontend via WebSocket."""
    agent_name: str
    content: str
    is_final: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert the AgentMessageStreaming to a dictionary for JSON serialization."""
        return asdict(self)

@dataclass(slots=True)
class AgentToolMessage:
    """Message from an agent using a tool."""
    agent_name: str
    tool_calls: List['AgentToolCall'] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the AgentToolMessage to a dictionary for JSON serialization."""
        return asdict(self)
    
@dataclass(slots=True)
class AgentToolCall:
    """Message representing a tool call from an agent."""
    tool_name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the AgentToolCall to a dictionary for JSON serialization."""
        return asdict(self)

@dataclass(slots=True)
class PlanApprovalRequest:
    """Request for plan approval from the frontend."""
    plan: MPlan
    status: PlanStatus
    context: dict | None = None

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

@dataclass(slots=True)
class FinalResultMessage:
    """Final result message from the backend to the frontend."""
    result: str
    summary: str | None = None

@dataclass(slots=True)
class HumanFeedback(KernelBaseModel):
    """Message containing human feedback on a step."""

    step_id: Optional[str] = None
    plan_id: str
    session_id: str
    approved: bool
    human_feedback: Optional[str] = None
    updated_action: Optional[str] = None

@dataclass(slots=True)
class HumanClarification(KernelBaseModel):
    """Message containing human clarification on a plan."""

    plan_id: str
    session_id: str
    human_clarification: str

@dataclass(slots=True)
class ApprovalRequest(KernelBaseModel):
    """Message sent to HumanAgent to request approval for a step."""

    step_id: str
    plan_id: str
    session_id: str
    user_id: str
    action: str
    agent_name: str