# Copyright (c) Microsoft. All rights reserved.

import os
import asyncio
from azure.identity.aio import DefaultAzureCredential
from azure.identity import InteractiveBrowserCredential

from azure.ai.agents.models import BingGroundingTool
from azure.ai.agents.models import CodeInterpreterToolDefinition
from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin
from semantic_kernel.agents.azure_ai.azure_ai_agent import AzureAIAgent
from semantic_kernel.agents.azure_ai.azure_ai_agent_settings import \
    AzureAIAgentSettings

# Environment variables are used in two ways:
# 1. Automatically by AzureAIAgentSettings (AZURE_OPENAI_... variables)
# 2. Directly created below (for bing grounding and MCP capabilities)

class FoundryAgentTemplate:
    """A template agent that manages its own async context for client connections."""

    AGENT_NAME = "EnhancedResearchAgent"
    AGENT_DESCRIPTION = "A comprehensive research assistant with web search and MCP capabilities."
    AGENT_INSTRUCTIONS="""You are an Enhanced Research Agent with access to Bing web search capabilities and MCP tools.

    CRITICAL: You MUST use your Bing search tools for any questions about current events, recent news, or time-sensitive information. Examine your available MCP tools and use these where they may be applicable.

    AUTONOMY: You should make reasonable decisions and proceed without asking for user confirmation unless absolutely critical. When in doubt, choose the most comprehensive approach.

    SEARCH STRATEGY:
    - Always search for current events, recent news, or dates
    - Use specific, targeted search queries with current year (2025)
    - Search multiple times with different keywords if needed
    - Include dates, locations, and specific terms in searches

    DECISION MAKING:
    - If multiple approaches are possible, choose the most thorough one
    - Don't ask for permission to proceed - just do the work
    - Only ask for clarification if the task is genuinely ambiguous

    Always use your search tools and MCP tools - do not rely on training data for current information.
    Provide comprehensive results with URLs and sources when available."""

    initialized = False
    
    # To do: pass capability parameters in the constructor:
    # To do: pass name, description and instructions in the constructor
    # 1. MCP server endpoint and use
    # 2. Bing grounding option
    # 3. Reasoning model name (some settings are different and cannot be used with bing grounding)
    # 4. Coding skills - CodeInterpreterToolDefinition
    # 5. Grounding Data - requires index endpoint
    # This will allow the factory to create all base models except researcher with bing - this is
    # is coming with a deep research offering soon (preview now in two regions)
    def __init__(self):
        self._agent = None
        self.client = None
        self.creds = None
        self.mcp_plugin = None
        self.bing_tool_name = os.environ["BING_CONNECTION_NAME"] or ""
        self.mcp_srv_endpoint = os.environ["MCP_SERVER_ENDPOINT"] or ""
        self.mcp_srv_name= os.environ["MCP_SERVER_NAME"] or ""
        self.mcp_srv_description = os.environ["MCP_SERVER_DESCRIPTION"] or ""
        self.tenant_id = os.environ["TENANT_ID"] or ""
        self.client_id = os.environ["CLIENT_ID"] or ""

    def __getattr__(self, name):
        """Delegate all attribute access to the wrapped agent."""
        if hasattr(self, '_agent') and self._agent is not None:
            return getattr(self._agent, name)
        else:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    async def __aenter__(self):
        """Initialize the agent and return it within an async context."""
        # Initialize credentials and client
        if not self.initialized:
           await self.create_agent_async()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the async contexts."""
        # Exit MCP plugin context first
        if self.mcp_plugin and hasattr(self.mcp_plugin, '__aexit__'):
            await self.mcp_plugin.__aexit__(exc_type, exc_val, exc_tb)
        
        # Then exit Azure contexts
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
        if self.creds:
            await self.creds.__aexit__(exc_type, exc_val, exc_tb)

    
    async def create_agent_async(self):
        """Create the template agent with all tools - must be called within async context."""
        self.initialized = True

        self.creds = DefaultAzureCredential()
        self.client = AzureAIAgent.create_client(credential=self.creds)
        
        # Get MCP authentication headers
        headers = await self._get_mcp_auth_headers()
        
        # Create Bing tools
        bing = None
        try:
            bing_connection = await self.client.connections.get(name=self.bing_tool_name)
            conn_id = bing_connection.id
            print(f"🔍 Attempting Bing tool creation with connection name: {self.bing_tool_name}")
            bing = BingGroundingTool(connection_id=conn_id)
            print(f"🔍 Bing tool created with {conn_id} - {len(bing.definitions)} tools available")
        except Exception as name_error:
            print(f"⚠️  Bing tool creation with {self.bing_tool_name} failed: {name_error}")

        # Create MCP plugin and enter its async context
        try:
            print("🔗 Creating MCP plugin within async context...")
            self.mcp_plugin = MCPStreamableHttpPlugin(
                name=self.mcp_srv_name,
                description=self.mcp_srv_description,
                url=self.mcp_srv_endpoint,
                headers=headers,
            )
            
            # Enter the MCP plugin's async context
            if hasattr(self.mcp_plugin, '__aenter__'):
                await self.mcp_plugin.__aenter__()
                self._mcp_context_entered = True
                print("✅ MCP plugin async context entered")
            else:
                print("ℹ️  MCP plugin doesn't require async context")
                
        except Exception as mcp_error:
            print(f"⚠️  MCP plugin creation failed: {mcp_error}")
            self.mcp_plugin = None
            self._mcp_context_entered = False

        # Create agent settings and definition
        ai_agent_settings = AzureAIAgentSettings()
        template_agent_definition = await self.client.agents.create_agent(
            model=ai_agent_settings.model_deployment_name,
            # Name, description and instructions are provided for demonstration purposes
            name=self.AGENT_NAME,
            description=self.AGENT_DESCRIPTION,
            instructions= self.AGENT_INSTRUCTIONS,
            tools=bing.definitions if bing else [],
            # Add Code Interpreter tool for coding capabilities
            # tools=[CodeInterpreterToolDefinition()] if self.mcp_plugin else []
        )

        # Create the final agent
        plugins = [self.mcp_plugin] if self.mcp_plugin else []
        self._agent = AzureAIAgent(
            client=self.client,
            definition=template_agent_definition,
            plugins=plugins
        )
        
        print("✅ Template agent created successfully!")

    async def close(self):
        """Clean up async resources."""
        if not self.initialized:
            return 
        
        print("🧹 Cleaning up agent resources...")
        if self.mcp_plugin and self._mcp_context_entered:
            try:
                # Exit MCP plugin context first
                if hasattr(self.mcp_plugin, '__aexit__'):
                    #await self.mcp_plugin.__aexit__(None, None, None)
                    self.mcp_plugin = None
                    print("✅ MCP plugin context cleaned up")
                # Getting the following error during cleanup: Attempted to exit a cancel scope that isn't the current tasks's current cancel scope
                # Seems to be related to https://github.com/microsoft/semantic-kernel/issues/12627?
            except Exception as e:
                print(f"⚠️ {self.AGENT_NAME}: Error cleaning up MCP plugin: {e}")
            finally:
                self._mcp_context_entered = False
                self.mcp_plugin = None        
            try:
                # Then exit Azure contexts
                if self.client:
                    await self.client.__aexit__(None, None, None)
            except Exception as e:
                print(f"⚠️ {self.AGENT_NAME}: Error cleaning up client: {e}")           
            try:
                if self.creds:
                    await self.creds.__aexit__(None, None, None)
            except Exception as e:
                print(f"⚠️ {self.AGENT_NAME}: Error cleaning up credentials: {e}")
                
            self.initialized = False
            print("✅ Agent cleanup completed")

    # Add __del__ for emergency cleanup
    def __del__(self):
        """Emergency cleanup when object is garbage collected."""
        if self.initialized:
            try:
                # Try to schedule cleanup in the event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
            except Exception:
                # If we can't schedule cleanup, just warn
                print(f"⚠️  Warning: {self.AGENT_NAME} was not properly cleaned up")
    
    async def _get_mcp_auth_headers(self) -> dict:
        """Get MCP authentication headers."""       
        try:
            interactive_credential = InteractiveBrowserCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id
            )
            token = interactive_credential.get_token(f"api://{self.client_id}/access_as_user")
            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json"
            }
            print("✅ Successfully obtained MCP authentication token")
            return headers
        except Exception as e:
            print(f"❌ Failed to get MCP token: {e}")
            return {}


# Factory function for your agent factory
# Add parameters to allow creation of agents with different capabilities
async def create_foundry_agent():
    """Factory function that returns a AzureAiAgentTemplate context manager."""
    return_agent = FoundryAgentTemplate()
    await return_agent.create_agent_async()
    return return_agent


# Test harness
async def test_agent():
    """Simple chat test harness for the agent."""
    print("🤖 Starting agent test harness...")
    
    try:
        async with FoundryAgentTemplate() as agent:
            print("💬 Type 'quit' or 'exit' to stop\n")
            
            while True:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                try:
                    print("🤖 Agent: ", end="", flush=True)
                    async for message in agent.invoke(user_input):
                        if hasattr(message, 'content'):
                            print(message.content, end="", flush=True)
                        else:
                            print(str(message), end="", flush=True)
                    print()
                    
                except Exception as e:
                    print(f"❌ Error: {e}")
                    
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")


if __name__ == "__main__":
    asyncio.run(test_agent())