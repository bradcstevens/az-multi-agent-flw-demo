# Copyright (c) Microsoft. All rights reserved.
"""Factory for creating and managing agents from JSON team configurations.

Replaces v4/magentic_agents/magentic_agent_factory.py.
Key change: uses AgentTemplate (FoundryChatClient + Agent, GA) instead of
FoundryAgentTemplate (AzureAIAgentClient + ChatAgent, deprecated).
"""

import asyncio
import logging
from types import SimpleNamespace
from typing import List, Optional, Sequence

from agents.agent_template import AgentTemplate
from agents.model_allowlist import (RefusedAgent, SupportedModelsNotConfigured,
                                    configured_supported_models, is_supported,
                                    unsupported_reason)
from common.config.app_config import config
from common.database.database_base import DatabaseBase
from common.models.messages import TeamConfiguration
from config.mcp_config import KnowledgeBaseConfig, MCPConfig, VectorStoreConfig
from tools.clarification_tool import request_user_clarification


class UnsupportedModelError(Exception):
    """Raised when the configured model is not in the supported-models list."""


# ---------------------------------------------------------------------------
# Universal prompt segment for agents whose team config has user_responses=true.
# Directs them to call request_user_clarification tool when they need user info.
# The framework pauses automatically and resumes with the user's answer.
# ---------------------------------------------------------------------------

_UNIVERSAL_USER_INTERACTION_PROMPT = """

CRITICAL RULES — READ BEFORE ACTING:

1. NEVER FABRICATE INFORMATION. If a tool requires a parameter you do not have
   (dates, names, emails, hardware models, salary, preferences), you MUST request
   it from the user. Do NOT invent values, use placeholders, or guess.

2. GATHER ALL MISSING INFO BEFORE EXECUTING. Before calling action tools, check
   whether you have every required parameter. If ANY required parameter is missing
   from the conversation context, call the request_user_clarification tool with
   clear, numbered questions listing exactly what you need.

3. PRESENT OPTIONS TO THE USER. If you have optional steps or overridable
   defaults, include them in your clarification request so the user can decide.

4. EXECUTE ONLY AFTER ANSWERS ARRIVE. Once the request_user_clarification tool
   returns the user's answers, proceed with execution using the real values provided.

5. ALWAYS USE THE TOOL. To ask the user a question, you MUST call
   request_user_clarification. Do NOT simply state that you need information —
   the user cannot see your text until the task completes.

6. Do NOT re-ask anything already answered in the conversation history.
"""


class AgentFactory:
    """Create and manage teams of agents from JSON configuration.

    Usage::

        factory = AgentFactory()
        agents = await factory.get_agents(user_id, team_config, memory_store)
        # ... use agents in orchestrator ...
        await factory.close_all()
    """

    def __init__(self, team_service: Optional[object] = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.team_service = team_service
        self._agent_list: List = []
        #: Agents this factory was asked for and did not build (#113). Kept on
        #: the factory rather than only logged, because a warning in a
        #: container is not a thing any caller — or any surface — can read.
        self.refused_agents: List[RefusedAgent] = []

    # ------------------------------------------------------------------
    # Single-agent creation
    # ------------------------------------------------------------------

    async def create_agent_from_config(
        self,
        user_id: str,
        agent_obj: SimpleNamespace,
        team_config: TeamConfiguration,
        memory_store: DatabaseBase,
        supported_models: Optional[Sequence[str]] = None,
    ) -> AgentTemplate:
        """Create and open a single agent from a SimpleNamespace config object.

        Args:
            user_id:      The requesting user ID.
            agent_obj:    Per-agent config parsed from the team JSON.
            team_config:  The parent team configuration.
            memory_store: Cosmos DB store for agent persistence.
            supported_models: The allowlist to check against. Resolved from app
                config when omitted; ``get_agents`` resolves it **once** and
                passes it in so a configuration error cannot be mistaken for a
                per-agent fault.

        Returns:
            An initialized ``AgentTemplate``.

        Raises:
            UnsupportedModelError:      If the deployment name is not in SUPPORTED_MODELS.
            SupportedModelsNotConfigured: If SUPPORTED_MODELS is unset or unparseable.
        """
        deployment_name = getattr(agent_obj, "deployment_name", None)

        # Validate model against the one allowlist (agents/model_allowlist.py).
        if supported_models is None:
            supported_models = configured_supported_models()
        if not is_supported(deployment_name, supported_models):
            raise UnsupportedModelError(
                unsupported_reason(deployment_name, supported_models)
            )

        # Foundry IQ (FileSearchTool + vector stores)
        vector_store_name = getattr(agent_obj, "vector_store_name", None)
        vector_store_config: Optional[VectorStoreConfig] = (
            VectorStoreConfig(vector_store_name=vector_store_name)
            if getattr(agent_obj, "use_file_search", False) and vector_store_name
            else None
        )

        # Foundry IQ Knowledge Base (server-side MCP on Azure AI Search)
        kb_name = getattr(agent_obj, "knowledge_base_name", None)
        kb_config: Optional[KnowledgeBaseConfig] = (
            KnowledgeBaseConfig.from_env(kb_name)
            if getattr(agent_obj, "use_knowledge_base", False) and kb_name
            else None
        )

        # Toolbox MCP config: domain-specific server only (use_toolbox).
        use_toolbox = getattr(agent_obj, "use_toolbox", False)
        user_responses = getattr(agent_obj, "user_responses", False)
        if use_toolbox:
            toolbox_filter = getattr(agent_obj, "toolbox_filter", None)
            mcp_config: Optional[MCPConfig] = MCPConfig.from_env(domain=toolbox_filter)
        else:
            mcp_config = None

        self.logger.info(
            "Creating AgentTemplate '%s' (model=%s, use_file_search=%s, use_toolbox=%s).",
            agent_obj.name,
            deployment_name,
            vector_store_config is not None,
            mcp_config is not None,
        )

        # Build agent instructions from system_message + optional interaction rules
        instructions = getattr(agent_obj, "system_message", "")

        # Universal user-interaction rules for agents that have
        # user_responses=true — tells them to call request_user_clarification.
        if user_responses:
            instructions += _UNIVERSAL_USER_INTERACTION_PROMPT

        # Agents with user_responses=true get the clarification tool directly.
        extra_tools = [request_user_clarification] if user_responses else None

        agent = AgentTemplate(
            agent_name=agent_obj.name,
            agent_description=getattr(agent_obj, "description", ""),
            agent_instructions=instructions,
            model_deployment_name=deployment_name,
            project_endpoint=config.AZURE_AI_PROJECT_ENDPOINT,
            enable_code_interpreter=getattr(agent_obj, "coding_tools", False),
            mcp_config=mcp_config,
            vector_store_config=vector_store_config,
            kb_config=kb_config,
            temperature=getattr(agent_obj, "temperature", None),
            team_config=team_config,
            memory_store=memory_store,
            extra_tools=extra_tools,
        )

        try:
            await agent.open()
        except asyncio.CancelledError:
            try:
                await agent.close()
            except Exception:
                self.logger.exception(
                    "Failed to close cancelled agent '%s'.", agent_obj.name
                )
            raise
        self.logger.info("Initialized agent '%s'.", agent_obj.name)
        return agent

    # ------------------------------------------------------------------
    # Team creation
    # ------------------------------------------------------------------

    async def get_agents(
        self,
        user_id: str,
        team_config_input: TeamConfiguration,
        memory_store: DatabaseBase,
    ) -> List:
        """Create and return a full team of agents from a TeamConfiguration.

        Args:
            user_id:           The requesting user ID.
            team_config_input: Parsed team configuration from Cosmos DB.
            memory_store:      Cosmos DB store for agent persistence.

        Returns:
            List of initialized ``AgentTemplate`` instances.

        Raises:
            SupportedModelsNotConfigured: If the deployment's allowlist is
                unset or unparseable. Deliberately resolved **before** the loop
                and outside the per-agent ``try``: read inside it, a missing
                environment variable was caught by the broad ``except`` once per
                agent and returned an empty team as if every agent had failed
                on its own (#113).
        """
        supported_models = configured_supported_models()

        initialized: List = []
        self.refused_agents = []

        for i, agent_cfg in enumerate(team_config_input.agents, 1):
            try:
                self.logger.info(
                    "Creating agent %d/%d: %s.",
                    i,
                    len(team_config_input.agents),
                    agent_cfg.name,
                )
                agent = await self.create_agent_from_config(
                    user_id,
                    agent_cfg,
                    team_config_input,
                    memory_store,
                    supported_models=supported_models,
                )
                initialized.append(agent)
                self._agent_list.append(agent)
                self.logger.info(
                    "Agent %d/%d ready: %s.",
                    i,
                    len(team_config_input.agents),
                    agent_cfg.name,
                )
            except SupportedModelsNotConfigured:
                raise
            except UnsupportedModelError as exc:
                self.refused_agents.append(
                    RefusedAgent(
                        name=getattr(agent_cfg, "name", "") or "",
                        deployment_name=getattr(agent_cfg, "deployment_name", None),
                        reason=str(exc),
                    )
                )
                self.logger.error(
                    "Agent %d/%d '%s' was not built — %s",
                    i,
                    len(team_config_input.agents),
                    agent_cfg.name,
                    exc,
                )
            except Exception as exc:
                self.refused_agents.append(
                    RefusedAgent(
                        name=getattr(agent_cfg, "name", "") or "",
                        deployment_name=getattr(agent_cfg, "deployment_name", None),
                        reason=str(exc),
                    )
                )
                self.logger.error(
                    "Skipping agent %d/%d '%s' — unexpected error: %s.",
                    i,
                    len(team_config_input.agents),
                    agent_cfg.name,
                    exc,
                )

        return initialized

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close_all(self) -> None:
        """Close all agents created by this factory instance."""
        await AgentFactory.cleanup_all_agents(self._agent_list)

    @staticmethod
    async def cleanup_all_agents(agent_list: list) -> None:
        """Close all agents in the given list and clear it.

        Mirrors the v4 MagenticAgentFactory.cleanup_all_agents static method.
        Safe to call with an empty list; errors are logged but do not propagate.
        """
        logger = logging.getLogger(__name__)
        for agent in list(agent_list):
            try:
                if hasattr(agent, "close"):
                    await agent.close()
            except Exception as exc:
                logger.warning(
                    "Error closing agent '%s': %s.",
                    getattr(agent, "agent_name", type(agent).__name__),
                    exc,
                )
        agent_list.clear()
