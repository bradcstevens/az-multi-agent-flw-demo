"""The Copilot Studio SOP agent over Direct Line (issue #18, ADR-011).

Everything ADR-011 makes binding on this client is here, and each rule is a
test in `src/tests/backend/sop/test_direct_line.py`:

- **The Direct Line hostname is never assembled.** The base URL comes from the
  environment's own regional channel settings service at runtime. This
  contradicts a snippet in the public web-security documentation and matches
  Microsoft's own working sample.
- **Tokens live 3600 seconds**, not the 30 minutes the superseded document
  states.
- **Activities are filtered to the bot role** — Direct Line replaces the sender
  identifier with a server-generated value, so the role is the only reliable
  way to tell the agent apart from the echo of our own message — and
  **de-duplicated by activity identifier**.
- **One fast retry, then a fixed failure message.** Never a fallback to model
  knowledge, and no local copy of the SOP corpus: a hidden fallback would make
  the cross-platform claim untestable and, if it fired on stage, unfalsifiable.
"""

import asyncio
import base64
import binascii
import json
import logging
import socket
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlsplit

from common.config.app_config import config

from services.base_api_service import BaseAPIService
from sop.citation import Citation, citations_from_activity

logger = logging.getLogger(__name__)

# The regional channel settings service, on the environment's own Power
# Platform host. `channelUrlsById.directline` is the only source of the Direct
# Line base URL this client will accept.
REGIONAL_CHANNEL_SETTINGS = "powervirtualagents/regionalchannelsettings"
CHANNEL_SETTINGS_API_VERSION = "2022-03-01-preview"

# ADR-011: tokens live 3600 seconds. Amended by #18 — a Copilot Studio token is
# also scoped to one conversation (it carries a `conv` claim), so this is the
# life of a single conversation's token, not the life of a cache. Used only as
# the floor when an environment reports no `expires_in`.
TOKEN_LIFETIME_SECONDS = 3600

# A generative answer over the corpus came back in 5-20 seconds live (#17).
ANSWER_TIMEOUT_SECONDS = 45
POLL_INTERVAL_SECONDS = 1.0

# How many consecutive polls must add nothing before the agent counts as having
# finished. One is not enough: a poll landing between two activities is quiet
# without the answer being over, and an answer cut short there loses its
# citations — the Grounding panel's whole subject.
SETTLE_POLLS = 2

# The two answers that mean an environment serves no channel settings service:
# the host has no such path, or the host has no such name. Everything else is
# retried — see `_is_absent`.
ABSENT_STATUSES = frozenset({404, 501})
ABSENT_DNS_ERRORS = frozenset(
    code
    for code in (
        getattr(socket, "EAI_NONAME", None),
        getattr(socket, "EAI_NODATA", None),
    )
    if code is not None
)
RETRY_DELAY_SECONDS = 0.5

# The fixed failure message. It says the SOP agent could not be reached rather
# than answering anyway, because the alternative — a plausible answer from
# somewhere else — is the one outcome this demo cannot survive.
DIRECT_LINE_FAILURE = (
    "I could not reach the store procedure assistant just now, so I have no "
    "procedure to give you. Please try again, or ask your shift lead."
)


@dataclass(frozen=True)
class SopAnswer:
    """What one question to the SOP agent produced."""

    text: str
    citations: List[Citation] = field(default_factory=list)
    failed: bool = False
    conversation_id: Optional[str] = None


def _api_base(root: str) -> str:
    """Normalise a Direct Line service root to its 3.0 API base.

    Microsoft's sample appends `v3/directline` to the URL the settings service
    names, and the token's issuer claim is a bare root too.
    """
    root = root.rstrip("/")
    if root.endswith("/v3/directline"):
        return root
    return f"{root}/v3/directline"


def _root_from_token_claims(token: str) -> Optional[str]:
    """The Direct Line service a token names as its own audience.

    The claims are read, never verified: this is not authentication, it is
    asking a token the service minted moments ago over TLS where it lives.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError, binascii.Error, UnicodeDecodeError):
        return None
    audience = claims.get("aud") or claims.get("iss")
    return audience if isinstance(audience, str) and audience else None


def _is_absent(exc: BaseException) -> bool:
    """Whether a failed settings call means *this environment has none*.

    Narrow on purpose. Only two answers are final: **404** (and 501, an API the
    host does not implement), which is how the legacy gateway says it serves no
    channel settings — finding 8 — and a name the resolver says **does not
    exist**. Everything else is this minute's weather and is retried on the next
    conversation: a 408 or 429 is the service asking for patience, a 5xx is an
    outage, and `EAI_AGAIN` is a resolver that could not reach *its* server,
    which is the opposite of a name that is not there.
    """
    status = getattr(exc, "status", None)
    if isinstance(status, int):
        return status in ABSENT_STATUSES
    causes = (exc, exc.__cause__, getattr(exc, "os_error", None))
    return any(
        isinstance(cause, socket.gaierror) and cause.errno in ABSENT_DNS_ERRORS
        for cause in causes
    )


class DirectLineClient(BaseAPIService):
    """Drives one Direct Line conversation per question, anonymously."""

    @classmethod
    def from_app_config(cls, **kwargs: Any) -> "DirectLineClient":
        """The client the SOP tool runs on in the deployed environment.

        Deliberately not named `from_config`: the inherited factory of that
        name takes an AppConfig *attribute name*, and giving a
        differently-shaped method the same name would make the base class lie
        about its own contract.
        """
        endpoint = config.COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT
        if not endpoint:
            raise ValueError(
                "COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT is not configured; "
                "it is what `PvaGetDirectLineEndpoint` returned for the "
                "published agent and is never assembled from a hostname"
            )
        return cls(endpoint, **kwargs)

    def __init__(
        self,
        token_endpoint: str,
        *,
        answer_timeout: float = ANSWER_TIMEOUT_SECONDS,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        settle_polls: int = SETTLE_POLLS,
        retry_delay: float = RETRY_DELAY_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        **kwargs: Any,
    ) -> None:
        if not token_endpoint:
            raise ValueError("token_endpoint is required")
        # The base URL is the environment's own regional Power Platform host —
        # the host that issued the token endpoint, and the one that serves the
        # channel settings. The *Direct Line* host is never derived from it.
        parts = urlsplit(token_endpoint)
        super().__init__(f"{parts.scheme}://{parts.netloc}", **kwargs)
        self.token_endpoint = token_endpoint
        self.answer_timeout = answer_timeout
        self.poll_interval = poll_interval
        self.settle_polls = settle_polls
        self.retry_delay = retry_delay
        self._clock = clock
        self._direct_line_base: Optional[str] = None
        self._settings_absent = False
        self._token_lifetime: float = TOKEN_LIFETIME_SECONDS

    def _url(self, path: str) -> str:
        """Allow an already-absolute URL through unchanged.

        The client talks to two hosts — the Power Platform environment and
        whatever Direct Line host the channel settings named — so a path is
        sometimes a full URL.
        """
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return super()._url(path)

    # ---- the two resolutions ADR-011 makes rules about -------------------

    async def direct_line_base(self, token: Optional[str] = None) -> str:
        """The Direct Line 3.0 base URL, resolved from the service at runtime.

        Never assembled here. Two sources, in order, both of them the service's
        own word:

        1. **`channelUrlsById.directline` from the regional channel settings
           service**, built from the token endpoint's own origin — Microsoft's
           working sample's path, and the one the public web-security
           documentation's hardcoded snippet contradicts.
        2. **The `aud`/`iss` claim on the token the service just issued**, for
           environments that do not serve channel settings at all. Measured
           2026-08-13: this tenant's Default environment sits on the legacy
           `powervamg…gateway…powerapps.com` host, which mints the token and
           answers 404 for the settings.

        Neither answering raises. A demo pointed at a hostname nobody chose
        fails subtly on stage; this fails loudly here.

        The answer is cached only when it is a **verdict** rather than a bad
        minute: settings that answered, or an environment that said it has no
        settings service. A 503 or a timeout resolves this one conversation
        from the token claim and leaves the preferred source to be asked again.
        """
        if self._direct_line_base:
            return self._direct_line_base
        root = await self._root_from_channel_settings()
        durable = root is not None or self._settings_absent
        if not root:
            root = _root_from_token_claims(token or await self.token())
        if not root:
            raise ValueError(
                "neither the regional channel settings service nor the token "
                "named a Direct Line service; the default hostname is never "
                "assembled (ADR-011)"
            )
        base = _api_base(root)
        if durable:
            self._direct_line_base = base
        return base

    async def _root_from_channel_settings(self) -> Optional[str]:
        """The Direct Line root the settings service names, or None."""
        try:
            settings = await self.get_json(
                REGIONAL_CHANNEL_SETTINGS,
                params={"api-version": self._channel_settings_api_version()},
            )
        except Exception as exc:
            # An environment on the legacy gateway has no settings service at
            # all. That is a shape, not an outage — the token claim answers it,
            # and the answer is good for the life of the process. Anything else
            # is this minute's weather, and is not allowed to retire the source
            # ADR-011 names.
            self._settings_absent = _is_absent(exc)
            logger.info(
                "sop: no regional channel settings (%s): %s",
                "absent" if self._settings_absent else "transient",
                exc,
            )
            return None
        return ((settings or {}).get("channelUrlsById") or {}).get("directline")

    def _channel_settings_api_version(self) -> str:
        """The api-version the token endpoint itself was issued under.

        Microsoft's sample reads it off the token endpoint rather than pinning
        one, so an environment on a newer contract is asked on its own terms.
        """
        declared = parse_qs(urlsplit(self.token_endpoint).query).get("api-version")
        return declared[0] if declared else CHANNEL_SETTINGS_API_VERSION

    async def token(self) -> str:
        """A Direct Line token for **one** conversation.

        Never cached across conversations. A Copilot Studio Direct Line token
        carries a `conv` claim, so starting a conversation with a token that
        has already been spent rejoins the *old* conversation and replays its
        transcript — measured live 2026-08-13, where a second question came
        back with the first question's answer.

        The 3600-second life the service reports (ADR-011, and confirmed live:
        `expires_in` is 3600, and `exp - nbf` on the token agrees) governs how
        long that one conversation's token stays good, which is far longer than
        the 45 seconds an answer takes. It is **not** the 30 minutes the
        superseded document states.
        """
        payload = await self.get_json(self.token_endpoint)
        self._token_lifetime = payload.get("expires_in") or TOKEN_LIFETIME_SECONDS
        return payload["token"]

    # ---- the conversation ------------------------------------------------

    async def ask(self, question: str) -> SopAnswer:
        """Ask the SOP agent one question in a fresh conversation.

        A fresh conversation every time, deliberately: a published change never
        reaches a conversation that is already open (see **Publish
        propagation**), so reusing one is how a rehearsal convinces itself a fix
        did not work.

        One fast retry, then the fixed failure message.
        """
        for attempt in (1, 2):
            try:
                return await self._ask_once(question)
            except Exception as exc:
                logger.warning(
                    "sop: Direct Line attempt %s failed: %s", attempt, exc
                )
                if attempt == 1 and self.retry_delay:
                    await asyncio.sleep(self.retry_delay)
        return SopAnswer(text=DIRECT_LINE_FAILURE, failed=True)

    async def _ask_once(self, question: str) -> SopAnswer:
        token = await self.token()
        base = await self.direct_line_base(token)

        if self.answer_timeout >= self._token_lifetime:
            raise ValueError(
                f"an answer timeout of {self.answer_timeout}s outlives the "
                f"{self._token_lifetime}s Direct Line token it would be spent on"
            )

        conversation = await self.post_json(
            f"{base}/conversations",
            headers=self._bearer(token),
            json={},
        )
        identifier = conversation["conversationId"]
        # The conversation-scoped token supersedes the one that started it.
        token = conversation.get("token") or token

        await self.post_json(
            f"{base}/conversations/{identifier}/activities",
            headers=self._bearer(token),
            json={
                "type": "message",
                "text": question,
                "from": {"id": f"orchestrator-{uuid.uuid4().hex[:8]}", "role": "user"},
                "locale": "en-US",
            },
        )

        replies = await self._drain(base, identifier, token)
        text = "\n\n".join(
            reply.get("text", "").strip() for reply in replies if reply.get("text")
        )
        if not text:
            raise ValueError("the SOP agent replied with no text")

        citations: List[Citation] = []
        for reply in replies:
            citations.extend(citations_from_activity(reply))
        return SopAnswer(
            text=text, citations=citations, conversation_id=identifier
        )

    async def _drain(
        self, base: str, identifier: str, token: str
    ) -> List[Dict[str, Any]]:
        """Poll the transcript until the agent has finished, or time runs out.

        "Finished" is `SETTLE_POLLS` consecutive polls that add nothing, not
        the first activity that arrives: a generative answer is delivered as
        however many activities the agent chose to send, so returning on the
        first one hands back the preamble and drops both the procedure and its
        citations. More than one quiet poll is required because a poll landing
        between two activities is quiet without the agent being done.

        The deadline stays a **failure** even once the agent has spoken. "Let
        me look that up" is not a procedure, and returning it because the clock
        ran out dresses a timeout as an answer — the one outcome this demo
        cannot survive. A timed-out answer takes the retry and then the fixed
        failure message, which says what actually happened.
        """
        watermark: Optional[str] = None
        seen: set = set()
        replies: List[Dict[str, Any]] = []
        quiet = 0
        deadline = self._clock() + self.answer_timeout
        while True:
            path = f"{base}/conversations/{identifier}/activities"
            payload = await self.get_json(
                path,
                headers=self._bearer(token),
                params={"watermark": watermark} if watermark else None,
            )
            watermark = payload.get("watermark") or watermark
            arrived = 0
            for activity in payload.get("activities") or []:
                if (activity.get("from") or {}).get("role") != "bot":
                    continue
                if activity.get("id") in seen:
                    continue
                seen.add(activity.get("id"))
                if activity.get("type") == "message":
                    replies.append(activity)
                    arrived += 1
            quiet = 0 if arrived else quiet + 1
            if replies and quiet >= self.settle_polls:
                return replies
            if self._clock() >= deadline:
                raise TimeoutError(
                    f"the SOP agent had not finished within {self.answer_timeout}s"
                )
            if self.poll_interval:
                await asyncio.sleep(self.poll_interval)

    @staticmethod
    def _bearer(token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
