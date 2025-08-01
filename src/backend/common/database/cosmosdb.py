"""CosmosDB implementation of the database interface."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type

from azure.cosmos import PartitionKey, exceptions
from azure.cosmos.aio import CosmosClient
from azure.cosmos.aio._database import DatabaseProxy
from azure.cosmos.exceptions import CosmosResourceExistsError

from .database_base import DatabaseBase
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
    DataType,
)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class CosmosDBClient(DatabaseBase):
    """CosmosDB implementation of the database interface."""

    MODEL_CLASS_MAPPING = {
        "session": SessionRecord,
        "plan": PlanRecord,
        "step": StepRecord,
        "agent_message": AgentMessageRecord,
        "message": MessageRecord,
        "team_config": TeamConfigurationRecord,
        "thread": ThreadRecord,
        "agent": AgentRecord,
    }

    def __init__(
        self,
        endpoint: str,
        credential: Any,
        database_name: str,
        container_name: str,
        session_id: str = "",
        user_id: str = "",
    ):
        self.endpoint = endpoint
        self.credential = credential
        self.database_name = database_name
        self.container_name = container_name
        self.session_id = session_id
        self.user_id = user_id

        self.logger = logging.getLogger(__name__)
        self.client = None
        self.database = None
        self.container = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the CosmosDB client and create container if needed."""
        try:
            if not self._initialized:
                self.client = CosmosClient(
                    url=self.endpoint, credential=self.credential
                )
                self.database = self.client.get_database_client(self.database_name)

                self.container = await self._get_or_create_container(
                    self.database, self.container_name, "/session_id"
                )
                self._initialized = True

        except Exception as e:
            self.logger.error("Failed to initialize CosmosDB: %s", str(e))
            raise

    async def _get_or_create_container(
        self, database: DatabaseProxy, container_name: str, partition_key: str
    ):
        """Get or create a CosmosDB container."""
        try:
            return await database.create_container(
                id=container_name, partition_key=PartitionKey(path=partition_key)
            )
        except CosmosResourceExistsError:
            return database.get_container_client(container_name)
        except Exception as e:
            self.logger.error("Failed to get/create CosmosDB container: %s", str(e))
            raise

    async def close(self) -> None:
        """Close the CosmosDB connection."""
        if self.client:
            await self.client.close()
            self.logger.info("Closed CosmosDB connection")

    # Core CRUD Operations
    async def add_item(self, item: BaseDataModel) -> None:
        """Add an item to CosmosDB."""
        await self._ensure_initialized()

        try:
            # Convert to dictionary and handle datetime serialization
            document = item.model_dump()
            document = json.loads(json.dumps(document, cls=DateTimeEncoder))

            await self.container.create_item(body=document)
        except Exception as e:
            self.logger.error("Failed to add item to CosmosDB: %s", str(e))
            raise

    async def update_item(self, item: BaseDataModel) -> None:
        """Update an item in CosmosDB."""
        await self._ensure_initialized()

        try:
            # Convert to dictionary and handle datetime serialization
            document = item.model_dump()
            document = json.loads(json.dumps(document, cls=DateTimeEncoder))

            await self.container.upsert_item(body=document)
        except Exception as e:
            self.logger.error("Failed to update item in CosmosDB: %s", str(e))
            raise

    async def get_item_by_id(
        self, item_id: str, partition_key: str, model_class: Type[BaseDataModel]
    ) -> Optional[BaseDataModel]:
        """Retrieve an item by its ID and partition key."""
        await self._ensure_initialized()

        try:
            item = await self.container.read_item(
                item=item_id, partition_key=partition_key
            )
            return model_class.model_validate(item)
        except Exception as e:
            self.logger.error("Failed to retrieve item from CosmosDB: %s", str(e))
            return None

    async def query_items(
        self,
        query: str,
        parameters: List[Dict[str, Any]],
        model_class: Type[BaseDataModel],
    ) -> List[BaseDataModel]:
        """Query items from CosmosDB and return a list of model instances."""
        await self._ensure_initialized()

        try:
            items = self.container.query_items(query=query, parameters=parameters)
            result_list = []
            async for item in items:
                try:
                    result_list.append(model_class.model_validate(item))
                except Exception as validation_error:
                    self.logger.warning(
                        "Failed to validate item: %s", str(validation_error)
                    )
                    continue
            return result_list
        except Exception as e:
            self.logger.error("Failed to query items from CosmosDB: %s", str(e))
            return []

    async def delete_item(self, item_id: str, partition_key: str) -> None:
        """Delete an item from CosmosDB."""
        await self._ensure_initialized()

        try:
            await self.container.delete_item(item=item_id, partition_key=partition_key)
        except Exception as e:
            self.logger.error("Failed to delete item from CosmosDB: %s", str(e))
            raise

    # Session Operations
    async def add_session(self, session: SessionRecord) -> None:
        """Add a session to CosmosDB."""
        await self.add_item(session)

    async def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """Retrieve a session by session_id."""
        query = "SELECT * FROM c WHERE c.id=@id AND c.data_type=@data_type"
        parameters = [
            {"name": "@id", "value": session_id},
            {"name": "@data_type", "value": "session"},
        ]
        results = await self.query_items(query, parameters, SessionRecord)
        return results[0] if results else None

    async def get_all_sessions(self) -> List[SessionRecord]:
        """Retrieve all sessions for the user."""
        query = "SELECT * FROM c WHERE c.user_id=@user_id AND c.data_type=@data_type"
        parameters = [
            {"name": "@user_id", "value": self.user_id},
            {"name": "@data_type", "value": "session"},
        ]
        return await self.query_items(query, parameters, SessionRecord)

    # Plan Operations
    async def add_plan(self, plan: PlanRecord) -> None:
        """Add a plan to CosmosDB."""
        await self.add_item(plan)

    async def update_plan(self, plan: PlanRecord) -> None:
        """Update a plan in CosmosDB."""
        await self.update_item(plan)

    async def get_plan_by_session(self, session_id: str) -> Optional[PlanRecord]:
        """Retrieve a plan by session_id."""
        query = (
            "SELECT * FROM c WHERE c.session_id=@session_id AND c.data_type=@data_type"
        )
        parameters = [
            {"name": "@session_id", "value": session_id},
            {"name": "@data_type", "value": "plan"},
        ]
        results = await self.query_items(query, parameters, PlanRecord)
        return results[0] if results else None

    async def get_plan_by_plan_id(self, plan_id: str) -> Optional[PlanRecord]:
        """Retrieve a plan by plan_id."""
        query = "SELECT * FROM c WHERE c.id=@plan_id AND c.data_type=@data_type"
        parameters = [
            {"name": "@plan_id", "value": plan_id},
            {"name": "@data_type", "value": "plan"},
        ]
        results = await self.query_items(query, parameters, PlanRecord)
        return results[0] if results else None

    async def get_plan(self, plan_id: str) -> Optional[PlanRecord]:
        """Retrieve a plan by plan_id."""
        return await self.get_plan_by_plan_id(plan_id)

    async def get_all_plans(self) -> List[PlanRecord]:
        """Retrieve all plans for the user."""
        query = "SELECT * FROM c WHERE c.user_id=@user_id AND c.data_type=@data_type"
        parameters = [
            {"name": "@user_id", "value": self.user_id},
            {"name": "@data_type", "value": "plan"},
        ]
        return await self.query_items(query, parameters, PlanRecord)

    # Step Operations
    async def add_step(self, step: StepRecord) -> None:
        """Add a step to CosmosDB."""
        await self.add_item(step)

    async def update_step(self, step: StepRecord) -> None:
        """Update a step in CosmosDB."""
        await self.update_item(step)

    async def get_steps_by_plan(self, plan_id: str) -> List[StepRecord]:
        """Retrieve all steps for a plan."""
        query = "SELECT * FROM c WHERE c.plan_id=@plan_id AND c.data_type=@data_type ORDER BY c.timestamp"
        parameters = [
            {"name": "@plan_id", "value": plan_id},
            {"name": "@data_type", "value": "step"},
        ]
        return await self.query_items(query, parameters, StepRecord)

    async def get_step(self, step_id: str, session_id: str) -> Optional[StepRecord]:
        """Retrieve a step by step_id and session_id."""
        query = "SELECT * FROM c WHERE c.id=@step_id AND c.session_id=@session_id AND c.data_type=@data_type"
        parameters = [
            {"name": "@step_id", "value": step_id},
            {"name": "@session_id", "value": session_id},
            {"name": "@data_type", "value": "step"},
        ]
        results = await self.query_items(query, parameters, StepRecord)
        return results[0] if results else None

    # Message Operations
    async def add_agent_message(self, message: AgentMessageRecord) -> None:
        """Add an agent message to CosmosDB."""
        await self.add_item(message)

    async def add_message(self, message: MessageRecord) -> None:
        """Add a message to CosmosDB."""
        await self.add_item(message)

    async def get_messages(self, session_id: str) -> List[MessageRecord]:
        """Retrieve all messages for a session."""
        query = "SELECT * FROM c WHERE c.session_id=@session_id AND c.data_type=@data_type ORDER BY c.timestamp"
        parameters = [
            {"name": "@session_id", "value": session_id},
            {"name": "@data_type", "value": "message"},
        ]
        return await self.query_items(query, parameters, MessageRecord)

    # Team Configuration Operations
    async def add_team_configuration(self, config: TeamConfigurationRecord) -> None:
        """Add a team configuration to CosmosDB."""
        await self.add_item(config)

    async def get_team_configuration(
        self, config_id: str, user_id: str
    ) -> Optional[TeamConfigurationRecord]:
        """Retrieve a team configuration by ID and user ID."""
        query = "SELECT * FROM c WHERE c.id=@config_id AND c.user_id=@user_id AND c.data_type=@data_type"
        parameters = [
            {"name": "@config_id", "value": config_id},
            {"name": "@user_id", "value": user_id},
            {"name": "@data_type", "value": "team_config"},
        ]
        results = await self.query_items(query, parameters, TeamConfigurationRecord)
        return results[0] if results else None

    async def get_all_team_configurations(
        self, user_id: str
    ) -> List[TeamConfigurationRecord]:
        """Retrieve all team configurations for a user."""
        query = "SELECT * FROM c WHERE c.user_id=@user_id AND c.data_type=@data_type"
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@data_type", "value": "team_config"},
        ]
        return await self.query_items(query, parameters, TeamConfigurationRecord)

    async def delete_team_configuration(self, config_id: str, user_id: str) -> bool:
        """Delete a team configuration by ID and user ID."""
        try:
            # First verify the configuration exists and belongs to the user
            config = await self.get_team_configuration(config_id, user_id)
            if config is None:
                return False

            await self.delete_item(config_id, config.session_id)
            return True
        except Exception as e:
            self.logger.error("Failed to delete team configuration: %s", str(e))
            return False

    # Thread and Agent Operations
    async def add_thread(self, thread: ThreadRecord) -> None:
        """Add a thread record to CosmosDB."""
        await self.add_item(thread)

    async def get_thread_by_session(self, session_id: str) -> Optional[ThreadRecord]:
        """Retrieve a thread by session_id."""
        query = (
            "SELECT * FROM c WHERE c.session_id=@session_id AND c.data_type=@data_type"
        )
        parameters = [
            {"name": "@session_id", "value": session_id},
            {"name": "@data_type", "value": "thread"},
        ]
        results = await self.query_items(query, parameters, ThreadRecord)
        return results[0] if results else None

    async def add_agent_record(self, agent: AgentRecord) -> None:
        """Add an agent record to CosmosDB."""
        await self.add_item(agent)

    # Data Management Operations
    async def get_data_by_type(self, data_type: str) -> List[BaseDataModel]:
        """Retrieve all data of a specific type."""
        query = "SELECT * FROM c WHERE c.data_type=@data_type AND c.user_id=@user_id"
        parameters = [
            {"name": "@data_type", "value": data_type},
            {"name": "@user_id", "value": self.user_id},
        ]

        # Get the appropriate model class
        model_class = self.MODEL_CLASS_MAPPING.get(data_type, BaseDataModel)
        return await self.query_items(query, parameters, model_class)

    async def delete_all_messages(self, data_type: str) -> None:
        """Delete all messages of a specific type."""
        query = "SELECT c.id, c.session_id FROM c WHERE c.data_type=@data_type AND c.user_id=@user_id"
        parameters = [
            {"name": "@data_type", "value": data_type},
            {"name": "@user_id", "value": self.user_id},
        ]

        await self._ensure_initialized()
        items = self.container.query_items(query=query, parameters=parameters)

        async for item in items:
            try:
                await self.delete_item(item["id"], item["session_id"])
            except Exception as e:
                self.logger.warning("Failed to delete item %s: %s", item["id"], str(e))

    async def delete_all_items(self, data_type: str) -> None:
        """Delete all items of a specific type."""
        await self.delete_all_messages(data_type)

    async def get_all_messages(self) -> List[Dict[str, Any]]:
        """Retrieve all messages as dictionaries."""
        query = "SELECT * FROM c WHERE c.data_type=@data_type AND c.user_id=@user_id"
        parameters = [
            {"name": "@data_type", "value": "message"},
            {"name": "@user_id", "value": self.user_id},
        ]

        await self._ensure_initialized()
        items = self.container.query_items(query=query, parameters=parameters)
        results = []
        async for item in items:
            results.append(item)
        return results

    async def get_all_items(self) -> List[Dict[str, Any]]:
        """Retrieve all items as dictionaries."""
        query = "SELECT * FROM c WHERE c.user_id=@user_id"
        parameters = [
            {"name": "@user_id", "value": self.user_id},
        ]

        await self._ensure_initialized()
        items = self.container.query_items(query=query, parameters=parameters)
        results = []
        async for item in items:
            results.append(item)
        return results

    # Collection Management (for compatibility)
    async def create_collection(self, collection_name: str) -> None:
        """Create a collection (no-op for CosmosDB as collections are containers)."""
        # In CosmosDB, collections are containers which are created at initialization
        pass

    async def get_collections(self) -> List[str]:
        """Get all collection names (returns container name)."""
        return [self.container_name] if self.container else []

    async def does_collection_exist(self, collection_name: str) -> bool:
        """Check if a collection exists."""
        return collection_name == self.container_name and self.container is not None

    async def delete_collection(self, collection_name: str) -> None:
        """Delete a collection (deletes all items with matching collection prefix)."""
        query = f"SELECT c.id, c.session_id FROM c WHERE STARTSWITH(c.id, '{collection_name}_')"

        await self._ensure_initialized()
        items = self.container.query_items(query=query)

        async for item in items:
            try:
                await self.delete_item(item["id"], item["session_id"])
            except Exception as e:
                self.logger.warning("Failed to delete item %s: %s", item["id"], str(e))

    async def delete_collection_async(self, collection_name: str) -> None:
        """Delete a collection asynchronously."""
        await self.delete_collection(collection_name)

    # Memory Store Operations (for compatibility with existing code)
    async def upsert_async(self, collection_name: str, record: Dict[str, Any]) -> str:
        """Upsert a record asynchronously."""
        await self._ensure_initialized()

        try:
            # Ensure the record has required fields
            if "id" not in record:
                record["id"] = str(uuid.uuid4())

            # Prefix the ID with collection name for organization
            record["id"] = f"{collection_name}_{record['id']}"

            # Ensure session_id exists for partitioning
            if "session_id" not in record:
                record["session_id"] = self.session_id or "default"

            # Handle datetime serialization
            record = json.loads(json.dumps(record, cls=DateTimeEncoder))

            await self.container.upsert_item(body=record)
            return record["id"]
        except Exception as e:
            self.logger.error("Failed to upsert record: %s", str(e))
            raise

    async def upsert_memory_record(self, collection: str, record: MemoryRecord) -> str:
        """Upsert a memory record."""
        record_dict = {
            "id": f"{collection}_{record.id}",
            "session_id": self.session_id or "default",
            "user_id": self.user_id or "default",
            "data_type": "memory",
            "collection": collection,
            "text": record.text,
            "description": record.description,
            "additional_metadata": record.additional_metadata,
            "external_source_name": record.external_source_name,
            "is_reference": record.is_reference,
            "embedding": record.embedding,
            "key": record.key,
            "timestamp": record.timestamp or datetime.now(timezone.utc),
        }

        return await self.upsert_async(collection, record_dict)

    async def remove_memory_record(self, collection: str, key: str) -> None:
        """Remove a memory record."""
        record_id = f"{collection}_{key}"
        try:
            await self.delete_item(record_id, self.session_id or "default")
        except Exception as e:
            self.logger.warning(
                "Failed to remove memory record %s: %s", record_id, str(e)
            )

    async def remove(self, collection_name: str, key: str) -> None:
        """Remove a record by key."""
        await self.remove_memory_record(collection_name, key)

    async def remove_batch(self, collection_name: str, keys: List[str]) -> None:
        """Remove multiple records by keys."""
        for key in keys:
            try:
                await self.remove(collection_name, key)
            except Exception as e:
                self.logger.warning("Failed to remove key %s: %s", key, str(e))

    # Helper Methods
    async def _ensure_initialized(self) -> None:
        """Ensure the database is initialized."""
        if not self._initialized:
            await self.initialize()

    # Additional compatibility methods
    async def get_steps_for_plan(self, plan_id: str) -> List[StepRecord]:
        """Alias for get_steps_by_plan for compatibility."""
        return await self.get_steps_by_plan(plan_id)

    async def query_items_dict(
        self, collection_name: str, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Query items and return as dictionaries (for compatibility)."""
        query = f"SELECT * FROM c WHERE STARTSWITH(c.id, '{collection_name}_') OFFSET 0 LIMIT @limit"
        parameters = [{"name": "@limit", "value": limit}]

        await self._ensure_initialized()
        items = self.container.query_items(query=query, parameters=parameters)
        results = []
        async for item in items:
            results.append(item)
        return results
