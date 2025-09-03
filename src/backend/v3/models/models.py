import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MStep(BaseModel):
    """model of a step in a plan"""
    _agent: str = ""
    action: str = ""

    @property
    def agent(self):
        return self._agent

    @agent.setter
    def agent(self, value):
        self._agent = value if value is not None else ""


class MPlan(BaseModel):
    """model of a plan"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    team_id: str = ""
    plan_id: str = ""
    overall_status: PlanStatus = PlanStatus.CREATED
    user_request: str = ""
    team: List[str] = []
    facts: str = ""
    steps: List[MStep] = []