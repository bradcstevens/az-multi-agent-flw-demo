"""The embedding deployment the Identity boundary gate's similarity tier uses.

ADR-014 puts `text-embedding-3-small` in the first deployment because the
similarity tier cannot run without it. This client is the one place that talks
to it: the Guardrail corpus harness embeds probes through it while tuning the
threshold, and the gate embeds requests through it in production.

It subclasses `BaseAPIService` so tests drive it by patching the inherited
request method, and it takes its endpoint, deployment and token provider as
arguments rather than reading AppConfig — the Guardrail corpus harness points
it at the deployed environment, and the gate will point it at AppConfig when
#14 wires the gate up.
"""

from typing import Any, Awaitable, Callable, List, Sequence

from backend.services.base_api_service import BaseAPIService

DEFAULT_EMBEDDING_DEPLOYMENT = "text-embedding-3-small"
COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"

TokenProvider = Callable[[], Awaitable[str]]


class EmbeddingClient(BaseAPIService):
    """Azure OpenAI embeddings, keyless."""

    def __init__(
        self,
        endpoint: str,
        deployment: str,
        *,
        api_version: str,
        token_provider: TokenProvider,
        **kwargs: Any,
    ) -> None:
        super().__init__(endpoint, **kwargs)
        self.deployment = deployment
        self.api_version = api_version
        self._token_provider = token_provider

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of texts, returned in request order.

        The service is not obliged to return the batch in the order it was
        sent, so the vectors are reordered by the index it stamps on each one:
        a corpus scored against the wrong probe would be silently wrong rather
        than loudly wrong. A short response raises instead of being padded.
        """
        if not texts:
            return []

        token = await self._token_provider()
        payload = await self.post_json(
            f"openai/deployments/{self.deployment}/embeddings",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            params={"api-version": self.api_version},
            json={"input": list(texts)},
        )

        data = payload.get("data") or []
        if len(data) != len(texts):
            raise ValueError(
                f"embedding deployment '{self.deployment}' returned "
                f"{len(data)} vectors for {len(texts)} texts"
            )

        ordered = sorted(data, key=lambda item: item.get("index", 0))
        return [list(item["embedding"]) for item in ordered]

    async def embed_one(self, text: str) -> List[float]:
        """Embed a single text."""
        (vector,) = await self.embed([text])
        return vector
