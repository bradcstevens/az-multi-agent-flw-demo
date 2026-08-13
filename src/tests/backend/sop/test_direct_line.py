"""The Direct Line client the orchestrator reaches the SOP agent through (#18).

The seam is the request method the client inherits from `BaseAPIService` — the
pattern `test_embeddings.py` already uses — so no outbound-HTTP mocking
dependency is added. Every payload here is the shape recorded live in
`docs/copilot-studio/sop-agent.md`.
"""

from unittest.mock import AsyncMock

import pytest

from sop.direct_line import (CHANNEL_SETTINGS_API_VERSION, DIRECT_LINE_FAILURE,
                             REGIONAL_CHANNEL_SETTINGS, DirectLineClient)

TOKEN_ENDPOINT = (
    "https://0f87abfb.environment.api.powerplatform.com/powervirtualagents"
    "/botsbyschema/cr48b_StoreSopAssistant/directline/token"
    "?api-version=2022-03-01-preview"
)
# What `PvaGetDirectLineEndpoint` actually returned for the published agent on
# 2026-08-13. This host serves the token but **not** the channel settings.
GATEWAY_TOKEN_ENDPOINT = (
    "https://powervamg.us-il102.gateway.prod.island.powerapps.com"
    "/api/botmanagement/v1/directline/directlinetoken?botId=2796f713&tenantId=0f87abfb"
)
REGIONAL_DIRECT_LINE = "https://unitedstates.directline.botframework.com/v3/directline"
CONVERSATION = "8Yq3RmzL2NfKpX1"
SOP_102 = "SOP-102 Store Closing Procedure.docx"
ANSWER = "1. Count the drawer.\n2. Lock the safe. [1]"


def direct_line_jwt(audience="https://directline.botframework.com/"):
    """A Direct Line token, whose claims name the service that issued it.

    Unsigned-shaped on purpose: nothing here verifies the token, it only reads
    where the service that minted it says it lives.
    """
    import base64
    import json

    def segment(payload):
        raw = json.dumps(payload).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    claims = {"bot": "2796f713", "conv": CONVERSATION, "nbf": 0, "exp": 3600}
    if audience:
        claims["iss"] = audience
        claims["aud"] = audience
    return f"{segment({'alg': 'RS256'})}.{segment(claims)}.signature"


def channel_settings():
    return {
        "channelUrlsById": {
            "directline": REGIONAL_DIRECT_LINE,
            "webchat": "https://unitedstates.webchat.botframework.com/",
        }
    }


def token_payload(token=None, expires_in=3600):
    return {
        "token": token or direct_line_jwt(),
        "expires_in": expires_in,
        "conversationId": CONVERSATION,
    }


def bot_message(identifier="reply-1", text=ANSWER, cites=(SOP_102,)):
    """A bot-role message activity, optionally citing documents."""
    activity = {
        "id": identifier,
        "type": "message",
        "from": {"id": "bot-server-generated", "role": "bot"},
        "text": text,
    }
    if cites:
        activity["entities"] = [
            {
                "type": "https://schema.org/Message",
                "citation": [
                    {
                        "@type": "Claim",
                        "position": position + 1,
                        "appearance": {
                            "@type": "DigitalDocument",
                            "name": name,
                            "abstract": name,
                            "text": f"<h1>{name.split(' ', 1)[1]}</h1> body",
                        },
                    }
                    for position, name in enumerate(cites)
                ],
            }
        ]
    return activity


def user_echo(identifier="echo-1", text="How do I close the store?"):
    """Direct Line echoes the caller's own activity back on the transcript."""
    return {
        "id": identifier,
        "type": "message",
        "from": {"id": "server-replaced-this", "role": "user"},
        "text": text,
    }


class FakeTransport:
    """Canned responses keyed by (method, url-fragment), in call order."""

    def __init__(self, *responses):
        self.queue = list(responses)
        self.calls = []

    async def __call__(self, method, path="", **kwargs):
        self.calls.append((method.upper(), path, kwargs))
        payload = self.queue.pop(0) if self.queue else {}
        if isinstance(payload, Exception):
            raise payload
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value=payload)
        response.raise_for_status = lambda: None
        return response


def client_with(*responses, **kwargs):
    """A `DirectLineClient` whose inherited request method is the transport."""
    client = DirectLineClient(TOKEN_ENDPOINT, poll_interval=0, retry_delay=0, **kwargs)
    client._request = FakeTransport(*responses)
    return client


def conversation_responses(*activity_batches, token=None):
    """Channel settings, token, conversation start, then activity polls."""
    # The token comes first: the base URL is resolved from the token's own
    # claims where an environment serves no channel settings.
    responses = [token or token_payload(), channel_settings()]
    responses.extend(conversation_only(*activity_batches))
    return responses


def conversation_only(*activity_batches):
    """The conversation itself, for a client whose base and token are cached."""
    responses = [
        {"conversationId": CONVERSATION, "token": direct_line_jwt()},
        {},
    ]
    for index, batch in enumerate(activity_batches):
        responses.append({"activities": list(batch), "watermark": str(index + 1)})
    return responses


def after_setup(*responses):
    """Responses that begin once the base URL and token have been resolved."""
    return [token_payload(), channel_settings(), *responses]


def conversation_with_token(*activity_batches):
    """A second conversation, which needs a token of its very own."""
    return [token_payload(), *conversation_only(*activity_batches)]


def retry(*responses):
    """The retry attempt, which fetches its own token before anything else."""
    return [token_payload(), *responses]


class TestAsk:
    @pytest.mark.asyncio
    async def test_returns_the_agents_answer(self):
        client = client_with(*conversation_responses([bot_message()]))

        answer = await client.ask("How do I close the store?")

        assert answer.text == ANSWER

    @pytest.mark.asyncio
    async def test_carries_the_citation_the_grounding_panel_needs(self):
        client = client_with(*conversation_responses([bot_message()]))

        answer = await client.ask("How do I close the store?")

        assert [citation.name for citation in answer.citations] == [SOP_102]

    @pytest.mark.asyncio
    async def test_ignores_the_echo_of_our_own_message(self):
        # Direct Line replaces the sender identifier with a server-generated
        # value, so the role is the only reliable way to tell the agent's
        # activities from the echo of ours. Returning the echo would answer a
        # procedure question with the question.
        client = client_with(
            *conversation_responses([user_echo(), bot_message()])
        )

        answer = await client.ask("How do I close the store?")

        assert answer.text == ANSWER

    @pytest.mark.asyncio
    async def test_keeps_polling_while_only_the_echo_has_arrived(self):
        # The agent takes 5-20 seconds to answer, so the first poll routinely
        # sees nothing but the echo. Treating that as the reply would make
        # every answer the question.
        client = client_with(
            *conversation_responses([user_echo()], [bot_message()])
        )

        answer = await client.ask("How do I close the store?")

        assert answer.text == ANSWER

    @pytest.mark.asyncio
    async def test_de_duplicates_by_activity_identifier(self):
        # A watermark the service does not advance replays activities already
        # seen; without de-duplication the answer is printed twice.
        reply = bot_message()
        client = client_with(*conversation_responses([reply, dict(reply)]))

        answer = await client.ask("How do I close the store?")

        assert answer.text == ANSWER
        assert [citation.name for citation in answer.citations] == [SOP_102]

    @pytest.mark.asyncio
    async def test_starts_a_fresh_conversation_for_every_question(self):
        # A published change never reaches a conversation that is already open
        # (CONTEXT.md, "Publish propagation"), so reusing one is how a
        # rehearsal convinces itself a fix did not work.
        client = client_with(
            *conversation_responses([bot_message()]),
            *conversation_with_token([bot_message("reply-2", text="Second.")]),
        )

        await client.ask("How do I close the store?")
        await client.ask("How do I open the store?")

        starts = [
            call
            for call in client._request.calls
            if call[0] == "POST" and call[1].endswith("/conversations")
        ]
        assert len(starts) == 2

    @pytest.mark.asyncio
    async def test_a_token_is_never_reused_for_a_second_conversation(self):
        # Measured live 2026-08-13: a Copilot Studio Direct Line token carries
        # a `conv` claim, so starting a conversation with a token that has
        # already been spent rejoins the *old* conversation and replays its
        # transcript. The second question then answers with the first answer —
        # observed, and the reason a token is fetched per conversation rather
        # than cached for its 3600-second life.
        client = client_with(
            *conversation_responses([bot_message()]),
            *conversation_with_token([bot_message("reply-2", text="Second.")]),
        )

        await client.ask("How do I close the store?")
        await client.ask("How do I open the store?")

        token_calls = [call for call in client._request.calls if "/token" in call[1]]
        assert len(token_calls) == 2


class TestDirectLineBase:
    @pytest.mark.asyncio
    async def test_reads_the_base_url_from_the_regional_channel_settings(self):
        client = client_with(*conversation_responses([bot_message()]))

        await client.ask("How do I close the store?")

        settings_calls = [
            call
            for call in client._request.calls
            if REGIONAL_CHANNEL_SETTINGS in call[1]
        ]
        assert settings_calls
        assert all(
            REGIONAL_DIRECT_LINE in call[1]
            for call in client._request.calls
            if "/conversations" in call[1]
        )

    @pytest.mark.asyncio
    async def test_the_environments_channel_settings_win_over_the_token_claim(self):
        # Microsoft's own working sample reads `channelUrlsById.directline`
        # from the settings service. Where an environment serves one, it is
        # the answer — the token claim is only for environments that do not.
        client = client_with(
            channel_settings(),
            token_payload(direct_line_jwt("https://directline.botframework.com/")),
        )

        assert await client.direct_line_base() == REGIONAL_DIRECT_LINE

    @pytest.mark.asyncio
    async def test_falls_back_to_the_service_the_token_says_issued_it(self):
        # Measured live 2026-08-13: this tenant's Default environment is on the
        # legacy `powervamg…gateway…powerapps.com` host, which serves the token
        # but answers 404 for `regionalchannelsettings`. The token it mints
        # names its own Direct Line service in `iss`/`aud`, so the base is still
        # read from the service rather than assembled here.
        client = DirectLineClient(GATEWAY_TOKEN_ENDPOINT, poll_interval=0, retry_delay=0)
        client._request = FakeTransport(
            RuntimeError("404 Not Found"),
            token_payload(direct_line_jwt("https://europe.directline.botframework.com/")),
        )

        assert await client.direct_line_base() == (
            "https://europe.directline.botframework.com/v3/directline"
        )

    @pytest.mark.asyncio
    async def test_never_assembles_the_default_direct_line_hostname(self):
        # Neither source named a service: fail loudly here rather than quietly
        # against a hostname nobody chose.
        client = client_with(
            {"channelUrlsById": {"webchat": "https://wc/"}},
            token_payload(direct_line_jwt(audience=None)),
        )

        with pytest.raises(ValueError, match="never assembled"):
            await client.direct_line_base()

    @pytest.mark.asyncio
    async def test_asks_the_settings_service_on_the_token_endpoints_own_terms(self):
        # Microsoft's sample reads the api-version off the token endpoint
        # rather than pinning one, so an environment on a newer contract is
        # asked on its own terms instead of being told what it supports.
        endpoint = TOKEN_ENDPOINT.replace("2022-03-01-preview", "2099-01-01")
        client = DirectLineClient(endpoint, poll_interval=0, retry_delay=0)
        client._request = FakeTransport(channel_settings())

        await client.direct_line_base()

        assert client._request.calls[0][2]["params"] == {"api-version": "2099-01-01"}

    @pytest.mark.asyncio
    async def test_a_token_endpoint_with_no_api_version_falls_back_to_the_known_one(self):
        # The legacy gateway endpoint carries `botId` and `tenantId` and no
        # api-version at all, so there is nothing to read off it.
        client = DirectLineClient(
            GATEWAY_TOKEN_ENDPOINT, poll_interval=0, retry_delay=0
        )
        client._request = FakeTransport(channel_settings())

        await client.direct_line_base()

        assert client._request.calls[0][2]["params"] == {
            "api-version": CHANNEL_SETTINGS_API_VERSION
        }

    @pytest.mark.asyncio
    async def test_resolves_the_base_url_once_per_client(self):
        client = client_with(
            *conversation_responses([bot_message()]),
            *conversation_only([bot_message("reply-2", text="Second.")]),
        )

        await client.ask("How do I close the store?")
        await client.ask("How do I open the store?")

        settings_calls = [
            call
            for call in client._request.calls
            if REGIONAL_CHANNEL_SETTINGS in call[1]
        ]
        assert len(settings_calls) == 1


class TestToken:
    @pytest.mark.asyncio
    async def test_reads_the_life_the_service_reports_rather_than_assuming_one(self):
        # ADR-011 correction 8: 3600 seconds, not the 30 minutes the superseded
        # document states. Read off the payload, so an environment reporting
        # something else is believed.
        client = client_with(token_payload(expires_in=1800))

        await client.token()

        assert client._token_lifetime == 1800

    @pytest.mark.asyncio
    async def test_an_answer_timeout_that_outlives_its_token_is_refused(self):
        # A conversation held open past its token's life reads as the agent
        # falling silent, which is indistinguishable from a grounding failure.
        client = client_with(
            token_payload(expires_in=30),
            channel_settings(),
            token_payload(expires_in=30),
            *conversation_only([bot_message()]),
            answer_timeout=45,
        )

        answer = await client.ask("How do I close the store?")

        assert answer.failed is True
        assert not [c for c in client._request.calls if c[0] == "POST"]

    @pytest.mark.asyncio
    async def test_the_token_endpoint_is_the_one_the_environment_published(self):
        client = client_with(token_payload())

        await client.token()

        assert client._request.calls[0][1] == TOKEN_ENDPOINT


class TestFailure:
    @pytest.mark.asyncio
    async def test_retries_once_and_then_returns_the_fixed_failure_message(self):
        client = client_with(
            *after_setup(RuntimeError("Direct Line 502")),
            *retry(RuntimeError("Direct Line 502")),
        )

        answer = await client.ask("How do I close the store?")

        assert answer.text == DIRECT_LINE_FAILURE
        assert answer.failed is True

    @pytest.mark.asyncio
    async def test_a_second_attempt_that_succeeds_is_the_answer(self):
        client = client_with(
            *after_setup(RuntimeError("Direct Line 502")),
            *retry(*conversation_only([bot_message()])),
        )

        answer = await client.ask("How do I close the store?")

        assert answer.text == ANSWER
        assert answer.failed is False

    @pytest.mark.asyncio
    async def test_retries_exactly_once(self):
        # "One fast retry" is the rule: a client that retried indefinitely
        # would hold the orchestrator open through a whole outage.
        client = client_with(
            *after_setup(RuntimeError("Direct Line 502")),
            *retry(*([RuntimeError("Direct Line 502")] * 4)),
        )

        await client.ask("How do I close the store?")

        starts = [
            call
            for call in client._request.calls
            if call[0] == "POST" and call[1].endswith("/conversations")
        ]
        assert len(starts) == 2

    @pytest.mark.asyncio
    async def test_the_failure_message_offers_no_procedure_of_its_own(self):
        # No fallback to model knowledge and no local copy of the SOP corpus:
        # a hidden fallback would make the cross-platform claim unfalsifiable.
        client = client_with(
            *after_setup(RuntimeError("Direct Line 502")),
            *retry(RuntimeError("Direct Line 502")),
        )

        answer = await client.ask("How do I close the store?")

        assert answer.citations == []
        assert "shift lead" in answer.text

    @pytest.mark.asyncio
    async def test_an_agent_that_says_nothing_is_a_failure_not_an_empty_answer(self):
        client = client_with(
            *after_setup(*conversation_only([])),
            *retry(*conversation_only([])),
            answer_timeout=0,
        )

        answer = await client.ask("How do I close the store?")

        assert answer.failed is True
