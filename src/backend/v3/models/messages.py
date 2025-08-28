"""Messages from the backend to the frontend via WebSocket."""

from dataclasses import dataclass

from models import MPlan, PlanStatus


@dataclass(slots=True)
class AgentMessage:
    """Message from the backend to the frontend via WebSocket."""
    agent_name: str
    timestamp: str
    content: str

@dataclass(slots=True)
class AgentMessageStreaming:
    """Streaming message from the backend to the frontend via WebSocket."""
    agent_name: str
    content: str
    is_final: bool = False

@dataclass(slots=True)
class PlanApprovalRequest:
    """Request for plan approval from the frontend."""
    plan: MPlan
    status: PlanStatus

    context: dict | None = None

@dataclass(slots=True)
class PlanApprovalResponse:
    """Response for plan approval from the frontend."""
    approved: bool
    feedback: str | None = None

@dataclass(slots=True)
class ReplanApprovalRequest:
    """Request for replan approval from the frontend."""
    reason: str
    context: dict | None = None

@dataclass(slots=True)
class ReplanApprovalResponse:   
    """Response for replan approval from the frontend."""
    approved: bool
    feedback: str | None = None

@dataclass(slots=True)
class UserClarificationRequest:
    """Request for user clarification from the frontend."""
    question: str
    context: dict | None = None

@dataclass(slots=True)
class UserClarificationResponse:
    """Response for user clarification from the frontend."""
    def __init__(self, answer: str):
        self.answer = answer

@dataclass(slots=True)
class FinalResultMessage:
    """Final result message from the backend to the frontend."""
    result: str
    summary: str | None = None
    context: dict | None = None
