import asyncio
import json
import logging
import uuid
from typing import Optional

from opentelemetry import trace

import models.messages as messages
from models.messages import WebsocketMessageType
from auth.auth_utils import get_authenticated_user_details
from common.config.app_config import config
from common.database.database_factory import DatabaseFactory
from common.models.messages import (InputTask, Plan, PlanStatus,
                                    SessionStatePatch, TeamSelectionRequest)
from common.utils.event_utils import track_event_if_configured
from common.utils.team_utils import (find_first_available_team, rai_success,
                                     rai_validate_team_config)
from fastapi import (APIRouter, BackgroundTasks, File, HTTPException, Query,
                     Request, UploadFile, WebSocket, WebSocketDisconnect)
from associate.answer import personal_answer_detail
from associate.records import DEMO_ASSOCIATE, lookup_associate
from chat.deletion import STILL_RUNNING_DETAIL, DeletionOutcome
from guardrail.gate import identity_boundary_gate
from guardrail.identity import ANONYMOUS
from guardrail.refusal import policy_block_detail
from lane.router import select_lane
from orchestration.connection_config import (connection_config,
                                             orchestration_config, team_config)
from orchestration.orchestration_manager import OrchestrationManager
from services.plan_service import PlanService
from services.team_service import TeamService
from session.store import SessionStateStore
from sop.direct_line import DIRECT_LINE_FAILURE, DirectLineClient, SopAnswer
from sop.provenance import SOP_PLATFORM, SOP_SOURCE
from sop.rehearsal import (end_rehearsal_turn, forget_rehearsal,
                           note_rehearsal,
                           rehearsal_stands_for_current_turn)
from transparency.alert import REHEARSED_ALERT, REHEARSED_ALERTS  # noqa: F401  (the rehearsed copy, asserted on in tests)
from transparency.alert import presenter_alert as build_presenter_alert
from transparency.source import source_used
from troubleshooting.steps import parse_attempted_steps
from troubleshooting.store import TroubleshootingStore
from troubleshooting.turn import note_turn, sole_turn
from escalation.payloads import TicketRaised
from escalation.store import TicketStatus, TicketStore, render_ticket

router = APIRouter()
logger = logging.getLogger(__name__)

app_router = APIRouter(
    prefix="/api/v4",
    responses={404: {"description": "Not found"}},
)


@app_router.websocket("/socket/{process_id}")
async def start_comms(
    websocket: WebSocket, process_id: str, user_id: str = Query(None)
):
    """Web-Socket endpoint for real-time process status updates."""

    # Always accept the WebSocket connection first
    await websocket.accept()

    user_id = user_id or "00000000-0000-0000-0000-000000000000"

    # Manually create a span for WebSocket since excluded_urls suppresses auto-instrumentation.
    # Without this, all track_event_if_configured calls inside WebSocket would get operation_Id = 0.
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(
        "WebSocket_Connection",
        attributes={"process_id": process_id, "user_id": user_id},
    ) as ws_span:
        # Resolve session_id from plan for telemetry
        session_id = None
        try:
            memory_store = await DatabaseFactory.get_database(user_id=user_id)
            plan = await memory_store.get_plan_by_plan_id(plan_id=process_id)
            if plan:
                session_id = getattr(plan, 'session_id', None)
                if session_id:
                    ws_span.set_attribute("session_id", session_id)
        except Exception as e:
            logging.warning(f"[websocket] Failed to resolve session_id: {e}")

        # Add to the connection manager for backend updates
        connection_config.add_connection(
            process_id=process_id, connection=websocket, user_id=user_id
        )
        ws_props = {"process_id": process_id, "user_id": user_id}
        if session_id:
            ws_props["session_id"] = session_id
        track_event_if_configured("WebSocket_Connected", ws_props)

        # Keepalive: reasoning models (gpt-5.4/-mini) stream nothing during long
        # thinking gaps; a periodic frame stops the ingress proxy idle-timing-out
        # and dropping the socket (which would lose the final-result message).
        HEARTBEAT_INTERVAL_SECONDS = 20

        async def _heartbeat() -> None:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                try:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": WebsocketMessageType.PING,
                                "data": {"ts": asyncio.get_event_loop().time()},
                            },
                            default=str,
                        )
                    )
                except Exception as hb_exc:
                    logging.debug(
                        "Heartbeat stopped for user %s, process %s: %s",
                        user_id, process_id, hb_exc,
                    )
                    break

        heartbeat_task = asyncio.create_task(_heartbeat())

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
                    # Ignore timeouts to keep the WebSocket connection open, but avoid a tight loop.
                    logging.debug(
                        f"WebSocket receive timeout for user {user_id}, process {process_id}"
                    )
                    await asyncio.sleep(0.1)
                except WebSocketDisconnect:
                    dc_props = {"process_id": process_id, "user_id": user_id}
                    if session_id:
                        dc_props["session_id"] = session_id
                    track_event_if_configured("WebSocket_Disconnected", dc_props)
                    logging.info(f"Client disconnected from batch {process_id}")
                    break
        except Exception as e:
            logging.error(f"Error in WebSocket connection: {str(e)}")
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                # Expected: we just cancelled the heartbeat task above.
                pass
            except Exception as e:
                logging.debug(
                    f"Unexpected error awaiting cancelled heartbeat task for user {user_id}: {e}"
                )
            await connection_config.close_connection(
                process_id=process_id, connection=websocket
            )


@app_router.get("/init_team")
async def init_team(
    request: Request,
    team_switched: bool = Query(False),
):  # add team_switched: bool parameter
    """Initialize the user's current team of agents"""

    # Get first available team from 4 to 1 (RFP -> Retail -> Marketing -> HR)
    # Falls back to HR if no teams are available.
    logger.debug("Init team called, team_switched=%s", team_switched)
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]
        if not user_id:
            track_event_if_configured(
                "Error_User_Not_Found", {"status_code": 400, "detail": "no user"}
            )
            raise HTTPException(status_code=400, detail="no user")

        # Initialize memory store and service
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        team_service = TeamService(memory_store)

        init_team_id = await find_first_available_team(team_service, user_id)

        # Get current team if user has one
        user_current_team = await memory_store.get_current_team(user_id=user_id)

        # If no teams available and no current team, return empty state to allow custom team upload
        if not init_team_id and not user_current_team:
            logger.info("No teams found in database. System ready for custom team upload.")
            return {
                "status": "No teams configured. Please upload a team configuration to get started.",
                "team_id": None,
                "team": None,
                "requires_team_upload": True,
            }

        # Use current team if available, otherwise use found team
        if user_current_team:
            init_team_id = user_current_team.team_id
            logger.debug("Using user's current team: %s", init_team_id)
        elif init_team_id:
            logger.debug("Using first available team: %s", init_team_id)
            user_current_team = await team_service.handle_team_selection(
                user_id=user_id, team_id=init_team_id
            )
            if user_current_team:
                init_team_id = user_current_team.team_id

        # Verify the team exists and user has access to it
        team_configuration = await team_service.get_team_configuration(
            init_team_id, user_id
        )
        if team_configuration is None:
            # If team doesn't exist, clear current team and return empty state
            await memory_store.delete_current_team(user_id)
            logger.warning("Team configuration '%s' not found. Cleared current team.", init_team_id)
            return {
                "status": "Current team configuration not found. Please select or upload a team configuration.",
                "team_id": None,
                "team": None,
                "requires_team_upload": True,
            }

        # Set as current team in memory
        team_config.set_current_team(
            user_id=user_id, team_configuration=team_configuration
        )

        # Initialize agent team for this user session
        await OrchestrationManager.get_current_or_new_orchestration(
            user_id=user_id,
            team_config=team_configuration,
            team_switched=team_switched,
            team_service=team_service,
        )

        return {
            "status": "Request started successfully",
            "team_id": init_team_id,
            "team": team_configuration,
        }

    except Exception as e:
        track_event_if_configured(
            "Error_Init_Team_Failed",
            {
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=400, detail=f"Error starting request: {e}"
        ) from e


@app_router.post("/process_request")
async def process_request(
    background_tasks: BackgroundTasks, input_task: InputTask, request: Request
):
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
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        event_props = {"status_code": 400, "detail": "no user"}
        if input_task and hasattr(input_task, 'session_id') and input_task.session_id:
            event_props["session_id"] = input_task.session_id
        track_event_if_configured("Error_User_Not_Found", event_props)
        raise HTTPException(status_code=400, detail="no user found")

    # The Identity boundary gate (ADR-014). Deliberately the first thing that
    # happens after the caller is known and before *anything* costs money: the
    # team lookup, the RAI agent and the orchestration manager are all below
    # it, so a refused request short-circuits with no agent invoked and no
    # tokens spent. Its Session identity comes from server-side session state
    # (issue #20) — acquiring the container is the one thing above the gate,
    # because the gate's identity is its *input* and a Cosmos read instantiates
    # no agent. A container that cannot be reached leaves the identity
    # anonymous, which is the refusing state.
    memory_store = None
    session_state = None
    try:
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        session_state = SessionStateStore(memory_store, user_id=user_id)
    except Exception:
        logger.warning(
            "Session state unavailable for session '%s' — the Identity boundary "
            "gate resolves the anonymous identity, which refuses",
            input_task.session_id,
            exc_info=True,
        )

    if session_state is not None and input_task.session_id:
        identity = await session_state.resolve_identity(input_task.session_id)
    else:
        identity = ANONYMOUS
    verdict = await identity_boundary_gate().evaluate(
        input_task.description, identity
    )
    if verdict.refused:
        track_event_if_configured(
            "Identity_Boundary_Refusal",
            {
                "status": "Request refused - identity boundary",
                "reason": verdict.reason.value,
                "session_id": input_task.session_id,
            },
        )
        raise HTTPException(status_code=403, detail=policy_block_detail())

    # The Mocked unlock (issue #27). The mirror image of the refusal directly
    # above it: the *same* keyword match decided both, and the only thing that
    # differs between the two outcomes is whether anybody is signed in. So it
    # short-circuits here for the same reasons the refusal does — no agent
    # invoked, no plan persisted, no tokens spent — and the presenter sees the
    # answer land in the place the refusal just was.
    #
    # An admitted personal question whose name has no **Associate record**
    # falls through to the ordinary request path, which is the honest
    # direction: the agents say they hold nothing about an individual, and
    # nobody is ever shown a balance nobody authored.
    if verdict.personal:
        record = lookup_associate(identity.display_name)
        if record is not None:
            track_event_if_configured(
                "Identity_Boundary_Unlocked",
                {
                    "status": "Answered from the associate's record",
                    "session_id": input_task.session_id,
                },
            )
            return {
                "status": "Answered from the associate's record",
                "session_id": input_task.session_id,
                # No plan was created, so there is nothing to navigate to. A
                # plan id here would send the surface to a page that does not
                # exist.
                "plan_id": None,
                "personal_answer": personal_answer_detail(record),
            }

    try:
        if memory_store is None:
            memory_store = await DatabaseFactory.get_database(user_id=user_id)
        user_current_team = await memory_store.get_current_team(user_id=user_id)
        team_id = None
        if user_current_team:
            team_id = user_current_team.team_id
        team = await memory_store.get_team_by_id(team_id=team_id)
        if not team:
            raise HTTPException(
                status_code=404,
                detail=f"Team configuration '{team_id}' not found or access denied",
            )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error retrieving team configuration: {e}",
        ) from e

    if not await rai_success(input_task.description, team, memory_store):
        track_event_if_configured(
            "Error_RAI_Check_Failed",
            {
                "status": "Plan not created - RAI check failed",
                "description": input_task.description,
                "session_id": input_task.session_id,
            },
        )
        raise HTTPException(
            status_code=400,
            detail="Request contains content that doesn't meet our safety guidelines, try again.",
        )

    if not input_task.session_id:
        input_task.session_id = str(uuid.uuid4())

    # Which session this user's request in flight belongs to (issue #21). The
    # MCP container calls back to the backend with no session of its own and
    # the model has no session identifier in its instructions to pass one, so
    # the backend resolves it from here rather than trusting a copied value —
    # a mis-copied one writes this associate's attempted steps onto another's
    # fault. Left above the plan so a tool call made anywhere in the turn can
    # be attributed.
    note_turn(user_id, input_task.session_id)
    # The rehearsal marker (#54) is **disarmed here and armed later**, and the
    # asymmetry is deliberate: both failure directions have to be the safe one.
    # A request that is not the rehearsal disarms immediately, because a marker
    # left standing would answer the honest-miss beat's car-wash question with
    # the closing checklist. A request that *is* the rehearsal arms only once
    # its orchestration task is about to be scheduled, because the disarm lives
    # in that task's `finally` — arming here would strand the marker for the
    # full TTL on any request that failed before the task existed.
    is_rehearsal = input_task.description == REHEARSED_SOP_QUERY
    if not is_rehearsal:
        forget_rehearsal(input_task.session_id)

    # Attach session_id to current span for Application Insights
    span = trace.get_current_span()
    if span:
        span.set_attribute("session_id", input_task.session_id)

    try:
        plan_id = str(uuid.uuid4())
        # Initialize memory store and service
        plan = Plan(
            id=plan_id,
            plan_id=plan_id,
            user_id=user_id,
            session_id=input_task.session_id,
            team_id=team_id,
            initial_goal=input_task.description,
            overall_status=PlanStatus.in_progress,
        )
        await memory_store.add_plan(plan)

        track_event_if_configured(
            "Plan_Created",
            {
                "status": "success",
                "plan_id": plan.plan_id,
                "session_id": input_task.session_id,
                "user_id": user_id,
                "team_id": team_id,
                "description": input_task.description,
            },
        )
    except Exception as e:
        logger.error("Error creating plan: %s", e)
        track_event_if_configured(
            "Error_Plan_Creation_Failed",
            {
                "status": "error",
                "description": input_task.description,
                "session_id": input_task.session_id,
                "user_id": user_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to create plan") from e

    # Ensure the workflow is valid (rebuild if terminated or stuck from a prior run)
    current_workflow = orchestration_config.get_current_orchestration(user_id)

    cached_team_id = getattr(current_workflow, "_team_id", None)
    team_mismatch = (
        current_workflow is not None and cached_team_id != team_id
    )

    # The lane router (ADR-013). Below the Identity boundary gate on purpose:
    # the two are separate components with opposite failure modes — the gate
    # fails closed, this fails open to the Deliberate lane — and a refused
    # request must never have paid for routing. This is the one place a Lane
    # becomes a Plan review value.
    lane = select_lane(input_task.lane, input_task.description)

    # The lane taken, recorded into server-side session state (issue #20). The
    # plan page is handed it through router state, which a reload throws away —
    # and the browser cannot re-derive it, because re-deriving it would be a
    # second lane router with its own opinion. Best-effort on purpose: a badge
    # that cannot be restored after a reload is no reason to refuse to start
    # the request.
    if session_state is not None:
        try:
            await session_state.write(input_task.session_id, lane=lane.value)
        except Exception:
            logger.warning(
                "Could not record the lane taken for session '%s'",
                input_task.session_id,
                exc_info=True,
            )

    # The cache-invalidation predicate's lane term (ADR-013). /init_team eagerly
    # builds a workflow before any task is submitted, so without this the first
    # request after a page load reuses that workflow and silently ignores the
    # lane this request was routed into.
    cached_plan_review = getattr(current_workflow, "_plan_review", None)
    plan_review_mismatch = (
        current_workflow is not None
        and cached_plan_review != lane.plan_review
    )

    workflow_unusable = (
        current_workflow is None
        or getattr(current_workflow, "_terminated", False)
        or getattr(current_workflow, "_is_running", False)
        or team_mismatch
        or plan_review_mismatch
    )
    if workflow_unusable:
        logger.info(
            "Workflow unusable for user '%s' (None=%s, terminated=%s, is_running=%s, "
            "team_mismatch=%s cached_team=%s selected_team=%s, "
            "plan_review_mismatch=%s cached_plan_review=%s lane=%s) "
            "— rebuilding",
            user_id,
            current_workflow is None,
            getattr(current_workflow, "_terminated", False),
            getattr(current_workflow, "_is_running", False),
            team_mismatch,
            cached_team_id,
            team_id,
            plan_review_mismatch,
            cached_plan_review,
            lane.value,
        )

        # Force-clear the running flag so get_current_or_new_orchestration
        # sees it as terminated and takes the lightweight reset path.
        if current_workflow is not None and getattr(current_workflow, "_is_running", False):
            current_workflow._is_running = False
            current_workflow._terminated = True
        team_service = TeamService(memory_store)
        await OrchestrationManager.get_current_or_new_orchestration(
            user_id=user_id,
            team_config=team,
            team_switched=False,
            team_service=team_service,
            plan_review=lane.plan_review,
        )

    try:

        async def run_orchestration_task(rehearsal_token):
            try:
                await OrchestrationManager().run_orchestration(user_id, input_task)
            finally:
                # The rehearsal marker's bound (#54). It stands for every SOP
                # tool call this turn makes rather than only the first, so the
                # turn's own end is what disarms it; the next request calling
                # `forget_rehearsal` is the backstop, not the bound. Held to
                # this turn's token because a cancelled turn is cleaned up
                # asynchronously and could otherwise outlive its successor's
                # arming — the presenter asking the rehearsed question twice.
                end_rehearsal_turn(input_task.session_id, rehearsal_token)
                # Clear our slot if we're still the registered active task
                current = orchestration_config.active_tasks.get(user_id)
                if current is not None and current.done():
                    orchestration_config.active_tasks.pop(user_id, None)

        # Cancel any in-flight orchestration for this user before starting a new one
        prior_task = orchestration_config.active_tasks.get(user_id)
        if prior_task is not None and not prior_task.done():
            try:
                prior_task.cancel()
                # Give the cancelled task a chance to clean up
                await asyncio.sleep(0)
            except Exception:
                logger.exception(
                    "Failed to cancel prior orchestration task for user '%s'", user_id
                )
            orchestration_config.active_tasks.pop(user_id, None)

        # Schedule new task and register it so subsequent requests can cancel it
        # The marker is armed here, after the prior turn's cancellation has had
        # its chance to clean up, so this turn's arming is the last word.
        new_task = asyncio.create_task(
            run_orchestration_task(
                note_rehearsal(input_task.session_id) if is_rehearsal else None
            )
        )
        orchestration_config.active_tasks[user_id] = new_task

        return {
            "status": "Request started successfully",
            "session_id": input_task.session_id,
            "plan_id": plan_id,
            # The lane taken, surfaced as a feature rather than hidden as an
            # implementation detail (ADR-013). It is the router's output, not
            # the client's declaration — free-typed input cannot know it
            # without being told.
            "lane": lane.value,
        }

    except Exception as e:
        track_event_if_configured(
            "Error_Request_Start_Failed",
            {
                "session_id": input_task.session_id,
                "description": input_task.description,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=400, detail=f"Error starting request: {e}"
        ) from e


@app_router.post("/plan_approval")
async def plan_approval(
    human_feedback: messages.PlanApprovalResponse, request: Request
):
    """
    Endpoint to receive the associate's verdict on a Reviewable plan.
    ---
    tags:
      - Plans
    parameters:
      - name: user_principal_id
        in: header
        type: string
        required: true
        description: User ID extracted from the authentication header
    requestBody:
      description: Plan verdict payload
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              m_plan_id:
                type: string
                description: The internal m_plan id for the plan (required)
              approved:
                type: boolean
                description: >-
                  Whether the plan is approved (true) or sent back for revision
                  (false). There is no third verdict: leaving the conversation
                  is navigation, not a verdict.
              feedback:
                type: string
                description: >-
                  What the associate would change. Required when the plan is
                  sent back.
              plan_id:
                type: string
                description: Optional user-facing plan_id
    responses:
      200:
        description: Verdict recorded successfully
        content:
          application/json:
            schema:
              type: object
              properties:
                status:
                  type: string
      401:
        description: Missing or invalid user information
      404:
        description: No active plan found for approval
      422:
        description: A plan sent back with nothing asked
      500:
        description: Internal server error
    """
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )

    # The verdict on a **Reviewable plan** is binary: approve it, or send it
    # back saying what you would change (#108). There is no reject, so a
    # send-back with nothing asked is refused here rather than replanned into
    # an identical plan the associate has no way to read differently. Refused
    # *before* the try block below, whose `except Exception` would otherwise
    # turn this into an opaque 500.
    feedback = (human_feedback.feedback or "").strip()
    if not human_feedback.approved and not feedback:
        raise HTTPException(
            status_code=422,
            detail="Sending a plan back requires saying what you would change",
        )

    # Attach session_id to span if plan_id is available and capture for events
    session_id = None
    if human_feedback.plan_id:
        try:
            memory_store = await DatabaseFactory.get_database(user_id=user_id)
            plan = await memory_store.get_plan_by_plan_id(plan_id=human_feedback.plan_id)
            if plan and plan.session_id:
                session_id = plan.session_id
                span = trace.get_current_span()
                if span:
                    span.set_attribute("session_id", session_id)
        except Exception:
            pass  # Don't fail request if span attribute fails

    # Set the approval in the orchestration config
    try:
        if user_id and human_feedback.m_plan_id:
            if (
                orchestration_config
                and human_feedback.m_plan_id in orchestration_config.approvals
            ):
                orchestration_config.set_approval_result(
                    human_feedback.m_plan_id,
                    human_feedback.approved,
                    feedback=feedback or None,
                )
                logger.debug("Plan approval received: %s", human_feedback)

                try:
                    result = await PlanService.handle_plan_approval(
                        human_feedback, user_id
                    )
                    logger.debug("Plan approval processed: %s", result)

                except ValueError as ve:
                    logger.error(f"ValueError processing plan approval: {ve}")
                    await connection_config.send_status_update_async(
                        {
                            "type": WebsocketMessageType.ERROR_MESSAGE,
                            "data": {
                                "content": "Approval failed due to invalid input.",
                                "status": "error",
                                "timestamp": asyncio.get_event_loop().time(),
                            },
                        },
                        user_id,
                        message_type=WebsocketMessageType.ERROR_MESSAGE,
                    )

                except Exception:
                    logger.error("Error processing plan approval", exc_info=True)
                    await connection_config.send_status_update_async(
                        {
                            "type": WebsocketMessageType.ERROR_MESSAGE,
                            "data": {
                                "content": "An unexpected error occurred while processing the approval.",
                                "status": "error",
                                "timestamp": asyncio.get_event_loop().time(),
                            },
                        },
                        user_id,
                        message_type=WebsocketMessageType.ERROR_MESSAGE,
                    )

                # Use dynamic event name based on the verdict given
                approval_status = (
                    "Approved" if human_feedback.approved else "SentBack"
                )
                event_name = f"Plan_{approval_status}"
                event_props = {
                    "plan_id": human_feedback.plan_id,
                    "m_plan_id": human_feedback.m_plan_id,
                    "approved": human_feedback.approved,
                    "user_id": user_id,
                    "feedback": human_feedback.feedback,
                }
                if session_id:
                    event_props["session_id"] = session_id
                track_event_if_configured(event_name, event_props)

                if human_feedback.approved:
                    return {"status": "approval recorded"}
                return {"status": "revision requested"}
            else:
                logging.warning(
                    "No orchestration or plan found for plan_id: %s",
                    human_feedback.m_plan_id
                )
                raise HTTPException(
                    status_code=404, detail="No active plan found for approval"
                )
    except Exception as e:
        logging.error(f"Error processing plan approval: {e}")
        try:
            await connection_config.send_status_update_async(
                {
                    "type": WebsocketMessageType.ERROR_MESSAGE,
                    "data": {
                        "content": "An error occurred while processing your approval request.",
                        "status": "error",
                        "timestamp": asyncio.get_event_loop().time(),
                    },
                },
                user_id,
                message_type=WebsocketMessageType.ERROR_MESSAGE,
            )
        except Exception as ws_error:
            # Don't let WebSocket send failure break the HTTP response
            logging.warning(f"Failed to send WebSocket error: {ws_error}")
        raise HTTPException(status_code=500, detail="Internal server error")

    return None


# ------------------------------------------------------------------
# MCP ask_user bridge
# ------------------------------------------------------------------

@app_router.post("/clarification/ask")
async def clarification_ask(request: Request):
    """Synchronous bridge for the MCP ``ask_user`` tool.

    The MCP server POSTs ``{question, user_id}`` here. This endpoint:
    1. Sends a ``USER_CLARIFICATION_REQUEST`` to the user via WebSocket.
    2. Blocks until the user responds (or the request times out).
    3. Returns ``{answer}`` so the MCP tool can pass it back to the agent.
    """
    body = await request.json()
    question = body.get("question", "")
    user_id = body.get("user_id", "")

    if not question or not user_id:
        raise HTTPException(status_code=400, detail="question and user_id are required")

    request_id = str(uuid.uuid4())

    # Register the pending clarification in orchestration state
    orchestration_config.set_clarification_pending(request_id)

    # Send the question to the user's browser via WebSocket
    clarification_request = messages.UserClarificationRequest(
        question=question,
        request_id=request_id,
    )
    await connection_config.send_status_update_async(
        {
            "type": WebsocketMessageType.USER_CLARIFICATION_REQUEST,
            "data": clarification_request,
        },
        user_id=user_id,
        message_type=WebsocketMessageType.USER_CLARIFICATION_REQUEST,
    )

    # Block until the user responds (the existing /user_clarification
    # endpoint calls set_clarification_result when the user answers).
    try:
        answer = await orchestration_config.wait_for_clarification(request_id)
    except asyncio.TimeoutError:
        return {"answer": ""}
    except Exception as exc:
        logger.error("clarification/ask: error waiting for response: %s", exc)
        return {"answer": ""}

    return {"answer": answer}


# ------------------------------------------------------------------
# MCP bridge to the Copilot Studio SOP agent (issue #18, ADR-011)
# ------------------------------------------------------------------

# The Direct Line client is a backend module: the MCP container ships only its
# own directory and `httpx`, so it cannot hold one. One client per process,
# built lazily so a backend with no SOP agent configured still starts.
_sop_client: Optional[DirectLineClient] = None

# The presenter opens the walkthrough with this corpus-authored query. The
# orchestrator can rephrase it before it calls the MCP tool, so /process_request
# arms a turn-scoped, session-scoped marker for this exact presenter request.
# This is not a keyword match: a direct or qualified question is left unchanged.
REHEARSED_SOP_QUERY = "How do I close the store?"


def sop_client() -> DirectLineClient:
    """The process's Direct Line client, built on first use."""
    global _sop_client
    if _sop_client is None:
        _sop_client = DirectLineClient.from_app_config()
    return _sop_client


def _retrieval_query(tool_query: str) -> str:
    """Return the corpus query for the one explicitly rehearsed procedure."""
    if tool_query == REHEARSED_SOP_QUERY or rehearsal_stands_for_current_turn():
        return REHEARSED_SOP_QUERY
    return tool_query


@app_router.post("/sop/ask")
async def sop_ask(request: Request):
    """Ask the Copilot Studio SOP agent a procedure question.

    The MCP ``search_store_procedures`` tool POSTs ``{question}`` here. The
    reply carries the answer and the citations parsed structurally out of the
    Direct Line activity, plus which platform and source answered — the two
    facts R6's Grounding panel is a claim about.

    A SOP agent that cannot be reached, or is not configured at all, returns
    the **fixed failure message** and says it failed. It never answers from
    anywhere else: a hidden fallback would make the cross-platform claim
    unfalsifiable.
    """
    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    retrieval_query = _retrieval_query(question)
    # What the orchestrator actually wrote (#54). The tool call is the only
    # place the rephrasing is visible, and until it was recorded, a missed
    # rehearsed hit could be blamed on the orchestrator, the tool or the
    # Dataverse index with equal confidence and no evidence. The Demo
    # validator keeps this per run in `e2e/artifacts/sop-evidence.jsonl`;
    # this line is how a presenter's own rehearsal leaves the same trace in
    # the container log, where `az containerapp logs` can read it back.
    logger.info(
        "sop/ask: the orchestrator asked %r; retrieving against %r%s",
        question,
        retrieval_query,
        "" if retrieval_query == question
        else " — the rehearsed turn's corpus wording",
    )

    try:
        answer = await sop_client().ask(retrieval_query)
    except Exception as exc:
        logger.error("sop/ask: no SOP agent to ask: %s", exc)
        answer = SopAnswer(text=DIRECT_LINE_FAILURE, failed=True)

    # And what came back (#54). The request half above exonerates the
    # rephrasing; on its own it says nothing about the reply, and the reply is
    # where the beat was still failing once the rephrasing was handled.
    # Measured 2026-08-14: three of six validator runs red, two of them the
    # honest miss, every one of them retrieved against the corpus's own
    # wording — and ten direct probes of that same wording cited SOP-102 every
    # time. An agent that answers "no matching procedure" and an agent that
    # answers the procedure with no citation metadata are different faults at
    # different layers, and both reach the Grounding panel as an empty list.
    #
    # It names the retrieval query and the conversation because the request
    # record is a separate line with an `await` between them and this backend
    # serves the whole agent pool at once: two interleaved turns would
    # otherwise read as one question answered twice.
    #
    # A Direct Line failure is **not** the honest miss and must never be
    # logged as one. The miss is a demonstrated capability — the agent
    # searched and said so; the failure is the hop not happening. Both carry
    # zero citations, and only one of them means the corpus is wrong.
    if answer.failed:
        emptiness = " — the hop failed"
    elif not answer.citations:
        emptiness = " — the honest miss"
    else:
        emptiness = ""
    logger.info(
        "sop/ask: %r came back with %d citation(s)%s %s "
        "(conversation %s): %r",
        retrieval_query,
        len(answer.citations),
        emptiness,
        [citation.name for citation in answer.citations],
        answer.conversation_id,
        (answer.text or "")[:400],
    )

    reply = {
        "text": answer.text,
        "failed": answer.failed,
        "conversation_id": answer.conversation_id,
        "tool_query": question,
        "retrieval_query": retrieval_query,
        "platform": SOP_PLATFORM,
        "source": SOP_SOURCE,
        "agent": config.COPILOT_STUDIO_AGENT_NAME,
        "citations": [
            {
                "position": citation.position,
                "name": citation.name,
                "snippet": citation.snippet(),
                "url": citation.url,
            }
            for citation in answer.citations
        ],
    }

    # The Grounding panel's first signal (#23), emitted where the hop actually
    # happened rather than inferred later from the transcript. `source_used`
    # returns nothing for a failed reply.
    await _push_source_used(reply)

    return reply


async def _push_source_used(reply: dict) -> None:
    """Tell the Grounding panel which platform answered (issue #23).

    The recipient is resolved **server-side and nowhere else**. The MCP
    container calls this bridge with no user of its own and is deliberately not
    asked for one the way ``ask_user`` asks: a model mis-copying a UUID must
    not be able to darken the demo's centrepiece panel, and a bridge reachable
    without credentials must not be able to push one associate's provenance
    onto another's screen.

    Every failure here is swallowed. R6 is a presentation surface; no answer
    may ever be lost because its provenance could not be reported.
    """
    try:
        signal = source_used(reply)
        if signal is None:
            return
        recipient = _panel_recipient()
        if not recipient:
            logger.debug("sop/ask: nobody connected to tell about the source used")
            return
        await connection_config.send_status_update_async(
            signal,
            user_id=recipient,
            message_type=WebsocketMessageType.SOURCE_USED,
        )
    except Exception as exc:
        logger.error("sop/ask: could not report the source used: %s", exc)


def _panel_recipient() -> Optional[str]:
    """Whose Grounding panel a bridge-originated push belongs on.

    **The user asking outranks the count of who is connected.** Both questions
    refuse to guess, so neither can put one associate's provenance on another's
    screen; they differ only in what they are counting, and a request in flight
    is the stronger evidence. A second socket — the presenter's other tab, a
    colleague's screen, a reconnect the backend has not noticed closing yet —
    is not a second question.

    Measured before it was believed. The Routing probe (issue #54) took one
    Fast-lane turn with a single idle bystander socket registered and graded it
    ``no-tool-call``: the answer cited ``SOP-102`` and listed its steps, and
    the panel stayed dark, because ``sole_user()`` counted two and stopped. On
    stage that is the demonstration's centrepiece failing on a retrieval that
    worked, for a reason nothing on the screen explains.
    """
    turn = sole_turn()
    if turn:
        return turn[0]
    return connection_config.sole_user()


# ------------------------------------------------------------------
# The Presenter alert's hidden route (issue #23)
# ------------------------------------------------------------------

@app_router.post("/presenter/alert", include_in_schema=False)
async def presenter_alert(request: Request):
    """Fire R8's proactive shift-task alert over the existing WebSocket.

    Hidden — kept out of the published schema — because the audience is looking
    at the same screen and the beat only works if the control is invisible and
    unguessable. The frontend's keyboard chord (#24) POSTs here with an empty
    body, which fires the rehearsed alert.

    Hidden is not authenticated, so the route is built so that being found
    costs little: the **words are the server's** and the **recipient is the
    server's**. A caller names one of the rehearsed alerts and can neither
    compose a message nor choose whose screen it lands on. The worst an
    uninvited caller achieves is a rehearsed shift-task alert appearing early.

    There is deliberately **no wall-clock timer** anywhere on this path. The
    beat has to land when the presenter is talking about it; a timer would land
    it whenever the timer said so, and on stage that is an interruption rather
    than a demonstration.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    recipient = connection_config.sole_user()
    if not recipient:
        # Unlike the Grounding panel's push, this one has no answer to protect.
        # The presenter pressed a key and nothing happened; saying so is the
        # difference between a bug and a chord that missed.
        raise HTTPException(status_code=404, detail="no connected client to alert")

    delivered = await connection_config.send_status_update_async(
        build_presenter_alert(body.get("alert")),
        user_id=recipient,
        message_type=WebsocketMessageType.PRESENTER_ALERT,
    )
    if not delivered:
        raise HTTPException(status_code=502, detail="the alert was not delivered")
    return {"status": "alerted"}


@app_router.post("/user_clarification")
async def user_clarification(
    human_feedback: messages.UserClarificationResponse, request: Request
):
    """
    Endpoint to receive user clarification responses for clarification requests sent by the system.

    ---
    tags:
      - Plans
    parameters:
      - name: user_principal_id
        in: header
        type: string
        required: true
        description: User ID extracted from the authentication header
    requestBody:
      description: User clarification payload
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              request_id:
                type: string
                description: The clarification request id sent by the system (required)
              answer:
                type: string
                description: The user's answer or clarification text
              plan_id:
                type: string
                description: (Optional) Associated plan_id
              m_plan_id:
                type: string
                description: (Optional) Internal m_plan id
    responses:
      200:
        description: Clarification recorded successfully
      400:
        description: RAI check failed or invalid input
      401:
        description: Missing or invalid user information
      404:
        description: No active plan found for clarification
      500:
        description: Internal server error
    """

    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )

    # Attach session_id to span if plan_id is available and capture for events
    session_id = None

    try:
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        if human_feedback.plan_id:
            try:
                plan = await memory_store.get_plan_by_plan_id(plan_id=human_feedback.plan_id)
                if plan and plan.session_id:
                    session_id = plan.session_id
                    span = trace.get_current_span()
                    if span:
                        span.set_attribute("session_id", session_id)
            except Exception:
                pass  # Don't fail request if span attribute fails
        user_current_team = await memory_store.get_current_team(user_id=user_id)
        team_id = None
        if user_current_team:
            team_id = user_current_team.team_id
        team = await memory_store.get_team_by_id(team_id=team_id)
        if not team:
            raise HTTPException(
                status_code=404,
                detail=f"Team configuration '{team_id}' not found or access denied",
            )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error retrieving team configuration: {e}",
        ) from e
    # Set the approval in the orchestration config
    if user_id and human_feedback.request_id:
        # validate rai
        if human_feedback.answer is not None and str(human_feedback.answer).strip() != "":
            if not await rai_success(human_feedback.answer, team, memory_store):
                event_props = {
                    "status": "Plan Clarification ",
                    "description": human_feedback.answer,
                    "request_id": human_feedback.request_id,
                }
                if session_id:
                    event_props["session_id"] = session_id
                track_event_if_configured("Error_RAI_Check_Failed", event_props)
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

        if (
            orchestration_config
            and human_feedback.request_id in orchestration_config.clarifications
        ):
            # Use the new event-driven method to set clarification result
            orchestration_config.set_clarification_result(
                human_feedback.request_id, human_feedback.answer
            )
            try:
                result = await PlanService.handle_human_clarification(
                    human_feedback, user_id
                )
                logger.debug("Human clarification processed: %s", result)
            except ValueError as ve:
                logger.error("ValueError processing human clarification: %s", ve)
            except Exception as e:
                logger.error("Error processing human clarification: %s", e)
            track_event_if_configured(
                "HumanClarificationReceived",
                {
                    "request_id": human_feedback.request_id,
                    "answer": human_feedback.answer,
                    "user_id": user_id,
                },
            )
            return {
                "status": "clarification recorded",
            }
        else:
            logging.warning(
                f"No orchestration or plan found for request_id: {human_feedback.request_id}"
            )
            raise HTTPException(
                status_code=404, detail="No active plan found for clarification"
            )

    return None


@app_router.post("/agent_message")
async def agent_message_user(
    agent_message: messages.AgentMessageResponse, request: Request
):
    """
    Endpoint to receive messages from agents (agent -> user communication).

    ---
    tags:
      - Agents
    parameters:
      - name: user_principal_id
        in: header
        type: string
        required: true
        description: User ID extracted from the authentication header
    requestBody:
      description: Agent message payload
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              plan_id:
                type: string
                description: ID of the plan this message relates to
              agent:
                type: string
                description: Name or identifier of the agent sending the message
              content:
                type: string
                description: The message content
              agent_type:
                type: string
                description: Type of agent (AI/Human)
              m_plan_id:
                type: string
                description: Optional internal m_plan id
    responses:
      200:
        description: Message recorded successfully
        schema:
          type: object
          properties:
            status:
              type: string
      401:
        description: Missing or invalid user information
    """

    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing or invalid user information"
        )

    # Attach session_id to span if plan_id is available and capture for events
    session_id = None
    if agent_message.plan_id:
        try:
            memory_store = await DatabaseFactory.get_database(user_id=user_id)
            plan = await memory_store.get_plan_by_plan_id(plan_id=agent_message.plan_id)
            if plan and plan.session_id:
                session_id = plan.session_id
                span = trace.get_current_span()
                if span:
                    span.set_attribute("session_id", session_id)
        except Exception:
            pass  # Don't fail request if span attribute fails

    # Set the approval in the orchestration config

    try:

        result = await PlanService.handle_agent_messages(agent_message, user_id)
        logger.debug("Agent message processed: %s", result)
    except ValueError as ve:
        logger.error("ValueError processing agent message: %s", ve)
    except Exception as e:
        logger.error("Error processing agent message: %s", e)

    # Use dynamic event name with agent identifier
    event_name = f"Agent_Message_From_{agent_message.agent.replace(' ', '_')}"
    event_props = {
        "agent": agent_message.agent,
        "content": agent_message.content,
        "user_id": user_id,
    }
    if session_id:
        event_props["session_id"] = session_id
    track_event_if_configured(event_name, event_props)
    return {
        "status": "message recorded",
    }


@app_router.post("/upload_team_config")
async def upload_team_config(
    request: Request,
    file: UploadFile = File(...),
    team_id: Optional[str] = Query(None),
):
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
        track_event_if_configured(
            "Error_User_Not_Found", {"status_code": 400, "detail": "no user"}
        )
        raise HTTPException(status_code=400, detail="no user found")
    try:
        memory_store = await DatabaseFactory.get_database(user_id=user_id)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error retrieving team configuration: {e}",
        ) from e
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
            ) from e

        # Validate content with RAI before processing
        if not team_id:
            rai_valid, rai_error = await rai_validate_team_config(json_data, memory_store)
            if not rai_valid:
                track_event_if_configured(
                    "Error_Config_RAI_Validation_Failed",
                    {
                        "status": "failed",
                        "user_id": user_id,
                        "filename": file.filename,
                        "reason": rai_error,
                    },
                )
                raise HTTPException(status_code=400, detail=rai_error)

        track_event_if_configured(
            "Config_RAI_Validation_Passed",
            {"status": "passed", "user_id": user_id, "filename": file.filename},
        )
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
                "Error_Config_Model_Validation_Failed",
                {
                    "status": "failed",
                    "user_id": user_id,
                    "filename": file.filename,
                    "missing_models": missing_models,
                },
            )
            raise HTTPException(status_code=400, detail=error_message)

        track_event_if_configured(
            "Config_Model_Validation_Passed",
            {"status": "passed", "user_id": user_id, "filename": file.filename},
        )

        # Validate search indexes
        logger.info(f"Validating search indexes for user: {user_id}")
        search_valid, search_errors = await team_service.validate_team_search_indexes(
            json_data
        )
        if not search_valid:
            logger.warning(f"Search validation failed for user {user_id}: {search_errors}")
            error_message = (
                f"Search index validation failed:\n\n{chr(10).join([f'• {error}' for error in search_errors])}\n\n"
                f"Please ensure all referenced search indexes exist in your Azure AI Search service."
            )
            track_event_if_configured(
                "Error_Config_Search_Validation_Failed",
                {
                    "status": "failed",
                    "user_id": user_id,
                    "filename": file.filename,
                    "search_errors": search_errors,
                },
            )
            raise HTTPException(status_code=400, detail=error_message)

        logger.info(f"Search validation passed for user: {user_id}")
        track_event_if_configured(
            "Config_Search_Validation_Passed",
            {"status": "passed", "user_id": user_id, "filename": file.filename},
        )

        # Validate and parse the team configuration
        try:
            team_configuration = await team_service.validate_and_parse_team_config(
                json_data, user_id
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Save the configuration
        try:
            logger.debug("Saving team configuration for team_id=%s", team_id)
            if team_id:
                team_configuration.team_id = team_id
                team_configuration.id = team_id  # Ensure id is also set for updates
            team_id = await team_service.save_team_configuration(team_configuration)
        except ValueError as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to save configuration: {str(e)}"
            ) from e

        track_event_if_configured(
            "Config_Team_Uploaded",
            {
                "status": "success",
                "team_id": team_id,
                "user_id": user_id,
                "agents_count": len(team_configuration.agents),
                "tasks_count": len(team_configuration.starting_tasks),
            },
        )

        return {
            "status": "success",
            "team_id": team_id,
            "name": team_configuration.name,
            "message": "Team configuration uploaded and saved successfully",
            "team": team_configuration.model_dump(),  # Return the full team configuration
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error("Unexpected error uploading team configuration: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error occurred")


@app_router.get("/team_configs")
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
        team_configs = await team_service.get_all_team_configurations()

        # Convert to dictionaries for response
        configs_dict = [config.model_dump() for config in team_configs]

        return configs_dict

    except Exception as e:
        logging.error(f"Error retrieving team configurations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")


@app_router.get("/team_configs/{team_id}")
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
        team_configuration = await team_service.get_team_configuration(team_id, user_id)

        if team_configuration is None:
            raise HTTPException(status_code=404, detail="Team configuration not found")

        # Convert to dictionary for response
        return team_configuration.model_dump()

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logging.error(f"Error retrieving team configuration: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")


@app_router.delete("/team_configs/{team_id}")
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
            "Config_Team_Deleted",
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


@app_router.post("/select_team")
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
        team_configuration = await team_service.get_team_configuration(
            selection.team_id, user_id
        )
        if team_configuration is None:  # ensure that id is valid
            raise HTTPException(
                status_code=404,
                detail=f"Team configuration '{selection.team_id}' not found or access denied",
            )
        set_team = await team_service.handle_team_selection(
            user_id=user_id, team_id=selection.team_id
        )
        if not set_team:
            track_event_if_configured(
                "Error_Config_Team_Selection_Failed",
                {
                    "status": "failed",
                    "team_id": selection.team_id,
                    "team_name": team_configuration.name,
                    "user_id": user_id,
                },
            )
            raise HTTPException(
                status_code=404,
                detail=f"Team configuration '{selection.team_id}' failed to set",
            )

        # save to in-memory config for current user
        team_config.set_current_team(
            user_id=user_id, team_configuration=team_configuration
        )

        # Track the team selection event
        track_event_if_configured(
            "Config_Team_Selected",
            {
                "status": "success",
                "team_id": selection.team_id,
                "team_name": team_configuration.name,
                "user_id": user_id,
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
            "Error_Config_Team_Selection",
            {
                "status": "error",
                "team_id": selection.team_id,
                "user_id": user_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Internal server error occurred")


# ---------------------------------------------------------------------------
# Server-side session state (issue #20)
#
# The state of a session lives here rather than in browser storage so a mid-demo
# reload does not lose it. Two things are held today and neither can be
# re-derived by the client: the **Session identity** the Identity boundary gate
# reads (ADR-014), and the **Lane taken** as the lane router decided it
# (ADR-013).
# ---------------------------------------------------------------------------
@app_router.get("/session_state/{session_id}")
async def get_session_state(session_id: str, request: Request):
    """Read a session's server-side state.

    A session nobody has written to is not a 404 — it reads back as the state
    the demo opens in: anonymous, no lane taken yet.
    """
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(status_code=400, detail="no user found")

    try:
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        return await SessionStateStore(memory_store, user_id=user_id).read(session_id)
    except Exception as e:
        logger.error("Error reading session state for '%s': %s", session_id, e)
        raise HTTPException(
            status_code=500, detail="Internal server error occurred"
        ) from e


@app_router.post("/session_state/{session_id}/sign_in")
async def sign_in_session(session_id: str, request: Request):
    """The Mocked sign-in (issue #27) — the whole of the identity provider.

    **It takes no name.** The route declares no body, so a caller that supplies
    one is ignored: the name the header shows and the name the **Associate
    record** is keyed by would otherwise be two strings in two languages, free
    to drift, and the drift's symptom is a header confidently naming somebody
    the Identity boundary gate will not answer for. The one associate the demo
    signs in as is authored in ``associate/records.py`` and read from there.

    Its own route rather than a ``PATCH`` with a name in it for the same
    reason. Signing out *is* that patch — clearing an identity needs no
    authored content and a present-but-null field already means it.

    No real identity provider is involved anywhere in this flow, which is the
    beat's plainest requirement and the conversation it exists to open.
    """
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(status_code=400, detail="no user found")

    try:
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        store = SessionStateStore(memory_store, user_id=user_id)
        state = await store.write(
            session_id,
            identity={"display_name": DEMO_ASSOCIATE.display_name},
        )
    except Exception as e:
        logger.error("Error signing in session '%s': %s", session_id, e)
        raise HTTPException(
            status_code=500, detail="Internal server error occurred"
        ) from e

    track_event_if_configured(
        "Identity_Mocked_Sign_In",
        {"status": "Signed in (mocked)", "session_id": session_id},
    )
    return state


@app_router.patch("/session_state/{session_id}")
async def patch_session_state(
    session_id: str, patch: SessionStatePatch, request: Request
):
    """Merge a partial write into a session's server-side state.

    A merge rather than a replace: the mocked sign-in owns the identity and the
    request path owns the lane taken, and whichever wrote last must not erase
    the other. Only the fields the body actually names are written, so a
    present-but-null field is an explicit clear — that is what signing out is.
    """
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(status_code=400, detail="no user found")

    # The body's fields are handed to the store as plain data rather than as
    # request models: the store's contract is "a mapping or nothing", which
    # keeps it from depending on the identity of a class defined in the API
    # layer.
    updates = {}
    if "identity" in patch.model_fields_set:
        updates["identity"] = (
            patch.identity.model_dump() if patch.identity is not None else None
        )
    if "lane" in patch.model_fields_set:
        updates["lane"] = patch.lane

    try:
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        store = SessionStateStore(memory_store, user_id=user_id)
        return await store.write(session_id, **updates)
    except Exception as e:
        logger.error("Error writing session state for '%s': %s", session_id, e)
        raise HTTPException(
            status_code=500, detail="Internal server error occurred"
        ) from e


# ---------------------------------------------------------------------------
# The troubleshooting record, reached by the MCP container (issue #21)
#
# The MCP container has **no Cosmos access at all** — no connection
# configuration and no dependency — so it asks the backend over HTTP for the
# record, the same pattern the clarification and SOP bridges use.
#
# Neither route takes a session or a user. Both resolve the turn in flight
# server-side (``troubleshooting.turn``), the same refusal-to-guess
# ``sole_user()`` applies to the transparency pushes: a session identifier
# copied by a model would write one associate's attempted steps onto another
# associate's fault, or read back steps nobody on this shift tried and skip a
# real runbook branch. And neither route fails the agent's turn — the record is
# the memory of one shift, and losing it costs a repeated step where raising
# would cost the answer.
# ---------------------------------------------------------------------------
async def _troubleshooting_store():
    """The store for the turn in flight, or ``(None, None)``."""
    turn = sole_turn()
    if turn is None:
        return None, None
    user_id, session_id = turn
    memory_store = await DatabaseFactory.get_database(user_id=user_id)
    return TroubleshootingStore(memory_store, user_id=user_id), session_id


@app_router.get("/troubleshooting/attempted")
async def get_attempted_steps():
    """What the associate has already tried on the fault in flight.

    Total: no turn in flight, an unreadable container and a session nobody has
    written to all read back as an empty record, because the caller is about to
    offer a runbook and the safe default is to offer all of it.
    """
    empty = {"session_id": None, "attempted": [], "equipment": None, "note": ""}
    try:
        store, session_id = await _troubleshooting_store()
        if store is None:
            return empty
        record = await store.read(session_id)
        return {
            "session_id": session_id,
            "attempted": record.attempted,
            "equipment": record.equipment,
            "note": TroubleshootingStore.note_for(record.attempted),
        }
    except Exception as e:
        logger.warning("Could not read the troubleshooting record: %s", e)
        return empty


@app_router.post("/troubleshooting/attempted")
async def record_attempted_steps(request: Request):
    """Record what the associate reports having tried on the fault in flight.

    ``steps`` arrives as the associate said it and is split into discrete steps
    here rather than in the container, so the same parser decides "the same
    step" wherever a report comes from. ``recorded`` reports honestly whether
    anything was written — an agent told the write succeeded when it did not
    would stop asking.
    """
    body = await request.json()
    steps = body.get("steps") if isinstance(body, dict) else None
    equipment = body.get("equipment") if isinstance(body, dict) else None
    if isinstance(steps, list):
        parsed = []
        for item in steps:
            parsed.extend(parse_attempted_steps(item))
    else:
        parsed = parse_attempted_steps(steps)

    try:
        store, session_id = await _troubleshooting_store()
        if store is None:
            return {"recorded": False, "attempted": [], "note": ""}
        record = await store.record(session_id, parsed, equipment=equipment)
        return {
            "recorded": True,
            "attempted": record.attempted,
            "note": TroubleshootingStore.note_for(record.attempted),
        }
    except Exception as e:
        logger.warning("Could not record the attempted steps: %s", e)
        return {"recorded": False, "attempted": [], "note": ""}


# ---------------------------------------------------------------------------
# The Simulated ticket, drafted by the MCP container (issue #22)
#
# The same seam and the same server-side session resolution as the record
# above — and sharper, because a mis-resolved session here drafts one
# associate's fault onto another associate's approval.
#
# There is deliberately **no submit route**. TKT-001 says the associate
# confirms the ticket once and the confirmation is the approval step, so
# submission happens at the plan-approval seam
# (``orchestration_manager._raise_confirmed_ticket``) and nowhere else. A route
# that raised a ticket would be a second confirmation step reachable by a model
# — which is exactly the step the requirement says does not exist.
# ---------------------------------------------------------------------------
async def _ticket_stores():
    """The ticket store, the record store and the session, or all three None."""
    turn = sole_turn()
    if turn is None:
        return None, None, None
    user_id, session_id = turn
    memory_store = await DatabaseFactory.get_database(user_id=user_id)
    return (
        TicketStore(memory_store, user_id=user_id),
        TroubleshootingStore(memory_store, user_id=user_id),
        session_id,
    )


def _no_ticket() -> dict:
    """What every failure here reads as: no draft, and nothing claiming one."""
    return {"drafted": False, "fields": {}, "rendered": ""}


def _ticket_response(ticket) -> dict:
    return {
        "drafted": True,
        "session_id": ticket.session_id,
        "fields": ticket.fields,
        "rendered": render_ticket(ticket.fields),
    }


@app_router.get("/escalation/ticket")
async def get_service_ticket():
    """This conversation's ticket, if one has been drafted."""
    try:
        store, _record, session_id = await _ticket_stores()
        if store is None:
            return _no_ticket()
        ticket = await store.read(session_id)
        if ticket is None:
            return _no_ticket()
        return _ticket_response(ticket)
    except Exception as e:
        logger.warning("Could not read the service ticket: %s", e)
        return _no_ticket()


@app_router.get("/chats/{session_id}/ticket")
async def get_chat_ticket(session_id: str, request: Request):
    """The submitted Simulated ticket for one of this user's Chats, if any.

    This is a Chat read, not a ticket-number lookup: the route accepts the
    Session the browser already opened and the store enforces its owner. Drafts
    remain invisible because the associate has not raised them yet.
    """
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        raise HTTPException(status_code=400, detail="no user")

    memory_store = await DatabaseFactory.get_database(user_id=user_id)
    ticket = await TicketStore(memory_store, user_id=user_id).read(session_id)
    if (
        ticket is None
        or ticket.user_id != user_id
        or ticket.fields.get("status") != TicketStatus.submitted
    ):
        return None
    return TicketRaised.from_fields(ticket.fields).to_dict()


@app_router.post("/escalation/ticket")
async def draft_service_ticket(request: Request):
    """Draft — or correct — this conversation's ticket.

    ``steps_attempted`` is filled here from the troubleshooting record and a
    value on the wire is **discarded**. That is the requirement — the ticket
    carries what the associate already reported, with nothing re-typed —
    enforced by the route rather than asked of a model, because a paraphrase of
    what an associate tried is not what they tried and nobody downstream can
    tell the difference.

    ``drafted`` reports honestly whether anything was persisted: an agent told
    a draft is waiting for approval that the approval seam will never find
    would present the associate a ticket that confirming does nothing to.
    """
    body = await request.json()
    supplied = body if isinstance(body, dict) else {}

    try:
        store, record_store, session_id = await _ticket_stores()
        if store is None:
            return _no_ticket()

        record = await record_store.read(session_id)
        ticket = await store.draft(
            session_id,
            supplied,
            attempted=record.attempted,
            equipment=record.equipment,
        )
        if ticket is None:
            return _no_ticket()
        return _ticket_response(ticket)
    except Exception as e:
        logger.warning("Could not draft the service ticket: %s", e)
        return _no_ticket()


# Get plans is called in the initial side rendering of the frontend
@app_router.get("/plans")
async def get_plans(request: Request):
    """
    Retrieve plans for the current user.

    ---
    tags:
      - Plans
    """

    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        track_event_if_configured(
            "Error_User_Not_Found", {"status_code": 400, "detail": "no user"}
        )
        raise HTTPException(status_code=400, detail="no user")

    # Initialize memory context
    memory_store = await DatabaseFactory.get_database(user_id=user_id)

    current_team = await memory_store.get_current_team(user_id=user_id)
    if not current_team:
        return []

    # Every status, deliberately (#74). Filtering to `PlanStatus.completed`
    # meant five of the six statuses never reached the chat list, and the chat
    # most worth resuming is the one that did not finish. Listing `failed` and
    # `canceled` too makes rehearsal debris visible, which is what Chat
    # deletion (ADR-026) answers.
    all_plans = await memory_store.get_all_plans_by_team_id(
        team_id=current_team.team_id
    )

    return all_plans


@app_router.delete("/chats")
async def delete_all_chats(request: Request):
    """
    Delete every Chat belonging to the current user (#76, ADR-026).

    ---
    tags:
      - Chats

    One chat's delete answers in an HTTP status. A sweep of the whole list
    cannot: its chats do not all end the same way, and a status code carrying
    the worst of them would throw away which rows the panel may now drop. So
    the accounting is the body of the response, not its status code — the
    route always answers 200 and lets the caller read what actually happened.

    Nothing about which chats to take comes from the request: the sessions
    swept come from this user's own plans, read inside the store, not from
    whatever the browser's list happened to show.

    They are, however, the chats the browser was *looking at*. ``GET /plans``
    above lists the current team's chats and the confirmation states that
    list's count, so the sweep is scoped to the same team — found by review, as
    an irreversible action that reached past the list it asked about.

    Without a team there is no list to sweep, and this route **fails** rather
    than reporting an empty one. ``get_current_team`` reads through
    ``query_items``, which logs a Cosmos failure and returns ``[]`` — so "this
    associate has no current team" and "the store could not be reached" arrive
    here as the same ``None``, and answering the second one with a cleared list
    would tell a presenter their history is gone while every chat sits in
    Cosmos. The same reading ``delete_chat`` refuses, for the same reason. A
    genuinely team-less associate has no chats listed, so the control they
    would be refused is one the panel has already disabled.
    """
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        track_event_if_configured(
            "Error_User_Not_Found", {"status_code": 400, "detail": "no user"}
        )
        raise HTTPException(status_code=400, detail="no user")

    memory_store = await DatabaseFactory.get_database(user_id=user_id)

    current_team = await memory_store.get_current_team(user_id=user_id)
    if not current_team:
        logger.error("Could not read a current team for %s; nothing swept", user_id)
        raise HTTPException(
            status_code=500,
            detail="Could not read the chat list, so no chats were deleted.",
        )

    result = await memory_store.delete_all_chats(team_id=current_team.team_id)

    track_event_if_configured(
        "Chats_Deleted",
        {
            "status": result.status,
            "deleted_count": len(result.deleted),
            "chats_kept_running": result.kept_running,
            "chats_failed": result.failed,
            "user_id": user_id,
        },
    )

    return {
        "status": result.status,
        "deleted_sessions": list(result.deleted),
        "documents_deleted": result.documents_deleted,
        "chats_kept_running": result.kept_running,
        "chats_failed": result.failed,
    }


@app_router.delete("/chats/{session_id}")
async def delete_chat(session_id: str, request: Request):
    """
    Delete one Chat — every document in its session partition.

    ---
    tags:
      - Chats

    #75 / ADR-026. **Chat deletion**, not plan deletion: a Chat is a Session
    and everything the conversation produced lives in that session's partition
    — its plans, their steps, the transcript, ``m_plan``, the **Troubleshooting
    record**, the **Simulated ticket** and the **Session state**.
    ``delete_plan_by_plan_id`` is deliberately not reached from here; it takes
    one document, is not scoped by ``user_id``, and reports success whatever
    happened.

    The route reports what the store actually managed. A running Chat is
    refused with the reason the surface shows, a chat that is not this user's
    is simply not found, and a sweep that left documents behind is a failure
    rather than a success with a smaller number in it.
    """
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        track_event_if_configured(
            "Error_User_Not_Found", {"status_code": 400, "detail": "no user"}
        )
        raise HTTPException(status_code=400, detail="no user")

    # The store is built for this user, and its `user_id` predicate is the whole
    # of the authorization — a session id is not a secret.
    memory_store = await DatabaseFactory.get_database(user_id=user_id)
    result = await memory_store.delete_chat(session_id=session_id)

    if result.outcome in (DeletionOutcome.no_such_chat, DeletionOutcome.not_yours):
        # One answer for "no such chat" and "not yours" alike: distinguishing
        # them tells a caller something about somebody else's chat. The store
        # logs which of the two it was.
        raise HTTPException(status_code=404, detail="Chat not found")

    if result.outcome is DeletionOutcome.still_running:
        raise HTTPException(status_code=409, detail=STILL_RUNNING_DETAIL)

    if result.outcome is DeletionOutcome.incomplete:
        logger.error(
            "Chat %s was only partly deleted: %s documents went, %s did not",
            session_id,
            result.deleted,
            result.failed,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                f"Deleted {result.deleted} of {result.deleted + result.failed} "
                "documents; this chat is still partly in the record."
            ),
        )

    track_event_if_configured(
        "Chat_Deleted",
        {"status": "success", "session_id": session_id, "user_id": user_id},
    )

    return {
        "status": "deleted",
        "session_id": session_id,
        "documents_deleted": result.deleted,
    }


# Get plans is called in the initial side rendering of the frontend
@app_router.get("/plan")
async def get_plan_by_id(
    request: Request,
    plan_id: Optional[str] = Query(None),
):
    """
    Retrieve a plan by ID for the current user.

    ---
    tags:
      - Plans
    """

    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    if not user_id:
        track_event_if_configured(
            "Error_User_Not_Found", {"status_code": 400, "detail": "no user"}
        )
        raise HTTPException(status_code=400, detail="no user")

    # Initialize memory context
    memory_store = await DatabaseFactory.get_database(user_id=user_id)
    try:
        if plan_id:
            plan = await memory_store.get_plan_by_plan_id(plan_id=plan_id)
            if not plan:
                event_props = {"status_code": 400, "detail": "Plan not found"}
                # No session_id available since plan not found
                track_event_if_configured("Error_Plan_Not_Found", event_props)
                raise HTTPException(status_code=404, detail="Plan not found")

            # Attach session_id to span
            if plan.session_id:
                span = trace.get_current_span()
                if span:
                    span.set_attribute("session_id", plan.session_id)

            # Use get_steps_by_plan to match the original implementation

            team = await memory_store.get_team_by_id(team_id=plan.team_id)
            agent_messages = await memory_store.get_agent_messages(plan_id=plan.plan_id)
            mplan = plan.m_plan if plan.m_plan else None
            streaming_message = plan.streaming_message if plan.streaming_message else ""
            plan.streaming_message = ""  # clear streaming message after retrieval
            plan.m_plan = None  # remove m_plan from plan object for response
            return {
                "plan": plan,
                "team": team if team else None,
                "messages": agent_messages,
                "m_plan": mplan,
                "streaming_message": streaming_message,
            }
        else:
            track_event_if_configured(
                "GetPlanId", {"status_code": 400, "detail": "no plan id"}
            )
            raise HTTPException(status_code=400, detail="no plan id")
    except Exception as e:
        logging.error(f"Error retrieving plan: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")


@app_router.get("/images/{blob_name:path}")
async def get_generated_image(blob_name: str):
    """Proxy a generated image from Azure Blob Storage."""
    from azure.storage.blob import BlobServiceClient
    from fastapi.responses import Response

    blob_url = config.AZURE_STORAGE_BLOB_URL
    container = config.AZURE_STORAGE_IMAGES_CONTAINER
    if not blob_url:
        raise HTTPException(status_code=503, detail="Image storage not configured")

    # Validate blob_name to prevent path traversal
    import re
    if not re.match(r'^[\w\-]+\.png$', blob_name):
        raise HTTPException(status_code=400, detail="Invalid image name")

    try:
        credential = config.get_azure_credential(config.AZURE_CLIENT_ID)
        blob_service = BlobServiceClient(account_url=blob_url.rstrip("/"), credential=credential)
        blob_client = blob_service.get_blob_client(container=container, blob=blob_name)
        stream = blob_client.download_blob()
        data = stream.readall()
        return Response(content=data, media_type="image/png")
    except Exception as exc:
        logging.error(f"Error retrieving image '{blob_name}': {exc}")
        raise HTTPException(status_code=404, detail="Image not found")
