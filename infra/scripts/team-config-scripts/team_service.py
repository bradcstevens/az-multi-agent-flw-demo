from typing import Any, Dict
from datetime import datetime, timezone
from models import TeamConfiguration, TeamAgent, StartingTask
import uuid

def validate_and_parse_team_config(
    json_data: Dict[str, Any], user_id: str, team_id: str
) -> TeamConfiguration:
    """
    Validate and parse team configuration JSON.

    Args:
        json_data: Raw JSON data
        user_id: User ID who uploaded the configuration
        team_id: Team ID for the configuration

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
        # unique_team_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
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
            agent = _validate_and_parse_agent(agent_data)
            agents.append(agent)

        # Parse starting tasks
        starting_tasks = []
        for task_data in json_data["starting_tasks"]:
            task = _validate_and_parse_task(task_data)
            starting_tasks.append(task)

        # Create team configuration
        team_config = TeamConfiguration(
            session_id=session_id,
            team_id=team_id,  # Use provided team_id
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

        print(f"Successfully validated team configuration: {team_config.team_id} (ID: {team_config.id})")
        return team_config

    except Exception as e:
        print(f"Error validating team configuration: {str(e)}")
        raise ValueError(f"Invalid team configuration: {str(e)}") from e

def _validate_and_parse_agent(agent_data: Dict[str, Any]) -> TeamAgent:
    """Validate and parse a single agent."""
    required_fields = ["input_key", "type", "name", "icon", "deployment_name"]
    for field in required_fields:
        if field not in agent_data:
            raise ValueError(f"Agent missing required field: {field}")

    return TeamAgent(
        input_key=agent_data["input_key"],
        type=agent_data["type"],
        name=agent_data["name"],
        deployment_name=agent_data.get("deployment_name", ""),
        icon=agent_data["icon"],
        system_message=agent_data.get("system_message", ""),
        description=agent_data.get("description", ""),
        use_rag=agent_data.get("use_rag", False),
        use_mcp=agent_data.get("use_mcp", False),
        use_bing=agent_data.get("use_bing", False),
        use_reasoning=agent_data.get("use_reasoning", False),
        index_name=agent_data.get("index_name", ""),
        coding_tools=agent_data.get("coding_tools", False),
    )

def _validate_and_parse_task(task_data: Dict[str, Any]) -> StartingTask:
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
