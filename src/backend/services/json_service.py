import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from models.messages_kernel import TeamConfiguration, TeamAgent, StartingTask
from context.cosmos_memory_kernel import CosmosMemoryContext


class JsonService:
    """Service for handling JSON team configuration operations."""

    def __init__(self, memory_context: CosmosMemoryContext):
        """Initialize with memory context."""
        self.memory_context = memory_context
        self.logger = logging.getLogger(__name__)

    async def validate_and_parse_team_config(
        self, json_data: Dict[str, Any], user_id: str
    ) -> TeamConfiguration:
        """
        Validate and parse team configuration JSON.

        Args:
            json_data: Raw JSON data
            user_id: User ID who uploaded the configuration

        Returns:
            TeamConfiguration object

        Raises:
            ValueError: If JSON structure is invalid
        """
        try:
            # Validate required top-level fields (id and team_id will be generated)
            required_fields = [
                "name",
                "status",
            ]
            for field in required_fields:
                if field not in json_data:
                    raise ValueError(f"Missing required field: {field}")

            # Generate unique IDs and timestamps
            unique_team_id = str(uuid.uuid4())
            current_timestamp = datetime.now(timezone.utc).isoformat()

            # Validate agents array exists and is not empty
            if "agents" not in json_data or not isinstance(json_data["agents"], list):
                raise ValueError(
                    "Missing or invalid 'agents' field - must be a non-empty array"
                )

            if len(json_data["agents"]) == 0:
                raise ValueError("Agents array cannot be empty")

            # Validate starting_tasks array exists and is not empty
            if "starting_tasks" not in json_data or not isinstance(
                json_data["starting_tasks"], list
            ):
                raise ValueError(
                    "Missing or invalid 'starting_tasks' field - must be a non-empty array"
                )

            if len(json_data["starting_tasks"]) == 0:
                raise ValueError("Starting tasks array cannot be empty")

            # Parse agents
            agents = []
            for agent_data in json_data["agents"]:
                agent = self._validate_and_parse_agent(agent_data)
                agents.append(agent)

            # Parse starting tasks
            starting_tasks = []
            for task_data in json_data["starting_tasks"]:
                task = self._validate_and_parse_task(task_data)
                starting_tasks.append(task)

            # Create team configuration
            team_config = TeamConfiguration(
                id=unique_team_id,  # Use generated GUID
                team_id=unique_team_id,  # Use generated GUID
                name=json_data["name"],
                status=json_data["status"],
                created=current_timestamp,  # Use generated timestamp
                created_by=user_id,  # Use user_id who uploaded the config
                agents=agents,
                description=json_data.get("description", ""),
                logo=json_data.get("logo", ""),
                plan=json_data.get("plan", ""),
                starting_tasks=starting_tasks,
                user_id=user_id,
            )

            self.logger.info(
                "Successfully validated team configuration: %s (ID: %s)",
                team_config.team_id,
                team_config.id,
            )
            return team_config

        except Exception as e:
            self.logger.error("Error validating team configuration: %s", str(e))
            raise ValueError(f"Invalid team configuration: {str(e)}") from e

    def _validate_and_parse_agent(self, agent_data: Dict[str, Any]) -> TeamAgent:
        """Validate and parse a single agent."""
        required_fields = ["input_key", "type", "name", "icon"]
        for field in required_fields:
            if field not in agent_data:
                raise ValueError(f"Agent missing required field: {field}")

        return TeamAgent(
            input_key=agent_data["input_key"],
            type=agent_data["type"],
            name=agent_data["name"],
            system_message=agent_data.get("system_message", ""),
            description=agent_data.get("description", ""),
            icon=agent_data["icon"],
            index_name=agent_data.get("index_name", ""),
        )

    def _validate_and_parse_task(self, task_data: Dict[str, Any]) -> StartingTask:
        """Validate and parse a single starting task."""
        required_fields = ["id", "name", "prompt", "created", "creator", "logo"]
        for field in required_fields:
            if field not in task_data:
                raise ValueError(f"Starting task missing required field: {field}")

        return StartingTask(
            id=task_data["id"],
            name=task_data["name"],
            prompt=task_data["prompt"],
            created=task_data["created"],
            creator=task_data["creator"],
            logo=task_data["logo"],
        )

    async def save_team_configuration(self, team_config: TeamConfiguration) -> str:
        """
        Save team configuration to the database.

        Args:
            team_config: TeamConfiguration object to save

        Returns:
            The unique ID of the saved configuration
        """
        try:
            # Use the specific add_team method from cosmos memory context
            await self.memory_context.add_team(team_config)

            self.logger.info(
                "Successfully saved team configuration with ID: %s", team_config.id
            )
            return team_config.id

        except Exception as e:
            self.logger.error("Error saving team configuration: %s", str(e))
            raise ValueError(f"Failed to save team configuration: {str(e)}") from e

    async def get_team_configuration(
        self, config_id: str, user_id: str
    ) -> Optional[TeamConfiguration]:
        """
        Retrieve a team configuration by ID.

        Args:
            config_id: Configuration ID to retrieve
            user_id: User ID for access control

        Returns:
            TeamConfiguration object or None if not found
        """
        try:
            # Get the specific configuration using the team-specific method
            team_config = await self.memory_context.get_team_by_id(config_id)

            if team_config is None:
                return None

            # Verify the configuration belongs to the user
            if team_config.user_id != user_id:
                self.logger.warning(
                    "Access denied: config %s does not belong to user %s",
                    config_id,
                    user_id,
                )
                return None

            return team_config

        except (KeyError, TypeError, ValueError) as e:
            self.logger.error("Error retrieving team configuration: %s", str(e))
            return None

    async def get_all_team_configurations(
        self, user_id: str
    ) -> List[TeamConfiguration]:
        """
        Retrieve all team configurations for a user.

        Args:
            user_id: User ID to retrieve configurations for

        Returns:
            List of TeamConfiguration objects
        """
        try:
            # Use the specific get_all_teams_by_user method
            team_configs = await self.memory_context.get_all_teams_by_user(user_id)
            return team_configs

        except (KeyError, TypeError, ValueError) as e:
            self.logger.error("Error retrieving team configurations: %s", str(e))
            return []

    async def delete_team_configuration(self, config_id: str, user_id: str) -> bool:
        """
        Delete a team configuration by ID.

        Args:
            config_id: Configuration ID to delete
            user_id: User ID for access control

        Returns:
            True if deleted successfully, False if not found
        """
        try:
            # First, verify the configuration exists and belongs to the user
            team_config = await self.memory_context.get_team_by_id(config_id)

            if team_config is None:
                self.logger.warning(
                    "Team configuration not found for deletion: %s", config_id
                )
                return False

            # Verify the configuration belongs to the user
            if team_config.user_id != user_id:
                self.logger.warning(
                    "Access denied: cannot delete config %s for user %s",
                    config_id,
                    user_id,
                )
                return False

            # Delete the configuration using the specific delete_team_by_id method
            success = await self.memory_context.delete_team_by_id(config_id)

            if success:
                self.logger.info(
                    "Successfully deleted team configuration: %s", config_id
                )

            return success

        except (KeyError, TypeError, ValueError) as e:
            self.logger.error("Error deleting team configuration: %s", str(e))
            return False
