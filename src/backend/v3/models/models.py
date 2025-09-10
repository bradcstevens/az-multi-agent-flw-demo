import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from common.models.messages_kernel import DataType


class PlanStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MStep(BaseModel):
    """model of a step in a plan"""
    agent: str = ""
    action: str = ""

class MPlan(BaseModel):
    """model of a plan"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_type: Literal[DataType.m_plan] = Field(DataType.m_plan, Literal=True)
    user_id: str = ""
    team_id: str = ""
    plan_id: str = ""
    overall_status: PlanStatus = PlanStatus.CREATED
    user_request: str = ""
    team: List[str] = []
    facts: str = ""
    steps: List[MStep] = []