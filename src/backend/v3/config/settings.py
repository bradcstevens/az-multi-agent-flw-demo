"""
Configuration settings for the Magentic Employee Onboarding system.
Handles Azure OpenAI, MCP, and environment setup.
"""

import asyncio
import json
import logging
from typing import Dict

from common.config.app_config import config
from fastapi import WebSocket
from semantic_kernel.agents.orchestration.magentic import MagenticOrchestration
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion, OpenAIChatPromptExecutionSettings)

logger = logging.getLogger(__name__)

class AzureConfig:
    """Azure OpenAI and authentication configuration."""

    def __init__(self):
        self.endpoint = config.AZURE_OPENAI_ENDPOINT
        self.reasoning_model = config.REASONING_MODEL_NAME
        self.standard_model = config.AZURE_OPENAI_DEPLOYMENT_NAME
        self.bing_connection_name = config.AZURE_BING_CONNECTION_NAME

        # Create credential
        self.credential = config.get_azure_credentials()

    def create_chat_completion_service(self, use_reasoning_model=False):
        """Create Azure Chat Completion service."""
        model_name = (
            self.reasoning_model if use_reasoning_model else self.standard_model
        )

        return AzureChatCompletion(
            deployment_name=model_name,
            endpoint=self.endpoint,
            ad_token_provider=config.get_access_token(),
        )

    def create_execution_settings(self):
        """Create execution settings for OpenAI."""
        return OpenAIChatPromptExecutionSettings(max_tokens=4000, temperature=0.1)


class MCPConfig:
    """MCP server configuration."""

    def __init__(self):
        self.url = "http://127.0.0.1:8000/mcp/"
        self.name = "MCPGreetingServer"
        self.description = "MCP server with greeting and planning tools"

    def get_headers(self, token):
        """Get MCP headers with authentication token."""
        return (
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if token
            else {}
        )


class OrchestrationConfig:
    """Configuration for orchestration settings."""

    def __init__(self):
        self.orchestrations = {}
        self.plans = {}       # job_id -> current plan
        self.approvals = {}   # job_id -> True/False/None
        self.sockets = {}     # job_id -> WebSocket

    def get_current_orchestration(self, user_id: str) -> MagenticOrchestration:
        """get existing orchestration instance."""
        return self.orchestrations.get(user_id, None)
    
class ConnectionConfig:
    """Connection manager for WebSocket connections."""

    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    def add_connection(self, process_id, connection):
        """Add a new connection."""
        self.connections[process_id] = connection

    def remove_connection(self, process_id):
        """Remove a connection."""
        if process_id in self.connections:
            del self.connections[process_id]

    def get_connection(self, process_id):
        """Get a connection."""
        return self.connections.get(process_id)
    
    async def close_connection(self, process_id):
        """Remove a connection."""
        connection = self.get_connection(process_id)
        if connection:
            asyncio.run_coroutine_threadsafe(connection.close(), asyncio.get_event_loop())
            logger.info("Connection closed for batch ID: %s", process_id)
        else:
            logger.warning("No connection found for batch ID: %s", process_id)
        connection_config.remove_connection(process_id)
        logger.info("Connection removed for batch ID: %s", process_id)

    async def send_status_update_async(self, message: str, process_id: str):
        """Send a status update to a specific client."""
        connection = self.get_connection(process_id)
        if connection:
            await connection.send_text(message)
        else:
            logger.warning("No connection found for batch ID: %s", process_id)


    def send_status_update(self, message: str, process_id: str):
        """Send a status update to a specific client."""
        connection = self.get_connection(str(process_id))
        if connection:
            try:
                # Directly send the message using this connection object
                asyncio.run_coroutine_threadsafe(
                    connection.send_text(
                        message
                    ),
                    asyncio.get_event_loop(),
                )
            except Exception as e:
                logger.error("Failed to send message: %s", e)
        else:
            logger.warning("No connection found for batch ID: %s", process_id)


# Global config instances
azure_config = AzureConfig()
mcp_config = MCPConfig()
orchestration_config = OrchestrationConfig()
connection_config = ConnectionConfig()
