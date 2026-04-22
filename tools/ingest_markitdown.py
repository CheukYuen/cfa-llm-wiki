#!/usr/bin/env python3
"""Convert CFA PDFs from `raw/cfa/` into markdown under `staging/markdown/cfa/`.

Incremental by default: a PDF is reconverted only when its mtime is newer
than the corresponding markdown file. Pass `--force` to reconvert everything.

This tool never writes into `wiki/`.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from utils import RAW_DIR, STAGING_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        type=Path,
        default=RAW_DIR,
        help=f"Directory containing PDFs to convert (default: {RAW_DIR}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=STAGING_DIR,
        help=f"Directory to write markdown into (default: {STAGING_DIR}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reconvert every PDF, even if the markdown is already up to date.",
    )
    return parser.parse_args()


def _needs_rebuild(pdf_path: Path, md_path: Path, force: bool) -> bool:
    if force:
        return True
    if not md_path.exists():
        return True
    return md_path.stat().st_mtime < pdf_path.stat().st_mtime


def _convert_one(pdf_path: Path, md_path: Path) -> None:
    """Convert a single PDF to markdown. Lazy imports so --help does not need deps."""
    from markitdown import MarkItDown  # noqa: WPS433 (intentional lazy import)

    md_path.parent.mkdir(parents=True, exist_ok=True)
    converter = MarkItDown()
    result = converter.convert(str(pdf_path))
    md_path.write_text(result.text_content, encoding="utf-8")


def main() -> int:
    args = parse_args()

    source: Path = args.source
    output: Path = args.output

    if not source.exists():
        print(f"[warn] source directory does not exist: {source}", file=sys.stderr)
        print("[done] ok=0 skipped=0 failed=0")
        return 0

    pdfs = sorted(source.rglob("*.pdf"))
    if not pdfs:
        print(f"[info] no PDFs found under {source}")
        print("[done] ok=0 skipped=0 failed=0")
        return 0

    ok = 0
    skipped = 0
    failed = 0

    for pdf_path in pdfs:
        rel = pdf_path.relative_to(source)
        md_path = output / rel.with_suffix(".md")

        if not _needs_rebuild(pdf_path, md_path, args.force):
            print(f"[skip] {rel}")
            skipped += 1
            continue

        try:
            _convert_one(pdf_path, md_path)
            print(f"[ok]   {rel} -> {md_path.relative_to(output.parent) if output.parent in md_path.parents else md_path}")
            ok += 1
        except Exception as exc:  # noqa: BLE001 — intentional: keep going on any failure
            print(f"[fail] {rel}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            failed += 1

    print(f"[done] ok={ok} skipped={skipped} failed={failed}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
