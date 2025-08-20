# Copyright (c) Microsoft. All rights reserved.

import asyncio
import os

from dotenv import load_dotenv

# Load environment variables from .env file for command line execution
load_dotenv()

from typing import Any, List, Optional

from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
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
from v3.magentic_agents.magentic_agent_factory import (cleanup_all_agents,
                                                       get_agents)
from v3.orchestration.human_approval_manager import \
    HumanApprovalMagenticManager

magentic_orchestration: MagenticOrchestration = None # Global reference for Magentic orchestration

# track this should be offline state and attached to a session id
coderagent = False

def agent_response_callback(message: ChatMessageContent) -> None:
    """Observer function to print detailed information about streaming messages."""
    global coderagent
    # import sys

    # Get agent name to determine handling
    agent_name = message.name or "Unknown Agent"

    # Debug information about the message
    message_type = type(message).__name__
    metadata = getattr(message, 'metadata', {})
    # when streaming code - list the coder info first once - 
    if 'code' in metadata and metadata['code'] is True:
        if coderagent == False:
            print(f"\n🧠 **{agent_name}** [{message_type}]")
            print("-" * (len(agent_name) + len(message_type) + 10))
            coderagent = True
        print(message.content, end='', flush=False)
        return
    elif coderagent == True:
        coderagent = False
    role = getattr(message, 'role', 'unknown')

    print(f"\n🧠 **{agent_name}** [{message_type}] (role: {role})")
    print("-" * (len(agent_name) + len(message_type) + 10))
    if message.items[-1].content_type == 'function_call':
        print(f"🔧 Function call: {message.items[-1].function_name}, Arguments: {message.items[-1].arguments}")
    if metadata:
        print(f"📋 Metadata: {metadata}")
    
# Add this function after your agent_response_callback function
async def streaming_agent_response_callback(streaming_message: StreamingChatMessageContent, is_final: bool) -> None:
    """Simple streaming callback to show real-time agent responses."""
    if streaming_message.name != "CoderAgent":
        # Print streaming content as it arrives
        if hasattr(streaming_message, 'content') and streaming_message.content:
            print(streaming_message.content, end='', flush=False)

async def start_orchestration():
    """Main function to run the agents."""

    global magentic_orchestration

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
        members=await get_agents(),
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

if __name__ == "__main__":
    asyncio.run(start_orchestration())