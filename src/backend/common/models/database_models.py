"""Data models for the database layer."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DataType(str, Enum):
    """Enumeration of possible data types for documents in the database."""

    session = "session"
    plan = "plan"
    step = "step"
    message = "message"
    agent_message = "agent_message"
    team_config = "team_config"
    thread = "thread"
    agent = "agent"


class BaseDataModel(BaseModel):
    """Base data model with common fields."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class DatabaseRecord(BaseDataModel):
    """Base class for all database records."""

    data_type: str
    session_id: str  # Partition key
    user_id: str


class SessionRecord(DatabaseRecord):
    """Represents a user session in the database."""

    data_type: str = Field(default="session", frozen=True)
    current_status: str
    message_to_user: Optional[str] = None


class PlanRecord(DatabaseRecord):
    """Represents a plan in the database."""

    data_type: str = Field(default="plan", frozen=True)
    initial_goal: str
    overall_status: str = "in_progress"
    source: str = "Planner_Agent"
    summary: Optional[str] = None
    human_clarification_request: Optional[str] = None
    human_clarification_response: Optional[str] = None


class StepRecord(DatabaseRecord):
    """Represents a step in the database."""

    data_type: str = Field(default="step", frozen=True)
    plan_id: str
    action: str
    agent: str
    status: str = "planned"
    agent_reply: Optional[str] = None
    human_feedback: Optional[str] = None
    human_approval_status: Optional[str] = "requested"
    updated_action: Optional[str] = None


class AgentMessageRecord(DatabaseRecord):
    """Represents an agent message in the database."""

    data_type: str = Field(default="agent_message", frozen=True)
    plan_id: str
    content: str
    source: str
    step_id: Optional[str] = None


class MessageRecord(DatabaseRecord):
    """Represents a chat message in the database."""

    data_type: str = Field(default="message", frozen=True)
    role: str
    content: str
    plan_id: Optional[str] = None
    step_id: Optional[str] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ThreadRecord(DatabaseRecord):
    """Represents a thread ID in the database."""

    data_type: str = Field(default="thread", frozen=True)
    thread_id: str


class AgentRecord(DatabaseRecord):
    """Represents an agent ID in the database."""

    data_type: str = Field(default="agent", frozen=True)
    action: str
    agent: str
    agent_id: str


class TeamAgentRecord(BaseModel):
    """Represents an agent within a team."""

    input_key: str
    type: str
    name: str
    system_message: str = ""
    description: str = ""
    icon: str
    index_name: str = ""


class StartingTaskRecord(BaseModel):
    """Represents a starting task for a team."""

    id: str
    name: str
    prompt: str
    created: str
    creator: str
    logo: str


class TeamConfigurationRecord(DatabaseRecord):
    """Represents a team configuration in the database."""

    data_type: str = Field(default="team_config", frozen=True)
    team_id: str
    name: str
    status: str
    created: str
    created_by: str
    agents: List[TeamAgentRecord] = Field(default_factory=list)
    description: str = ""
    logo: str = ""
    plan: str = ""
    starting_tasks: List[StartingTaskRecord] = Field(default_factory=list)


class MemoryRecord(BaseModel):
    """Memory record for semantic kernel compatibility."""

    id: str
    text: str
    description: str = ""
    additional_metadata: str = ""
    external_source_name: str = ""
    is_reference: bool = False
    embedding: Optional[List[float]] = None
    key: Optional[str] = None
    timestamp: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class QueryResult(BaseModel):
    """Result of a database query."""

    records: List[BaseDataModel]
    count: int
    continuation_token: Optional[str] = None
