"""The embedding client the Guardrail corpus scores against (issue #13).

The seam is HTTP: the client is exercised by patching the request method it
inherits from `BaseAPIService`, the pattern the repo already uses, rather than
by adding an outbound-HTTP mocking dependency. No module-level `sys.modules`
assignment — the client takes its endpoint, deployment and token provider as
arguments, and only reaches AppConfig from `from_config`.
"""

from unittest.mock import AsyncMock

import pytest

from backend.guardrail.embeddings import EmbeddingClient

ENDPOINT = "https://aif-test.openai.azure.com/"
DEPLOYMENT = "text-embedding-3-small"


def embedding_response(*vectors, out_of_order=False):
    """An Azure OpenAI embeddings response carrying the given vectors."""
    data = [
        {"index": index, "embedding": list(vector)}
        for index, vector in enumerate(vectors)
    ]
    if out_of_order:
        data.reverse()
    return {"data": data, "model": DEPLOYMENT}


def client_with_response(payload, status=200):
    """An EmbeddingClient whose inherited request method returns `payload`."""
    client = EmbeddingClient(
        ENDPOINT,
        DEPLOYMENT,
        api_version="2024-12-01-preview",
        token_provider=AsyncMock(return_value="a-token"),
    )
    response = AsyncMock()
    response.status = status
    response.json = AsyncMock(return_value=payload)
    response.raise_for_status = lambda: None
    client._request = AsyncMock(return_value=response)
    return client


class TestEmbed:
    @pytest.mark.asyncio
    async def test_returns_a_vector_per_text(self):
        client = client_with_response(embedding_response([0.1, 0.2], [0.3, 0.4]))

        assert await client.embed(["one", "two"]) == [[0.1, 0.2], [0.3, 0.4]]

    @pytest.mark.asyncio
    async def test_reorders_vectors_by_the_index_the_service_returns(self):
        # The service is not required to return the batch in request order,
        # and a corpus scored against the wrong probe would be silently wrong.
        client = client_with_response(
            embedding_response([0.1, 0.2], [0.3, 0.4], out_of_order=True)
        )

        assert await client.embed(["one", "two"]) == [[0.1, 0.2], [0.3, 0.4]]

    @pytest.mark.asyncio
    async def test_posts_to_the_deployment_s_embeddings_path(self):
        client = client_with_response(embedding_response([0.1]))

        await client.embed(["one"])

        method, path = client._request.call_args.args
        assert method == "POST"
        assert path == f"openai/deployments/{DEPLOYMENT}/embeddings"

    @pytest.mark.asyncio
    async def test_sends_the_texts_as_the_input_payload(self):
        client = client_with_response(embedding_response([0.1], [0.2]))

        await client.embed(["one", "two"])

        assert client._request.call_args.kwargs["json"]["input"] == ["one", "two"]

    @pytest.mark.asyncio
    async def test_pins_the_api_version(self):
        client = client_with_response(embedding_response([0.1]))

        await client.embed(["one"])

        assert client._request.call_args.kwargs["params"] == {
            "api-version": "2024-12-01-preview"
        }

    @pytest.mark.asyncio
    async def test_authorises_with_the_token_provider(self):
        client = client_with_response(embedding_response([0.1]))

        await client.embed(["one"])

        headers = client._request.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer a-token"

    @pytest.mark.asyncio
    async def test_an_empty_batch_makes_no_request(self):
        client = client_with_response(embedding_response())

        assert await client.embed([]) == []
        client._request.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_short_response_is_an_error_rather_than_a_silent_miss(self):
        client = client_with_response(embedding_response([0.1]))

        with pytest.raises(ValueError, match="2 texts"):
            await client.embed(["one", "two"])

    @pytest.mark.asyncio
    async def test_embed_one_returns_a_single_vector(self):
        client = client_with_response(embedding_response([0.1, 0.2]))

        assert await client.embed_one("one") == [0.1, 0.2]
