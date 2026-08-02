from sop_corpus.corpus import load_corpus, load_document

SOURCE = """+++
doc_id = "SOP-101"
title = "Store Opening Procedure"
version = "1.4"
owner = "Regional Operations"
effective = "2026-03-02"
+++

## Purpose

Bring the store from overnight lockup to trading condition.

## Procedure

1. Unlock the staff door and disarm the alarm.
2. Switch on the sales-floor lighting.

## Escalation

Call the duty manager.
"""


def test_document_carries_its_identity_and_numbered_steps(tmp_path):
    source = tmp_path / "010-store-opening.md"
    source.write_text(SOURCE, encoding="utf-8")

    document = load_document(source)

    assert document.doc_id == "SOP-101"
    assert document.title == "Store Opening Procedure"
    assert document.version == "1.4"
    assert document.owner == "Regional Operations"
    assert document.effective == "2026-03-02"
    assert document.filename == "SOP-101 Store Opening Procedure.docx"
    assert [section.heading for section in document.sections] == [
        "Purpose",
        "Procedure",
        "Escalation",
    ]
    assert document.steps == [
        "Unlock the staff door and disarm the alarm.",
        "Switch on the sales-floor lighting.",
    ]


CORPUS_TOML = """
banner = "Brightpath Convenience"
store = "Store 223"

[honest_miss]
question = "How do I restart the car wash after a vehicle stalls in the bay?"
quick_task = "Car wash restart"
absent_terms = ["car wash", "wash bay"]
rationale = "No car-wash procedure was written, so the answer is an honest miss."
"""


def make_corpus(tmp_path, extra_body=""):
    (tmp_path / "corpus.toml").write_text(CORPUS_TOML, encoding="utf-8")
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "010-store-opening.md").write_text(SOURCE + extra_body, encoding="utf-8")
    return tmp_path


def test_corpus_carries_its_documents_and_the_rehearsed_honest_miss_question(tmp_path):
    corpus = load_corpus(make_corpus(tmp_path))

    assert [document.doc_id for document in corpus.documents] == ["SOP-101"]
    assert corpus.honest_miss.question == (
        "How do I restart the car wash after a vehicle stalls in the bay?"
    )
    assert corpus.honest_miss.quick_task == "Car wash restart"


def test_the_honest_miss_question_is_reported_as_uncovered_by_the_corpus(tmp_path):
    corpus = load_corpus(make_corpus(tmp_path))

    assert corpus.honest_miss_coverage() == []


def test_a_document_that_answers_the_honest_miss_question_is_reported(tmp_path):
    covered = make_corpus(
        tmp_path, extra_body="\nRestart the car wash controller before calling anyone.\n"
    )

    corpus = load_corpus(covered)

    assert corpus.honest_miss_coverage() == [("car wash", "SOP-101")]


WRAPPED_SOURCE = SOURCE.replace(
    "2. Switch on the sales-floor lighting.",
    "2. Switch on the sales-floor lighting, the forecourt canopy lighting\n"
    "   and the exterior sign.",
)


def test_a_step_wrapped_over_several_source_lines_stays_one_step(tmp_path):
    source = tmp_path / "010-store-opening.md"
    source.write_text(WRAPPED_SOURCE, encoding="utf-8")

    document = load_document(source)

    assert document.steps[1] == (
        "Switch on the sales-floor lighting, the forecourt canopy lighting and the exterior sign."
    )


PROSE_SOURCE = """+++
doc_id = "SOP-101"
title = "Store Opening Procedure"
version = "1.4"
owner = "Regional Operations"
effective = "2026-03-02"
+++

## Purpose

Bring the store from overnight lockup to trading condition, in a fixed order,
so that the first customer is served by a store that is lit and secure.

This is a second paragraph.

## Procedure

1. Unlock the staff door.
"""


def test_a_paragraph_wrapped_over_several_source_lines_stays_one_paragraph(tmp_path):
    source = tmp_path / "010-store-opening.md"
    source.write_text(PROSE_SOURCE, encoding="utf-8")

    purpose = load_document(source).sections[0]

    assert [block.text for block in purpose.blocks] == [
        "Bring the store from overnight lockup to trading condition, in a fixed order, "
        "so that the first customer is served by a store that is lit and secure.",
        "This is a second paragraph.",
    ]


def test_steps_that_do_not_run_one_to_n_are_rejected(tmp_path):
    import pytest

    from sop_corpus.corpus import CorpusError

    source = tmp_path / "010-store-opening.md"
    source.write_text(
        SOURCE.replace("2. Switch on the sales-floor lighting.", "3. Switch on the lighting."),
        encoding="utf-8",
    )

    with pytest.raises(CorpusError, match="Procedure"):
        load_document(source)
