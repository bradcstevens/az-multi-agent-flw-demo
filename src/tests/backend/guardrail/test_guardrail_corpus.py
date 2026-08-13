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

import pytest
import pytest_asyncio

from guardrail.corpus import (
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


@pytest_asyncio.fixture
async def scored_corpus(embedding_endpoint):
    """Every probe's two-class margin: personal anchors minus store anchors."""
    from azure.identity.aio import DefaultAzureCredential

    credential = DefaultAzureCredential()

    async def token_provider():
        token = await credential.get_token(COGNITIVE_SERVICES_SCOPE)
        return token.token

    client = EmbeddingClient(
        embedding_endpoint,
        DEPLOYMENT,
        api_version=API_VERSION,
        token_provider=token_provider,
        timeout_seconds=120,
    )
    try:
        personal = await client.embed(PERSONAL_INTENT_ANCHORS)
        store = await client.embed(STORE_SCOPE_ANCHORS)
        positives = await client.embed(POSITIVE_PROBES)
        negatives = await client.embed(NEGATIVE_CONTROLS)
    finally:
        await client.close()
        await credential.close()

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
