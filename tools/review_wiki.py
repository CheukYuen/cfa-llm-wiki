#!/usr/bin/env python3
"""Human-in-the-loop review tool: promote drafts from `wiki_drafts/` to `wiki/`.

`tools/ingest_wiki.py` writes LLM-generated drafts under `wiki_drafts/`. They
do not become part of the wiki until a human inspects them and runs this tool
to promote them.

Promotion rules:
  - status flips from `draft` to `reviewed`.
  - `updated` is set to today.
  - locked target pages are never overwritten.
  - existing reviewed target pages require `--force` to overwrite.
  - every promotion appends a single line to `wiki/log.md`.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

import frontmatter

from utils import (
    CONCEPTS_DIR,
    DRAFTS_CONCEPTS_DIR,
    DRAFTS_TOPICS_DIR,
    LOG_PATH,
    PROJECT_ROOT,
    TOPICS_DIR,
    WIKI_DRAFTS_DIR,
    now_iso,
    read_markdown,
    today_iso,
    write_markdown,
)


def _draft_path(slug: str, type_: str) -> Path:
    base = DRAFTS_CONCEPTS_DIR if type_ == "concept" else DRAFTS_TOPICS_DIR
    return base / f"{slug}.md"


def _wiki_path(slug: str, type_: str) -> Path:
    base = CONCEPTS_DIR if type_ == "concept" else TOPICS_DIR
    return base / f"{slug}.md"


def _load_post(path: Path) -> frontmatter.Post:
    return read_markdown(path)


def _show(slug: str, type_: str) -> int:
    draft = _draft_path(slug, type_)
    target = _wiki_path(slug, type_)
    if not draft.exists():
        print(f"[err] no draft at {draft.relative_to(PROJECT_ROOT)}", file=sys.stderr)
        return 1

    print(f"# draft:  {draft.relative_to(PROJECT_ROOT)}")
    print(f"# target: {target.relative_to(PROJECT_ROOT)}"
          + ("  (exists)" if target.exists() else "  (new)"))

    draft_post = _load_post(draft)
    print("\n## frontmatter (draft)")
    for k, v in draft_post.metadata.items():
        print(f"  {k}: {v}")

    sources = draft_post.metadata.get("sources") or []
    print(f"\n## sources: {len(sources) if isinstance(sources, list) else 0}")
    if isinstance(sources, list):
        for s in sources:
            if isinstance(s, dict):
                print(f"  - {s.get('path', '?')} — {s.get('evidence', '')}")

    body = draft_post.content or ""
    print("\n## body (first 40 lines)")
    for line in body.splitlines()[:40]:
        print(f"  {line}")

    if target.exists():
        target_post = _load_post(target)
        diff = difflib.unified_diff(
            (target_post.content or "").splitlines(),
            body.splitlines(),
            fromfile=f"a/{target.name}",
            tofile=f"b/{draft.name}",
            lineterm="",
            n=2,
        )
        print("\n## diff (target → draft)")
        printed = False
        for line in diff:
            print(f"  {line}")
            printed = True
        if not printed:
            print("  (bodies identical)")
    return 0


def _promote_one(slug: str, type_: str, *, force: bool) -> str:
    draft = _draft_path(slug, type_)
    target = _wiki_path(slug, type_)
    if not draft.exists():
        return f"[skip] {type_}/{slug}: no draft at {draft.relative_to(PROJECT_ROOT)}"

    if target.exists():
        try:
            existing = _load_post(target)
        except Exception as exc:  # noqa: BLE001
            return f"[err] {type_}/{slug}: cannot read target: {exc}"
        existing_status = str(existing.metadata.get("status", ""))
        if existing_status == "locked":
            return f"[skip] {type_}/{slug}: target is locked; refusing to overwrite"
        if existing_status == "reviewed" and not force:
            return f"[skip] {type_}/{slug}: target is reviewed; pass --force to overwrite"

    try:
        draft_post = _load_post(draft)
    except Exception as exc:  # noqa: BLE001
        return f"[err] {type_}/{slug}: cannot read draft: {exc}"

    sources = draft_post.metadata.get("sources") or []
    if not (isinstance(sources, list) and sources):
        return (
            f"[skip] {type_}/{slug}: draft has no sources; "
            "refusing to promote (rerun ingest_wiki with valid context)"
        )

    new_meta = dict(draft_post.metadata)
    new_meta["status"] = "reviewed"
    new_meta["updated"] = today_iso()

    new_post = frontmatter.Post(content=draft_post.content, **new_meta)
    write_markdown(target, new_post)

    src_count = len(sources)
    return (
        f"[ok] {type_}/{slug}: promoted "
        f"{draft.relative_to(PROJECT_ROOT)} → {target.relative_to(PROJECT_ROOT)} "
        f"(sources={src_count})"
    )


def _all_drafts() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for sub, type_ in (("concepts", "concept"), ("topics", "topic")):
        d = WIKI_DRAFTS_DIR / sub
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md")):
            pairs.append((p.stem, type_))
    return pairs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slug")
    parser.add_argument("--type", choices=("concept", "topic"))
    parser.add_argument("--all", action="store_true", help="Promote every draft.")
    parser.add_argument("--show", action="store_true", help="Print draft details and diff.")
    parser.add_argument("--promote", action="store_true", help="Write the draft into wiki/.")
    parser.add_argument("--force", action="store_true", help="Overwrite reviewed targets.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not (args.show or args.promote):
        print("[err] pass --show or --promote", file=sys.stderr)
        return 2

    if args.show:
        if not (args.slug and args.type):
            print("[err] --show requires --slug and --type", file=sys.stderr)
            return 2
        return _show(args.slug, args.type)

    # --promote
    pairs: list[tuple[str, str]] = []
    if args.all:
        pairs = _all_drafts()
    else:
        if not (args.slug and args.type):
            print("[err] --promote requires either --all or (--slug and --type)", file=sys.stderr)
            return 2
        pairs = [(args.slug, args.type)]

    if not pairs:
        print("[info] no drafts to promote")
        return 0

    promoted = 0
    for slug, type_ in pairs:
        line = _promote_one(slug, type_, force=args.force)
        print(line)
        if line.startswith("[ok]"):
            promoted += 1
            with LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"- `{now_iso()}` review_wiki: promoted {type_}/{slug} "
                    "from wiki_drafts to wiki\n"
                )

    print(f"[done] promoted {promoted}/{len(pairs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
