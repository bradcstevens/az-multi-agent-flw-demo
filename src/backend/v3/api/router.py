import asyncio
import contextvars
import json
import logging
import uuid
from typing import Optional

import v3.models.messages as messages
from auth.auth_utils import get_authenticated_user_details
from common.database.database_factory import DatabaseFactory
from common.models.messages_kernel import (GeneratePlanRequest, InputTask,
                                           Plan, PlanStatus,
                                           TeamSelectionRequest, UserCurrentTeam)
from common.utils.event_utils import track_event_if_configured
from common.utils.utils_kernel import rai_success, rai_validate_team_config
from fastapi import (APIRouter, BackgroundTasks, Depends, FastAPI, File, Query,
                     HTTPException, Request, UploadFile, WebSocket,
                     WebSocketDisconnect)
from kernel_agents.agent_factory import AgentFactory
from semantic_kernel.agents.runtime import InProcessRuntime
from v3.common.services.team_service import TeamService
from v3.config.settings import (connection_config, current_user_id,
                                orchestration_config, team_config)
from v3.orchestration.orchestration_manager import OrchestrationManager

router = APIRouter()
logger = logging.getLogger(__name__)

app_v3 = APIRouter(
    prefix="/api/v3",
    responses={404: {"description": "Not found"}},
)

@app_v3.websocket("/socket/{process_id}")
async def start_comms(websocket: WebSocket, process_id: str):
    """ Web-Socket endpoint for real-time process status updates. """
        
    # Always accept the WebSocket connection first
    await websocket.accept()

    user_id = None
    try:
        # WebSocket headers are different, try to get user info
        headers = dict(websocket.headers)
        authenticated_user = get_authenticated_user_details(request_headers=headers)
        user_id = authenticated_user.get("user_principal_id")
        if not user_id:
            user_id = "00000000-0000-0000-0000-000000000000"
    except Exception as e:
        logging.warning(f"Could not extract user from WebSocket headers: {e}")
        user_id = "00000000-0000-0000-0000-000000000000"

    current_user_id.set(user_id)

    # Add to the connection manager for backend updates
    connection_config.add_connection(process_id=process_id, connection=websocket, user_id=user_id)
    track_event_if_configured("WebSocketConnectionAccepted", {"process_id": process_id, "user_id": user_id})

    # Keep the connection open - FastAPI will close the connection if this returns
    try:
        # Keep the connection open - FastAPI will close the connection if this returns
        while True:
            # no expectation that we will receive anything from the client but this keeps
            # the connection open and does not take cpu cycle
            try:
                message = await websocket.receive_text()
                logging.debug(f"Received WebSocket message from {user_id}: {message}")
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                track_event_if_configured("WebSocketDisconnect", {"process_id": process_id, "user_id": user_id})
                logging.info(f"Client disconnected from batch {process_id}")
                break
    except Exception as e:
        # Fixed logging syntax - removed the error= parameter
        logging.error(f"Error in WebSocket connection: {str(e)}")
    finally:
        # Always clean up the connection
        await connection_config.close_connection(user_id)

@app_v3.get("/init_team")
async def init_team(
    request: Request,
):
    """ Initialize the user's current team of agents """

    # Need to store this user state in cosmos db, retrieve it here, and initialize the team
    # current in-memory store is in team_config from settings.py
    # For now I will set the initial install team ids as 00000000-0000-0000-0000-000000000001 (HR),
    # 00000000-0000-0000-0000-000000000002 (Marketing), and 00000000-0000-0000-0000-000000000003 (Retail),
    # and use this value to initialize to HR each time.
    init_team_id = "00000000-0000-0000-0000-000000000001"

    try:
      authenticated_user = get_authenticated_user_details(request_headers=request.headers)
      user_id = authenticated_user["user_principal_id"]
      if not user_id:
          track_event_if_configured(
              "UserIdNotFound", {"status_code": 400, "detail": "no user"}
          )
          raise HTTPException(status_code=400, detail="no user")
      
      # Initialize memory store and service
      memory_store = await DatabaseFactory.get_database(user_id=user_id)
      team_service = TeamService(memory_store)
      user_current_team = await memory_store.get_current_team(user_id=user_id)
      if not user_current_team:
          await team_service.handle_team_selection(user_id=user_id, team_id=init_team_id)
      else:
          init_team_id = user_current_team.team_id
      # Verify the team exists and user has access to it
      team_configuration = await team_service.get_team_configuration(init_team_id, user_id)
      if team_configuration is None:
          raise HTTPException(
              status_code=404, 
              detail=f"Team configuration '{init_team_id}' not found or access denied"
          )
      
      # Set as current team in memory
      team_config.set_current_team(user_id=user_id, team_configuration=team_configuration)
      
      # Initialize agent team for this user session
      await OrchestrationManager.get_current_or_new_orchestration(user_id=user_id, team_config=team_configuration)

      return {
          "status": "Request started successfully",
          "team_id": init_team_id,
          "team": team_configuration
      }

    except Exception as e:
        track_event_if_configured(
            "InitTeamFailed",
            {
                "error": str(e),
            },
        )
        raise HTTPException(status_code=400, detail=f"Error starting request: {e}") from e

@app_v3.post("/process_request")
async def process_request(background_tasks: BackgroundTasks, input_task: InputTask, request: Request):
    """
    Create a new plan without full processing.

    ---
    tags:
      - Plans
    parameters:
      - name: user_principal_id
        in: header
        type: string
        required: true
        description: User ID extracted from the authentication header
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            session_id:
              type: string
              description: Session ID for the plan
            description:
              type: string
              description: The task description to validate and create plan for
    responses:
      200:
        description: Plan created successfully
        schema:
          type: object
          properties:
            plan_id:
              type: string
              description: The ID of the newly created plan
            status:
              type: string
              description: Success message
            session_id:
              type: string
              description: Session ID associated with the plan
      400:
        description: RAI check failed or invalid input
        schema:
          type: object
          properties:
            detail:
              type: string
              description: Error message
    """


    if not await rai_success(input_task.description, False):
        track_event_if_configured(
            "RAI failed",
            {
                "status": "Plan not created - RAI check failed",
                "description": input_task.description,
                "session_id": input_task.session_id,
            },
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error_type": "RAI_VALIDATION_FAILED",
                "message": "Content Safety Check Failed",
                "description": "Your request contains content that doesn't meet our safety guidelines. Please modify your request to ensure it's appropriate and try again.",
                "suggestions": [
                    "Remove any potentially harmful, inappropriate, or unsafe content",
                    "Use more professional and constructive language",
                    "Focus on legitimate business or educational objectives",
                    "Ensure your request complies with content policies",
                ],
                "user_action": "Please revise your request and try again",
            },
        )

    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    if not user_id:
        track_event_if_configured(
            "UserIdNotFound", {"status_code": 400, "detail": "no user"}
        )
        raise HTTPException(status_code=400, detail="no user")

    # if not input_task.team_id:
    #     track_event_if_configured(
    #         "TeamIDNofound", {"status_code": 400, "detail": "no team id"}
    #     )
    #     raise HTTPException(status_code=400, detail="no team id")

    if not input_task.session_id:
        input_task.session_id = str(uuid.uuid4())
    try:
        plan_id = str(uuid.uuid4())
        # Initialize memory store and service
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        plan = Plan(
            id=plan_id,
            plan_id=plan_id,
            user_id=user_id,
            session_id=input_task.session_id,
            team_id=None,  #TODO add current_team_id
            initial_goal=input_task.description,
            overall_status=PlanStatus.in_progress,
        )
        await memory_store.add_plan(plan)


        track_event_if_configured(
            "PlanCreated",
            {
                "status": "success",
                "plan_id": plan.plan_id,
                "session_id": input_task.session_id,
                "user_id": user_id,
                "team_id": "", #TODO add current_team_id
                "description": input_task.description,
            },
        )
    except Exception as e:
        print(f"Error creating plan: {e}")
        track_event_if_configured(
            "PlanCreationFailed",
            {
                "status": "error",
                "description": input_task.description,
                "session_id": input_task.session_id,
                "user_id": user_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to create plan")

    try:
        current_user_id.set(user_id)  # Set context
        current_context = contextvars.copy_context()  # Capture context
        # background_tasks.add_task(
        #     lambda: current_context.run(lambda:OrchestrationManager().run_orchestration, user_id, input_task)
        # )

        async def run_with_context():
            return await current_context.run(OrchestrationManager().run_orchestration, user_id, input_task)

        background_tasks.add_task(run_with_context)

        return {
            "status": "Request started successfully",
            "session_id": input_task.session_id,
            "plan_id": plan_id,
        }

    except Exception as e:
        track_event_if_configured(
            "RequestStartFailed",
            {
                "session_id": input_task.session_id,
                "description": input_task.description,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=400, detail=f"Error starting request: {e}") from e

@app_v3.post("/plan_approval")
async def plan_approval(human_feedback: messages.PlanApprovalResponse, request: Request):
    """ Endpoint to receive plan approval or rejection from the user. """
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )
    # Set the approval in the orchestration config
    if user_id and human_feedback.plan_dot_id:
        if orchestration_config and human_feedback.plan_dot_id in orchestration_config.approvals:
            orchestration_config.approvals[human_feedback.plan_dot_id] = human_feedback.approved
            orchestration_config.plans[human_feedback.plan_dot_id]["plan_id"] = human_feedback.plan_id
            print("Plan approval received:", human_feedback)
            print("Updated orchestration config:", orchestration_config.plans[human_feedback.plan_dot_id])
            track_event_if_configured(
                "PlanApprovalReceived",
                {
                    "plan_id": human_feedback.plan_id,
                    "plan_dot_id": human_feedback.plan_dot_id,
                    "approved": human_feedback.approved,
                    "user_id": user_id,
                    "feedback": human_feedback.feedback
                },
            )
            return {"status": "approval recorded"}
        else:
            logging.warning(f"No orchestration or plan found for plan_id: {human_feedback.plan_dot_id}")
            raise HTTPException(status_code=404, detail="No active plan found for approval")

@app_v3.post("/user_clarification")
async def user_clarification(human_feedback: messages.UserClarificationResponse, request: Request):
    """ Endpoint to receive plan approval or rejection from the user. """
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )
    # Set the approval in the orchestration config
    if user_id and human_feedback.request_id:
        if orchestration_config and human_feedback.request_id in orchestration_config.clarifications:
            orchestration_config.clarifications[human_feedback.request_id] = human_feedback.answer
            track_event_if_configured(
                "PlanApprovalReceived",
                {
                    "request_id": human_feedback.request_id,
                    "answer": human_feedback.answer,
                    "user_id": user_id,
                },
            )
            return {"status": "clarification recorded"}
        else:
            logging.warning(f"No orchestration or plan found for request_id: {human_feedback.request_id}")
            raise HTTPException(status_code=404, detail="No active plan found for clarification")


@app_v3.post("/upload_team_config")
async def upload_team_config(request: Request, file: UploadFile = File(...),     team_id: Optional[str] = Query(None),):
    """
    Upload and save a team configuration JSON file.

    ---
    tags:
      - Team Configuration
    parameters:
      - name: user_principal_id
        in: header
        type: string
        required: true
        description: User ID extracted from the authentication header
      - name: file
        in: formData
        type: file
        required: true
        description: JSON file containing team configuration
    responses:
      200:
        description: Team configuration uploaded successfully
      400:
        description: Invalid request or file format
      401:
        description: Missing or invalid user information
      500:
        description: Internal server error
    """
    # Validate user authentication
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )

    # Validate file is provided and is JSON
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a JSON file")

    try:
        # Read and parse JSON content
        content = await file.read()
        try:
            json_data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid JSON format: {str(e)}"
            )

        # Validate content with RAI before processing
        rai_valid, rai_error = await rai_validate_team_config(json_data)
        if not rai_valid:
            track_event_if_configured(
                "Team configuration RAI validation failed",
                {
                    "status": "failed",
                    "user_id": user_id,
                    "filename": file.filename,
                    "reason": rai_error,
                },
            )
            raise HTTPException(status_code=400, detail=rai_error)

        track_event_if_configured(
            "Team configuration RAI validation passed",
            {"status": "passed", "user_id": user_id, "filename": file.filename},
        )

        # Initialize memory store and service
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        team_service = TeamService(memory_store)

        # Validate model deployments
        models_valid, missing_models = await team_service.validate_team_models(
            json_data
        )
        if not models_valid:
            error_message = (
                f"The following required models are not deployed in your Azure AI project: {', '.join(missing_models)}. "
                f"Please deploy these models in Azure AI Foundry before uploading this team configuration."
            )
            track_event_if_configured(
                "Team configuration model validation failed",
                {
                    "status": "failed",
                    "user_id": user_id,
                    "filename": file.filename,
                    "missing_models": missing_models,
                },
            )
            raise HTTPException(status_code=400, detail=error_message)

        track_event_if_configured(
            "Team configuration model validation passed",
            {"status": "passed", "user_id": user_id, "filename": file.filename},
        )

        # Validate search indexes
        search_valid, search_errors = await team_service.validate_team_search_indexes(
            json_data
        )
        if not search_valid:
            error_message = (
                f"Search index validation failed:\n\n{chr(10).join([f'• {error}' for error in search_errors])}\n\n"
                f"Please ensure all referenced search indexes exist in your Azure AI Search service."
            )
            track_event_if_configured(
                "Team configuration search validation failed",
                {
                    "status": "failed",
                    "user_id": user_id,
                    "filename": file.filename,
                    "search_errors": search_errors,
                },
            )
            raise HTTPException(status_code=400, detail=error_message)

        track_event_if_configured(
            "Team configuration search validation passed",
            {"status": "passed", "user_id": user_id, "filename": file.filename},
        )

        # Validate and parse the team configuration
        try:
            team_config = await team_service.validate_and_parse_team_config(
                json_data, user_id
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Save the configuration
        try:
            print("Saving team configuration...", team_id)
            if team_id:
                team_config.team_id = team_id
                team_config.id = team_id  # Ensure id is also set for updates
            team_id = await team_service.save_team_configuration(team_config)
        except ValueError as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to save configuration: {str(e)}"
            )

        track_event_if_configured(
            "Team configuration uploaded",
            {
                "status": "success",
                "team_id": team_id,
                "team_id": team_config.team_id,
                "user_id": user_id,
                "agents_count": len(team_config.agents),
                "tasks_count": len(team_config.starting_tasks),
            },
        )

        return {
            "status": "success",
            "team_id": team_id,
            "name": team_config.name,
            "message": "Team configuration uploaded and saved successfully",
            "team": team_config.model_dump()  # Return the full team configuration
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error uploading team configuration: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")


@app_v3.get("/team_configs")
async def get_team_configs(request: Request):
    """
    Retrieve all team configurations for the current user.

    ---
    tags:
      - Team Configuration
    parameters:
      - name: user_principal_id
        in: header
        type: string
        required: true
        description: User ID extracted from the authentication header
    responses:
      200:
        description: List of team configurations for the user
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: string
              team_id:
                type: string
              name:
                type: string
              status:
                type: string
              created:
                type: string
              created_by:
                type: string
              description:
                type: string
              logo:
                type: string
              plan:
                type: string
              agents:
                type: array
              starting_tasks:
                type: array
      401:
        description: Missing or invalid user information
    """
    # Validate user authentication
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )

    try:
        # Initialize memory store and service
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        team_service = TeamService(memory_store)

        # Retrieve all team configurations
        team_configs = await team_service.get_all_team_configurations(user_id)

        # Convert to dictionaries for response
        configs_dict = [config.model_dump() for config in team_configs]

        return configs_dict

    except Exception as e:
        logging.error(f"Error retrieving team configurations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")


@app_v3.get("/team_configs/{team_id}")
async def get_team_config_by_id(team_id: str, request: Request):
    """
    Retrieve a specific team configuration by ID.

    ---
    tags:
      - Team Configuration
    parameters:
      - name: team_id
        in: path
        type: string
        required: true
        description: The ID of the team configuration to retrieve
      - name: user_principal_id
        in: header
        type: string
        required: true
        description: User ID extracted from the authentication header
    responses:
      200:
        description: Team configuration details
        schema:
          type: object
          properties:
            id:
              type: string
            team_id:
              type: string
            name:
              type: string
            status:
              type: string
            created:
              type: string
            created_by:
              type: string
            description:
              type: string
            logo:
              type: string
            plan:
              type: string
            agents:
              type: array
            starting_tasks:
              type: array
      401:
        description: Missing or invalid user information
      404:
        description: Team configuration not found
    """
    # Validate user authentication
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )

    try:
        # Initialize memory store and service
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        team_service = TeamService(memory_store)

        # Retrieve the specific team configuration
        team_config = await team_service.get_team_configuration(team_id, user_id)

        if team_config is None:
            raise HTTPException(status_code=404, detail="Team configuration not found")

        # Convert to dictionary for response
        return team_config.model_dump()

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logging.error(f"Error retrieving team configuration: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")


@app_v3.delete("/team_configs/{team_id}")
async def delete_team_config(team_id: str, request: Request):
    """
    Delete a team configuration by ID.

    ---
    tags:
      - Team Configuration
    parameters:
      - name: team_id
        in: path
        type: string
        required: true
        description: The ID of the team configuration to delete
      - name: user_principal_id
        in: header
        type: string
        required: true
        description: User ID extracted from the authentication header
    responses:
      200:
        description: Team configuration deleted successfully
        schema:
          type: object
          properties:
            status:
              type: string
            message:
              type: string
            team_id:
              type: string
      401:
        description: Missing or invalid user information
      404:
        description: Team configuration not found
    """
    # Validate user authentication
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )

    try:
        # To do: Check if the team is the users current team, or if it is 
        # used in any active sessions/plans.  Refuse request if so.

        # Initialize memory store and service
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        team_service = TeamService(memory_store)

        # Delete the team configuration
        deleted = await team_service.delete_team_configuration(team_id, user_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Team configuration not found")

        # Track the event
        track_event_if_configured(
            "Team configuration deleted",
            {"status": "success", "team_id": team_id, "user_id": user_id},
        )

        return {
            "status": "success",
            "message": "Team configuration deleted successfully",
            "team_id": team_id,
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logging.error(f"Error deleting team configuration: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")


@app_v3.get("/model_deployments")
async def get_model_deployments(request: Request):
    """
    Get information about available model deployments for debugging/validation.

    ---
    tags:
      - Model Validation
    responses:
      200:
        description: List of available model deployments
      401:
        description: Missing or invalid user information
    """
    # Validate user authentication
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )

    try:
        team_service = TeamService()
        deployments = [] #await team_service.extract_models_from_agent()
        summary = await team_service.get_deployment_status_summary()
        return {"deployments": deployments, "summary": summary}
    except Exception as e:
        logging.error(f"Error retrieving model deployments: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")


@app_v3.post("/select_team")
async def select_team(selection: TeamSelectionRequest, request: Request):
    """
    Select the current team for the user session.
    """
    # Validate user authentication
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )

    if not selection.team_id:
        raise HTTPException(status_code=400, detail="Team ID is required")

    try:
        # Initialize memory store and service
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        team_service = TeamService(memory_store)

        # Verify the team exists and user has access to it
        team_configuration = await team_service.get_team_configuration(selection.team_id, user_id)
        if team_config is None:
            raise HTTPException(
                status_code=404, 
                detail=f"Team configuration '{selection.team_id}' not found or access denied"
            )
        set_team = await team_service.handle_team_selection(user_id=user_id, team_id=selection.team_id)
        if not set_team:
            track_event_if_configured(
            "Team selected",
            {
                "status": "failed",
                "team_id": selection.team_id,
                "team_name": team_configuration.name,
                "user_id": user_id
            },
        )
            raise HTTPException(
                status_code=404,
                detail=f"Team configuration '{selection.team_id}' failed to set"
            )

        # save to in-memory config for current user
        team_config.set_current_team(user_id=user_id, team_configuration=team_configuration)
        
        # Track the team selection event
        track_event_if_configured(
            "Team selected",
            {
                "status": "success",
                "team_id": selection.team_id,
                "team_name": team_configuration.name,
                "user_id": user_id
            },
        )

        return {
            "status": "success",
            "message": f"Team '{team_configuration.name}' selected successfully",
            "team_id": selection.team_id,
            "team_name": team_configuration.name,
            "agents_count": len(team_configuration.agents),
            "team_description": team_configuration.description,
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logging.error(f"Error selecting team: {str(e)}")
        track_event_if_configured(
            "Team selection error",
            {
                "status": "error",
                "team_id": selection.team_id,
                "user_id": user_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Internal server error occurred")


@app_v3.get("/search_indexes")
async def get_search_indexes(request: Request):
    """
    Get information about available search indexes for debugging/validation.

    ---
    tags:
      - Search Validation
    responses:
      200:
        description: List of available search indexes
      401:
        description: Missing or invalid user information
    """
    # Validate user authentication
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )

    try:
        team_service = TeamService()
        summary = await team_service.get_search_index_summary()
        return {"search_summary": summary}
    except Exception as e:
        logging.error(f"Error retrieving search indexes: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")