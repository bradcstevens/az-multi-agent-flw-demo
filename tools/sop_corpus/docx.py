"""Emit each SOP document as a plain, unlabelled `.docx`.

Copilot Studio silently excludes files it will not read, so the package is deliberately
minimal: no sensitivity label, no custom document properties, no macros, no images. Steps are
written as literal `1.` … `n.` text rather than Word auto-numbering so the ordinal survives
text extraction on the ingestion side.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from sop_corpus.corpus import Document

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>
"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>
"""

DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""

STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{WORD_NS}">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:outlineLvl w:val="0"/><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:outlineLvl w:val="1"/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="DocumentMeta"><w:name w:val="Document Meta"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:after="120"/></w:pPr><w:rPr><w:i/><w:color w:val="404040"/></w:rPr></w:style>
</w:styles>
"""


def _paragraph(text: str, style: str | None = None, indent: bool = False) -> str:
    properties = ""
    if style or indent:
        parts = []
        if style:
            parts.append(f'<w:pStyle w:val="{style}"/>')
        if indent:
            parts.append('<w:ind w:left="360"/>')
        properties = f"<w:pPr>{''.join(parts)}</w:pPr>"
    return f"<w:p>{properties}<w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"


def _core_properties(document: Document) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:title>{escape(document.title)}</dc:title>"
        f"<dc:subject>{escape(document.doc_id)}</dc:subject>"
        f"<dc:creator>{escape(document.owner)}</dc:creator>"
        f"<cp:category>Standard Operating Procedure</cp:category>"
        f"<cp:contentStatus>Published</cp:contentStatus>"
        f"<cp:revision>{escape(document.version)}</cp:revision>"
        "</cp:coreProperties>\n"
    )


def header_line(document: Document) -> str:
    return (
        f"Document ID: {document.doc_id} | Version: {document.version} "
        f"| Effective: {document.effective}"
    )


def render_document_xml(document: Document) -> str:
    body = [
        _paragraph(document.title, style="Heading1"),
        _paragraph(header_line(document), style="DocumentMeta"),
        _paragraph(f"Owner: {document.owner}", style="DocumentMeta"),
    ]
    for section in document.sections:
        body.append(_paragraph(section.heading, style="Heading2"))
        for block in section.blocks:
            if block.kind == "step":
                body.append(_paragraph(f"{block.number}. {block.text}", indent=True))
            elif block.kind == "bullet":
                body.append(_paragraph(f"\u2022 {block.text}", indent=True))
            else:
                body.append(_paragraph(block.text))
    body.append(_paragraph(f"End of {document.doc_id} {document.title}.", style="DocumentMeta"))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:document xmlns:w="{WORD_NS}"><w:body>' + "".join(body) + "</w:body></w:document>\n"
    )


def write_docx(document: Document, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / document.filename

    parts = {
        "[Content_Types].xml": CONTENT_TYPES,
        "_rels/.rels": ROOT_RELS,
        "docProps/core.xml": _core_properties(document),
        "word/_rels/document.xml.rels": DOCUMENT_RELS,
        "word/document.xml": render_document_xml(document),
        "word/styles.xml": STYLES,
    }

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as package:
        for name, content in parts.items():
            info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            package.writestr(info, content)

    return out_path
