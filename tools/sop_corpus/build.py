"""Build the SOP corpus from markdown sources and verify the result before upload."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sop_corpus.corpus import load_corpus
from sop_corpus.docx import write_docx
from sop_corpus.ingestion import check_corpus

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parents[2] / "content" / "sop"


def build_corpus(content_dir: Path, out_dir: Path) -> list[Path]:
    corpus = load_corpus(content_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    expected = {document.filename for document in corpus.documents}
    for stale in out_dir.glob("*.docx"):
        if stale.name not in expected:
            stale.unlink()
    return [write_docx(document, out_dir) for document in corpus.documents]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sop_corpus", description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--content-dir", type=Path, default=DEFAULT_CONTENT_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    out_dir = args.out_dir or args.content_dir / "docx"

    if args.command == "build":
        built = build_corpus(args.content_dir, out_dir)
        for path in built:
            print(f"built {path.relative_to(Path.cwd()) if path.is_absolute() else path}")

    findings = check_corpus(out_dir)
    corpus = load_corpus(args.content_dir)
    for term, doc_id in corpus.honest_miss_coverage():
        print(f"honest-miss term '{term}' is covered by {doc_id}", file=sys.stderr)
    for finding in findings:
        print(str(finding), file=sys.stderr)

    if findings or corpus.honest_miss_coverage():
        return 1
    print(f"{len(corpus.documents)} documents ready for upload from {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
