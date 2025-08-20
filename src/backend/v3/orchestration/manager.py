# Copyright (c) Microsoft. All rights reserved.

import asyncio
import os

from dotenv import load_dotenv

# Load environment variables from .env file for command line execution
load_dotenv()

from typing import Any, List, Optional

from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
from common.config.app_config import config
from semantic_kernel.agents.orchestration.magentic import (
    MagenticOrchestration, StandardMagenticManager)
from semantic_kernel.agents.runtime import InProcessRuntime
# Create custom execution settings to fix schema issues
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion, OpenAIChatPromptExecutionSettings)
from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin
from semantic_kernel.contents import (ChatMessageContent,
                                      StreamingChatMessageContent)
from semantic_kernel.kernel_pydantic import KernelBaseModel
from v3.callbacks.response_handlers import (agent_response_callback,
                                            streaming_agent_response_callback)
from v3.magentic_agents.magentic_agent_factory import (cleanup_all_agents,
                                                       get_agents)
from v3.orchestration.human_approval_manager import \
    HumanApprovalMagenticManager


async def init_orchestration(agents: List)-> MagenticOrchestration:
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

async def run_orchestration(magentic_orchestration: MagenticOrchestration) -> None:
    # 2. Create a runtime and start it
    runtime = InProcessRuntime()
    runtime.start()

    # Chat interface loop
    print("Example requests:")
    # Test if MCP is available
    print("  • 'Please greet Tom")
    # Test if Bing grounding is available
    print("  • 'What is the weather today in New York City?'")
    # Test coder agent
    print("  • 'Write and execute a Python function to calculate Fibonacci numbers'")
    # Good reasoning prompts
    print("  • 'Find recent AI developments and explain their implications'")
    print("  • 'Search for quantum computing news and calculate market projections'")
    print()
    print("Type 'quit' or 'exit' to end the session.")
    print("=" * 70)
    
    try:
        while True:
            # Get user input
            user_input = input("\nEnter your request: ").strip()
            
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if not user_input:
                print("Please enter a valid request.")
                continue
            
            print(f"\nProcessing your request: {user_input}")
            print("-" * 50)
            
            # 3. Invoke the orchestration with user input
            orchestration_result = await magentic_orchestration.invoke(
                task=user_input,
                runtime=runtime,
            )

            # 4. Wait for the results with streaming output
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

    except KeyboardInterrupt:
        print("\nSession interrupted by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Clean up agents before stopping runtime
        try:
            await cleanup_all_agents()
        except Exception as e:
            print(f"⚠️  Error during agent cleanup: {e}")
        # 5. Stop the runtime when idle
        await runtime.stop_when_idle()
