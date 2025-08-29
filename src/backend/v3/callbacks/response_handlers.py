"""
Enhanced response callbacks for employee onboarding agent system.
Provides detailed monitoring and response handling for different agent types.
"""
import asyncio
import sys

from semantic_kernel.contents import (ChatMessageContent,
                                      StreamingChatMessageContent)
from v3.config.settings import connection_config, current_user_id

coderagent = False

# Module-level variable to store current user_id
_current_user_id: str = None

def set_user_context(user_id: str):
    """Set the user context for callbacks in this module."""
    global _current_user_id
    _current_user_id = user_id

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

    # Send to WebSocket
    if _current_user_id:
        try:
            asyncio.create_task(connection_config.send_status_update_async({
                "type": "agent_message",
                "data": {"agent_name": agent_name, "content": message.content, "role": role}
            }, _current_user_id))
        except Exception as e:
            print(f"Error sending WebSocket message: {e}")

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
