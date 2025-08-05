"""
Configuration settings for the Magentic Employee Onboarding system.
Handles Azure OpenAI, MCP, and environment setup.
"""

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, OpenAIChatPromptExecutionSettings

# Load environment variables
load_dotenv()

# Azure configuration
TENANT_ID = "52b39610-0746-4c25-a83d-d4f89fadedfe"
CLIENT_ID = "7a95e70b-062e-4cd3-a88c-603fc70e1c73"

class AzureConfig:
    """Azure OpenAI and authentication configuration."""
    
    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.reasoning_model = os.getenv("REASONING_MODEL_NAME", "o3")
        self.standard_model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        self.bing_connection_name = os.getenv("BING_CONNECTION_NAME")
        
        # Create credential
        self.credential = SyncDefaultAzureCredential()
    
    def get_azure_token(self):
        """Get Azure token for authentication."""
        token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
        return token.token
    
    def create_chat_completion_service(self, use_reasoning_model=False):
        """Create Azure Chat Completion service."""
        model_name = self.reasoning_model if use_reasoning_model else self.standard_model
        
        return AzureChatCompletion(
            deployment_name=model_name,
            endpoint=self.endpoint,
            ad_token_provider=self.get_azure_token
        )
    
    def create_execution_settings(self):
        """Create execution settings for OpenAI."""
        return OpenAIChatPromptExecutionSettings(
            max_tokens=4000,
            temperature=0.1
        )

class MCPConfig:
    """MCP server configuration."""
    
    def __init__(self):
        self.url = "http://127.0.0.1:8000/mcp/"
        self.name = "MCPGreetingServer"
        self.description = "MCP server with greeting and planning tools"
    
    def get_headers(self, token):
        """Get MCP headers with authentication token."""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        } if token else {}

# Global config instances
azure_config = AzureConfig()
mcp_config = MCPConfig()
