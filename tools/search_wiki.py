#!/usr/bin/env python3
"""Simple substring search over `wiki/` markdown pages.

Only the wiki layer is searched. Staging markdown and raw PDFs are ignored.
Meta pages (`index.md`, `log.md`) are excluded from results.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from utils import WIKI_DIR, read_markdown


MATCH_MODES = ("any", "name", "title", "body")
EXCERPT_RADIUS = 40


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", help="Substring to search for (case-insensitive).")
    parser.add_argument(
        "--in",
        dest="match_in",
        choices=MATCH_MODES,
        default="any",
        help="Which field to search against (default: any).",
    )
    return parser.parse_args()


def _excerpt(haystack: str, needle_lower: str) -> str:
    idx = haystack.lower().find(needle_lower)
    if idx < 0:
        return ""
    start = max(0, idx - EXCERPT_RADIUS)
    end = min(len(haystack), idx + len(needle_lower) + EXCERPT_RADIUS)
    window = haystack[start:end].replace("\n", " ").replace("\r", " ")
    window = " ".join(window.split())  # collapse runs of whitespace
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(haystack) else ""
    return f"{prefix}{window}{suffix}"


def _iter_pages() -> list[Path]:
    pages: list[Path] = []
    for path in sorted(WIKI_DIR.rglob("*.md")):
        if not path.is_file():
            continue
        if path.name in {"index.md", "log.md"}:
            continue
        pages.append(path)
    return pages


def main() -> int:
    args = parse_args()
    needle = args.query
    needle_lower = needle.lower()
    mode = args.match_in

    if not WIKI_DIR.exists():
        print(f"[err] wiki directory missing: {WIKI_DIR}", file=sys.stderr)
        return 1

    hits = 0

    for page in _iter_pages():
        name_str = page.name
        try:
            post = read_markdown(page)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] could not read {page.relative_to(WIKI_DIR)}: {exc}", file=sys.stderr)
            continue

        title_str = str(post.metadata.get("title", "")) if post.metadata else ""
        body_str = post.content or ""

        matched_field: str | None = None
        excerpt = ""

        def _check(field_name: str, text: str) -> tuple[bool, str]:
            if not text:
                return False, ""
            if needle_lower in text.lower():
                return True, _excerpt(text, needle_lower)
            return False, ""

        if mode in ("any", "name"):
            ok, exc_text = _check("name", name_str)
            if ok:
                matched_field = "name"
                excerpt = exc_text or name_str

        if matched_field is None and mode in ("any", "title"):
            ok, exc_text = _check("title", title_str)
            if ok:
                matched_field = "title"
                excerpt = exc_text or title_str

        if matched_field is None and mode in ("any", "body"):
            ok, exc_text = _check("body", body_str)
            if ok:
                matched_field = "body"
                excerpt = exc_text

        if matched_field is None:
            continue

        rel = page.relative_to(WIKI_DIR.parent)
        print(f"{rel}  [{matched_field}]")
        if excerpt:
            print(f"    {excerpt}")
        hits += 1

    print(f"[done] {hits} match(es)")
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
