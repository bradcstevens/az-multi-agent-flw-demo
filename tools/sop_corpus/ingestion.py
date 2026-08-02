"""Check built SOP files against Copilot Studio's file-ingestion rules.

Copilot Studio does not report the files it refuses; it just answers as though they were never
uploaded. Every rule here is therefore a silent-exclusion rule, checked locally before anything
is uploaded to Dataverse.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXTENSIONS = frozenset({".doc", ".docx", ".ppt", ".pptx", ".pdf"})
MAX_FILE_BYTES = 7 * 1024 * 1024
MIN_DOCUMENTS = 8
MAX_DOCUMENTS = 12

_LABEL_MARKERS = ("MSIP_Label", "ClassificationWatermark", "MicrosoftIrmProtector")
_LABEL_PARTS = ("docProps/custom.xml", "customXml/item1.xml")
_MAIN_PARTS = {".docx": "word/document.xml", ".pptx": "ppt/presentation.xml"}


@dataclass(frozen=True)
class Finding:
    path: Path
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path.name}: [{self.rule}] {self.detail}"


def _read_package(path: Path) -> tuple[set[str], str] | None:
    """Part names plus the label-bearing metadata, or None if the package is unreadable."""
    try:
        with zipfile.ZipFile(path) as package:
            if package.testzip() is not None:
                return None
            names = set(package.namelist())
            payload = "".join(
                package.read(part).decode("utf-8", "ignore")
                for part in _LABEL_PARTS
                if part in names
            )
    except (zipfile.BadZipFile, OSError):
        return None
    return names, payload


def check_file(path: Path) -> list[Finding]:
    path = Path(path)
    findings: list[Finding] = []

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        findings.append(
            Finding(
                path,
                "unsupported-file-type",
                f"{path.suffix or 'no extension'} is not one of "
                f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            )
        )

    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        findings.append(
            Finding(path, "file-too-large", f"{size} bytes exceeds the {MAX_FILE_BYTES}-byte limit")
        )

    main_part = _MAIN_PARTS.get(path.suffix.lower())
    if main_part:
        package = _read_package(path)
        if package is None:
            findings.append(
                Finding(path, "unreadable-package", "is not a readable OOXML package")
            )
        elif main_part not in package[0]:
            findings.append(
                Finding(
                    path,
                    "unreadable-package",
                    f"is missing its main part {main_part}",
                )
            )
        else:
            markers = [marker for marker in _LABEL_MARKERS if marker in package[1]]
            if markers:
                findings.append(
                    Finding(
                        path,
                        "sensitivity-label",
                        f"carries sensitivity-label metadata ({', '.join(markers)}); Copilot "
                        "Studio silently excludes labelled files",
                    )
                )

    return findings


def check_files(paths) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        findings.extend(check_file(Path(path)))
    return findings


def check_corpus(docx_dir: Path) -> list[Finding]:
    docx_dir = Path(docx_dir)
    files = sorted(p for p in docx_dir.iterdir() if p.is_file() and not p.name.startswith("."))
    findings = check_files(files)
    if not MIN_DOCUMENTS <= len(files) <= MAX_DOCUMENTS:
        findings.append(
            Finding(
                docx_dir,
                "corpus-size",
                f"{len(files)} documents is outside the {MIN_DOCUMENTS}-{MAX_DOCUMENTS} range",
            )
        )
    return findings
