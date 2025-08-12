"""
Service for validating Azure AI Search index endpoints during team configuration upload.
"""

import os
import logging
from typing import Dict, Any, Tuple, List
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError, ClientAuthenticationError, HttpResponseError

logger = logging.getLogger(__name__)


class SearchValidationService:
    """Service for validating Azure AI Search indexes."""
    
    def __init__(self):
        """Initialize the search validation service."""
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_KEY")
        
        # Use key-based auth if available, otherwise use DefaultAzureCredential
        if self.search_key:
            self.credential = AzureKeyCredential(self.search_key)
        else:
            self.credential = DefaultAzureCredential()
    
    async def validate_team_search_indexes(self, team_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that all search indexes referenced in the team config exist.
        Only validates if there are actually search indexes/RAG agents in the config.
        
        Args:
            team_config: The team configuration dictionary
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        try:
            # Extract all index names from the team configuration
            index_names = self.extract_index_names(team_config)
            
            # Check if there are any RAG/search agents that need validation
            has_rag_agents = self.has_rag_or_search_agents(team_config)
            
            if not index_names and not has_rag_agents:
                # No search indexes or RAG agents specified, validation passes
                logger.info("No search indexes or RAG agents found in team config - skipping search validation")
                return True, []
            
            if not self.search_endpoint:
                if index_names or has_rag_agents:
                    error_msg = "Team configuration references search indexes but no Azure Search endpoint is configured"
                    logger.warning(error_msg)
                    return False, [error_msg]
                else:
                    # No search functionality needed and no endpoint configured - that's fine
                    return True, []
            
            if not index_names:
                # Has RAG agents but no specific indexes - validation passes (might use default)
                logger.info("RAG agents found but no specific search indexes specified")
                return True, []
            
            # Validate each unique index
            validation_errors = []
            unique_indexes = set(index_names)
            
            logger.info(f"Validating {len(unique_indexes)} search indexes: {list(unique_indexes)}")
            
            for index_name in unique_indexes:
                is_valid, error_message = await self.validate_single_index(index_name)
                if not is_valid:
                    validation_errors.append(error_message)
            
            return len(validation_errors) == 0, validation_errors
            
        except Exception as e:
            logger.error(f"Error validating search indexes: {str(e)}")
            return False, [f"Search index validation error: {str(e)}"]
    
    def extract_index_names(self, team_config: Dict[str, Any]) -> List[str]:
        """
        Extract all index names from RAG agents in the team configuration.
        Only RAG agents require index_name for search functionality.
        
        Args:
            team_config: The team configuration dictionary
            
        Returns:
            List of index names found in RAG agents
        """
        index_names = []
        
        # Check agents for index_name field (only in RAG agents)
        agents = team_config.get("agents", [])
        for agent in agents:
            if isinstance(agent, dict):
                # Only check RAG agents for index_name
                agent_type = agent.get("type", "").strip().lower()
                if agent_type == "rag":
                    # Extract index_name from RAG agents
                    index_name = agent.get("index_name")
                    if index_name and index_name.strip():
                        index_names.append(index_name.strip())
        
        # Return unique names
        return list(set(index_names))
    
    def has_rag_or_search_agents(self, team_config: Dict[str, Any]) -> bool:
        """
        Check if the team configuration contains RAG agents.
        Only RAG agents require search index validation.
        
        Args:
            team_config: The team configuration dictionary
            
        Returns:
            True if RAG agents are found, False otherwise
        """
        agents = team_config.get("agents", [])
        
        for agent in agents:
            if isinstance(agent, dict):
                # Check agent type for RAG agents (case-insensitive)
                agent_type = agent.get("type", "").strip().lower()
                if agent_type == "rag":
                    return True
        
        return False
    
    async def validate_single_index(self, index_name: str) -> Tuple[bool, str]:
        """
        Validate that a single search index exists and is accessible.
        
        Args:
            index_name: Name of the search index to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Create SearchIndexClient to check if index exists
            index_client = SearchIndexClient(
                endpoint=self.search_endpoint,
                credential=self.credential
            )
            
            # Try to get the index
            index = index_client.get_index(index_name)
            
            if index:
                logger.info(f"Search index '{index_name}' found and accessible")
                return True, ""
            else:
                error_msg = f"Search index '{index_name}' exists but may not be properly configured"
                logger.warning(error_msg)
                return False, error_msg
                
        except ResourceNotFoundError:
            error_msg = f"Search index '{index_name}' does not exist"
            logger.error(error_msg)
            return False, error_msg
            
        except ClientAuthenticationError as e:
            error_msg = f"Authentication failed for search index '{index_name}': {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
        except HttpResponseError as e:
            error_msg = f"Error accessing search index '{index_name}': {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error validating search index '{index_name}': {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def get_search_index_summary(self) -> Dict[str, Any]:
        """Get a summary of available search indexes for debugging/monitoring."""
        try:
            if not self.search_endpoint:
                return {"error": "No Azure Search endpoint configured"}
            
            index_client = SearchIndexClient(
                endpoint=self.search_endpoint,
                credential=self.credential
            )
            
            # List all indexes
            indexes = list(index_client.list_indexes())
            
            summary = {
                "search_endpoint": self.search_endpoint,
                "total_indexes": len(indexes),
                "available_indexes": [index.name for index in indexes]
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting search index summary: {e}")
            return {"error": str(e)}
