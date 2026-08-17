"""
Agent Framework model equivalents for former agent framework -backed data models.

"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DataType(str, Enum):
    session = "session"
    session_state = "session_state"
    troubleshooting = "troubleshooting"
    service_ticket = "service_ticket"
    plan = "plan"
    step = "step"
    agent_message = "agent_message"
    team_config = "team_config"
    user_current_team = "user_current_team"
    current_team_agent = "current_team_agent"
    m_plan = "m_plan"
    m_plan_message = "m_plan_message"


class AgentType(str, Enum):
    HUMAN = "Human_Agent"
    HR = "Hr_Agent"
    MARKETING = "Marketing_Agent"
    PROCUREMENT = "Procurement_Agent"
    PRODUCT = "Product_Agent"
    GENERIC = "Generic_Agent"
    TECH_SUPPORT = "Tech_Support_Agent"
    GROUP_CHAT_MANAGER = "Group_Chat_Manager"
    PLANNER = "Planner_Agent"
    # Extend as needed


class StepStatus(str, Enum):
    planned = "planned"
    awaiting_feedback = "awaiting_feedback"
    approved = "approved"
    rejected = "rejected"
    action_requested = "action_requested"
    completed = "completed"
    failed = "failed"


class PlanStatus(str, Enum):
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"
    approved = "approved"
    created = "created"


class HumanFeedbackStatus(str, Enum):
    requested = "requested"
    accepted = "accepted"
    rejected = "rejected"


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    function = "function"


class AgentMessageType(str, Enum):
    # Removed trailing commas to avoid tuple enum values
    HUMAN_AGENT = "Human_Agent"
    AI_AGENT = "AI_Agent"


# ---------------------------------------------------------------------------
# Base Models
# ---------------------------------------------------------------------------

class BaseDataModel(BaseModel):
    """Base data model with common fields."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentMessage(BaseDataModel):
    """Base class for messages sent between agents."""
    data_type: Literal[DataType.agent_message] = DataType.agent_message
    plan_id: str
    content: str
    source: str
    step_id: Optional[str] = None


class Session(BaseDataModel):
    """Represents a user session."""
    data_type: Literal[DataType.session] = DataType.session
    user_id: str
    current_status: str
    message_to_user: Optional[str] = None


class SessionIdentityState(BaseModel):
    """Who, if anyone, is signed in on the shared store device (issue #20).

    Mocked end to end — no real identity provider writes this. Absent means
    anonymous, and anonymous is the *refusing* state at the Identity boundary
    gate, so a half-written record degrades towards a refusal.
    """
    display_name: Optional[str] = None


class SessionState(BaseDataModel):
    """The state of one session, held server-side so a reload does not lose it.

    A record in the schemaless memory container like every other: partitioned
    by ``session_id`` and discriminated by ``data_type``, so it needed one new
    enumeration member and this one model and no migration. Its ``id`` is
    derived from the session (``session.store.session_state_id``) rather than a
    fresh uuid, which is what makes a session's state a point read and makes a
    second write replace the first rather than accumulate.
    """
    data_type: Literal[DataType.session_state] = DataType.session_state
    # Who the record belongs to. The container's records carry their owner and
    # its reads are scoped by it; this one is no exception, so one user's
    # session record can never unlock another user's Identity boundary gate.
    user_id: Optional[str] = None
    identity: SessionIdentityState = Field(default_factory=SessionIdentityState)
    # The Lane taken, as the lane router decided it (ADR-013) — recorded here
    # because it is the router's output and a reloaded plan page cannot
    # re-derive it: re-deriving would be a second router.
    lane: Optional[str] = None


class TroubleshootingRecord(BaseDataModel):
    """What one associate has already tried on this fault (issue #21).

    Framework checkpoint state is in-memory and must not be relied on, so the
    steps an associate reports trying are persisted here, explicitly. Like the
    session state beside it this is an ordinary document in the schemaless
    memory container — partitioned by ``session_id``, discriminated by
    ``data_type``, reached through the generic CRUD — so it cost one
    enumeration member and this one model and **no migration**. Its ``id`` is
    derived from the session (``troubleshooting.store.troubleshooting_record_id``)
    rather than a fresh uuid, which makes a read a point read and a second write
    replace the first.
    """
    data_type: Literal[DataType.troubleshooting] = DataType.troubleshooting
    # Who the record belongs to. Scoped like every other record in the
    # container: one associate's fault is not another's.
    user_id: Optional[str] = None
    # The associate's own words, first wording kept, in the order reported —
    # they are what #22's ticket quotes back rather than asking again.
    attempted: List[str] = Field(default_factory=list)
    # What broke. Carried because the turn that reports a step is rarely the
    # turn that named the equipment, and the ticket needs both.
    equipment: Optional[str] = None


class ServiceTicket(BaseDataModel):
    """The Simulated ticket raised from one conversation (issue #22).

    A sibling of ``TroubleshootingRecord`` in the same schemaless memory
    container — partitioned by ``session_id``, discriminated by ``data_type``,
    reached through the generic CRUD, its ``id`` derived from the session
    (``escalation.store.ticket_record_id``) so a re-draft **corrects** the draft
    it replaces rather than leaving two tickets for one fault. One enumeration
    member and this one model; no migration.

    The template's fields live in one ``fields`` map rather than as columns.
    ``TKT-001`` is content, authored in the content pack and revisable there,
    and a model with a named attribute per row would make every future template
    edit a schema change — and, worse, would give the ticket's status two homes
    that could disagree.
    """
    data_type: Literal[DataType.service_ticket] = DataType.service_ticket
    # Who raised it. Scoped like every other record in the container: one
    # associate's fault, and one associate's ticket.
    user_id: Optional[str] = None
    # TKT-001's fields, in the template's own names. ``fields["status"]`` is the
    # single source of draft-versus-submitted.
    fields: Dict[str, str] = Field(default_factory=dict)


class UserCurrentTeam(BaseDataModel):
    """Represents the current team of a user."""
    data_type: Literal[DataType.user_current_team] = DataType.user_current_team
    user_id: str
    team_id: str


class CurrentTeamAgent(BaseDataModel):
    """Represents the current agent of a user."""
    data_type: Literal[DataType.current_team_agent] = DataType.current_team_agent
    team_id: str
    team_name: str
    agent_name: str
    agent_description: str
    agent_instructions: str
    agent_foundry_id: str


class Plan(BaseDataModel):
    """Represents a plan containing multiple steps."""
    data_type: Literal[DataType.plan] = DataType.plan
    plan_id: str
    user_id: str
    initial_goal: str
    overall_status: PlanStatus = PlanStatus.in_progress
    approved: bool = False
    source: str = AgentType.PLANNER.value
    m_plan: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    team_id: Optional[str] = None
    streaming_message: Optional[str] = None
    human_clarification_request: Optional[str] = None
    human_clarification_response: Optional[str] = None
    # The Reviewable plan's lineage (#108). A plan the associate sent back is
    # revised, never destroyed, so the row records which revision is on screen
    # and what was asked to get there.
    revision: int = 1
    revision_feedback: List[str] = Field(default_factory=list)


class Step(BaseDataModel):
    """Represents an individual step (task) within a plan."""
    data_type: Literal[DataType.step] = DataType.step
    plan_id: str
    user_id: str
    action: str
    agent: AgentType
    status: StepStatus = StepStatus.planned
    agent_reply: Optional[str] = None
    human_feedback: Optional[str] = None
    human_approval_status: Optional[HumanFeedbackStatus] = HumanFeedbackStatus.requested
    updated_action: Optional[str] = None


class TeamSelectionRequest(BaseDataModel):
    """Request model for team selection."""
    team_id: str


class TeamAgent(BaseModel):
    """Represents an agent within a team."""
    input_key: str
    type: str
    name: str
    deployment_name: str
    system_message: str = ""
    description: str = ""
    icon: str = ""
    use_file_search: bool = False
    vector_store_name: str | None = None
    use_knowledge_base: bool = False
    knowledge_base_name: str | None = None
    use_toolbox: bool = False
    toolbox_filter: str | None = None
    user_responses: bool = False
    coding_tools: bool = False
    temperature: float | None = None


class StartingTask(BaseModel):
    """Represents a starting task for a team."""
    id: str
    name: str
    prompt: str
    created: str
    creator: str
    logo: str
    # The declared Lane (issue #16, ADR-013). Deliberately an unvalidated
    # ``str`` rather than the ``Lane`` enum: a value that is not one of the two
    # lanes — the realistic authoring slip — must fail open to the Deliberate
    # lane in the lane router rather than reject the whole team definition. A
    # value that is not a string at all is still a malformed definition and is
    # rejected here, loudly, at upload time.
    lane: Optional[str] = None

    # The Rehearsed replies (issue #26) — one-tap answers to a Clarification,
    # authored on the Quick Task that provokes one. Content is deliberately
    # unvalidated for the same reason ``lane`` is: a reply that reads oddly is
    # a beat that reads oddly, not a team definition worth rejecting. Empty
    # rather than ``None`` when absent, because only one beat asks a question
    # back and every other task would otherwise have to be asked twice whether
    # it has any.
    rehearsed_replies: List[str] = Field(default_factory=list)

    # The post-approval ticket-status inquiry (issue #105). It is authored on
    # the ticketing task because only that task can raise the ticket whose
    # conversation may offer the reply.
    ticket_status_reply: Optional[Dict[str, str]] = None

    # The next Quick Task in this conversation (issue #61, ADR-024). Like
    # ``lane``, the pointer is authored configuration: a missing or unknown
    # task simply produces no follow-on affordance in the surface.
    follow_on: Optional[str] = None

    # The escalation task's explicit completion behavior (issue #62). This is
    # authored on the task rather than inferred from its wording so a content
    # edit cannot silently stop the approval seam from storing its ticket.
    ticket_on_approval: bool = False


class TeamConfiguration(BaseDataModel):
    """Represents a team configuration stored in the database."""
    team_id: str
    data_type: Literal[DataType.team_config] = DataType.team_config
    session_id: str  # partition key
    name: str
    status: str
    created: str
    created_by: str
    deployment_name: str
    agents: List[TeamAgent] = Field(default_factory=list)
    description: str = ""
    logo: str = ""
    plan: str = ""
    starting_tasks: List[StartingTask] = Field(default_factory=list)
    user_id: str  # who uploaded this configuration
    is_default: bool = False  # default teams are visible to all users
    # Whether every agent on this team must appear in every plan (#54). True is
    # the inherited behaviour and the default, so a team that predates the flag
    # keeps it. A team whose agents are alternatives rather than a pipeline
    # sets it False: see `orchestration.plan_review_helpers`.
    require_all_agents: bool = True


class PlanWithSteps(Plan):
    """Plan model that includes the associated steps."""
    steps: List[Step] = Field(default_factory=list)
    total_steps: int = 0
    planned: int = 0
    awaiting_feedback: int = 0
    approved: int = 0
    rejected: int = 0
    action_requested: int = 0
    completed: int = 0
    failed: int = 0

    def update_step_counts(self) -> None:
        """Update the counts of steps by their status."""
        status_counts = {
            StepStatus.planned: 0,
            StepStatus.awaiting_feedback: 0,
            StepStatus.approved: 0,
            StepStatus.rejected: 0,
            StepStatus.action_requested: 0,
            StepStatus.completed: 0,
            StepStatus.failed: 0,
        }
        for step in self.steps:
            status_counts[step.status] += 1

        self.total_steps = len(self.steps)
        self.planned = status_counts[StepStatus.planned]
        self.awaiting_feedback = status_counts[StepStatus.awaiting_feedback]
        self.approved = status_counts[StepStatus.approved]
        self.rejected = status_counts[StepStatus.rejected]
        self.action_requested = status_counts[StepStatus.action_requested]
        self.completed = status_counts[StepStatus.completed]
        self.failed = status_counts[StepStatus.failed]

        # Mark the plan as complete if the sum of completed and failed steps equals the total number of steps
        if self.total_steps > 0 and (self.completed + self.failed) == self.total_steps:
            self.overall_status = PlanStatus.completed


class InputTask(BaseModel):
    """Message representing the initial input task from the user."""
    session_id: str
    description: str
    # The Lane the request declares (issue #16, ADR-013), carried through from
    # the Quick Task the presenter tapped. Absent for free-typed input, which
    # the lane router then routes by its keyword fallback. It is deliberately
    # the *only* lane declaration on the wire — Plan review is what the router
    # maps it onto, and two ways to say the same thing on one message is how a
    # request ends up in a lane nobody chose.
    lane: Optional[str] = None
    # The authored task that produced this request. The server resolves its
    # behavior from the active team's configuration rather than trusting a
    # browser-supplied behavior flag.
    starting_task_id: Optional[str] = None


class UserLanguage(BaseModel):
    language: str


class SessionStatePatch(BaseModel):
    """A partial write to a session's state (issue #20).

    Partial on purpose: two surfaces write this record — the mocked sign-in
    writes an identity, the request path writes the Lane taken — so a write
    names only the fields it owns. A field that is present and null is an
    explicit clear (signing out is a write, not the absence of one), which is
    why the route reads ``model_fields_set`` rather than the values alone.
    """
    identity: Optional[SessionIdentityState] = None
    lane: Optional[str] = None


class AgentMessageData(BaseDataModel):
    """Represents a multi-plan agent message."""
    data_type: Literal[DataType.m_plan_message] = DataType.m_plan_message
    plan_id: str
    user_id: str
    agent: str
    m_plan_id: Optional[str] = None
    agent_type: AgentMessageType = AgentMessageType.AI_AGENT
    content: str
    raw_data: str
    steps: List[Any] = Field(default_factory=list)
    next_steps: List[Any] = Field(default_factory=list)
