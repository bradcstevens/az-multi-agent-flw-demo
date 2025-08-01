"""Database base class for managing database operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from ..models.database_models import (
    BaseDataModel,
    SessionRecord,
    PlanRecord,
    StepRecord,
    AgentMessageRecord,
    MessageRecord,
    TeamConfigurationRecord,
    ThreadRecord,
    AgentRecord,
    MemoryRecord,
    QueryResult,
)


class DatabaseBase(ABC):
    """Abstract base class for database operations."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the database client and create containers if needed."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close database connection."""
        pass

    # Core CRUD Operations
    @abstractmethod
    async def add_item(self, item: BaseDataModel) -> None:
        """Add an item to the database."""
        pass

    @abstractmethod
    async def update_item(self, item: BaseDataModel) -> None:
        """Update an item in the database."""
        pass

    @abstractmethod
    async def get_item_by_id(
        self, item_id: str, partition_key: str, model_class: Type[BaseDataModel]
    ) -> Optional[BaseDataModel]:
        """Retrieve an item by its ID and partition key."""
        pass

    @abstractmethod
    async def query_items(
        self,
        query: str,
        parameters: List[Dict[str, Any]],
        model_class: Type[BaseDataModel],
    ) -> List[BaseDataModel]:
        """Query items from the database and return a list of model instances."""
        pass

    @abstractmethod
    async def delete_item(self, item_id: str, partition_key: str) -> None:
        """Delete an item from the database."""
        pass

    # Session Operations
    @abstractmethod
    async def add_session(self, session: SessionRecord) -> None:
        """Add a session to the database."""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """Retrieve a session by session_id."""
        pass

    @abstractmethod
    async def get_all_sessions(self) -> List[SessionRecord]:
        """Retrieve all sessions for the user."""
        pass

    # Plan Operations
    @abstractmethod
    async def add_plan(self, plan: PlanRecord) -> None:
        """Add a plan to the database."""
        pass

    @abstractmethod
    async def update_plan(self, plan: PlanRecord) -> None:
        """Update a plan in the database."""
        pass

    @abstractmethod
    async def get_plan_by_session(self, session_id: str) -> Optional[PlanRecord]:
        """Retrieve a plan by session_id."""
        pass

    @abstractmethod
    async def get_plan_by_plan_id(self, plan_id: str) -> Optional[PlanRecord]:
        """Retrieve a plan by plan_id."""
        pass

    @abstractmethod
    async def get_plan(self, plan_id: str) -> Optional[PlanRecord]:
        """Retrieve a plan by plan_id."""
        pass

    @abstractmethod
    async def get_all_plans(self) -> List[PlanRecord]:
        """Retrieve all plans for the user."""
        pass

    # Step Operations
    @abstractmethod
    async def add_step(self, step: StepRecord) -> None:
        """Add a step to the database."""
        pass

    @abstractmethod
    async def update_step(self, step: StepRecord) -> None:
        """Update a step in the database."""
        pass

    @abstractmethod
    async def get_steps_by_plan(self, plan_id: str) -> List[StepRecord]:
        """Retrieve all steps for a plan."""
        pass

    @abstractmethod
    async def get_step(self, step_id: str, session_id: str) -> Optional[StepRecord]:
        """Retrieve a step by step_id and session_id."""
        pass

    # Message Operations
    @abstractmethod
    async def add_agent_message(self, message: AgentMessageRecord) -> None:
        """Add an agent message to the database."""
        pass

    @abstractmethod
    async def add_message(self, message: MessageRecord) -> None:
        """Add a message to the database."""
        pass

    @abstractmethod
    async def get_messages(self, session_id: str) -> List[MessageRecord]:
        """Retrieve all messages for a session."""
        pass

    # Team Configuration Operations
    @abstractmethod
    async def add_team_configuration(self, config: TeamConfigurationRecord) -> None:
        """Add a team configuration to the database."""
        pass

    @abstractmethod
    async def get_team_configuration(
        self, config_id: str, user_id: str
    ) -> Optional[TeamConfigurationRecord]:
        """Retrieve a team configuration by ID and user ID."""
        pass

    @abstractmethod
    async def get_all_team_configurations(
        self, user_id: str
    ) -> List[TeamConfigurationRecord]:
        """Retrieve all team configurations for a user."""
        pass

    @abstractmethod
    async def delete_team_configuration(self, config_id: str, user_id: str) -> bool:
        """Delete a team configuration by ID and user ID."""
        pass

    # Thread and Agent Operations
    @abstractmethod
    async def add_thread(self, thread: ThreadRecord) -> None:
        """Add a thread record to the database."""
        pass

    @abstractmethod
    async def get_thread_by_session(self, session_id: str) -> Optional[ThreadRecord]:
        """Retrieve a thread by session_id."""
        pass

    @abstractmethod
    async def add_agent_record(self, agent: AgentRecord) -> None:
        """Add an agent record to the database."""
        pass

    # Data Management Operations
    @abstractmethod
    async def get_data_by_type(self, data_type: str) -> List[BaseDataModel]:
        """Retrieve all data of a specific type."""
        pass

    @abstractmethod
    async def delete_all_messages(self, data_type: str) -> None:
        """Delete all messages of a specific type."""
        pass

    @abstractmethod
    async def delete_all_items(self, data_type: str) -> None:
        """Delete all items of a specific type."""
        pass

    @abstractmethod
    async def get_all_messages(self) -> List[Dict[str, Any]]:
        """Retrieve all messages as dictionaries."""
        pass

    @abstractmethod
    async def get_all_items(self) -> List[Dict[str, Any]]:
        """Retrieve all items as dictionaries."""
        pass

    # Collection Management (for compatibility)
    @abstractmethod
    async def create_collection(self, collection_name: str) -> None:
        """Create a collection."""
        pass

    @abstractmethod
    async def get_collections(self) -> List[str]:
        """Get all collection names."""
        pass

    @abstractmethod
    async def does_collection_exist(self, collection_name: str) -> bool:
        """Check if a collection exists."""
        pass

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> None:
        """Delete a collection."""
        pass

    @abstractmethod
    async def delete_collection_async(self, collection_name: str) -> None:
        """Delete a collection asynchronously."""
        pass

    # Memory Store Operations (for compatibility with existing code)
    @abstractmethod
    async def upsert_async(self, collection_name: str, record: Dict[str, Any]) -> str:
        """Upsert a record asynchronously."""
        pass

    @abstractmethod
    async def upsert_memory_record(self, collection: str, record: MemoryRecord) -> str:
        """Upsert a memory record."""
        pass

    @abstractmethod
    async def remove_memory_record(self, collection: str, key: str) -> None:
        """Remove a memory record."""
        pass

    @abstractmethod
    async def remove(self, collection_name: str, key: str) -> None:
        """Remove a record by key."""
        pass

    @abstractmethod
    async def remove_batch(self, collection_name: str, keys: List[str]) -> None:
        """Remove multiple records by keys."""
        pass

    # Context Manager Support
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Async context manager exit."""
        await self.close()
