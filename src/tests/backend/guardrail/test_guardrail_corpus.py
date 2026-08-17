"""The Guardrail corpus scored against the real embedding deployment.

R5's acceptance criterion is numeric — 10/10 personal probes refused, 0/10
false positives on store-level controls — so a mocked embedder would only
prove plumbing (ADR-014). This suite is simultaneously that acceptance test
and the tuning harness that produced
`IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD`: it prints the full threshold sweep,
so a specific threshold can be read off the numbers rather than guessed.

It carries the `integration` marker the repo already declares and is
deselected in CI by `-m 'not integration'`, in both `scripts/backend-tests.sh`
and `.github/workflows/test.yml`.

To run it, point it at the deployed environment and sign in with `az login`:

    export GUARDRAIL_EMBEDDING_ENDPOINT="$(
        grep AZURE_OPENAI_ENDPOINT .azure/macae-flw-v1/.env | cut -d= -f2- | tr -d '"'
    )"
    .venv/bin/python -m pytest src/tests/backend/guardrail/test_guardrail_corpus.py \
        -m integration -s

The endpoint is read from a guardrail-specific variable on purpose: the
backend test conftest sets a fake `AZURE_OPENAI_ENDPOINT` for every other
suite, and an integration test that quietly scored a placeholder host would
be worse than no integration test at all.
"""

import os
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio

from guardrail.corpus import (
    IMPROVISED_PARAPHRASES,
    NEGATIVE_CONTROLS,
    PERSONAL_INTENT_ANCHORS,
    POSITIVE_PROBES,
    STORE_SCOPE_ANCHORS,
)
from guardrail.embeddings import (
    COGNITIVE_SERVICES_SCOPE,
    DEFAULT_EMBEDDING_DEPLOYMENT,
    EmbeddingClient,
)
from guardrail.gate import GateReason, IdentityBoundaryGate
from guardrail.identity import SessionIdentity
from guardrail.similarity import (
    IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD,
    choose_threshold,
    format_sweep,
    personal_intent_margin,
    sweep,
)

pytestmark = pytest.mark.integration

ENDPOINT = os.environ.get("GUARDRAIL_EMBEDDING_ENDPOINT", "")
DEPLOYMENT = os.environ.get(
    "GUARDRAIL_EMBEDDING_DEPLOYMENT", DEFAULT_EMBEDDING_DEPLOYMENT
)
API_VERSION = os.environ.get("GUARDRAIL_EMBEDDING_API_VERSION", "2024-12-01-preview")


@pytest.fixture(scope="module")
def embedding_endpoint():
    if not ENDPOINT:
        pytest.skip(
            "GUARDRAIL_EMBEDDING_ENDPOINT is not set — the Guardrail corpus scores "
            "against the real embedding deployment and will not score a placeholder."
        )
    return ENDPOINT


@asynccontextmanager
async def live_embedding_client(endpoint):
    """An EmbeddingClient pointed at the deployed embedding deployment."""
    from azure.identity.aio import DefaultAzureCredential

    credential = DefaultAzureCredential()

    async def token_provider():
        token = await credential.get_token(COGNITIVE_SERVICES_SCOPE)
        return token.token

    client = EmbeddingClient(
        endpoint,
        DEPLOYMENT,
        api_version=API_VERSION,
        token_provider=token_provider,
        timeout_seconds=120,
    )
    try:
        yield client
    finally:
        await client.close()
        await credential.close()


@pytest_asyncio.fixture
async def scored_corpus(embedding_endpoint):
    """Every probe's two-class margin: personal anchors minus store anchors."""
    async with live_embedding_client(embedding_endpoint) as client:
        personal = await client.embed(PERSONAL_INTENT_ANCHORS)
        store = await client.embed(STORE_SCOPE_ANCHORS)
        positives = await client.embed(POSITIVE_PROBES)
        negatives = await client.embed(NEGATIVE_CONTROLS)

    def margin(vector):
        return personal_intent_margin(vector, personal, store)

    return (
        [margin(vector) for vector in positives],
        [margin(vector) for vector in negatives],
    )


@pytest.mark.asyncio
async def test_the_corpus_refuses_ten_of_ten_and_admits_ten_of_ten(scored_corpus):
    """R5's acceptance numbers, at the measured threshold."""
    positives, negatives = scored_corpus

    (row,) = sweep(positives, negatives, [IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD])

    assert row.refused == len(POSITIVE_PROBES), (
        f"{row.positives - row.refused} personal probe(s) were admitted at "
        f"{IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD}"
    )
    assert row.false_positives == 0, (
        f"{row.false_positives} store-level control(s) were refused at "
        f"{IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD}"
    )


@pytest.mark.asyncio
async def test_the_sweep_is_reported_so_a_threshold_can_be_chosen(scored_corpus):
    """The tuning half of the harness: print the numbers, then assert on them."""
    positives, negatives = scored_corpus
    rows = sweep(positives, negatives)

    print("\n--- Guardrail corpus: probe scores ---")
    for text, score in zip(POSITIVE_PROBES, positives):
        print(f"  refuse  {score:+.4f}  {text}")
    for text, score in zip(NEGATIVE_CONTROLS, negatives):
        print(f"  admit   {score:+.4f}  {text}")

    print(f"\n--- Guardrail corpus: threshold sweep ({DEPLOYMENT}) ---")
    print(format_sweep(rows))

    chosen = choose_threshold(positives, negatives)
    print(f"\nwidest separating band midpoint: {chosen}")
    print(f"recorded threshold:              {IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD}")

    assert chosen is not None, (
        "no threshold separates the corpus: the similarity tier cannot carry R5 "
        "on this embedding deployment and the corpus or the anchors must change"
    )
    assert any(row.perfect for row in rows)


@pytest.mark.asyncio
async def test_the_recorded_threshold_still_sits_inside_the_perfect_band(
    scored_corpus,
):
    """Guards against the recorded number drifting out of the measured band."""
    positives, negatives = scored_corpus
    perfect = [row.threshold for row in sweep(positives, negatives) if row.perfect]

    assert perfect, "no threshold in the sweep band scores 10/10 and 0/10"
    assert min(perfect) <= IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD <= max(perfect)


# ---------------------------------------------------------------------------
# The gate itself (issue #14)
# ---------------------------------------------------------------------------
# The three suites above score the *similarity tier* — one of the Identity
# boundary gate's three tiers. Once the gate exists, R5's numbers belong to the
# thing the request path actually calls: identity, then the Keyword fast path,
# then the margin. The composition is not a formality. The fast path can only
# *add* refusals, so it is the tier that can blow the 0/10 false-positive
# criterion on its own, and no amount of margin headroom would rescue it.


@pytest_asyncio.fixture
async def gate_verdicts(embedding_endpoint):
    """Every corpus item, decided by the real gate on the real deployment."""
    async with live_embedding_client(embedding_endpoint) as client:
        gate = IdentityBoundaryGate(embed=client.embed)
        probes = [(text, await gate.evaluate(text)) for text in POSITIVE_PROBES]
        controls = [
            (text, await gate.evaluate(text)) for text in NEGATIVE_CONTROLS
        ]
    return probes, controls


@pytest.mark.asyncio
async def test_the_gate_refuses_ten_of_ten_and_admits_ten_of_ten(gate_verdicts):
    """R5's acceptance numbers, measured on the gate rather than on one tier."""
    probes, controls = gate_verdicts

    print("\n--- Identity boundary gate: the Guardrail corpus ---")
    for text, verdict in probes + controls:
        outcome = "REFUSED " if verdict.refused else "admitted"
        score = f"{verdict.score:+.4f}" if verdict.score is not None else "   --  "
        print(f"  {outcome}  {verdict.reason.value:<9}  {score}  {text}")

    admitted = [text for text, verdict in probes if not verdict.refused]
    falsely_refused = [text for text, verdict in controls if verdict.refused]

    assert not admitted, f"personal probe(s) admitted by the gate: {admitted}"
    assert not falsely_refused, (
        f"store-level control(s) refused by the gate: {falsely_refused}"
    )


@pytest.mark.asyncio
async def test_a_signed_in_associate_is_admitted_by_the_same_gate(
    embedding_endpoint,
):
    """The Mocked unlock is a parameter of this gate, not a second gate.

    The same probe, the same deployment, the same code path — only the Session
    identity differs. #27 flips exactly this parameter, so proving it against
    the live deployment now is what makes that ticket a UI change.
    """
    async with live_embedding_client(embedding_endpoint) as client:
        gate = IdentityBoundaryGate(embed=client.embed)
        anonymous = await gate.evaluate(POSITIVE_PROBES[0])
        signed_in = await gate.evaluate(
            POSITIVE_PROBES[0], SessionIdentity(display_name="Clara Reyes")
        )

    assert anonymous.refused
    assert not signed_in.refused


@pytest.mark.asyncio
async def test_the_similarity_tier_catches_an_improvised_paraphrase(
    embedding_endpoint,
):
    """ADR-014's live claim, with the fast path taken out of the picture.

    Every phrasing here is held out of the sweep and provably misses the
    Keyword fast path, so the gate refusing it is evidence about the
    similarity tier and nothing else. This is the test the presenter runs by
    improvising, and the one the audience will try to break.
    """
    async with live_embedding_client(embedding_endpoint) as client:
        gate = IdentityBoundaryGate(embed=client.embed)
        verdicts = [
            (text, await gate.evaluate(text)) for text in IMPROVISED_PARAPHRASES
        ]

    print("\n--- Identity boundary gate: held-out improvised paraphrases ---")
    for text, verdict in verdicts:
        outcome = "REFUSED " if verdict.refused else "admitted"
        score = f"{verdict.score:+.4f}" if verdict.score is not None else "   --  "
        print(f"  {outcome}  {verdict.reason.value:<9}  {score}  {text}")

    assert all(
        verdict.reason is GateReason.MARGIN for _, verdict in verdicts
    ), "a paraphrase was decided by a tier other than the similarity tier"

    admitted = [text for text, verdict in verdicts if not verdict.refused]
    assert not admitted, (
        "the similarity tier admitted an improvised paraphrase, which is the "
        f"live failure ADR-014 says a keyword list alone cannot survive: {admitted}"
    )
