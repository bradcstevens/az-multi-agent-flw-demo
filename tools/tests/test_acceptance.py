"""Acceptance tests for issue #8 — the SOP corpus the Copilot Studio agent is grounded on.

Each test names one acceptance criterion from the issue.
"""

import re
from pathlib import Path

import pytest
from sop_corpus.build import build_corpus
from sop_corpus.corpus import PROCEDURE_HEADING, load_corpus
from sop_corpus.ingestion import MAX_DOCUMENTS, MIN_DOCUMENTS, check_corpus

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content" / "sop"
DOCX_DIR = CONTENT_DIR / "docx"

REQUIRED_TITLES = ("store opening", "store closing", "restroom cleaning")

# Real-world names would break the "fictional throughout" criterion if they appeared in the
# procedures themselves. The demo's own branding lives in the app, never in the corpus.
REAL_WORLD_TERMS = ("circle k", "microsoft", "azure", "copilot", "dataverse", "sharepoint")

# Function words that dominate any English prose and are absent from other languages, so a
# document translated or drafted in another language fails even though it stays ASCII.
ENGLISH_FUNCTION_WORDS = ("the", "and", "of", "to", "is", "on", "with", "that", "not", "before")


@pytest.fixture(scope="module")
def corpus():
    return load_corpus(CONTENT_DIR)


def test_corpus_holds_eight_to_twelve_documents(corpus):
    assert MIN_DOCUMENTS <= len(corpus.documents) <= MAX_DOCUMENTS


def test_the_three_named_procedures_are_present(corpus):
    titles = [document.title.lower() for document in corpus.documents]
    for required in REQUIRED_TITLES:
        assert any(required in title for title in titles), f"missing a {required} procedure"


def test_every_built_file_survives_copilot_studio_ingestion():
    assert check_corpus(DOCX_DIR) == []


def test_every_document_answers_as_numbered_steps_from_a_named_source(corpus):
    for document in corpus.documents:
        headings = [section.heading for section in document.sections]
        assert PROCEDURE_HEADING in headings, f"{document.doc_id} has no Procedure section"
        assert len(document.steps) >= 3, f"{document.doc_id} has too few numbered steps"
        assert document.doc_id in document.filename
        assert document.title in document.filename


def test_content_is_fictional(corpus):
    for document in corpus.documents:
        text = corpus.text_of(document)
        assert corpus.banner.lower() in text, f"{document.doc_id} never names the fictional banner"
        for term in REAL_WORLD_TERMS:
            assert term not in text, f"{document.doc_id} mentions the real-world term '{term}'"


def test_content_is_english_only(corpus):
    assert corpus.locale == "en-US"
    for document in corpus.documents:
        assert document.source_path.read_text(encoding="utf-8").isascii(), (
            f"{document.doc_id} contains non-ASCII characters"
        )
        words = re.findall(r"[a-z']+", corpus.text_of(document))
        function_words = sum(1 for word in words if word in ENGLISH_FUNCTION_WORDS)
        assert function_words / len(words) > 0.15, (
            f"{document.doc_id} does not read as English prose"
        )


def test_the_rehearsed_question_is_not_covered_by_the_corpus(corpus):
    assert corpus.honest_miss.question
    assert corpus.honest_miss.quick_task
    assert corpus.honest_miss_coverage() == []


def test_the_built_docx_files_match_the_markdown_sources(tmp_path):
    rebuilt = build_corpus(CONTENT_DIR, tmp_path)

    committed = {path.name: path.read_bytes() for path in DOCX_DIR.glob("*.docx")}
    assert {path.name: path.read_bytes() for path in rebuilt} == committed
