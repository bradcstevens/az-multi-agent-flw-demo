"""The MCP container's one way of reaching the backend (issue #18).

The container has no Azure credentials, no Cosmos connection and no Direct Line
client — by design. Everything it cannot do itself it asks the backend for over
HTTP, using the backend URL already configured for it.

`AskUserService` built its `httpx.AsyncClient` inline, which left no seam: a
test either reached the network or replaced the module. The client is that seam,
and it is tested the way this repository tests outbound HTTP everywhere else —
by patching the request method — rather than by adding a mocking dependency.
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# In local dev this is typically http://localhost:8000; in Azure it is the
# Container App URL. Falls back to localhost for convenience.
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

DEFAULT_TIMEOUT_SECONDS = 60.0


class BackendClient:
    """Async JSON POSTs to the backend, with an injectable request method."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = (base_url or BACKEND_URL).rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """The seam. Tests replace this; nothing else here touches the network."""
        async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
            return await client.request(method.upper(), self._url(path), json=json)

    async def post_json(
        self,
        path: str,
        payload: Dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """POST `payload` and return the decoded body, raising on an error status."""
        response = await self._request("POST", path, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()

    async def get_json(
        self,
        path: str,
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """GET `path` and return the decoded body, raising on an error status.

        The read half of the troubleshooting bridge (#21). A GET because the
        request carries nothing: the backend resolves which session the turn in
        flight belongs to, so there is no body for the container to send.
        """
        response = await self._request("GET", path, timeout=timeout)
        response.raise_for_status()
        return response.json()
