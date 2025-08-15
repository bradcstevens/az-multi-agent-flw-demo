from typing import Any, Dict

from azure.ai.projects.aio import AIProjectClient

from common.config.app_config import config


class FoundryService:
    """Helper around Azure AI Foundry's AIProjectClient.

    Uses AppConfig.get_ai_project_client() to obtain a properly configured
    asynchronous client. Provides a small set of convenience methods and
    can be extended for specific project operations.
    """

    def __init__(self, client: AIProjectClient | None = None) -> None:
        self._client = client

    async def get_client(self) -> AIProjectClient:
        if self._client is None:
            self._client = config.get_ai_project_client()
        return self._client

    # Example convenience wrappers – adjust as your project needs evolve
    async def list_connections(self) -> list[Dict[str, Any]]:
        client = await self.get_client()
        conns = await client.connections.list()
        return [c.as_dict() if hasattr(c, "as_dict") else dict(c) for c in conns]

    async def get_connection(self, name: str) -> Dict[str, Any]:
        client = await self.get_client()
        conn = await client.connections.get(name=name)
        return conn.as_dict() if hasattr(conn, "as_dict") else dict(conn)
