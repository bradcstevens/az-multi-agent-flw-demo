from typing import Any, Dict, List, Literal, Optional
import uuid
from semantic_kernel.kernel_pydantic import Field, KernelBaseModel
from datetime import datetime, timezone

class BaseDataModel(KernelBaseModel):
    """Base data model with common fields."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

class StartingTask(KernelBaseModel):
    id: str
    name: str
    prompt: str
    created: str
    creator: str
    logo: str

class TeamAgent(KernelBaseModel):
    input_key: str
    type: str
    name: str
    deployment_name: str
    system_message: str = ""
    description: str = ""
    icon: str
    index_name: str = ""
    use_rag: bool = False
    use_mcp: bool = False
    use_bing: bool = False
    use_reasoning: bool = False
    coding_tools: bool = False

class TeamConfiguration(BaseDataModel):
    team_id: str
    data_type: Literal["team_config"] = Field("team_config", Literal=True)
    session_id: str  # Partition key
    name: str
    status: str
    created: str
    created_by: str
    agents: List[TeamAgent] = Field(default_factory=list)
    description: str = ""
    logo: str = ""
    plan: str = ""
    starting_tasks: List[StartingTask] = Field(default_factory=list)
    user_id: str  # Who uploaded this configuration