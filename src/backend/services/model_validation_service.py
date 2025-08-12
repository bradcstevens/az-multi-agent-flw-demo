"""
Model Validation Service
Validates that required models are deployed in Azure AI Foundry
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple
import aiohttp
from helpers.azure_credential_utils import get_azure_credential

class ModelValidationService:
    """Service for validating model deployments in Azure AI Foundry"""
    
    def __init__(self):
        self.subscription_id = os.getenv("AZURE_AI_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_AI_RESOURCE_GROUP") 
        self.project_name = os.getenv("AZURE_AI_PROJECT_NAME")
        self.project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
        
        if not all([self.subscription_id, self.resource_group, self.project_name]):
            logging.warning("Azure AI project configuration is incomplete")
    
    async def get_access_token(self) -> str:
        """Get Azure access token for API calls"""
        try:
            credential = get_azure_credential()
            # get_token is synchronous for DefaultAzureCredential
            token = credential.get_token("https://management.azure.com/.default")
            return token.token
        except Exception as e:
            logging.error(f"Failed to get access token: {e}")
            raise
    
    async def list_model_deployments(self) -> List[Dict[str, Any]]:
        """
        List all model deployments in the Azure AI project
        Uses the Azure AI Foundry REST API
        """
        if not all([self.subscription_id, self.resource_group, self.project_name]):
            logging.error("Azure AI project configuration is incomplete")
            return []
        
        try:
            token = await self.get_access_token()
            
            # Construct the API URL according to the documentation
            url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}/"
                f"resourceGroups/{self.resource_group}/providers/Microsoft.MachineLearningServices/"
                f"workspaces/{self.project_name}/onlineEndpoints"
            )
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "api-version": "2024-10-01"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        deployments = data.get("value", [])
                        
                        # Extract deployment names and model information
                        deployment_info = []
                        for deployment in deployments:
                            deployment_info.append({
                                "name": deployment.get("name"),
                                "model": deployment.get("properties", {}).get("model", {}),
                                "status": deployment.get("properties", {}).get("provisioningState"),
                                "endpoint_uri": deployment.get("properties", {}).get("scoringUri")
                            })
                        
                        return deployment_info
                    else:
                        error_text = await response.text()
                        logging.error(f"Failed to list deployments. Status: {response.status}, Error: {error_text}")
                        return []
                        
        except Exception as e:
            logging.error(f"Error listing model deployments: {e}")
            return []
    
    def extract_models_from_agent(self, agent: Dict[str, Any]) -> set:
        """
        Extract all possible model references from a single agent configuration
        
        Args:
            agent: Single agent configuration dictionary
            
        Returns:
            Set of model names found in the agent
        """
        models = set()
        
        # 1. Direct deployment_name field (primary field for all agents)
        if agent.get("deployment_name"):
            models.add(agent["deployment_name"].lower())
        
        # 2. Legacy model field (for backwards compatibility)
        if agent.get("model"):
            models.add(agent["model"].lower())
        
        # 3. Config section models
        config = agent.get("config", {})
        if isinstance(config, dict):
            # Common model fields in config
            model_fields = ["model", "deployment_name", "engine"]
            for field in model_fields:
                if config.get(field):
                    models.add(config[field].lower())
        
        # 4. Advanced: Parse instructions for model references (if needed for legacy configs)
        instructions = agent.get("instructions", "") or agent.get("system_message", "")
        if instructions:
            models.update(self.extract_models_from_text(instructions))
        
        return models
    
    def extract_models_from_text(self, text: str) -> set:
        """
        Extract model names from text using pattern matching
        
        Args:
            text: Text to search for model references
            
        Returns:
            Set of model names found in text
        """
        import re
        models = set()
        text_lower = text.lower()
        
        # Common model patterns
        model_patterns = [
            r'gpt-4o(?:-\w+)?',
            r'gpt-4(?:-\w+)?',
            r'gpt-35-turbo(?:-\w+)?',
            r'gpt-3\.5-turbo(?:-\w+)?',
            r'claude-3(?:-\w+)?',
            r'claude-2(?:-\w+)?',
            r'gemini-pro(?:-\w+)?',
            r'mistral-\w+',
            r'llama-?\d+(?:-\w+)?',
            r'text-davinci-\d+',
            r'text-embedding-\w+',
            r'ada-\d+',
            r'babbage-\d+',
            r'curie-\d+',
            r'davinci-\d+',
        ]
        
        for pattern in model_patterns:
            matches = re.findall(pattern, text_lower)
            models.update(matches)
        
        return models
    
    async def validate_team_models(self, team_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that all models required by agents in the team config are deployed
        
        Args:
            team_config: The team configuration dictionary
            
        Returns:
            Tuple of (is_valid, list_of_missing_models)
        """
        try:
            # Get list of available deployments
            deployments = await self.list_model_deployments()
            available_models = [d.get("name", "").lower() for d in deployments if d.get("status") == "Succeeded"]
            
            # Extract required models from team config
            required_models = set()
            agents = team_config.get("agents", [])
            
            for agent in agents:
                agent_models = self.extract_models_from_agent(agent)
                required_models.update(agent_models)
            
            # Also check team-level model configurations
            team_level_models = self.extract_team_level_models(team_config)
            required_models.update(team_level_models)
            
            # If no specific models found, assume default model is required
            if not required_models:
                default_model = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")
                required_models.add(default_model.lower())
            
            # Check which models are missing
            missing_models = []
            for model in required_models:
                if model not in available_models:
                    missing_models.append(model)
            
            is_valid = len(missing_models) == 0
            
            if not is_valid:
                logging.warning(f"Missing model deployments: {missing_models}")
                logging.info(f"Available deployments: {available_models}")
            
            return is_valid, missing_models
            
        except Exception as e:
            logging.error(f"Error validating team models: {e}")
            # Return True to not block uploads if validation fails
            return True, []
    
    async def get_deployment_status_summary(self) -> Dict[str, Any]:
        """Get a summary of deployment status for debugging/monitoring"""
        try:
            deployments = await self.list_model_deployments()
            
            summary = {
                "total_deployments": len(deployments),
                "successful_deployments": [],
                "failed_deployments": [],
                "pending_deployments": []
            }
            
            for deployment in deployments:
                name = deployment.get("name", "unknown")
                status = deployment.get("status", "unknown")
                
                if status == "Succeeded":
                    summary["successful_deployments"].append(name)
                elif status in ["Failed", "Canceled"]:
                    summary["failed_deployments"].append(name)
                else:
                    summary["pending_deployments"].append(name)
            
            return summary
            
        except Exception as e:
            logging.error(f"Error getting deployment summary: {e}")
            return {"error": str(e)}
    
    def extract_team_level_models(self, team_config: Dict[str, Any]) -> set:
        """
        Extract model references from team-level configuration
        
        Args:
            team_config: The team configuration dictionary
            
        Returns:
            Set of model names found at team level
        """
        models = set()
        
        # Team-level model configurations
        team_model_fields = ["default_model", "model", "llm_model"]
        for field in team_model_fields:
            if team_config.get(field):
                models.add(team_config[field].lower())
        
        # Check team settings
        settings = team_config.get("settings", {})
        if isinstance(settings, dict):
            for field in ["model", "deployment_name"]:
                if settings.get(field):
                    models.add(settings[field].lower())
        
        # Check environment configurations
        env_config = team_config.get("environment", {})
        if isinstance(env_config, dict):
            for field in ["model", "openai_deployment"]:
                if env_config.get(field):
                    models.add(env_config[field].lower())
        
        return models
