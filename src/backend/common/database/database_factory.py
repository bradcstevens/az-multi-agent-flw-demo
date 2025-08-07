"""Database factory for creating database instances."""

import logging
from typing import Optional

from .cosmosdb import CosmosDBClient
from .database_base import DatabaseBase


class DatabaseFactory:
    """Factory class for creating database instances."""

    _instance: Optional[DatabaseBase] = None
    _logger = logging.getLogger(__name__)

    @staticmethod
    async def get_database(
        endpoint: str,
        credential: any,
        database_name: str,
        container_name: str,
        session_id: str = "",
        user_id: str = "",
        force_new: bool = False,
    ) -> DatabaseBase:
        """
        Get a database instance.

        Args:
            endpoint: CosmosDB endpoint URL
            credential: Azure credential for authentication
            database_name: Name of the CosmosDB database
            container_name: Name of the CosmosDB container
            session_id: Session ID for partitioning
            user_id: User ID for data isolation
            force_new: Force creation of new instance

        Returns:
            DatabaseBase: Database instance
        """

        # Create new instance if forced or if singleton doesn't exist
        if force_new or DatabaseFactory._instance is None:
            cosmos_db_client = CosmosDBClient(
                endpoint=endpoint,
                credential=credential,
                database_name=database_name,
                container_name=container_name,
                session_id=session_id,
                user_id=user_id,
            )

            await cosmos_db_client.initialize()

            if not force_new:
                DatabaseFactory._instance = cosmos_db_client

            return cosmos_db_client

        return DatabaseFactory._instance

    @staticmethod
    async def create_database(
        endpoint: str,
        credential: any,
        database_name: str,
        container_name: str,
        session_id: str = "",
        user_id: str = "",
    ) -> DatabaseBase:
        """
        Create a new database instance (always creates new).

        Args:
            endpoint: CosmosDB endpoint URL
            credential: Azure credential for authentication
            database_name: Name of the CosmosDB database
            container_name: Name of the CosmosDB container
            session_id: Session ID for partitioning
            user_id: User ID for data isolation

        Returns:
            DatabaseBase: New database instance
        """
        return await DatabaseFactory.get_database(
            endpoint=endpoint,
            credential=credential,
            database_name=database_name,
            container_name=container_name,
            session_id=session_id,
            user_id=user_id,
            force_new=True,
        )

    @staticmethod
    def reset():
        """Reset the factory (mainly for testing)."""
        DatabaseFactory._instance = None

    @staticmethod
    async def close_all():
        """Close all database connections."""
        if DatabaseFactory._instance:
            await DatabaseFactory._instance.close()
            DatabaseFactory._instance = None
