import zipfile

from sop_corpus.ingestion import MAX_FILE_BYTES, check_files

LABEL_PROPERTY = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"'
    ' xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    '<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2"'
    ' name="MSIP_Label_f42aa342_Enabled"><vt:lpwstr>true</vt:lpwstr></property>'
    "</Properties>"
)


def make_docx(path, custom_properties=None):
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<document/>")
        if custom_properties:
            package.writestr("docProps/custom.xml", custom_properties)
    return path


def test_a_plain_docx_passes_every_ingestion_rule(tmp_path):
    make_docx(tmp_path / "SOP-101 Store Opening Procedure.docx")

    assert check_files([tmp_path / "SOP-101 Store Opening Procedure.docx"]) == []


def test_an_unsupported_file_type_is_reported(tmp_path):
    unsupported = tmp_path / "store-opening.txt"
    unsupported.write_text("steps", encoding="utf-8")

    findings = check_files([unsupported])

    assert [finding.rule for finding in findings] == ["unsupported-file-type"]


def test_a_file_over_the_size_ceiling_is_reported(tmp_path):
    oversized = tmp_path / "SOP-999 Oversized.pdf"
    oversized.write_bytes(b"0" * (MAX_FILE_BYTES + 1))

    findings = check_files([oversized])

    assert [finding.rule for finding in findings] == ["file-too-large"]


def test_a_sensitivity_label_is_reported_because_ingestion_silently_excludes_it(tmp_path):
    labelled = make_docx(tmp_path / "SOP-102 Store Closing Procedure.docx", LABEL_PROPERTY)

    findings = check_files([labelled])

    assert [finding.rule for finding in findings] == ["sensitivity-label"]
    assert "silently" in findings[0].detail


def test_a_package_that_is_not_readable_ooxml_is_reported(tmp_path):
    corrupt = tmp_path / "SOP-103 Restroom Cleaning and Inspection.docx"
    corrupt.write_bytes(b"not a zip at all")

    findings = check_files([corrupt])

    assert [finding.rule for finding in findings] == ["unreadable-package"]


def test_a_package_missing_its_main_document_part_is_reported(tmp_path):
    incomplete = tmp_path / "SOP-104 Coffee Bar Setup and Shutdown.docx"
    with zipfile.ZipFile(incomplete, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")

    findings = check_files([incomplete])

    assert [finding.rule for finding in findings] == ["unreadable-package"]
