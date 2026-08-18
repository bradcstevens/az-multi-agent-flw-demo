# Copyright (c) Microsoft. All rights reserved.
"""Plan models — merged from v4/models/models.py and v4/models/orchestration_models.py."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentAssignee(BaseModel):
    """An agent that can perform a Reviewable plan step."""

    kind: Literal["agent"] = "agent"
    name: str


class PersonAssignee(BaseModel):
    """A person the system can ask to complete a Reviewable plan step."""

    kind: Literal["person"] = "person"
    name: str
    relation: Literal["associate", "peer", "manager"]
    simulated: bool


Assignee = Annotated[
    Union[AgentAssignee, PersonAssignee],
    Field(discriminator="kind"),
]


class MStep(BaseModel):
    """Model of a step in a Reviewable plan."""

    id: Optional[int] = None
    agent: str = ""
    action: str = ""
    assignee: Optional[Assignee] = None
    waitsOn: Optional[int] = None


class MPlan(BaseModel):
    """Model of a plan."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    team_id: str = ""
    plan_id: str = ""
    overall_status: PlanStatus = PlanStatus.CREATED
    user_request: str = ""
    team: List[str] = []
    facts: str = ""
    steps: List[MStep] = []
    # Which revision of this Reviewable plan the associate is looking at, and
    # what they asked to change to get it (#108). Carried on the approval frame
    # so the surface can tell a fresh plan from one already sent back.
    revision: int = 1
    revision_feedback: List[str] = Field(default_factory=list)


@dataclass(slots=True)
class AgentDefinition:
    """Simple agent descriptor used in planning output."""

    name: str
    description: str

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r}, description={self.description!r})"


class PlannerResponseStep(BaseModel):
    """One planned step referencing an agent and an action to perform."""

    agent: AgentDefinition
    action: str


class PlannerResponsePlan(BaseModel):
    """Full planner output including request, team, facts, steps, and summary."""

    request: str
    team: List[AgentDefinition]
    facts: str
    steps: List[PlannerResponseStep] = []
    summary: str = ""
    clarification: Optional[str] = None
