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
                # Check for model in agent configuration
                model = agent.get("model")
                if model:
                    required_models.add(model.lower())
                
                # Check for model in agent settings/config
                agent_config = agent.get("config", {})
                if isinstance(agent_config, dict):
                    config_model = agent_config.get("model") or agent_config.get("deployment_name")
                    if config_model:
                        required_models.add(config_model.lower())
                
                # Check for model in instructions or other fields that might contain model references
                instructions = agent.get("instructions", "")
                if "gpt-4o" in instructions.lower():
                    required_models.add("gpt-4o")
                elif "gpt-4" in instructions.lower():
                    required_models.add("gpt-4")
                elif "gpt-35-turbo" in instructions.lower():
                    required_models.add("gpt-35-turbo")
            
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
