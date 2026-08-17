# Copyright (c) Microsoft. All rights reserved.
"""
WebSocket connection management and orchestration state configuration.

Extracted from v4/config/settings.py. Holds OrchestrationConfig, ConnectionConfig,
and TeamConfig — the three singletons imported together by the router.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from common.models.messages import TeamConfiguration
from fastapi import WebSocket
from models.messages import WebsocketMessageType
from models.plan_models import MPlan

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActiveTurn:
    """A user's turn in flight, and the **Chat** it is answering.

    The session is half of the record rather than an afterthought (#120,
    ADR-031 §6). Keyed by ``user_id`` alone, this registry could say *that* a
    turn was running but not *which conversation* it belonged to, so **Ending a
    turn** had nothing to scope itself by: leaving one Chat would cancel
    whatever the associate had running and mislabel a second conversation. One
    associate, one tab, one live turn is true in rehearsal, which is precisely
    why that would surface once, in front of an audience.
    """

    session_id: str
    task: asyncio.Task


class OrchestrationConfig:
    """Configuration and in-memory state for Magentic orchestration workflows."""

    def __init__(self):
        self.orchestrations: Dict[str, Any] = {}       # user_id -> workflow instance
        self.plans: Dict[str, MPlan] = {}              # plan_id -> plan details
        self.approvals: Dict[str, bool] = {}           # plan_id -> approval status (None = pending)
        # plan_id -> what the associate would change, set only when a plan is
        # sent back (#108). Read by the waiting review, which folds it into the
        # framework's revise path.
        self.plan_feedback: Dict[str, str] = {}
        self.sockets: Dict[str, WebSocket] = {}        # user_id -> WebSocket
        self.clarifications: Dict[str, str] = {}       # plan_id -> clarification response
        self.max_rounds: int = 30
        # user_id -> the one turn that user has in flight, and its Chat. One
        # slot per user because the Workflow itself is cached per user: a
        # second turn does not run beside the first, it replaces it.
        self.active_turns: Dict[str, ActiveTurn] = {}
        self.default_timeout: float = 300.0

        self._approval_events: Dict[str, asyncio.Event] = {}
        self._clarification_events: Dict[str, asyncio.Event] = {}

    def get_current_orchestration(self, user_id: str) -> Any:
        """Get existing orchestration workflow instance for user_id."""
        return self.orchestrations.get(user_id)

    # ------------------------------------------------------------------ #
    # The turn in flight
    # ------------------------------------------------------------------ #

    def register_active_turn(
        self, user_id: str, session_id: str, task: asyncio.Task
    ) -> None:
        """Record the turn ``user_id`` has in flight, and the Chat it answers."""
        self.active_turns[user_id] = ActiveTurn(session_id=session_id, task=task)

    def active_turn(self, user_id: str) -> Optional[ActiveTurn]:
        """The turn this user has in flight, if there is one still running.

        Storage, not judgement: the record carries the **Chat** it belongs to
        and **Ending a turn** is what compares that against the Chat being
        left (ADR-031 §6). Keeping the comparison with the primitive is what
        keeps it to one declaration.

        A task that has already finished is not in flight, so a Chat whose turn
        settled a moment ago is reported as having none. That is what keeps
        **Ending a turn** from cancelling a completed task and calling it a
        cancellation.
        """
        turn = self.active_turns.get(user_id)
        if turn is None or turn.task.done():
            return None
        return turn

    def release_active_turn(self, user_id: str, task: asyncio.Task) -> None:
        """Give up a turn's slot — but only if ``task`` is still the one in it.

        By identity, because the orchestration task clears its own slot as it
        ends and the associate's *next* request may already have registered a
        new turn there. A cancelled turn is cleaned up asynchronously, so a
        release that keyed on the user alone would take its successor with it.
        """
        turn = self.active_turns.get(user_id)
        if turn is not None and turn.task is task:
            self.active_turns.pop(user_id, None)

    # ------------------------------------------------------------------ #
    # Approval helpers
    # ------------------------------------------------------------------ #

    def set_approval_pending(self, plan_id: str) -> None:
        """Mark approval pending and create/reset its event."""
        self.approvals[plan_id] = None
        self.plan_feedback.pop(plan_id, None)
        if plan_id not in self._approval_events:
            self._approval_events[plan_id] = asyncio.Event()
        else:
            self._approval_events[plan_id].clear()

    def set_approval_result(
        self,
        plan_id: str,
        approved: bool,
        feedback: Optional[str] = None,
    ) -> None:
        """Record the associate's verdict and trigger its event.

        ``approved=False`` is a **send-back**, not a rejection: ``feedback``
        carries what the associate would change, and the waiting review folds
        it into the framework's revise path (#108).
        """
        self.approvals[plan_id] = approved
        if feedback:
            self.plan_feedback[plan_id] = feedback
        if plan_id in self._approval_events:
            self._approval_events[plan_id].set()

    def get_plan_feedback(self, plan_id: str) -> Optional[str]:
        """What the associate asked to change when they sent this plan back."""
        return self.plan_feedback.get(plan_id)

    async def wait_for_approval(self, plan_id: str, timeout: Optional[float] = None) -> bool:
        """
        Wait for an approval decision with timeout.

        Raises:
            asyncio.TimeoutError: if timeout is exceeded.
            KeyError: if plan_id is not tracked.
        """
        logger.info("Waiting for approval: %s", plan_id)
        if timeout is None:
            timeout = self.default_timeout

        if plan_id not in self.approvals:
            raise KeyError(f"Plan ID {plan_id} not found in approvals")

        if self.approvals[plan_id] is not None:
            return self.approvals[plan_id]

        if plan_id not in self._approval_events:
            self._approval_events[plan_id] = asyncio.Event()

        try:
            await asyncio.wait_for(self._approval_events[plan_id].wait(), timeout=timeout)
            logger.info("Approval received: %s", plan_id)
            return self.approvals[plan_id]
        except asyncio.TimeoutError:
            logger.warning("Approval timeout: %s", plan_id)
            self.cleanup_approval(plan_id)
            raise
        except asyncio.CancelledError:
            logger.debug("Approval request %s was cancelled", plan_id)
            raise
        except Exception as e:
            logger.error("Unexpected error waiting for approval %s: %s", plan_id, e)
            raise
        finally:
            if plan_id in self.approvals and self.approvals[plan_id] is None:
                self.cleanup_approval(plan_id)

    def cleanup_approval(self, plan_id: str) -> None:
        """Remove approval tracking data and event."""
        self.approvals.pop(plan_id, None)
        self.plan_feedback.pop(plan_id, None)
        self._approval_events.pop(plan_id, None)

    # ------------------------------------------------------------------ #
    # Clarification helpers
    # ------------------------------------------------------------------ #

    def set_clarification_pending(self, request_id: str) -> None:
        """Mark clarification pending and create/reset its event."""
        self.clarifications[request_id] = None
        if request_id not in self._clarification_events:
            self._clarification_events[request_id] = asyncio.Event()
        else:
            self._clarification_events[request_id].clear()

    def set_clarification_result(self, request_id: str, answer: str) -> None:
        """Set clarification answer and trigger event."""
        self.clarifications[request_id] = answer
        if request_id in self._clarification_events:
            self._clarification_events[request_id].set()

    async def wait_for_clarification(self, request_id: str, timeout: Optional[float] = None) -> str:
        """Wait for clarification response with timeout."""
        if timeout is None:
            timeout = self.default_timeout

        if request_id not in self.clarifications:
            raise KeyError(f"Request ID {request_id} not found in clarifications")

        if self.clarifications[request_id] is not None:
            return self.clarifications[request_id]

        if request_id not in self._clarification_events:
            self._clarification_events[request_id] = asyncio.Event()

        try:
            await asyncio.wait_for(self._clarification_events[request_id].wait(), timeout=timeout)
            return self.clarifications[request_id]
        except asyncio.TimeoutError:
            self.cleanup_clarification(request_id)
            raise
        except asyncio.CancelledError:
            logger.debug("Clarification request %s was cancelled", request_id)
            raise
        except Exception as e:
            logger.error("Unexpected error waiting for clarification %s: %s", request_id, e)
            raise
        finally:
            if request_id in self.clarifications and self.clarifications[request_id] is None:
                self.cleanup_clarification(request_id)

    def cleanup_clarification(self, request_id: str) -> None:
        """Remove clarification tracking data and event."""
        self.clarifications.pop(request_id, None)
        self._clarification_events.pop(request_id, None)


class ConnectionConfig:
    """WebSocket connection registry."""

    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.user_to_process: Dict[str, str] = {}

    def add_connection(
        self, process_id: str, connection: WebSocket, user_id: str = None
    ) -> None:
        """Add or replace a connection for a process/user."""
        if process_id in self.connections:
            try:
                asyncio.create_task(self.connections[process_id].close())
            except Exception as e:
                logger.error(
                    "Error closing existing connection for process %s: %s", process_id, e
                )

        self.connections[process_id] = connection

        if user_id:
            user_id = str(user_id)
            old_process_id = self.user_to_process.get(user_id)
            if old_process_id and old_process_id != process_id:
                old_conn = self.connections.get(old_process_id)
                if old_conn:
                    try:
                        asyncio.create_task(old_conn.close())
                        del self.connections[old_process_id]
                        logger.info(
                            "Closed old connection %s for user %s", old_process_id, user_id
                        )
                    except Exception as e:
                        logger.error(
                            "Error closing old connection for user %s: %s", user_id, e
                        )

            self.user_to_process[user_id] = process_id
            logger.info(
                "WebSocket connection added for process: %s (user: %s)", process_id, user_id
            )
        else:
            logger.info("WebSocket connection added for process: %s", process_id)

    def remove_connection(self, process_id: str) -> None:
        """Remove a connection and associated user mapping."""
        process_id = str(process_id)
        self.connections.pop(process_id, None)
        for user_id, mapped in list(self.user_to_process.items()):
            if mapped == process_id:
                del self.user_to_process[user_id]
                logger.debug("Removed user mapping: %s -> %s", user_id, process_id)
                break

    def get_connection(self, process_id: str) -> Optional[WebSocket]:
        """Fetch a connection by process_id."""
        return self.connections.get(process_id)

    def sole_user(self) -> Optional[str]:
        """The one connected user, when there is exactly one — else ``None``.

        The recipient for a push that originates outside a request the user
        made: the Grounding panel's source-used signal, emitted from the
        ``/sop/ask`` bridge that the MCP container calls with no user of its
        own, and the Presenter alert. Deliberately **not** a ``user_id`` copied
        by the model the way ``ask_user`` asks for one — a mis-copied UUID
        would make the demo's centrepiece panel go dark, and the panel is a
        presentation signal that must never be able to cost an answer.

        Refuses to guess with two users connected. That is the same rule
        ``send_status_update_async`` already applies below, named here so a
        caller can ask for it deliberately rather than by passing a wrong id
        and relying on the fallback.
        """
        if len(self.user_to_process) == 1:
            return next(iter(self.user_to_process))
        return None

    async def close_connection(
        self, process_id: str, connection: Optional[WebSocket] = None
    ) -> None:
        """Close and remove a connection by process_id.

        ``connection`` is the socket asking to be closed, and when it is given
        this is a no-op unless that socket is still the registered one. A
        second socket for one process supersedes the first, and
        ``add_connection`` closes the first — whose endpoint then reaches its
        ``finally`` and lands here. Keyed on the process alone, that arrival
        closes and unregisters the *replacement*, and every frame after it is
        dropped in silence. Both the browser's reconnect and React 18
        StrictMode mounting the plan page twice produce exactly that pair, and
        the second is what the **Connection window** narrowed in #63 depends on
        (ADR-021).
        """
        registered = self.get_connection(process_id)
        if connection is not None and registered is not connection:
            logger.info(
                "Ignoring close for a superseded socket on process %s — a newer "
                "one is registered",
                process_id,
            )
            return

        connection_to_close = registered
        if connection_to_close:
            try:
                await connection_to_close.close()
                logger.info("Connection closed for process ID: %s", process_id)
            except Exception as e:
                logger.error("Error closing connection for %s: %s", process_id, e)
        else:
            logger.warning("No connection found for process ID: %s", process_id)

        self.remove_connection(process_id)

    async def send_status_update_async(
        self,
        message: Any,
        user_id: str,
        message_type: WebsocketMessageType = WebsocketMessageType.SYSTEM_MESSAGE,
    ) -> bool:
        """Send a status update to a user via its mapped process connection.

        Returns whether the message reached a socket. Every pre-existing caller
        ignores the answer, which is right for them — a lost streaming chunk is
        not worth a branch. The Presenter alert (#23) is the one caller that
        needs it: the presenter pressed a key, and being told nothing happened
        is the difference between a bug and a chord that missed.
        """
        if not user_id:
            logger.warning("No user_id provided for WebSocket message")
            return False

        process_id = self.user_to_process.get(user_id)
        if not process_id:
            # Fallback: the LLM may have passed a wrong user_id (e.g. "default",
            # "USER").  If there is exactly one connected user, use that instead.
            if len(self.user_to_process) == 1:
                fallback_user_id = next(iter(self.user_to_process))
                logger.warning(
                    "No WebSocket for user_id '%s' — falling back to sole "
                    "connected user '%s'",
                    user_id,
                    fallback_user_id,
                )
                process_id = self.user_to_process[fallback_user_id]
            else:
                # A dropped frame. DEBUG because it fires once per streaming
                # token while the browser is still connecting, and at that rate
                # it buries the events worth reading.
                #
                # The Connection window it fires in is narrower since #63: the
                # browser starts its connect on the `createPlan` response
                # rather than after navigating and rendering the plan page
                # (ADR-021). Narrower, not closed — a fast enough orchestration
                # can still emit before that response reaches the browser, so
                # this path stays reachable and stays logged rather than being
                # quietly deleted as fixed.
                logger.debug(
                    "No active WebSocket process found for user ID: %s", user_id
                )
                return False

        try:
            if hasattr(message, "to_dict"):
                message_data = message.to_dict()
            elif isinstance(message, dict):
                message_data = message
            else:
                message_data = str(message)
        except Exception as e:
            logger.error("Error processing message data: %s", e)
            message_data = str(message)

        payload = {"type": message_type, "data": message_data}
        connection = self.get_connection(process_id)
        if connection:
            try:
                await connection.send_text(json.dumps(payload, default=str))
                logger.debug(
                    "Message sent to user %s via process %s", user_id, process_id
                )
                return True
            except Exception as e:
                logger.error("Failed to send message to user %s: %s", user_id, e)
                self.remove_connection(process_id)
                return False
        else:
            logger.warning(
                "No connection found for process ID: %s (user: %s)", process_id, user_id
            )
            self.user_to_process.pop(user_id, None)
        return False

    def send_status_update(self, message: str, process_id: str) -> None:
        """Sync helper to send a message by process_id."""
        process_id = str(process_id)
        connection = self.get_connection(process_id)
        if connection:
            try:
                asyncio.create_task(connection.send_text(message))
            except Exception as e:
                logger.error(
                    "Failed to send message to process %s: %s", process_id, e
                )
        else:
            logger.warning("No connection found for process ID: %s", process_id)


class TeamConfig:
    """Per-user team configuration store."""

    def __init__(self):
        self._teams: Dict[str, TeamConfiguration] = {}

    def set_current_team(
        self, user_id: str, team_configuration: TeamConfiguration
    ) -> None:
        """Store current team configuration for user."""
        self._teams[user_id] = team_configuration

    def get_current_team(self, user_id: str) -> Optional[TeamConfiguration]:
        """Retrieve current team configuration for user."""
        return self._teams.get(user_id)


# Module-level singletons
orchestration_config = OrchestrationConfig()
connection_config = ConnectionConfig()
team_config = TeamConfig()
