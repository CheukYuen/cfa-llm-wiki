#!/usr/bin/env python3
"""Ask an LLM to propose new concept slugs from the staging markdown.

The LLM returns a list of `snake_case` concept slugs. This tool deduplicates
them against the existing `data/concept_seed_list.yaml` and (unless
`--dry-run`) writes the combined list back.

The LLM never writes a wiki page. That is the author's job. This tool is the
only place in the project that talks to an LLM, and every provider-specific
detail lives inside `call_llm()` so a future swap (Anthropic, DeepSeek, an
internal gateway, etc.) only touches that one function.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from utils import (
    CONCEPT_SEEDS,
    LOG_PATH,
    STAGING_DIR,
    dump_yaml,
    load_yaml,
    now_iso,
    slugify,
)


# ---------------------------------------------------------------------------
# LLM boundary — keep every provider-specific detail inside this function.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You extract candidate financial concept slugs from CFA Level I study "
    "material. Return a JSON object of the exact shape "
    '{"concepts": ["slug_1", "slug_2", ...]}. '
    "Each slug MUST be snake_case ASCII (only [a-z0-9_]), a short noun or "
    "noun phrase naming a single idea (e.g. 'yield_curve', 'duration', "
    "'arbitrage_pricing_theory'). Do NOT return sentences, questions, or "
    "verbs. Do NOT wrap the object in any other keys. Do NOT include any "
    "text outside the JSON object."
)


def call_llm(text: str, max_new: int) -> list[str]:
    """Return a list of candidate concept slugs."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(
            "[err] OPENAI_API_KEY is not set. "
            "Export it (and optionally OPENAI_BASE_URL / OPENAI_MODEL) and retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    base_url = os.environ.get("OPENAI_BASE_URL") or None
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    from openai import OpenAI  # noqa: WPS433 (lazy import so --help works without deps)

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    user_prompt = (
        f"Propose at most {max_new} new concept slugs drawn from the text "
        "below. Return ONLY the JSON object described in the system prompt.\n\n"
        "---\n"
        f"{text}\n"
        "---"
    )

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content or ""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        print(f"[err] LLM did not return valid JSON: {exc}", file=sys.stderr)
        print(f"[err] raw content: {content!r}", file=sys.stderr)
        sys.exit(1)

    raw_concepts = parsed.get("concepts", [])
    if not isinstance(raw_concepts, list):
        print(
            f"[err] LLM JSON 'concepts' is not a list: {type(raw_concepts).__name__}",
            file=sys.stderr,
        )
        sys.exit(1)

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_concepts:
        if not isinstance(item, str):
            continue
        slug = slugify(item)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        cleaned.append(slug)
        if len(cleaned) >= max_new:
            break
    return cleaned


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        type=Path,
        default=STAGING_DIR,
        help=f"Directory containing staging markdown (default: {STAGING_DIR}).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=12000,
        help="Max number of staging characters sent to the LLM (default: 12000).",
    )
    parser.add_argument(
        "--max-new",
        type=int,
        default=20,
        help="Max number of candidate slugs the LLM may return (default: 20).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print candidates only. Do not write YAML or append to the log.",
    )
    return parser.parse_args()


def gather_text(source: Path, max_chars: int) -> str:
    parts: list[str] = []
    total = 0
    for md_path in sorted(source.rglob("*.md")):
        if not md_path.is_file():
            continue
        try:
            body = md_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] could not read {md_path}: {exc}", file=sys.stderr)
            continue
        rel = md_path.relative_to(source) if source in md_path.parents or md_path.parent == source else md_path
        header = f"\n\n# === FILE: {rel} ===\n\n"
        chunk = header + body
        if total + len(chunk) > max_chars:
            remaining = max_chars - total
            if remaining > 0:
                parts.append(chunk[:remaining])
                total += remaining
            break
        parts.append(chunk)
        total += len(chunk)
    return "".join(parts).strip()


def main() -> int:
    args = parse_args()

    if not args.source.exists():
        print(f"[info] staging directory missing: {args.source}. Run ingest first.")
        return 0

    text = gather_text(args.source, args.max_chars)
    if not text:
        print(f"[info] no staging markdown under {args.source}. "
              "Run `python tools/ingest_markitdown.py` first.")
        return 0

    print(f"[info] sending {len(text)} chars of staging to LLM "
          f"(max_new={args.max_new}, model={os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')})")

    candidates = call_llm(text, args.max_new)
    if candidates:
        print("[candidates]")
        for slug in candidates:
            print(f"  - {slug}")
    else:
        print("[candidates] (none)")

    if args.dry_run:
        print("[dry-run] not writing seed list")
        return 0

    existing_data = load_yaml(CONCEPT_SEEDS)
    existing_list = existing_data.get("concepts", []) or []
    if not isinstance(existing_list, list):
        print(
            f"[err] {CONCEPT_SEEDS} does not contain a list under 'concepts'",
            file=sys.stderr,
        )
        return 2

    existing_set = {str(x) for x in existing_list}
    new_slugs = [slug for slug in candidates if slug not in existing_set]
    merged = [str(x) for x in existing_list] + new_slugs

    existing_data["concepts"] = merged
    dump_yaml(CONCEPT_SEEDS, existing_data)

    if new_slugs:
        joined = ", ".join(new_slugs)
        print(f"[ok] appended {len(new_slugs)} new slug(s) to "
              f"{CONCEPT_SEEDS.relative_to(CONCEPT_SEEDS.parent.parent)}")
        log_line = f"- `{now_iso()}` extract_concepts: +{len(new_slugs)} candidate(s) ({joined})"
    else:
        print("[ok] no new slugs to add")
        log_line = f"- `{now_iso()}` extract_concepts: +0 candidate(s) -"

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(log_line.rstrip() + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
