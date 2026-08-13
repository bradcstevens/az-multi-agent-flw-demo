import shutil
import subprocess
import zipfile
from xml.etree import ElementTree

import pytest
from sop_corpus.corpus import load_document
from sop_corpus.docx import write_docx

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

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
"""


def paragraph_texts(docx_path):
    """Extract paragraph text the way any OOXML reader does: w:t runs under w:p."""
    with zipfile.ZipFile(docx_path) as package:
        document = ElementTree.fromstring(package.read("word/document.xml"))
    texts = []
    for paragraph in document.iter(f"{{{WORD_NS}}}p"):
        runs = [node.text or "" for node in paragraph.iter(f"{{{WORD_NS}}}t")]
        texts.append("".join(runs))
    return texts


@pytest.fixture()
def document(tmp_path):
    source = tmp_path / "010-store-opening.md"
    source.write_text(SOURCE, encoding="utf-8")
    return load_document(source)


def test_docx_renders_the_source_document_name_and_numbered_steps(tmp_path, document):
    out_path = write_docx(document, tmp_path)

    assert out_path.name == "SOP-101 Store Opening Procedure.docx"
    texts = paragraph_texts(out_path)
    assert texts[0] == "Store Opening Procedure"
    assert "Document ID: SOP-101 | Version: 1.4 | Effective: 2026-03-02" in texts
    assert "Purpose" in texts
    assert "1. Unlock the staff door and disarm the alarm." in texts
    assert "2. Switch on the sales-floor lighting." in texts


def test_docx_is_a_valid_package_a_third_party_reader_can_open(tmp_path, document):
    out_path = write_docx(document, tmp_path)

    with zipfile.ZipFile(out_path) as package:
        assert package.testzip() is None
        names = set(package.namelist())
        assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= names
        for name in names:
            if name.endswith(".xml") or name.endswith(".rels"):
                ElementTree.fromstring(package.read(name))


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_pandoc_can_read_the_generated_docx(tmp_path, document):
    out_path = write_docx(document, tmp_path)

    plain = subprocess.run(
        ["pandoc", str(out_path), "-t", "plain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    lines = [line for line in plain.splitlines() if line.strip()]
    assert lines[0] == "Store Opening Procedure"
    assert "Document ID: SOP-101 | Version: 1.4 | Effective: 2026-03-02" in lines
    assert "1. Unlock the staff door and disarm the alarm." in plain
