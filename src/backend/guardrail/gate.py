"""The Identity boundary gate: deterministic code in the request path.

ADR-014 settles what this is and, just as importantly, what it is not. It is
**not** a system message and **not** the accelerator's prompt-based team-scope
evaluation, which fails open in two places. It runs **before the lane router
and before orchestration**, and on a match the request short-circuits with no
agent invoked and no tokens spent — which is what makes the demo's "the
guardrail costs nothing" claim literally true.

Three tiers, cheapest first:

1. **Identity.** A signed-in session is admitted outright. The mocked unlock is
   a parameter of this gate, not a second gate, so it costs nothing and is
   checked first.
2. **Keyword fast path** (`guardrail.keywords`). Pure, no I/O, refuses
   the obvious personal question without an embedding round trip.
3. **Similarity tier** (`guardrail.similarity`). One embedding call,
   scored as the Two-class margin of ADR-015, for the paraphrase the presenter
   improvises live and a keyword list can never survive.

And it **fails closed**: an embedder that raises, times out or returns
something unusable refuses the request. It is modelled on the content-safety
check — the repo's one fail-closed precedent — not on its neighbour.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, List, Optional, Sequence

from guardrail.corpus import PERSONAL_INTENT_ANCHORS, STORE_SCOPE_ANCHORS
from guardrail.embeddings import EmbeddingClient
from guardrail.identity import ANONYMOUS, SessionIdentity
from guardrail.keywords import matches_personal_keyword
from guardrail.similarity import (
    IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD,
    personal_intent_margin,
    refuses,
)

logger = logging.getLogger(__name__)

Embedder = Callable[[Sequence[str]], Awaitable[List[List[float]]]]

# How long the similarity tier may take before the request is refused. The
# whole gate sits in front of a sub-10s fast lane, so a slow embedding call is
# a failure, and a failure is a refusal.
DEFAULT_TIMEOUT_SECONDS = 5.0


class GateReason(str, Enum):
    """Why the gate reached its verdict.

    Recorded on the verdict for telemetry and for the tests that assert *how*
    a request was decided, not merely that it was.
    """

    SIGNED_IN = "signed_in"
    KEYWORD = "keyword"
    MARGIN = "margin"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class GateVerdict:
    """The gate's decision about one request."""

    refused: bool
    reason: GateReason
    score: Optional[float] = None


@dataclass(frozen=True)
class _AnchorVectors:
    """Both anchor sets, embedded."""

    personal: List[List[float]]
    store: List[List[float]]


class IdentityBoundaryGate:
    """Refuses personal, individual-identity questions from a shared device."""

    def __init__(
        self,
        embed: Embedder,
        *,
        threshold: float = IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD,
        personal_anchors: Sequence[str] = PERSONAL_INTENT_ANCHORS,
        store_anchors: Sequence[str] = STORE_SCOPE_ANCHORS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._embed = embed
        self.threshold = threshold
        self.personal_anchors = tuple(personal_anchors)
        self.store_anchors = tuple(store_anchors)
        self.timeout_seconds = timeout_seconds
        self._anchor_vectors: Optional[_AnchorVectors] = None
        self._anchor_lock = asyncio.Lock()

    async def evaluate(
        self, request_text: str, identity: SessionIdentity = ANONYMOUS
    ) -> GateVerdict:
        """Decide one request, cheapest tier first."""
        if not identity.is_anonymous:
            return GateVerdict(refused=False, reason=GateReason.SIGNED_IN)

        if matches_personal_keyword(request_text):
            return GateVerdict(refused=True, reason=GateReason.KEYWORD)

        try:
            score = await asyncio.wait_for(
                self._score(request_text), timeout=self.timeout_seconds
            )
        except asyncio.CancelledError:
            # The caller went away. That is not a classifier failure, and
            # dressing it up as a policy decision would hide a shutdown.
            raise
        except Exception:
            logger.warning(
                "Identity boundary gate could not score a request; refusing "
                "(fail-closed, ADR-014).",
                exc_info=True,
            )
            return GateVerdict(refused=True, reason=GateReason.UNAVAILABLE)

        return GateVerdict(
            refused=refuses(score, self.threshold),
            reason=GateReason.MARGIN,
            score=score,
        )

    async def _score(self, request_text: str) -> float:
        """The request's Two-class margin against both anchor sets."""
        anchors = await self._anchors()
        (vector,) = await self._embed([request_text])
        return personal_intent_margin(vector, anchors.personal, anchors.store)

    async def _anchors(self) -> "_AnchorVectors":
        """Both anchor sets, embedded once and reused.

        ADR-015 notes the per-request cost is unchanged by the second anchor
        set precisely because the anchors are embedded once, not per request.
        A failure is deliberately *not* cached: the next request re-tries
        rather than inheriting a dead gate for the life of the process.
        """
        if self._anchor_vectors is not None:
            return self._anchor_vectors

        async with self._anchor_lock:
            if self._anchor_vectors is None:
                embedded = await self._embed(
                    self.personal_anchors + self.store_anchors
                )
                split = len(self.personal_anchors)
                self._anchor_vectors = _AnchorVectors(
                    personal=embedded[:split], store=embedded[split:]
                )
        return self._anchor_vectors


# The process-wide gate. The anchors are embedded once per process rather than
# once per request (ADR-015), so the gate has to outlive a request to be worth
# anything — hence one instance, built on first use rather than at import, so
# that importing the request path does not reach for AppConfig.
_GATE: Optional[IdentityBoundaryGate] = None


def build_identity_boundary_gate() -> IdentityBoundaryGate:
    """A gate wired to the configured embedding deployment."""
    return IdentityBoundaryGate(embed=EmbeddingClient.from_app_config().embed)


def identity_boundary_gate() -> IdentityBoundaryGate:
    """The process-wide Identity boundary gate."""
    global _GATE
    if _GATE is None:
        _GATE = build_identity_boundary_gate()
    return _GATE
