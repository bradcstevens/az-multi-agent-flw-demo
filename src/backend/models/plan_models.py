# Copyright (c) Microsoft. All rights reserved.
"""Plan models — merged from v4/models/models.py and v4/models/orchestration_models.py."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, computed_field, model_validator

from provenance import PLAN_PROVENANCE, VERDICT_PROVENANCE

# What a declined Verdict says it cost, authored beside the record that carries
# it rather than in the component that renders it (ADR-036 decision 4). The
# person's own words are generated, so they cannot be relied on to report the
# consequence: a colleague who says only that they are away that weekend has
# not told the associate that the shift lead was never asked.
DECLINE_STOPS_THE_PLAN = "Nothing waiting on this went ahead:"


class PlanStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VerdictOutcome(str, Enum):
    """The authored decision for a Person step after plan approval."""

    APPROVED = "approved"
    DECLINED = "declined"


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
    outcome: Optional[VerdictOutcome] = None


class Verdict(BaseModel):
    """One non-associate Person step resolved after the plan is approved."""

    step_id: int
    assignee: PersonAssignee
    outcome: VerdictOutcome
    words: str
    # The authored actions this decline stopped, in the plan's declared order.
    # Empty when nothing waited on the step — and refused outright on an
    # approval, which stops nothing by definition.
    stopped_steps: List[str] = Field(default_factory=list)
    provenance_line: str = VERDICT_PROVENANCE

    @model_validator(mode="after")
    def _only_a_decline_stops_anything(self) -> "Verdict":
        if self.stopped_steps and self.outcome is not VerdictOutcome.DECLINED:
            raise ValueError("An approved Verdict cannot have stopped a step")
        return self

    @computed_field(return_type=Optional[str])
    @property
    def stopped_line(self) -> Optional[str]:
        """What did not happen, said on the record that stopped it."""
        if not self.stopped_steps:
            return None
        actions = "; ".join(
            action.strip().rstrip(".") for action in self.stopped_steps
        )
        return f"{DECLINE_STOPS_THE_PLAN} {actions}."


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
    verdicts: List[Verdict] = Field(default_factory=list)
    # Which revision of this Reviewable plan the associate is looking at, and
    # what they asked to change to get it (#108). Carried on the approval frame
    # so the surface can tell a fresh plan from one already sent back.
    revision: int = 1
    revision_feedback: List[str] = Field(default_factory=list)

    @computed_field(return_type=Optional[str])
    @property
    def provenance_line(self) -> Optional[str]:
        """Disclose the plan's simulated people before the associate approves."""
        if any(
            isinstance(step.assignee, PersonAssignee) and step.assignee.simulated
            for step in self.steps
        ):
            return PLAN_PROVENANCE
        return None


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
