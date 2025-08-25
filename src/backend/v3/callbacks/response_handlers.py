"""
Enhanced response callbacks for employee onboarding agent system.
Provides detailed monitoring and response handling for different agent types.
"""

import sys

from semantic_kernel.contents import (ChatMessageContent,
                                      StreamingChatMessageContent)

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
