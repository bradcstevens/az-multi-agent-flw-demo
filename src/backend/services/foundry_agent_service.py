"""
Foundry Agent Service
Service for creating and managing agents in Azure AI Foundry based on scenario data
"""

import logging
import json
from typing import Dict, Any, List, Tuple, Optional
from azure.ai.projects.aio import AIProjectClient
from app_config import config
from utils_kernel import rai_validate_team_config

logger = logging.getLogger(__name__)


class FoundryAgentService:
    """Service for creating agents in Azure AI Foundry from scenario data."""
    
    def __init__(self):
        """Initialize the Foundry Agent Service."""
        self.client = None
    
    async def get_ai_project_client(self) -> AIProjectClient:
        """Get the AI Project client for Foundry operations."""
        if not self.client:
            self.client = config.get_ai_project_client()
        return self.client
    
    async def validate_scenario_descriptions(self, scenario_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate all description fields in the scenario data using RAI checks.
        
        Args:
            scenario_data: The scenario data dictionary containing scenarios and agents
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Use the existing RAI validation function from utils_kernel
            is_valid, error_message = await rai_validate_team_config(scenario_data)
            
            if not is_valid:
                logger.warning(f"RAI validation failed for scenario data: {error_message}")
                return False, error_message
            
            logger.info("RAI validation passed for scenario data")
            return True, ""
            
        except Exception as e:
            error_msg = f"Error during RAI validation: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def extract_scenarios_and_agents(self, scenario_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract scenario and agent information from the uploaded JSON.
        
        Expected JSON structure:
        {
            "scenarios": [
                {
                    "name": "Scenario Name",
                    "description": "Scenario description",
                    "agents": [
                        {
                            "name": "Agent Name",
                            "description": "Agent description",
                            "instructions": "Agent instructions",
                            "deployment_name": "model-deployment-name",
                            "type": "agent_type"
                        }
                    ]
                }
            ]
        }
        
        Args:
            scenario_data: The parsed JSON data
            
        Returns:
            List of agent configurations to create
        """
        agents_to_create = []
        
        scenarios = scenario_data.get("scenarios", [])
        if not scenarios:
            logger.warning("No scenarios found in uploaded data")
            return agents_to_create
        
        for scenario_idx, scenario in enumerate(scenarios):
            if not isinstance(scenario, dict):
                logger.warning(f"Scenario {scenario_idx} is not a valid dictionary")
                continue
            
            scenario_name = scenario.get("name", f"Scenario {scenario_idx + 1}")
            scenario_description = scenario.get("description", "")
            scenario_agents = scenario.get("agents", [])
            
            if not isinstance(scenario_agents, list):
                logger.warning(f"Agents in scenario '{scenario_name}' is not a valid list")
                continue
            
            for agent_idx, agent in enumerate(scenario_agents):
                if not isinstance(agent, dict):
                    logger.warning(f"Agent {agent_idx} in scenario '{scenario_name}' is not a valid dictionary")
                    continue
                
                # Extract agent information
                agent_config = {
                    "scenario_name": scenario_name,
                    "scenario_description": scenario_description,
                    "name": agent.get("name", f"Agent {agent_idx + 1}"),
                    "description": agent.get("description", ""),
                    "instructions": agent.get("instructions", agent.get("system_message", "")),
                    "deployment_name": agent.get("deployment_name", ""),
                    "type": agent.get("type", "generic"),
                    "tools": agent.get("tools", []),
                    "metadata": {
                        "scenario_index": scenario_idx,
                        "agent_index": agent_idx,
                        "created_from": "scenario_upload"
                    }
                }
                
                # Validate required fields
                if not agent_config["name"]:
                    logger.warning(f"Agent {agent_idx} in scenario '{scenario_name}' is missing a name")
                    continue
                
                if not agent_config["deployment_name"]:
                    logger.warning(f"Agent '{agent_config['name']}' in scenario '{scenario_name}' is missing deployment_name")
                    continue
                
                agents_to_create.append(agent_config)
        
        logger.info(f"Extracted {len(agents_to_create)} agents from {len(scenarios)} scenarios")
        return agents_to_create
    
    async def create_foundry_agent(self, agent_config: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """
        Create a single agent in Azure AI Foundry.
        
        Args:
            agent_config: Agent configuration dictionary
            
        Returns:
            Tuple of (success, error_message, agent_id)
        """
        try:
            client = await self.get_ai_project_client()
            
            # Prepare agent creation payload for Foundry
            agent_payload = {
                "model": agent_config["deployment_name"],
                "name": agent_config["name"],
                "description": agent_config["description"],
                "instructions": agent_config["instructions"],
                "metadata": {
                    **agent_config["metadata"],
                    "scenario_name": agent_config["scenario_name"],
                    "agent_type": agent_config["type"]
                }
            }
            
            # Add tools if specified
            if agent_config.get("tools"):
                agent_payload["tools"] = agent_config["tools"]
            
            # Create the agent using the AI Project client
            logger.info(f"Creating agent '{agent_config['name']}' in Foundry with model '{agent_config['deployment_name']}'")
            
            # Use the agents client to create the agent
            created_agent = await client.agents.create(**agent_payload)
            
            if created_agent and hasattr(created_agent, 'id'):
                agent_id = created_agent.id
                logger.info(f"Successfully created agent '{agent_config['name']}' with ID: {agent_id}")
                return True, "", agent_id
            else:
                error_msg = f"Failed to create agent '{agent_config['name']}': No agent ID returned"
                logger.error(error_msg)
                return False, error_msg, None
                
        except Exception as e:
            error_msg = f"Error creating agent '{agent_config['name']}' in Foundry: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
    
    async def create_agents_from_scenarios(self, scenario_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Process scenario data and create all agents in Azure AI Foundry.
        
        Args:
            scenario_data: The complete scenario data dictionary
            
        Returns:
            Tuple of (success, error_message, results_summary)
        """
        try:
            # First, validate all descriptions with RAI
            rai_valid, rai_error = await self.validate_scenario_descriptions(scenario_data)
            if not rai_valid:
                return False, f"RAI validation failed: {rai_error}", {}
            
            # Extract scenarios and agents
            agents_to_create = self.extract_scenarios_and_agents(scenario_data)
            
            if not agents_to_create:
                return False, "No valid agents found in scenario data", {}
            
            # Create agents in Foundry
            created_agents = []
            failed_agents = []
            
            for agent_config in agents_to_create:
                success, error_msg, agent_id = await self.create_foundry_agent(agent_config)
                
                if success and agent_id:
                    created_agents.append({
                        "name": agent_config["name"],
                        "agent_id": agent_id,
                        "scenario": agent_config["scenario_name"],
                        "deployment_name": agent_config["deployment_name"]
                    })
                else:
                    failed_agents.append({
                        "name": agent_config["name"],
                        "scenario": agent_config["scenario_name"],
                        "error": error_msg
                    })
            
            # Prepare results summary
            results = {
                "total_agents": len(agents_to_create),
                "created_count": len(created_agents),
                "failed_count": len(failed_agents),
                "created_agents": created_agents,
                "failed_agents": failed_agents
            }
            
            if failed_agents:
                # Some agents failed - return partial success
                error_summary = f"Created {len(created_agents)} agents successfully, but {len(failed_agents)} failed"
                logger.warning(error_summary)
                return False, error_summary, results
            else:
                # All agents created successfully
                success_msg = f"Successfully created all {len(created_agents)} agents in Azure AI Foundry"
                logger.info(success_msg)
                return True, success_msg, results
                
        except Exception as e:
            error_msg = f"Unexpected error processing scenarios: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, {}
