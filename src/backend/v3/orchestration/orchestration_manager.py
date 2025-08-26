# Copyright (c) Microsoft. All rights reserved.
""" Orchestration manager to handle the orchestration logic. """

import os
import uuid
from typing import List

from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
from semantic_kernel.agents.orchestration.magentic import MagenticOrchestration
from semantic_kernel.agents.runtime import InProcessRuntime
# Create custom execution settings to fix schema issues
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion, OpenAIChatPromptExecutionSettings)
from v3.callbacks.response_handlers import (agent_response_callback,
                                            streaming_agent_response_callback)
from v3.config.settings import config, orchestration_config
from v3.magentic_agents.magentic_agent_factory import MagenticAgentFactory
from v3.orchestration.human_approval_manager import \
    HumanApprovalMagenticManager


class OrchestrationManager:
    """Manager for handling orchestration logic."""
    @classmethod
    async def init_orchestration(cls, agents: List)-> MagenticOrchestration:
        """Main function to run the agents."""

        # Custom execution settings that should work with Azure OpenAI
        execution_settings = OpenAIChatPromptExecutionSettings(
            max_tokens=4000,
            temperature=0.1
        )

        # Create a token provider function for Azure OpenAI
        credential = SyncDefaultAzureCredential()

        def get_token():
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            return token.token

        # 1. Create a Magentic orchestration with Azure OpenAI
        magentic_orchestration = MagenticOrchestration(
            members=agents,
            manager=HumanApprovalMagenticManager(
                chat_completion_service=AzureChatCompletion(
                    deployment_name=os.getenv("AZURE_OPENAI_MODEL_NAME"),
                    endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    ad_token_provider=get_token  # Use token provider function
                ),
                execution_settings=execution_settings
            ),
            agent_response_callback=agent_response_callback,
            streaming_agent_response_callback=streaming_agent_response_callback,  # Add streaming callback
        )
        return magentic_orchestration
    
    @classmethod
    async def get_current_orchestration(cls, user_id: str) -> MagenticOrchestration:
        """get existing orchestration instance."""
        current_orchestration = orchestration_config.get_current_orchestration(user_id)
        if current_orchestration is None:
            factory = MagenticAgentFactory()
            # to do: change to parsing teams from cosmos db
            agents = await factory.get_agents(config.AGENT_TEAM_FILE)
            orchestration_config._orchestrations[user_id] = await cls.init_orchestration(agents)
        return orchestration_config.get_current_orchestration(user_id)

    @classmethod
    async def run_orchestration(cls, user_id, input_task) -> None:
        """ Run the orchestration with user input loop."""

        job_id = str(uuid.uuid4())
        orchestration_config.approvals[job_id] = None
    
        magentic_orchestration = orchestration_config.get_current_orchestration(user_id)

        if magentic_orchestration is None:
            raise ValueError("Orchestration not initialized for user.")
        
        runtime = InProcessRuntime()
        runtime.start()
        
        try:

            orchestration_result = await magentic_orchestration.invoke(
                task=input_task.description,
                runtime=runtime,
            )

            try:
                print("\nAgent responses:")
                value = await orchestration_result.get()
                print(f"\nFinal result:\n{value}")
                print("=" * 50)
            except Exception as e:
                print(f"Error: {e}")
                print(f"Error type: {type(e).__name__}")
                if hasattr(e, '__dict__'):
                    print(f"Error attributes: {e.__dict__}")
                print("=" * 50)

        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            await runtime.stop_when_idle()
