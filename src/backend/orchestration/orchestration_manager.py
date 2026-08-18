"""Orchestration manager (agent_framework version) handling multi-agent Magentic workflow creation and execution."""

import asyncio
import json
import logging
import uuid
import re
from dataclasses import dataclass, field
from typing import List, Optional

import models.messages as messages
from agent_framework import (Agent, AgentResponseUpdate,
                             InMemoryCheckpointStorage, Message,
                             WorkflowRunState)
from agent_framework_foundry import FoundryChatClient
from agent_framework_orchestrations import (MagenticBuilder,
                                            MagenticOrchestratorEvent,
                                            MagenticPlanReviewRequest)
from agents.agent_factory import AgentFactory
from callbacks.response_handlers import (agent_response_callback,
                                         format_agent_display_name,
                                         streaming_agent_response_callback)
from common.config.app_config import config
from common.database.database_base import DatabaseBase
from common.models.messages import TeamConfiguration
from common.utils.markdown_utils import \
    normalize_markdown_tables as _normalize_markdown_tables
from models.messages import AgentMessageStreaming, WebsocketMessageType
from orchestration.connection_config import (connection_config,
                                             orchestration_config)
from orchestration.plan_review_helpers import (convert_plan_review_to_mplan,
                                               get_magentic_prompt_kwargs,
                                               mandatory_participants,
                                               plans_minimally,
                                               wait_for_plan_approval)
from orchestration.plan_revision import PlanRevision
from patches.tool_history_leak import apply_tool_history_leak_patch
from services.team_service import TeamService
from transparency.tokens import token_usage

# Apply patch: MAF bug causes tool_call/tool_result messages to leak across
# participants in GroupChat, triggering "No tool call found for call_id" 400 errors.
# See localspec/bugs/framework/F1-tool-history-leak.md
apply_tool_history_leak_patch()

_BARE_IMAGE_URL_RE = re.compile(
    r"(?<![\(\]])"
    r"(?<!\]\()"
    r"("
    # Absolute image URL (any host, or a backend /api/v4/images path)
    r"https?://[^\s)]+?(?:/api/v4/images/[^\s)]+?|[^\s)]+?\.(?:png|jpe?g|gif|webp))"
    # Bare relative backend image path (emitted by the MCP/backend image tools).
    # The (?<![^\s]) guard requires the path to start at whitespace/string-start so
    # it never matches the same substring inside an absolute URL.
    r"|(?<![^\s])/api/v4/images/[^\s)]+?\.(?:png|jpe?g|gif|webp)"
    r")"
    r"(?=[\s)\]]|$)",
    re.IGNORECASE,
)


def _embed_bare_image_urls(text: str) -> str:
    """Wrap bare image URLs in markdown image syntax so the UI renders them inline.

    Skips URLs already inside ``![alt](url)`` or ``[text](url)`` (handled by the
    negative lookbehinds), so it never double-wraps an existing markdown embed.
    """
    if not text:
        return text
    return _BARE_IMAGE_URL_RE.sub(r"![Generated image](\1)", text)


@dataclass(frozen=True, slots=True)
class PlanReviewOutcome:
    """What the associate said about the plans this pause put in front of them.

    ``responses`` is what the workflow resumes with — an approval or a revise
    request per review — or ``None`` when no verdict arrived at all, which is
    the only way a plan review ends the run now that there is no reject (#108).
    ``approved`` is true only when every review was approved, so a run that has
    been sent back once does not auto-approve the plan that comes back.
    """

    responses: Optional[dict]
    revision: PlanRevision
    approved: bool
    verdicts: list = field(default_factory=list)


class OrchestrationManager:
    """Manager for handling orchestration logic using agent_framework Magentic workflow."""

    logger = logging.getLogger(f"{__name__}.OrchestrationManager")

    def __init__(self):
        self.user_id: Optional[str] = None
        self.logger = self.__class__.logger

    # ---------------------------
    # Orchestration construction
    # ---------------------------
    @classmethod
    async def init_orchestration(
        cls,
        agents: List,
        team_config: TeamConfiguration,
        memory_store: DatabaseBase,
        user_id: str | None = None,
        plan_review: bool = True,
    ):
        """
        Initialize a Magentic workflow using MagenticBuilder with:
          - enable_plan_review per request — on for the Deliberate lane, off for
            the Fast lane (ADR-013). Defaults to on, so a caller that says
            nothing gets the approval gate rather than losing it by omission.
          - Prompt customizations from get_magentic_prompt_kwargs()
          - FoundryChatClient as the underlying chat client
          - Event-based callbacks for streaming and final responses
        """
        if not user_id:
            raise ValueError("user_id is required to initialize orchestration")

        # Get credential from config
        credential = config.get_azure_credential(client_id=config.AZURE_CLIENT_ID)

        # Create Foundry chat client for orchestration
        try:
            chat_client = FoundryChatClient(
                project_endpoint=config.AZURE_AI_PROJECT_ENDPOINT,
                model=team_config.deployment_name,
                credential=credential,
            )

            cls.logger.info(
                "Created FoundryChatClient for orchestration with model '%s' at endpoint '%s'",
                team_config.deployment_name,
                config.AZURE_AI_PROJECT_ENDPOINT,
            )
        except Exception as e:
            cls.logger.error("Failed to create FoundryChatClient: %s", e)
            raise

        # Create a separate client for the orchestrator manager using a
        # dedicated orchestrator model (gpt-5.4-mini) — much more reliable at
        # structured JSON output and multi-step routing decisions.
        orchestrator_model = config.ORCHESTRATOR_MODEL_NAME
        try:
            manager_chat_client = FoundryChatClient(
                project_endpoint=config.AZURE_AI_PROJECT_ENDPOINT,
                model=orchestrator_model,
                credential=credential,
            )
            cls.logger.warning(
                "Manager model: '%s' (participants use '%s')",
                orchestrator_model, team_config.deployment_name,
            )
        except Exception as e:
            cls.logger.warning(
                "Failed to create manager client with '%s', falling back to '%s': %s",
                orchestrator_model, team_config.deployment_name, e,
            )
            manager_chat_client = chat_client

        # Detect whether any agent supports user interaction
        has_user_responses = any(
            getattr(ag, "user_responses", False) for ag in agents
        ) or any(
            getattr(ag, "user_responses", False)
            for ag in getattr(team_config, "agents", [])
        )

        manager_agent = Agent(manager_chat_client, name="MagenticManager")

        # Collect participant agent names so the orchestrator plan prompt can
        # enforce mandatory inclusion of every team agent (e.g. TriageAgent,
        # ComplianceAgent) — otherwise the manager silently drops them. A team
        # whose agents are alternatives rather than a pipeline opts out with
        # `require_all_agents: false`; see `mandatory_participants` (#54).
        participant_agent_names = []
        for ag in agents:
            nm = getattr(ag, "agent_name", None) or getattr(ag, "name", None)
            if nm:
                participant_agent_names.append(nm)

        required_agent_names = mandatory_participants(
            team_config, participant_agent_names)
        if not required_agent_names and participant_agent_names:
            cls.logger.info(
                "Team '%s' opts out of mandatory agent inclusion: the manager "
                "may plan a single step for %s",
                getattr(team_config, "name", "?"), participant_agent_names,
            )

        # Get prompt customization kwargs
        prompt_kwargs = get_magentic_prompt_kwargs(
            has_user_responses=has_user_responses,
            participant_names=required_agent_names,
            minimal_plan=plans_minimally(
                team_config, participant_agent_names),
        )

        cls.logger.info(
            "Building MagenticBuilder for user '%s' with max_rounds=%d, "
            "enable_plan_review=%s, has_user_responses=%s",
            user_id, orchestration_config.max_rounds, plan_review, has_user_responses,
        )

        # Build participant list (unwrap AgentTemplate._agent)
        participant_list = []
        for ag in agents:
            name = getattr(ag, "agent_name", None) or getattr(ag, "name", None)
            if not name:
                name = f"agent_{len(participant_list) + 1}"
            inner = getattr(ag, "_agent", None) or ag
            participant_list.append(inner)
            cls.logger.debug("Added participant '%s'", name)

        # MagenticBuilder config:
        #   enable_plan_review=True  → emits request_info events with MagenticPlanReviewRequest
        #   enable_plan_review=False → the Fast lane: no plan is generated and
        #                              nothing is approved
        #   intermediate_outputs=True → streams AgentResponseUpdate per token
        #   Both request_info event types (plan review + function_approval_request)
        #   pause the workflow in IDLE_WITH_PENDING_REQUESTS until responses are provided.
        storage = InMemoryCheckpointStorage()
        workflow = MagenticBuilder(
            participants=participant_list,
            manager_agent=manager_agent,
            max_round_count=orchestration_config.max_rounds,
            max_stall_count=5,
            checkpoint_storage=storage,
            output_from="all",
            enable_plan_review=plan_review,
            **prompt_kwargs,
        ).build()

        cls.logger.info(
            "Built Magentic workflow with %d participants (plan review %s)",
            len(participant_list), "enabled" if plan_review else "disabled",
        )

        # Attach context needed for the pre-planning team-scope gate
        # (see run_orchestration → _evaluate_team_scope). Stored on the workflow
        # so the gate can classify a request against this team's agents/data
        # without rebuilding a chat client.
        workflow._team_config = team_config
        workflow._manager_chat_client = manager_chat_client

        # Tags the two cache predicates read back off a cached Workflow — the
        # Full workflow rebuild predicate below and the cache-invalidation
        # predicate in api/router.py. Both were already reading _team_id;
        # nothing assigned it, so every request rebuilt the whole agent pool.
        workflow._team_id = getattr(team_config, "team_id", None)
        workflow._plan_review = plan_review

        return workflow

    # ---------------------------
    # Orchestration retrieval
    # ---------------------------
    @classmethod
    async def get_current_or_new_orchestration(
        cls,
        user_id: str,
        team_config: TeamConfiguration,
        team_switched: bool,
        team_service: Optional[TeamService] = None,
        plan_review: bool = True,
    ):
        """
        Return an existing workflow for the user or create a new one if:
          - None exists
          - Team switched flag is True
          - The cached workflow was built for the other lane, i.e. with a
            different plan_review value (ADR-013)

        When a previous workflow has completed (_terminated), we reuse the
        existing agent pool and only rebuild the workflow shell (Option 3).
        Full agent teardown only happens on explicit team switch.
        """
        current = orchestration_config.get_current_orchestration(user_id)
        workflow_terminated = getattr(current, "_terminated", False)

        # Detect a stale cached orchestration: it was built for a different team
        # than the one now selected. Without this, /select_team leaves the prior
        # team's workflow cached and the next run executes the wrong agents until
        # a page refresh rebuilds it. The team_id tag is set on every workflow we
        # build/reset below.
        current_team_id = getattr(current, "_team_id", None)
        team_changed = (
            current is not None and current_team_id != team_config.team_id
        )

        # Detect a cached orchestration built for the other lane. A Workflow
        # created for an earlier request must not silently ignore this request's
        # per-request value.
        current_plan_review = getattr(current, "_plan_review", None)
        plan_review_changed = (
            current is not None and current_plan_review != plan_review
        )

        cls.logger.info(
            "get_current_or_new_orchestration: user='%s' selected_team='%s' "
            "cached_team='%s' team_switched=%s team_changed=%s current_is_none=%s "
            "plan_review=%s cached_plan_review=%s plan_review_changed=%s",
            user_id, team_config.team_id, current_team_id,
            team_switched, team_changed, current is None,
            plan_review, current_plan_review, plan_review_changed,
        )

        # Full rebuild: no workflow exists, team explicitly switched, the cached
        # workflow belongs to a different team than the selected one, or it was
        # built for the other lane.
        needs_full_rebuild = (
            current is None or team_switched or team_changed or plan_review_changed
        )

        # Lightweight reset: workflow finished but agents are still valid for the
        # same team (a team change always routes to full rebuild above so we
        # never reuse the previous team's agents here).
        needs_workflow_reset = not needs_full_rebuild and workflow_terminated

        if needs_full_rebuild:
            if current is not None:
                cls.logger.info(
                    "Replacing workflow (team switched), closing previous agents for user '%s'",
                    user_id,
                )
                # Close prior agents — only on team switch
                for executor in current.get_executors_list():
                    agent = getattr(executor, "agent", executor)
                    agent_name = getattr(agent, "name", "") or getattr(executor, "id", "")
                    close_coro = getattr(agent, "close", None)
                    if callable(close_coro):
                        try:
                            result = close_coro()
                            if asyncio.iscoroutine(result):
                                await result
                            cls.logger.debug("Closed agent '%s'", agent_name)
                        except Exception as e:
                            cls.logger.error("Error closing agent: %s", e)

            assert team_service is not None, "team_service required for agent creation"
            memory_ctx = team_service.memory_context
            assert memory_ctx is not None, "memory_context required for agent creation"
            factory = AgentFactory(team_service=team_service)
            try:
                agents = await factory.get_agents(
                    user_id=user_id,
                    team_config_input=team_config,
                    memory_store=memory_ctx,
                )
                cls.logger.info("Created %d agents for user '%s'", len(agents), user_id)
            except asyncio.CancelledError:
                cls.logger.info(
                    "Workflow construction cancelled while creating agents for user '%s'.",
                    user_id,
                )
                await factory.close_all()
                raise
            except Exception as e:
                cls.logger.error(
                    "Failed to create agents for user '%s': %s", user_id, e
                )
                print(f"Failed to create agents for user '{user_id}': {e}")
                raise
            try:
                cls.logger.info("Initializing new orchestration for user '%s'", user_id)
                orchestration_config.orchestrations[user_id] = (
                    await cls.init_orchestration(
                        agents, team_config, memory_ctx, user_id,
                        plan_review=plan_review,
                    )
                )
            except asyncio.CancelledError:
                cls.logger.info(
                    "Workflow construction cancelled while initializing user '%s'.",
                    user_id,
                )
                await factory.close_all()
                raise
            except Exception as e:
                cls.logger.error(
                    "Failed to initialize orchestration for user '%s': %s", user_id, e
                )
                print(f"Failed to initialize orchestration for user '{user_id}': {e}")
                raise

        elif needs_workflow_reset:
            cls.logger.info(
                "Workflow completed — resetting workflow shell, reusing agents for user '%s'",
                user_id,
            )
            # Extract existing participant agents from the workflow executors.
            # Skip the MagenticManager — it is recreated by init_orchestration.
            reusable_agents = [
                executor.agent
                for executor in current.get_executors_list()
                if hasattr(executor, "agent")
                and getattr(executor.agent, "name", "") != "MagenticManager"
            ]
            cls.logger.info(
                "Reusing %d agents for new workflow", len(reusable_agents),
            )

            assert team_service is not None, "team_service required for workflow reset"
            reset_memory_ctx = team_service.memory_context
            assert reset_memory_ctx is not None, "memory_context required for workflow reset"
            try:
                orchestration_config.orchestrations[user_id] = (
                    await cls.init_orchestration(
                        reusable_agents, team_config,
                        reset_memory_ctx, user_id,
                        plan_review=plan_review,
                    )
                )
            except Exception as e:
                cls.logger.error(
                    "Failed to reset orchestration for user '%s': %s", user_id, e
                )
                print(f"Failed to reset orchestration for user '{user_id}': {e}")
                raise

        return orchestration_config.get_current_orchestration(user_id)

    # ---------------------------
    # Execution
    # ---------------------------
    async def run_orchestration(
        self, user_id: str, input_task, address_name: str = ""
    ) -> None:
        """
        Execute the Magentic workflow for the provided user and task description.

        Follows the framework's recommended pattern for plan review:
        1. Run the workflow, streaming events until it idles with pending requests.
        2. Collect any ``MagenticPlanReviewRequest`` events emitted during the run.
        3. Present the plan to the user and wait for approval/rejection.
        4. Resume with ``workflow.run(responses={request_id: response})``.
        5. Repeat until the workflow completes with no pending requests.
        """
        job_id = str(uuid.uuid4())
        orchestration_config.set_approval_pending(job_id)
        self.logger.info(
            "Starting orchestration job '%s' for user '%s'", job_id, user_id
        )

        workflow = orchestration_config.get_current_orchestration(user_id)
        if workflow is None:
            raise ValueError("Orchestration not initialized for user.")

        # Build task from input
        task_text = getattr(input_task, "description", str(input_task))
        ticket_on_approval = self._task_requires_ticket_on_approval(
            workflow, input_task
        )
        plan_steps = self._task_plan_steps(workflow, input_task)
        self.logger.debug("Task: %s", task_text)
        # The associate's words feed every record and decision. Only the
        # manager's initial view receives the per-turn address.
        manager_task_text = task_text
        if address_name.strip():
            manager_task_text = (
                f"The associate you are speaking with is {address_name.strip()}.\n\n"
                f"Associate request:\n{task_text}"
            )

        # ---- Team-scope gate (generic, team-agnostic) -------------------

        scope = await self._evaluate_team_scope(workflow, task_text)
        if scope is not None and not scope.get("in_scope", True):
            self.logger.info(
                "Request judged OUT OF SCOPE for team; presenting single "
                "MagenticManager out-of-scope step (job='%s')", job_id,
            )

            team_agent_names = self._get_team_agent_names(workflow)
            await self._handle_out_of_scope(
                user_id=user_id,
                task_text=task_text,
                out_of_scope_message=scope.get("message", ""),
                team_agent_names=team_agent_names,
            )
            await self._cleanup_workflow_mcp(user_id)
            return

        try:
            final_output_ref: list = [None]
            orchestrator_chunks: list[str] = []
            current_streaming_agent_ref: list = [None]

            # Collect participant names for plan conversion
            participant_names = [
                executor.id
                for executor in workflow.get_executors_list()
            ]
            self.logger.info("Participant names: %s", participant_names)

            self.logger.info("Starting workflow execution...")
            plan_already_approved = False
            # The Reviewable plan's lineage for this run. It survives each turn
            # of the resume loop, because a plan sent back twice is revision 3
            # and says so (#108).
            revision = PlanRevision()

            # Initial run — stream events, collect any pending requests
            pending = await self._process_event_stream(
                workflow.run(manager_task_text, stream=True),
                user_id=user_id,
                final_output_ref=final_output_ref,
                orchestrator_chunks=orchestrator_chunks,
                current_streaming_agent_ref=current_streaming_agent_ref,
            )

            # Resume loop — handle plan reviews and tool approvals until workflow completes
            while pending:
                plan_requests = pending.get("plan_reviews", {})
                tool_approvals = pending.get("tool_approvals", {})

                responses = {}

                # Handle plan reviews (present to user, wait for the verdict)
                if plan_requests:
                    if plan_already_approved:
                        self.logger.info(
                            "Auto-approving replanned workflow"
                        )
                        plan_responses = {
                            request_id: plan_review.approve()
                            for request_id, plan_review in plan_requests.items()
                        }
                    else:
                        self.logger.info(
                            "Workflow paused with %d plan review request(s)",
                            len(plan_requests),
                        )
                        outcome = await self._handle_plan_reviews(
                            plan_requests,
                            participant_names=participant_names,
                            task_text=task_text,
                            user_id=user_id,
                            ticket_on_approval=ticket_on_approval,
                            plan_steps=plan_steps,
                            associate_name=address_name.strip(),
                            manager_chat_client=getattr(
                                workflow, "_manager_chat_client", None
                            ),
                            revision=revision,
                        )
                        revision = outcome.revision
                        if outcome.responses is None:
                            # No verdict arrived — a timeout or a socket that
                            # went away. The associate has already been told,
                            # and there is nothing to resume the workflow with,
                            # so the run stops here. It is not an error and it
                            # destroys nothing: a plan sent back would have
                            # carried a revise response instead.
                            self.logger.info(
                                "No verdict on the plan — ending the run "
                                "(job='%s')", job_id,
                            )
                            return

                        # Only a real approval turns the gate off. A revised
                        # plan is a plan the associate has not seen yet.
                        plan_already_approved = outcome.approved
                        plan_responses = outcome.responses

                    responses.update(plan_responses)

                # Handle tool approval requests (clarification from user)
                if tool_approvals:
                    self.logger.info(
                        "Workflow paused with %d tool approval request(s)",
                        len(tool_approvals),
                    )
                    approval_responses = await self._handle_tool_approvals(
                        tool_approvals,
                        user_id=user_id,
                        # The same authored fact that makes the approval raise
                        # the ticket bounds what the turn may ask about it
                        # (#62): read once, carried, never derived twice.
                        asks_the_associate_nothing=ticket_on_approval,
                    )
                    if approval_responses is None:
                        await self._end_turn_after_expired_clarification(user_id)
                        return
                    responses.update(approval_responses)

                self.logger.info(
                    "Resuming workflow with %d response(s)",
                    len(responses),
                )

                # Resume the workflow with the collected responses
                pending = await self._process_event_stream(
                    workflow.run(stream=True, responses=responses),
                    user_id=user_id,
                    final_output_ref=final_output_ref,
                    orchestrator_chunks=orchestrator_chunks,
                    current_streaming_agent_ref=current_streaming_agent_ref,
                )

            # Use executor_completed Message if available; otherwise fall back to
            # accumulated orchestrator streaming chunks.
            final_text = final_output_ref[0] or "".join(orchestrator_chunks)

            # Repair collapsed markdown tables before rendering (Bug 47810).
            final_text = _normalize_markdown_tables(final_text)

            final_text = _embed_bare_image_urls(final_text)

            # Issue 1 diagnostic: confirm the final answer carries a renderable image
            # embed. has_image_markdown tracks TRUE markdown (![]) — the renderable form;
            # has_image_url tracks any image reference, even a bare URL.
            final_source = "executor" if final_output_ref[0] else "chunks"
            has_image_markdown = "![" in final_text
            has_image_url = "/api/v4/images/" in final_text
            self.logger.info(
                "[FINAL-ASSEMBLY] job=%s user=%s source=%s len=%d "
                "has_image_markdown=%s has_image_url=%s",
                job_id, user_id, final_source, len(final_text),
                has_image_markdown, has_image_url,
            )

            # Log results
            self.logger.info("\nAgent responses:")
            self.logger.info(
                "Orchestration completed. Final result length: %d chars",
                len(final_text),
            )
            self.logger.info("\nFinal result:\n%s", final_text)
            self.logger.info("=" * 50)

            # Send final result via WebSocket
            await connection_config.send_status_update_async(
                {
                    "type": WebsocketMessageType.FINAL_RESULT_MESSAGE,
                    "data": {
                        "content": final_text,
                        "status": "completed",
                        "timestamp": asyncio.get_event_loop().time(),
                    },
                },
                user_id,
                message_type=WebsocketMessageType.FINAL_RESULT_MESSAGE,
            )
            self.logger.info("Final result sent via WebSocket to user '%s'", user_id)

        except Exception as e:
            # Error handling
            self.logger.error("Unexpected orchestration error: %s", e, exc_info=True)
            self.logger.error("Error type: %s", type(e).__name__)
            if hasattr(e, "__dict__"):
                self.logger.error("Error attributes: %s", e.__dict__)
            self.logger.info("=" * 50)

            # Send error status to user
            try:
                await connection_config.send_status_update_async(
                    {
                        "type": WebsocketMessageType.FINAL_RESULT_MESSAGE,
                        "data": {
                            "content": f"Error during orchestration: {str(e)}",
                            "status": "error",
                            "timestamp": asyncio.get_event_loop().time(),
                        },
                    },
                    user_id,
                    message_type=WebsocketMessageType.FINAL_RESULT_MESSAGE,
                )
            except Exception as send_error:
                self.logger.error("Failed to send error status: %s", send_error)
            raise

        finally:
            # Clean up MCP connections to avoid noisy cross-task
            # RuntimeError from anyio when async generators are GC'd.
            await self._cleanup_workflow_mcp(user_id)

    async def _cleanup_workflow_mcp(self, user_id: str) -> None:
        """Close MCP async-generator contexts for the finished workflow."""
        workflow = orchestration_config.get_current_orchestration(user_id)
        if workflow is None:
            return

        # Mark workflow as terminated so next request creates a fresh one
        workflow._terminated = True

    # ---------------------------
    # Team-scope gate
    # ---------------------------
    async def _evaluate_team_scope(self, workflow, task_text: str) -> Optional[dict]:
        """Classify whether ``task_text`` is within the current team's scope.

        The decision is made by a focused single-purpose classifier call using
        the manager chat client, given the team's purpose, its agents (and the
        data/knowledge each works on), and representative example tasks. This is
        deliberately separate from the planning prompt so the strict scope
        decision is not diluted by the "include every agent" planning rules.

        Returns:
            ``{"in_scope": bool, "message": str}`` when the classification
            succeeds, or ``None`` when it cannot be evaluated (missing context or
            an error) — in which case the caller proceeds normally (fail-open).
        """
        team_config = getattr(workflow, "_team_config", None)
        chat_client = getattr(workflow, "_manager_chat_client", None)
        if team_config is None or chat_client is None or not task_text:
            return None

        try:
            agent_lines = []
            for ag in getattr(team_config, "agents", []) or []:
                name = getattr(ag, "name", "") or ""
                desc = getattr(ag, "description", "") or ""
                data = getattr(ag, "knowledge_base_name", "") or ""
                line = f"- {name}: {desc}"
                if data:
                    line += f" (works on data: {data})"
                agent_lines.append(line)
            agents_block = "\n".join(agent_lines) or "- (no agents listed)"

            example_lines = []
            for t in getattr(team_config, "starting_tasks", []) or []:
                tname = getattr(t, "name", "") or ""
                tprompt = getattr(t, "prompt", "") or ""
                example_lines.append(f"- {tname}: {tprompt}".strip())
            examples_block = "\n".join(example_lines) or "- (none provided)"

            system_prompt = (
                "You are a strict feasibility classifier for a specialized "
                "multi-agent team. Decide whether a user's request can actually be "
                "fulfilled by THIS team — considering BOTH (A) its specialization "
                "and (B) what its agents are actually able to DO.\n\n"
                "A team is defined ENTIRELY by its stated purpose, the specific "
                "agents it has and what each does, the data/knowledge those agents "
                "work with, and its representative example tasks.\n\n"
                "Rules:\n"
                "- IN SCOPE only if the request clearly matches this team's "
                "specialization AND the requested action is something these agents "
                "can actually perform with their described capabilities and data.\n"
                "- OUT OF SCOPE (kind=\"domain\") if the request belongs to a "
                "DIFFERENT specialization, even when superficially related or in a "
                "broadly similar field (e.g. drafting a product press release is NOT "
                "the same specialization as generating retail social-media content; "
                "HR onboarding is NOT product marketing; contract/NDA compliance is "
                "NOT RFP evaluation).\n"
                "- OUT OF SCOPE (kind=\"capability\") if the request asks the team to "
                "perform an ACTION its agents cannot actually do. Agents generally "
                "only retrieve, look up, analyze, summarize, or generate content "
                "using their data. Unless an agent's description EXPLICITLY says it "
                "can do so, the team CANNOT delete, erase, purge, remove, modify, "
                "update, overwrite, or otherwise change stored data, and cannot "
                "execute real-world side effects (place/cancel orders, send emails, "
                "make payments, provision/deactivate accounts). Treat such requests "
                "as OUT OF SCOPE — never let the team pretend it performed a "
                "destructive or state-changing action it cannot actually perform.\n"
                "- If the request is genuinely ambiguous or a reasonable subset of "
                "the example tasks, treat it as IN SCOPE.\n\n"
                "Respond with ONLY a compact JSON object and nothing else:\n"
                '{"in_scope": true|false, "kind": "domain"|"capability"|"", '
                '"reason": "<one sentence>", '
                '"message": "<empty string if in scope; otherwise a short, polite '
                "message. If kind=domain, say the request is outside this team's "
                "scope and the user should switch to the appropriate team and try "
                "again. If kind=capability, say this team cannot perform the "
                "requested action (e.g. deleting or modifying stored data) and can "
                "only help with the kinds of tasks its agents support; make clear "
                "that NO data was changed. In both cases: do NOT name, recommend, or "
                'guess any specific team; do NOT list what this team specializes in>"}'
            )
            user_prompt = (
                f"TEAM NAME: {getattr(team_config, 'name', '')}\n"
                f"TEAM PURPOSE: {getattr(team_config, 'description', '')}\n\n"
                f"AGENTS:\n{agents_block}\n\n"
                f"EXAMPLE IN-SCOPE TASKS:\n{examples_block}\n\n"
                f"USER REQUEST:\n{task_text}"
            )

            response = await chat_client.get_response(
                [Message("system", [system_prompt]),
                 Message("user", [user_prompt])]
            )
            raw = (getattr(response, "text", "") or "").strip()
            self.logger.info("[SCOPE-GATE] classifier raw response: %s", raw[:500])

            parsed = self._parse_scope_json(raw)
            if parsed is None:
                self.logger.warning(
                    "[SCOPE-GATE] Could not parse classifier output — proceeding "
                    "normally (fail-open)."
                )
                return None

            in_scope = bool(parsed.get("in_scope", True))
            kind = str(parsed.get("kind", "") or "").strip().lower()
            message = str(parsed.get("message", "") or "").strip()
            if not in_scope and not message:
                if kind == "capability":
                    message = (
                        "This team is not able to perform the requested action "
                        "(such as deleting or modifying stored data). No data has "
                        "been changed. It can only help with the kinds of tasks its "
                        "agents support. Please try a supported request instead."
                    )
                else:
                    message = (
                        "This request appears to be outside the scope of the "
                        "selected team, so it cannot be handled reliably here. "
                        "Please switch to the appropriate team and try again."
                    )
            self.logger.info(
                "[SCOPE-GATE] in_scope=%s kind=%s reason=%s",
                in_scope, kind, parsed.get("reason", ""),
            )
            return {"in_scope": in_scope, "message": message}
        except Exception as e:  # fail-open: never block a task on classifier error
            self.logger.warning(
                "[SCOPE-GATE] Scope evaluation failed (%s) — proceeding normally.", e
            )
            return None

    @staticmethod
    def _parse_scope_json(text: str) -> Optional[dict]:
        """Extract the first JSON object from a classifier response."""
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(
                ln for ln in cleaned.splitlines() if not ln.strip().startswith("```")
            ).strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except (json.JSONDecodeError, ValueError):
                return None
        return None

    @staticmethod
    def _get_team_agent_names(workflow) -> list[str]:
        """Return the plan ``team`` roster for the frontend "Agent Team" panel.

        Mirrors the normal plan exactly: ``run_orchestration`` builds its
        ``participant_names`` from ``workflow.get_executors_list()`` executor ids
        (which include the ``magentic_orchestrator`` shown as "Magentic
        Orchestrator"). Using the same source keeps the out-of-scope Agent Team
        identical to a normal plan's. Falls back to the stored team config's
        agent names when executors are unavailable.
        """
        try:
            names = [
                executor.id
                for executor in workflow.get_executors_list()
                if getattr(executor, "id", "")
            ]
            if names:
                return names
        except Exception as exc:
            OrchestrationManager.logger.debug(
                "Failed to read executor names from workflow; falling back to team config: %s",
                exc,
                exc_info=True,
            )

        team_config = getattr(workflow, "_team_config", None)
        return [
            getattr(ag, "name", "")
            for ag in getattr(team_config, "agents", []) or []
            if getattr(ag, "name", "")
        ]

    async def _handle_out_of_scope(
        self,
        *,
        user_id: str,
        task_text: str,
        out_of_scope_message: str,
        team_agent_names: Optional[list[str]] = None,
    ) -> None:
        """Present a single MagenticManager out-of-scope step for approval, then
        deliver the out-of-scope notice as the final answer (no agents run)."""
        from models.plan_models import MPlan, MStep

        message = out_of_scope_message or (
            "This request appears to be outside the scope of the selected team. "
            "Please switch to the appropriate team and try again."
        )

        team = list(team_agent_names) if team_agent_names else ["MagenticManager"]

        mplan = MPlan()
        mplan.user_id = user_id
        mplan.user_request = task_text
        mplan.team = team
        mplan.steps = [
            MStep(
                agent="MagenticManager",
                action=(
                    "Inform the user that this request cannot be handled by the "
                    "selected team — either because it falls outside the team's "
                    "scope or because the team's agents cannot perform the "
                    "requested action (such as deleting or modifying data) — and "
                    "that no data was changed."
                ),
            )
        ]

        try:
            orchestration_config.plans[mplan.id] = mplan
        except Exception as e:
            self.logger.error("Error storing out-of-scope plan: %s", e)

        approval_message = messages.PlanApprovalRequest(
            plan=mplan,
            status="PENDING_APPROVAL",  # type: ignore[arg-type]
            context={"task": task_text, "out_of_scope": True},
        )
        await connection_config.send_status_update_async(
            message=approval_message,
            user_id=user_id,
            message_type=WebsocketMessageType.PLAN_APPROVAL_REQUEST,
        )

        approval_response = await wait_for_plan_approval(mplan.id, user_id)

        if approval_response and approval_response.approved:
            self.logger.info("Out-of-scope plan approved — sending final notice.")
            await asyncio.sleep(1.5)
            await connection_config.send_status_update_async(
                {
                    "type": WebsocketMessageType.FINAL_RESULT_MESSAGE,
                    "data": {
                        "content": message,
                        "status": "completed",
                        "timestamp": asyncio.get_event_loop().time(),
                    },
                },
                user_id,
                message_type=WebsocketMessageType.FINAL_RESULT_MESSAGE,
            )
        else:
            self.logger.info("Out-of-scope plan rejected by user.")
            await connection_config.send_status_update_async(
                {
                    "type": WebsocketMessageType.PLAN_APPROVAL_RESPONSE,
                    "data": approval_response,
                },
                user_id=user_id,
                message_type=WebsocketMessageType.PLAN_APPROVAL_RESPONSE,
            )

    # ---------------------------
    # Plan review handling
    # ---------------------------
    async def _handle_plan_reviews(
        self,
        plan_requests: dict[str, "MagenticPlanReviewRequest"],
        *,
        participant_names: list[str],
        task_text: str,
        user_id: str,
        ticket_on_approval: bool = False,
        plan_steps: list | None = None,
        associate_name: str = "",
        manager_chat_client=None,
        revision: PlanRevision | None = None,
    ) -> PlanReviewOutcome:
        """Present collected plan review requests and gather the verdicts.

        The verdict is binary (#108). An approval settles the plan; anything
        else is a **send-back**, which folds the associate's feedback into the
        framework's ``revise`` path so the orchestrator replans and re-issues
        the review **on the same run**. There is no reject: the plan document
        is never removed and the conversation never ends on a disagreement.

        Args:
            revision: the lineage carried from earlier verdicts on this run, so
                the plan the associate sees says which revision it is.

        Returns:
            A ``PlanReviewOutcome``. ``responses`` is ``None`` only when no
            verdict arrived at all — a timeout or a dropped socket, which is
            not a verdict and leaves the run nothing to resume with.
        """
        revision = revision or PlanRevision()
        responses: dict = {}
        verdicts: list = []
        approved_all = True

        for request_id, plan_review in plan_requests.items():
            self.logger.info(
                "[PLAN_REVIEW] Presenting plan to user (request_id=%s, revision=%d)",
                request_id, revision.number,
            )

            # Convert to MPlan for frontend display
            mplan = convert_plan_review_to_mplan(
                plan_review,
                participant_names=participant_names,
                task_text=task_text,
                user_id=user_id,
            )
            # The lineage travels with the plan, so the surface can tell a
            # fresh plan from one the associate already sent back, and show
            # what they asked to change.
            mplan.revision = revision.number
            mplan.revision_feedback = list(revision.feedback)
            if plan_steps is not None:
                from models.plan_models import MStep

                mplan.steps = [
                    step if isinstance(step, MStep) else MStep.model_validate(step)
                    for step in plan_steps
                ]

            # Store plan
            try:
                orchestration_config.plans[mplan.id] = mplan
            except Exception as e:
                self.logger.error("Error storing plan: %s", e)

            # Send approval request to frontend via WebSocket
            approval_message = messages.PlanApprovalRequest(
                plan=mplan,
                status="PENDING_APPROVAL",  # type: ignore[arg-type]
                context={"task": task_text},
            )
            await connection_config.send_status_update_async(
                message=approval_message,
                user_id=user_id,
                message_type=WebsocketMessageType.PLAN_APPROVAL_REQUEST,
            )

            # Wait for the associate's verdict
            approval_response = await wait_for_plan_approval(mplan.id, user_id)

            if approval_response is None:
                self.logger.info(
                    "No verdict on the plan (request_id=%s) — nothing to resume with",
                    request_id,
                )
                return PlanReviewOutcome(
                    responses=None, revision=revision, approved=False
                )

            if approval_response.approved:
                self.logger.info("Plan approved (request_id=%s)", request_id)
                responses[request_id] = plan_review.approve()
                # The approval step **is** the ticket confirmation (issue #22,
                # TKT-001). Deterministic and here, not a tool the agent is
                # asked to call afterwards: a model that forgets leaves the
                # associate believing a ticket was raised, and a submit tool
                # the model *can* call is the second confirmation step the
                # template says there is not. Most approved plans are not
                # escalations, and those raise nothing — see ``_ticket_store``.
                await self._raise_confirmed_ticket(
                    user_id,
                    draft_from_record=ticket_on_approval,
                )
                person_steps = self._post_approval_person_steps(mplan)
                if person_steps:
                    resolved_verdicts = await self._resolve_person_steps(
                        person_steps,
                        associate_name=associate_name,
                        manager_chat_client=manager_chat_client,
                    )
                    mplan.verdicts = resolved_verdicts
                    verdicts.extend(resolved_verdicts)
                continue

            feedback = getattr(approval_response, "feedback", None) or ""
            try:
                revision = revision.sent_back(feedback)
            except ValueError:
                # The endpoint refuses a send-back with nothing asked, so this
                # is a verdict no client of ours can produce. Ask for the plan
                # again rather than resuming with a response the framework
                # would read as an approval.
                self.logger.warning(
                    "Plan sent back with nothing asked (request_id=%s)", request_id
                )
                return PlanReviewOutcome(
                    responses=None, revision=revision, approved=False
                )

            self.logger.info(
                "Plan sent back for revision %d (request_id=%s)",
                revision.number, request_id,
            )
            approved_all = False
            responses[request_id] = plan_review.revise(feedback)
            await connection_config.send_status_update_async(
                {
                    "type": WebsocketMessageType.PLAN_APPROVAL_RESPONSE,
                    "data": approval_response,
                },
                user_id=user_id,
                message_type=WebsocketMessageType.PLAN_APPROVAL_RESPONSE,
            )

        return PlanReviewOutcome(
            responses=responses or None,
            revision=revision,
            approved=bool(responses) and approved_all,
            verdicts=verdicts,
        )

    @staticmethod
    def _post_approval_person_steps(plan) -> list:
        """Return non-associate Person steps in their declared dependency order.

        The plan's own steps choose the post-approval mechanism (#151,
        ADR-042). A Person step assigned to somebody other than the associate
        is the only thing that creates waiting; the associate's own
        confirmation step is satisfied by the approval that got here. Nothing
        below reads the workflow's name, the task id or the lane, so the
        Simulated ticket — whose plan has no such step — reaches no executor at
        all rather than declining to use one, which is what keeps *there is no
        submit tool* (#21) closed by construction.

        The whole plan is ordered before it is filtered: `waitsOn` may name an
        agent step, so the peer's turn comes after the associate's confirmation
        even though only the peer records a Verdict.
        """
        steps = getattr(plan, "steps", None)
        if not isinstance(steps, list):
            return []

        unresolved = list(steps)
        step_ids = {
            step.id for step in steps
            if isinstance(getattr(step, "id", None), int)
        }
        resolved_ids: set[int] = set()
        ordered_steps = []

        while unresolved:
            ready = [
                step for step in unresolved
                if (
                    getattr(step, "waitsOn", None) is None
                    or getattr(step, "waitsOn") not in step_ids
                    or getattr(step, "waitsOn") in resolved_ids
                )
            ]
            if not ready:
                raise ValueError("Reviewable plan contains a waitsOn cycle")
            for step in ready:
                unresolved.remove(step)
                ordered_steps.append(step)
                if isinstance(getattr(step, "id", None), int):
                    resolved_ids.add(step.id)

        return [
            step for step in ordered_steps
            if (
                getattr(getattr(step, "assignee", None), "kind", None) == "person"
                and getattr(step.assignee, "relation", None) != "associate"
            )
        ]

    async def _resolve_person_steps(
        self,
        person_steps: list,
        *,
        associate_name: str,
        manager_chat_client,
    ) -> list:
        """Generate Verdict records for already-authored non-associate outcomes.

        ADR-038's split, one spec later: *whether* each person approves is
        authored on the Quick Task, and *what they say* rides the turn, so the
        beat is rehearsable and pinnable while the words differ run to run.

        The generation is also the pacing. Each verdict is a real request
        taking real time, so the gap between two of them reports something that
        happened (ADR-023) — there is no sleep here and nothing to tune. This
        path never enters the clarification seam: that seam times out at 300s
        and auto-approves with a synthetic answer (#87), which in this beat
        would let a stalled demonstration fabricate a person's approval out of
        nothing at all.

        Both guards below are unreachable from real input — `TeamService`
        refuses an authored Person step missing either fact, a generated plan
        carries no assignees, and the chat client is attached to every
        workflow. They fail loudly rather than substituting a fallback,
        because a person's words invented outside this call is exactly the
        thing the Provenance line on the record could not then disclose.
        """
        if manager_chat_client is None:
            raise RuntimeError("Manager chat client is required to resolve Person steps")

        from models.plan_models import Verdict

        verdicts = []
        for step in person_steps:
            outcome = getattr(step, "outcome", None)
            if outcome is None:
                raise ValueError(
                    f"Person step {getattr(step, 'id', '?')} has no authored outcome"
                )

            assignee = step.assignee
            action = (getattr(step, "action", "") or "").strip().rstrip(".")
            response = await manager_chat_client.get_response(
                [
                    Message(
                        "system",
                        [
                            "Write a brief, natural first-person reply from a "
                            "person who has just been asked to do something in "
                            "a workflow an associate approved. Their decision "
                            "is already made; put it in their own words and do "
                            "not change it."
                        ],
                    ),
                    Message(
                        "user",
                        [
                            f"{assignee.name} is the {assignee.relation}. "
                            + (f"They were asked to: {action}. " if action else "")
                            + "Their authored decision is "
                            f"{getattr(outcome, 'value', outcome)}. "
                            + (
                                f"Address the associate as {associate_name}. "
                                if associate_name
                                else ""
                            )
                            + "Write only their response."
                        ],
                    ),
                ]
            )
            words = str(getattr(response, "text", "") or "").strip()
            if not words:
                raise ValueError(
                    f"Manager generated no words for Person step {getattr(step, 'id', '?')}"
                )
            verdicts.append(
                Verdict(
                    step_id=step.id,
                    assignee=assignee,
                    outcome=outcome,
                    words=words,
                )
            )
        return verdicts

    def _task_requires_ticket_on_approval(self, workflow, input_task) -> bool:
        """Whether this request names the active team's ticketing task.

        The browser may carry a task identifier, but its behavior remains
        server-owned: only a matching task in the workflow's attached team
        configuration can request deterministic ticket drafting.
        """
        task_id = getattr(input_task, "starting_task_id", None)
        team_config = getattr(workflow, "_team_config", None)
        tasks = getattr(team_config, "starting_tasks", None)
        if not isinstance(task_id, str) or not task_id or not isinstance(tasks, list):
            return False

        for task in tasks:
            if getattr(task, "id", None) == task_id:
                return bool(getattr(task, "ticket_on_approval", False))

        self.logger.warning(
            "[TICKET] Request named unknown starting task '%s' — no ticket "
            "will be drafted",
            task_id,
        )
        return False

    def _task_plan_steps(self, workflow, input_task) -> list | None:
        """Return the active Quick Task's authored Reviewable plan steps.

        The browser can name a Quick Task but cannot choose its people or
        ordering. Those facts belong to the active team's content pack.
        ``None`` means no task declared an authored plan; an authored empty
        list remains empty and replaces generated steps.
        """
        task_id = getattr(input_task, "starting_task_id", None)
        team_config = getattr(workflow, "_team_config", None)
        tasks = getattr(team_config, "starting_tasks", None)
        if not isinstance(task_id, str) or not task_id or not isinstance(tasks, list):
            return None

        for task in tasks:
            if getattr(task, "id", None) == task_id:
                plan_steps = getattr(task, "plan_steps", None)
                if not isinstance(plan_steps, list):
                    return None
                from models.plan_models import MStep

                return [MStep.model_validate(step) for step in plan_steps]

        return None

    async def _handle_tool_approvals(
        self,
        tool_approvals: dict[str, object],
        *,
        user_id: str,
        asks_the_associate_nothing: bool = False,
    ) -> dict | None:
        """Handle pending tool approval requests (HITL clarification).

        For each approval request:
        1. Decide whether it is a question for the associate at all.
        2. Send a USER_CLARIFICATION_REQUEST to the frontend via WebSocket.
        3. Wait for the user's answer via the clarification event infrastructure.
        4. Store the answer so the tool body can read it after approval.
        5. Approve the tool call and return the response.

        Steps 2 to 4 are skipped, and the call approved with nothing asked,
        when the pause puts no question to the associate — see
        ``orchestration.clarification`` — or when the whole turn asks them
        nothing.

        Args:
            asks_the_associate_nothing: this turn's questions are bounded at
                **zero** (#62). A **ticket-on-approval** task raises the
                **Simulated ticket** deterministically from the session's
                record at the approval seam, so nothing the associate could
                answer changes what the ticket says: the attempted steps run
                one way out of the record and every unreported field is
                written ``not reported``. A question whose answer changes
                nothing the associate can see implies the ticket is waiting on
                it, and on stage it is an interview nobody can rehearse.

        Returns:
            A ``{request_id: approval_response}`` dict, or ``None`` when a
            **Clarification** expired and the turn must end rather than resume.
        """
        import threading

        from orchestration.clarification import (NOT_ASKED,
                                                 clarification_questions)
        from tools.clarification_tool import store_answer

        responses = {}

        for request_id, content in tool_approvals.items():
            fn_call = content.function_call  # type: ignore[attr-defined]
            questions = clarification_questions(fn_call)

            # The framework pauses on every approval-gated tool call, and only
            # one of them is a question. A pause that asks nobody anything is
            # approved here and the associate never hears of it — which is
            # what ``require_approval="never"`` would have done, and is the
            # only reading under which the answer that comes back belongs to
            # the question that was asked.
            if questions is None:
                self.logger.info(
                    "[TOOL_APPROVAL] Approving '%s' without asking the "
                    "associate — it puts no question to them (request_id=%s)",
                    getattr(fn_call, "name", "?"),
                    request_id,
                )
                responses[request_id] = content.to_function_approval_response(  # type: ignore[attr-defined]
                    approved=True
                )
                continue

            # A real question, on a turn that asks none. The agent is *told*
            # the associate was not asked rather than left with the tool
            # body's "no answer was provided", which reads as a failure worth
            # retrying — and it is told nothing that could pass for something
            # the associate said.
            #
            # Stored under the thread key alone, which is the one the tool body
            # pops and therefore the one that is consumed. The clarification
            # path below also stores under ``request_id``, which nothing in the
            # backend reads: that copy survives its turn, and the body's last
            # resort pops *any* entry left in the store. One more such copy is
            # this turn's answer reaching a later question — and this copy says
            # the associate was not asked, on a turn where they were.
            if asks_the_associate_nothing:
                self.logger.info(
                    "[TOOL_APPROVAL] This turn asks the associate nothing — "
                    "the ticket is raised from the session's record "
                    "(request_id=%s, unasked=%s)",
                    request_id, questions[:120],
                )
                store_answer(
                    f"_clarification_{threading.current_thread().ident}",
                    NOT_ASKED,
                )
                responses[request_id] = content.to_function_approval_response(  # type: ignore[attr-defined]
                    approved=True
                )
                continue

            self.logger.info(
                "[TOOL_APPROVAL] Sending clarification to user (request_id=%s): %s",
                request_id, questions[:120],
            )

            # Register pending clarification
            orchestration_config.set_clarification_pending(request_id)

            # Send to frontend via WebSocket
            await connection_config.send_status_update_async(
                {
                    "type": WebsocketMessageType.USER_CLARIFICATION_REQUEST,
                    "data": {
                        "request_id": request_id,
                        "questions": questions,
                        "agent_name": getattr(fn_call, "name", "agent"),
                    },
                },
                user_id=user_id,
                message_type=WebsocketMessageType.USER_CLARIFICATION_REQUEST,
            )

            # Wait for user's answer (uses existing async event infrastructure)
            try:
                answer = await orchestration_config.wait_for_clarification(
                    request_id, timeout=300.0,
                )
            except asyncio.TimeoutError:
                self.logger.warning(
                    "[TOOL_APPROVAL] Timeout waiting for user answer (request_id=%s)",
                    request_id,
                )
                return None
            except Exception as e:
                self.logger.error(
                    "[TOOL_APPROVAL] Error waiting for answer (request_id=%s): %s",
                    request_id, e,
                )
                answer = f"Error receiving response: {e}"

            self.logger.info(
                "[TOOL_APPROVAL] Received answer (request_id=%s): %s",
                request_id, answer[:120],
            )

            # The associate's answer to *what have you already tried* is
            # persisted where it is **received** (issue #21). Framework
            # checkpoint state is in-memory and must not be relied on, and a
            # model that is merely asked to remember will sometimes not.
            answer = await self._remember_attempted_steps(user_id, answer)

            # Store the answer so the tool body can retrieve it after approval.
            # Store under request_id and also under a thread-local key that
            # the tool body uses as its primary lookup.
            store_answer(request_id, answer)
            thread_key = f"_clarification_{threading.current_thread().ident}"
            store_answer(thread_key, answer)

            # Approve the tool call
            approval = content.to_function_approval_response(approved=True)  # type: ignore[attr-defined]
            responses[request_id] = approval

        return responses

    async def _end_turn_after_expired_clarification(self, user_id: str) -> None:
        """End the active turn when its **Clarification** expires.

        The expiry occurs inside the orchestration task, so ``end_turn`` keeps
        that task running long enough to write `canceled` onto its Plan record.
        """
        from chat.turn import end_turn
        from common.database.database_factory import DatabaseFactory

        turn = orchestration_config.active_turn(user_id)
        if turn is None:
            raise RuntimeError(
                "An expired clarification requires an active turn to settle."
            )

        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        await end_turn(
            user_id=user_id,
            session_id=turn.session_id,
            memory_store=memory_store,
            orchestration=orchestration_config,
        )

    async def _ticket_store(self, user_id: str):
        """The ticket store for the session this user has in flight.

        Returns ``(store, session_id)``, or ``(None, None)``. The session is
        resolved **server-side** from the note the request path left
        (``troubleshooting.turn``), the same refusal to let a model carry an
        identifier that ``_troubleshooting_store`` takes — and sharper here: a
        mis-resolved session would submit one associate's draft against
        another associate's approval.
        """
        from common.database.database_factory import DatabaseFactory
        from escalation.store import TicketStore
        from troubleshooting.turn import turn_for

        session_id = turn_for(user_id)
        if not session_id:
            return None, None
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        return TicketStore(memory_store, user_id=user_id), session_id

    async def _raise_confirmed_ticket(
        self,
        user_id: str,
        *,
        draft_from_record: bool = False,
    ):
        """Submit this conversation's drafted ticket, if there is one, and put
        it on the surface.

        Total in the direction that matters. Every failure — no session, no
        draft, a container that would not take the write, anything unforeseen —
        produces *no ticket and no card*, and none of them costs the approval
        the associate has already given. The other direction is the one this
        whole package exists to prevent: a card claiming a ticket that no
        container holds, quoting a number the associate could read down a
        telephone.
        """
        try:
            store, session_id = await self._ticket_store(user_id)
            if store is None:
                return None

            if draft_from_record:
                record_store, record_session_id = await self._troubleshooting_store(
                    user_id
                )
                if record_store is None or record_session_id != session_id:
                    self.logger.warning(
                        "[TICKET] Could not resolve the troubleshooting record "
                        "for session '%s' — no ticket was raised",
                        session_id,
                    )
                    return None

                record = await record_store.read(record_session_id)
                ticket = await store.draft(
                    session_id,
                    {},
                    attempted=record.attempted,
                    equipment=record.equipment,
                )
                if ticket is None:
                    return None

            ticket = await store.submit(session_id)
            if ticket is None:
                return None

            from escalation.payloads import TicketRaised

            await connection_config.send_status_update_async(
                TicketRaised.from_fields(ticket.fields).to_dict(),
                user_id=user_id,
                message_type=WebsocketMessageType.TICKET_RAISED,
            )
            self.logger.info(
                "[TICKET] Confirmed by plan approval (session=%s, ticket=%s)",
                session_id,
                ticket.fields.get("ticket_id"),
            )
            return ticket
        except Exception as e:
            self.logger.warning(
                "[TICKET] Could not raise the confirmed ticket for user '%s': "
                "%s — no ticket was raised and nothing claims one was",
                user_id,
                e,
                exc_info=True,
            )
            return None

    async def _troubleshooting_store(self, user_id: str):
        """The attempted-steps store for the session this user has in flight.

        Returns ``(store, session_id)``, or ``(None, None)`` when the session
        cannot be resolved. The session is resolved **server-side** from the
        note the request path left (``troubleshooting.turn``) rather than from
        an identifier the model was asked to carry: a mis-copied one would
        write this associate's attempted steps onto another associate's fault.
        """
        from common.database.database_factory import DatabaseFactory
        from troubleshooting.store import TroubleshootingStore
        from troubleshooting.turn import turn_for

        session_id = turn_for(user_id)
        if not session_id:
            self.logger.info(
                "[TROUBLESHOOTING] No session in flight for user '%s' — this "
                "turn's attempted steps are not recorded",
                user_id,
            )
            return None, None
        memory_store = await DatabaseFactory.get_database(user_id=user_id)
        return TroubleshootingStore(memory_store, user_id=user_id), session_id

    async def _remember_attempted_steps(self, user_id: str, answer: str) -> str:
        """Persist what the answer reports trying, and hand the record back.

        Both halves ride this one seam deliberately. The **write** happens
        here because this is where the associate's report actually arrives, so
        it happens on every clarification turn rather than whenever a model
        remembers to record it. The **read** rides back on the answer because
        the tool body returns exactly what was stored, so the agent cannot
        proceed without having been told what it must not repeat.

        Failure is swallowed. The record is memory of one shift; the answer is
        the associate's. An unreachable container costs a repeated step, and
        raising here would cost the turn.
        """
        try:
            from troubleshooting.steps import parse_attempted_steps

            store, session_id = await self._troubleshooting_store(user_id)
            if store is None:
                return answer

            steps = parse_attempted_steps(answer)
            await store.record(session_id, steps)
            self.logger.info(
                "[TROUBLESHOOTING] Recorded %d attempted step(s) for session "
                "'%s'", len(steps), session_id,
            )
            note = await store.note(session_id)
            return f"{answer}\n\n{note}" if note else answer
        except Exception as exc:
            self.logger.warning(
                "[TROUBLESHOOTING] Could not record the attempted steps for "
                "user '%s': %s — the turn keeps its answer", user_id, exc,
            )
            return answer

    async def _emit_token_usage(
        self, executor_id: str, messages: list, user_id: str
    ) -> None:
        """Report what one executor's completed turn cost (issue #23).

        Silent when the framework reported no usage: ``token_usage`` returns
        ``None`` rather than a zero, because a zero on the Token meter is the
        claim *this agent was free*.

        Failure here is swallowed. The meter is a presentation surface; an
        answer must never be lost because its price could not be reported.
        """
        try:
            usage = token_usage(
                executor_id, format_agent_display_name(executor_id), messages
            )
            if usage is None:
                # Deliberately observable. Whether the framework reports the
                # manager's own usage on this event is not verified live, and
                # this line is how the first real run says so rather than the
                # meter simply being short an agent.
                self.logger.debug(
                    "[TOKENS] %s completed with no usage reported", executor_id
                )
                return
            await connection_config.send_status_update_async(
                usage,
                user_id,
                message_type=WebsocketMessageType.TOKEN_USAGE,
            )
        except Exception as usage_err:
            self.logger.error(
                "Error emitting token usage for %s: %s", executor_id, usage_err
            )

    async def _process_event_stream(
        self,
        stream,
        *,
        user_id: str,
        final_output_ref: list,
        orchestrator_chunks: list[str],
        current_streaming_agent_ref: list,
    ) -> dict | None:
        """Process a workflow event stream, collecting pending requests.

        Follows the framework sample pattern: consume all events, collect any
        ``MagenticPlanReviewRequest`` objects and ``function_approval_request``
        events, and break when the workflow reaches
        ``IDLE_WITH_PENDING_REQUESTS``. The caller is responsible for
        presenting plans/questions to the user and resuming the workflow.

        Returns:
            A dict with ``plan_reviews`` and/or ``tool_approvals`` keys if any
            were requested, or ``None`` if the stream completed normally.
        """
        plan_requests: dict[str, MagenticPlanReviewRequest] = {}
        tool_approvals: dict[str, object] = {}  # request_id -> event.data (Content)

        async for event in stream:
            try:
                data_type = type(event.data).__name__ if event.data is not None else "None"
                executor = getattr(event, "executor_id", None) or "?"
                self.logger.debug(
                    "[EVENT] type=%s  data_type=%s  executor=%s",
                    event.type, data_type, executor,
                )

                # -------------------------------------------------------
                # MAF request_info event #1: Plan review
                # Emitted by enable_plan_review=True when the orchestrator
                # produces a task plan. We collect it and present to the user.
                # -------------------------------------------------------
                if event.type == "request_info" and isinstance(event.data, MagenticPlanReviewRequest):
                    request_id = event.request_id
                    self.logger.info(
                        "[PLAN_REVIEW] Collected plan review request (request_id=%s)",
                        request_id,
                    )
                    plan_requests[request_id] = event.data

                # -------------------------------------------------------
                # MAF request_info event #2: Function approval (HITL)
                # Emitted by @tool(approval_mode=\"always_require\") when an
                # agent calls request_user_clarification. The framework pauses
                # and waits for us to approve/reject after getting the user's answer.
                # -------------------------------------------------------
                elif (
                    event.type == "request_info"
                    and getattr(event.data, "type", None) == "function_approval_request"
                ):
                    request_id = event.request_id
                    fn_name = (
                        getattr(event.data.function_call, "name", None)
                        if event.data.function_call else "?"
                    )
                    self.logger.info(
                        "[TOOL_APPROVAL] Collected approval request (tool=%s, request_id=%s)",
                        fn_name, request_id,
                    )
                    tool_approvals[request_id] = event.data

                # -------------------------------------------------------
                # Status — log when idle with pending requests
                # (stream will end naturally; do NOT break)
                # -------------------------------------------------------
                elif event.type == "status" and event.state is WorkflowRunState.IDLE_WITH_PENDING_REQUESTS:
                    self.logger.info(
                        "[STATUS] Workflow idle with %d plan review(s) + %d tool approval(s)",
                        len(plan_requests), len(tool_approvals),
                    )

                # Magentic orchestrator events (plan created, replanned, progress ledger)
                elif event.type == "magentic_orchestrator":
                    orch_event: MagenticOrchestratorEvent = event.data
                    self.logger.info(
                        "[ORCHESTRATOR:%s]", orch_event.event_type.value
                    )

                # Streaming output
                elif event.type == "output":
                    executor = event.executor_id or "unknown"
                    output_data = event.data

                    if isinstance(output_data, AgentResponseUpdate):
                        if executor == "magentic_orchestrator" and output_data.text:
                            orchestrator_chunks.append(output_data.text)

                        if (
                            executor != "magentic_orchestrator"
                            and executor != current_streaming_agent_ref[0]
                        ):
                            current_streaming_agent_ref[0] = executor
                            await connection_config.send_status_update_async(
                                AgentMessageStreaming(
                                    agent_name=format_agent_display_name(executor),
                                    content="",
                                    is_final=False,
                                ),
                                user_id,
                                message_type=WebsocketMessageType.AGENT_MESSAGE_STREAMING,
                            )

                        if executor != "magentic_orchestrator":
                            try:
                                await streaming_agent_response_callback(
                                    executor, output_data, False, user_id,
                                )
                            except Exception as cb_err:
                                self.logger.error(
                                    "Error in streaming callback for %s: %s",
                                    executor, cb_err,
                                )

                # Executor completed
                elif (
                    event.type == "executor_completed"
                    and isinstance(event.data, list)
                    and event.executor_id
                ):
                    agent_id = event.executor_id
                    # The Token meter's one insertion point (#23). A turn is
                    # over here and its cost is final, and every executor is
                    # metered — including the orchestrator, whose tokens are
                    # the architecture's own price.
                    await self._emit_token_usage(agent_id, event.data, user_id)
                    if agent_id == "magentic_orchestrator":
                        for msg in event.data:
                            if isinstance(msg, Message) and msg.text:
                                final_output_ref[0] = msg.text
                    else:
                        try:
                            # ``executor_completed`` is the framework signal
                            # that this specialist's output stream is over.
                            await streaming_agent_response_callback(
                                agent_id, None, True, user_id,
                            )
                        except Exception as cb_err:
                            self.logger.error(
                                "Error completing stream for %s: %s",
                                agent_id, cb_err,
                            )
                        for msg in event.data:
                            if isinstance(msg, Message) and msg.text:
                                try:
                                    agent_response_callback(
                                        agent_id, msg, user_id
                                    )
                                except Exception as cb_err:
                                    self.logger.error(
                                        "Error in agent callback for %s: %s",
                                        agent_id, cb_err,
                                    )
                        if agent_id == current_streaming_agent_ref[0]:
                            current_streaming_agent_ref[0] = None

            except Exception as e:
                if "cancelled by user" in str(e):
                    raise
                self.logger.error(
                    "Error processing event type=%s: %s",
                    getattr(event, "type", "?"), e,
                    exc_info=True,
                )

        # Stream fully consumed or broke on IDLE_WITH_PENDING_REQUESTS
        if plan_requests or tool_approvals:
            result = {}
            if plan_requests:
                result["plan_reviews"] = plan_requests
            if tool_approvals:
                result["tool_approvals"] = tool_approvals
            return result
        return None
