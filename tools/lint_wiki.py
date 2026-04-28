#!/usr/bin/env python3
"""Health checks across `wiki/` and (optionally) `wiki_drafts/`.

Checks:
  1. Stub pages — bodies that still contain template placeholders.
  2. Missing sources — non-meta pages with no `sources` frontmatter and
     no `## Sources` body section. `draft` → warn, `reviewed` → error.
  3. Broken wikilinks — `[[slug]]` references that have no matching page.
  4. Index coverage — wiki pages absent from `wiki/index.md`.
  5. Pending drafts — files in `wiki_drafts/` are surfaced as info.
  6. Locked targets — drafts that would target a locked page (warn).

`qa/` is intentionally not checked: Q&A generation is not a P0 goal.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from utils import (
    CONCEPTS_DIR,
    DRAFTS_CONCEPTS_DIR,
    DRAFTS_TOPICS_DIR,
    INDEX_PATH,
    PROJECT_ROOT,
    TOPICS_DIR,
    WIKI_DIR,
    WIKI_DRAFTS_DIR,
    read_markdown,
)

PLACEHOLDER_MARKERS = (
    "_One sentence. Plain language._",
    "_Half a paragraph. Problem solved by this concept._",
    "_What is this topic about?",
    "_Why does the CFA exam care?",
    "[[slug_1]]",
    "[[concept_slug_1]]",
    "_(missing)_",
    "_Edge cases, formulae, mnemonics.",
)

WIKILINK_RE = re.compile(r"\[\[([a-z0-9_]+)\]\]")


def _iter_pages(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def _is_meta(post_meta: dict, path: Path) -> bool:
    if path.name in {"index.md", "log.md", "overview.md"}:
        return True
    return str(post_meta.get("type", "")) == "meta"


def _has_sources(meta: dict, body: str) -> bool:
    src = meta.get("sources")
    if isinstance(src, list) and src:
        return True
    return "## Sources" in body


def _all_slugs(roots: list[Path]) -> set[str]:
    slugs: set[str] = set()
    for root in roots:
        for p in _iter_pages(root):
            if p.name in {"index.md", "log.md"}:
                continue
            slugs.add(p.stem)
    return slugs


def lint(*, include_drafts: bool) -> tuple[int, int]:
    errors = 0
    warnings = 0

    wiki_slugs = _all_slugs([CONCEPTS_DIR, TOPICS_DIR])

    # 1, 2, 3: per-page checks under wiki/
    for path in _iter_pages(WIKI_DIR):
        rel = path.relative_to(PROJECT_ROOT)
        if path.name in {"index.md", "log.md"}:
            continue
        try:
            post = read_markdown(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[err] {rel}: cannot parse: {exc}")
            errors += 1
            continue
        meta = post.metadata
        body = post.content or ""
        is_meta = _is_meta(meta, path)

        if any(m in body for m in PLACEHOLDER_MARKERS):
            print(f"[warn] {rel}: stub page (template placeholders present)")
            warnings += 1

        if not is_meta and not _has_sources(meta, body):
            status = str(meta.get("status", ""))
            if status == "reviewed":
                print(f"[err] {rel}: reviewed page has no sources")
                errors += 1
            else:
                print(f"[warn] {rel}: missing sources")
                warnings += 1

        for target in WIKILINK_RE.findall(body):
            if target not in wiki_slugs:
                print(f"[warn] {rel}: broken wikilink [[{target}]]")
                warnings += 1

    # 4: index coverage
    if INDEX_PATH.exists():
        index_text = INDEX_PATH.read_text(encoding="utf-8")
        for path in _iter_pages(WIKI_DIR):
            if path.name in {"index.md", "log.md", "overview.md"}:
                continue
            if path.name not in index_text:
                rel = path.relative_to(PROJECT_ROOT)
                print(f"[warn] {rel}: not listed in wiki/index.md (run build_wiki.py)")
                warnings += 1

    # 5, 6: drafts
    draft_pages = _iter_pages(WIKI_DRAFTS_DIR)
    if draft_pages:
        print(f"[info] {len(draft_pages)} draft(s) pending review under wiki_drafts/")
        if include_drafts:
            for path in draft_pages:
                rel = path.relative_to(PROJECT_ROOT)
                try:
                    post = read_markdown(path)
                except Exception as exc:  # noqa: BLE001
                    print(f"[err] {rel}: cannot parse: {exc}")
                    errors += 1
                    continue
                body = post.content or ""
                meta = post.metadata
                if any(m in body for m in PLACEHOLDER_MARKERS):
                    print(f"[warn] {rel}: stub draft (template placeholders present)")
                    warnings += 1
                if not _has_sources(meta, body):
                    print(f"[warn] {rel}: draft missing sources")
                    warnings += 1
                # Locked target?
                slug = path.stem
                type_dir = path.parent.name
                target = (
                    CONCEPTS_DIR / f"{slug}.md"
                    if type_dir == "concepts"
                    else TOPICS_DIR / f"{slug}.md"
                )
                if target.exists():
                    try:
                        tpost = read_markdown(target)
                        if str(tpost.metadata.get("status", "")) == "locked":
                            print(
                                f"[warn] {rel}: target {target.relative_to(PROJECT_ROOT)} "
                                "is locked; promotion will be refused"
                            )
                            warnings += 1
                    except Exception:  # noqa: BLE001
                        pass

    return errors, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--include-drafts",
        action="store_true",
        help="Also check pages under wiki_drafts/.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on warnings as well as errors.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors, warnings = lint(include_drafts=args.include_drafts)
    print(f"[done] errors={errors} warnings={warnings}")
    if errors:
        return 1
    if warnings and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
