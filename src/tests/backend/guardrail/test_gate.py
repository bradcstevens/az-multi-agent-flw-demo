"""The Identity boundary gate itself (issue #14, ADR-014, ADR-015).

The seam is `IdentityBoundaryGate.evaluate`. Its one collaborator — the
embedder — is *injected*, so these tests drive real code through a plain async
stub rather than patching anything inside the gate, and there is no
module-level `sys.modules` assignment anywhere in this file.

The stub is a hand-rolled embedder rather than a MagicMock because two of the
properties under test are about *calls that must not happen*: an admitted
signed-in request must not embed at all, and a keyword hit must not embed
either. Counting them is the assertion.
"""

import asyncio
from types import SimpleNamespace
from typing import List, Sequence
from unittest.mock import MagicMock

import pytest

from guardrail.gate import GateReason, IdentityBoundaryGate
from guardrail.identity import ANONYMOUS, SessionIdentity
from guardrail.keywords import matches_personal_keyword
from guardrail.similarity import IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD


class StubEmbedder:
    """An embedder that answers from a table, and counts what it was asked."""

    def __init__(self, vectors=None, raises=None, delay=0.0):
        self.vectors = vectors or {}
        self.raises = raises
        self.delay = delay
        self.calls: List[List[str]] = []

    async def __call__(self, texts: Sequence[str]) -> List[List[float]]:
        self.calls.append(list(texts))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raises:
            raise self.raises
        return [self.vectors[text] for text in texts]

    @property
    def texts_embedded(self) -> List[str]:
        return [text for call in self.calls for text in call]


class TestASignedInIdentity:
    @pytest.mark.asyncio
    async def test_the_same_question_is_admitted_once_someone_is_signed_in(self):
        """The mocked unlock is a parameter of this gate, not a second gate.

        "my name is Tanya, how much PTO do I have?" is the demo's closing beat:
        refused anonymously, answered after sign-in, with nothing between the
        two moments but the identity.
        """
        embedder = StubEmbedder()
        gate = IdentityBoundaryGate(embed=embedder)

        verdict = await gate.evaluate(
            "my name is Tanya, how much PTO do I have?",
            identity=SessionIdentity(display_name="Tanya Reyes"),
        )

        assert verdict.refused is False
        assert verdict.reason is GateReason.SIGNED_IN

    @pytest.mark.asyncio
    async def test_a_signed_in_request_is_not_embedded_at_all(self):
        """Identity is checked first, so the unlock costs no embedding call."""
        embedder = StubEmbedder()
        gate = IdentityBoundaryGate(embed=embedder)

        await gate.evaluate(
            "whats left on my sick days",
            identity=SessionIdentity(display_name="Tanya Reyes"),
        )

        assert embedder.calls == []

    @pytest.mark.asyncio
    async def test_anonymous_is_the_default_identity(self):
        """Nobody is signed in until #27 wires the sign-in, so the gate bites."""
        embedder = StubEmbedder()
        gate = IdentityBoundaryGate(embed=embedder)

        verdict = await gate.evaluate("whats left on my sick days")

        assert verdict.refused is True
        assert ANONYMOUS.is_anonymous is True


class TestTheKeywordFastPath:
    @pytest.mark.asyncio
    async def test_an_obvious_personal_question_is_refused_on_keywords(self):
        embedder = StubEmbedder()
        gate = IdentityBoundaryGate(embed=embedder)

        verdict = await gate.evaluate("my name is Tanya, how much PTO do I have?")

        assert verdict.refused is True
        assert verdict.reason is GateReason.KEYWORD

    @pytest.mark.asyncio
    async def test_a_keyword_refusal_spends_no_embedding_call(self):
        """The fast path exists to make the obvious case free."""
        embedder = StubEmbedder()
        gate = IdentityBoundaryGate(embed=embedder)

        await gate.evaluate("whats left on my sick days")

        assert embedder.calls == []


# A paraphrase of "When is my next shift?" carrying no personal-scope
# vocabulary at all — the kind the presenter improvises live, and exactly what
# ADR-014 says a keyword list can never survive. The similarity tier has to
# earn its place on this one.
IMPROVISED_PARAPHRASE = "Am I working tomorrow evening?"

# Two-dimensional canned vectors, so every margin below is arithmetic anyone
# can check by hand rather than a number produced by the code under test.
PERSONAL_ANCHOR_VECTOR = [1.0, 0.0]
STORE_ANCHOR_VECTOR = [0.0, 1.0]


def two_anchor_gate(**probes):
    """A gate over one personal and one store anchor, plus canned probes."""
    vectors = {"a personal anchor": PERSONAL_ANCHOR_VECTOR,
               "a store anchor": STORE_ANCHOR_VECTOR}
    vectors.update(probes)
    embedder = StubEmbedder(vectors)
    gate = IdentityBoundaryGate(
        embed=embedder,
        personal_anchors=("a personal anchor",),
        store_anchors=("a store anchor",),
    )
    return gate, embedder


class TestTheSimilarityTier:
    def test_the_improvised_paraphrase_really_does_miss_the_fast_path(self):
        """Guards the tests below from quietly becoming keyword tests."""
        assert matches_personal_keyword(IMPROVISED_PARAPHRASE) is False

    @pytest.mark.asyncio
    async def test_a_live_improvised_paraphrase_is_still_caught(self):
        """R5's real test: the question nobody put on the keyword list."""
        gate, _ = two_anchor_gate(**{IMPROVISED_PARAPHRASE: [1.0, 0.1]})

        verdict = await gate.evaluate(IMPROVISED_PARAPHRASE)

        assert verdict.refused is True
        assert verdict.reason is GateReason.MARGIN
        # Nearest personal anchor 0.995, nearest store anchor 0.0995.
        assert verdict.score == pytest.approx(0.8955, abs=1e-4)

    @pytest.mark.asyncio
    async def test_a_store_level_question_is_admitted(self):
        """The guardrail must not make the tool useless."""
        question = "How do I close the store?"
        gate, _ = two_anchor_gate(**{question: [0.1, 1.0]})

        verdict = await gate.evaluate(question)

        assert verdict.refused is False
        assert verdict.reason is GateReason.MARGIN
        assert verdict.score == pytest.approx(-0.8955, abs=1e-4)

    @pytest.mark.asyncio
    async def test_a_margin_exactly_on_the_threshold_refuses(self):
        """Fail closed on the boundary itself, the rule `refuses` encodes."""
        question = "Is the delivery in yet?"
        gate, _ = two_anchor_gate(**{question: [1.0, 0.0]})
        gate.threshold = 1.0

        verdict = await gate.evaluate(question)

        assert verdict.refused is True

    @pytest.mark.asyncio
    async def test_the_request_is_embedded_once(self):
        gate, embedder = two_anchor_gate(**{IMPROVISED_PARAPHRASE: [1.0, 0.1]})

        await gate.evaluate(IMPROVISED_PARAPHRASE)

        assert embedder.texts_embedded.count(IMPROVISED_PARAPHRASE) == 1


class TestItFailsClosed:
    """ADR-014: model this on the content-safety check, not on its neighbour.

    Every one of these is a store-level question — one the gate would normally
    admit — so each test proves the *refusal* comes from the failure and not
    from the question.
    """

    STORE_QUESTION = "How do I reset the till after a mis-scan?"

    @pytest.mark.asyncio
    async def test_an_embedder_that_raises_refuses_the_request(self):
        embedder = StubEmbedder(raises=RuntimeError("the deployment is gone"))
        gate = IdentityBoundaryGate(embed=embedder)

        verdict = await gate.evaluate(self.STORE_QUESTION)

        assert verdict.refused is True
        assert verdict.reason is GateReason.UNAVAILABLE
        assert verdict.score is None

    @pytest.mark.asyncio
    async def test_an_embedder_that_times_out_refuses_the_request(self):
        embedder = StubEmbedder(delay=0.05)
        gate = IdentityBoundaryGate(embed=embedder, timeout_seconds=0.01)

        verdict = await gate.evaluate(self.STORE_QUESTION)

        assert verdict.refused is True
        assert verdict.reason is GateReason.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_an_unusable_embedding_response_refuses_the_request(self):
        """A vector of the wrong width cannot be scored, so it is refused.

        `cosine_similarity` raises on mismatched dimensions rather than
        guessing, and the gate turns that into the same refusal as any other
        failure.
        """
        gate, _ = two_anchor_gate(**{self.STORE_QUESTION: [0.1, 1.0, 0.5]})

        verdict = await gate.evaluate(self.STORE_QUESTION)

        assert verdict.refused is True
        assert verdict.reason is GateReason.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_cancellation_is_not_swallowed(self):
        """Fail-closed must not mean "swallow everything".

        A cancelled request is the caller going away, not a classifier
        failure; turning it into a refusal would hide a shutdown as a policy
        decision.
        """
        embedder = StubEmbedder(raises=asyncio.CancelledError())
        gate = IdentityBoundaryGate(embed=embedder)

        with pytest.raises(asyncio.CancelledError):
            await gate.evaluate(self.STORE_QUESTION)


class TestTheAnchorsAreEmbeddedOnce:
    @pytest.mark.asyncio
    async def test_a_second_request_reuses_the_embedded_anchors(self):
        """One embedding call per request, not three (ADR-015)."""
        first = "Is the delivery in yet?"
        second = "Where does the expired stock go?"
        gate, embedder = two_anchor_gate(**{first: [0.1, 1.0], second: [0.2, 1.0]})

        await gate.evaluate(first)
        await gate.evaluate(second)

        assert embedder.texts_embedded.count("a personal anchor") == 1
        assert embedder.calls[-1] == [second]

    @pytest.mark.asyncio
    async def test_a_failed_anchor_embedding_is_not_cached(self):
        """A dead gate must be able to recover on the next request.

        Caching the failure would turn one bad minute into a demo that refuses
        every question until the container is restarted.
        """
        question = "Is the delivery in yet?"
        embedder = StubEmbedder(
            {"a personal anchor": PERSONAL_ANCHOR_VECTOR,
             "a store anchor": STORE_ANCHOR_VECTOR,
             question: [0.1, 1.0]},
            raises=RuntimeError("transient"),
        )
        gate = IdentityBoundaryGate(
            embed=embedder,
            personal_anchors=("a personal anchor",),
            store_anchors=("a store anchor",),
        )

        assert (await gate.evaluate(question)).refused is True

        embedder.raises = None

        assert (await gate.evaluate(question)).refused is False

    @pytest.mark.asyncio
    async def test_concurrent_first_requests_embed_the_anchors_once(self):
        """The whole store hits the device at once; the anchors are shared."""
        question = "Is the delivery in yet?"
        gate, embedder = two_anchor_gate(**{question: [0.1, 1.0]})

        await asyncio.gather(*(gate.evaluate(question) for _ in range(5)))

        assert embedder.texts_embedded.count("a store anchor") == 1


class TestTheProcessWideGate:
    """How the request path gets a gate, without every request rebuilding one.

    `EmbeddingClient` is patched by name on the module under test — the
    convention the repo already uses in `test_router.py`, and the reason there
    is no new `sys.modules` assignment anywhere in this suite.
    """

    def test_it_is_built_on_the_configured_embedding_client(self, monkeypatch):
        from guardrail import gate as gate_mod

        client = StubEmbedder()
        client_class = MagicMock()
        client_class.from_app_config = MagicMock(
            return_value=SimpleNamespace(embed=client)
        )
        monkeypatch.setattr(gate_mod, "EmbeddingClient", client_class)

        built = gate_mod.build_identity_boundary_gate()

        client_class.from_app_config.assert_called_once()
        assert built._embed is client
        assert built.threshold == IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD

    def test_the_anchors_survive_between_requests(self, monkeypatch):
        """One gate for the process, so the anchors are embedded once for it."""
        from guardrail import gate as gate_mod

        client_class = MagicMock()
        client_class.from_app_config = MagicMock(
            return_value=SimpleNamespace(embed=StubEmbedder())
        )
        monkeypatch.setattr(gate_mod, "EmbeddingClient", client_class)
        monkeypatch.setattr(gate_mod, "_GATE", None)

        assert gate_mod.identity_boundary_gate() is gate_mod.identity_boundary_gate()
        client_class.from_app_config.assert_called_once()
