#!/usr/bin/env python3
"""LLM-assisted draft synthesis for concept and topic pages.

Reads context candidates from the staging layer (via grep or an external
`qmd` CLI), asks an LLM to produce structured JSON, and writes the rendered
markdown into `wiki_drafts/`. Never writes into `wiki/` — promotion is the
job of `tools/review_wiki.py` after human review.

This is the second LLM boundary in the project (the first being
`tools/extract_concepts.py`). Provider details live in `call_llm_concept`
and `call_llm_topic`. Swapping providers means editing those two
functions and nothing else.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from utils import (
    CONCEPTS_DIR,
    CONCEPT_SEEDS,
    DRAFTS_CONCEPTS_DIR,
    DRAFTS_TOPICS_DIR,
    LOG_PATH,
    PROJECT_ROOT,
    STAGING_DIR,
    TOPICS_DIR,
    TOPIC_SEEDS,
    WIKI_DIR,
    WIKI_DRAFTS_DIR,
    humanize,
    load_yaml,
    now_iso,
    read_markdown,
    today_iso,
    write_markdown,
)

import frontmatter


# ---------------------------------------------------------------------------
# LLM boundary
# ---------------------------------------------------------------------------

DASHSCOPE_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_DEFAULT_MODEL = "qwen3.6-max-preview"


CONCEPT_SYSTEM_PROMPT = (
    "You are drafting a single CFA Level I concept page for a local "
    "Karpathy-style markdown wiki. Output STRICT JSON of the exact shape:\n"
    "{\n"
    '  "definition": "one sentence, plain language",\n'
    '  "why_it_matters": "1-2 short paragraphs, the problem this concept solves",\n'
    '  "key_points": ["short bullet", "short bullet"],\n'
    '  "common_confusions": ["short bullet", "short bullet"],\n'
    '  "cfa_topic": "snake_case_topic_slug_or_empty_string",\n'
    '  "related_concepts": ["snake_case_slug", "snake_case_slug"],\n'
    '  "sources": [ {"path": "staging/markdown/cfa/...md", "evidence": "<=25 word paraphrased hint"} ]\n'
    "}\n"
    "Rules: do NOT copy long passages; paraphrase. Each evidence string is "
    "<= 25 words. Each source path MUST be one of the candidate paths "
    "provided to you, verbatim. Slugs are lowercase ASCII snake_case. "
    "Return ONLY the JSON object."
)


TOPIC_SYSTEM_PROMPT = (
    "You are drafting a single CFA Level I topic page for a local "
    "Karpathy-style markdown wiki. Output STRICT JSON of the exact shape:\n"
    "{\n"
    '  "scope": "2-3 sentences describing the topic scope",\n'
    '  "core_ideas": ["short bullet", "short bullet"],\n'
    '  "important_concepts": ["snake_case_slug", "snake_case_slug"],\n'
    '  "relevance": "why the CFA exam cares about this",\n'
    '  "sources": [ {"path": "staging/markdown/cfa/...md", "evidence": "<=25 word paraphrased hint"} ]\n'
    "}\n"
    "Rules: do NOT copy long passages; paraphrase. Each evidence string is "
    "<= 25 words. Each source path MUST be one of the candidate paths "
    "provided to you, verbatim. Slugs are lowercase ASCII snake_case. "
    "Return ONLY the JSON object."
)


def _llm_client() -> tuple[object, str]:
    from dotenv import load_dotenv  # noqa: WPS433

    load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print(
            "[err] DASHSCOPE_API_KEY is not set. Add it to .env or export it.",
            file=sys.stderr,
        )
        sys.exit(1)

    base_url = os.environ.get("DASHSCOPE_BASE_URL") or DASHSCOPE_DEFAULT_BASE_URL
    model = os.environ.get("DASHSCOPE_MODEL", DASHSCOPE_DEFAULT_MODEL)

    from openai import OpenAI  # noqa: WPS433

    return OpenAI(api_key=api_key, base_url=base_url), model


def _llm_json(system_prompt: str, user_prompt: str) -> dict:
    client, model = _llm_client()
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or ""
    return json.loads(content)


def call_llm_concept(
    slug: str,
    title: str,
    context_blocks: list["ContextBlock"],
    existing_body: str | None = None,
) -> dict:
    user = _build_user_prompt(
        kind="concept",
        slug=slug,
        title=title,
        context_blocks=context_blocks,
        existing_body=existing_body,
    )
    return _llm_json(CONCEPT_SYSTEM_PROMPT, user)


def call_llm_topic(
    slug: str,
    title: str,
    context_blocks: list["ContextBlock"],
    existing_body: str | None = None,
) -> dict:
    user = _build_user_prompt(
        kind="topic",
        slug=slug,
        title=title,
        context_blocks=context_blocks,
        existing_body=existing_body,
    )
    return _llm_json(TOPIC_SYSTEM_PROMPT, user)


def _build_user_prompt(
    *,
    kind: str,
    slug: str,
    title: str,
    context_blocks: list["ContextBlock"],
    existing_body: str | None = None,
) -> str:
    parts = [
        f"Draft a {kind} page for slug `{slug}` (title: {title}).",
        "",
        "Candidate context blocks (each tagged with its source path).",
        "Use them as the basis of your draft, but paraphrase. The `sources`",
        "field in your JSON MUST cite paths from this list verbatim.",
        "",
    ]
    if existing_body and existing_body.strip():
        parts.extend([
            "POLISH MODE — an existing author-written page already covers this",
            "concept. Preserve the author's voice, language (e.g. Chinese stays",
            "Chinese), and structural choices. Refine wording, fill obvious",
            "gaps, and add sources from the candidate blocks below. Do NOT",
            "translate, do NOT rewrite from scratch, do NOT remove content the",
            "author kept on purpose.",
            "",
            "--- BEGIN EXISTING_AUTHOR_NOTES ---",
            existing_body.strip(),
            "--- END EXISTING_AUTHOR_NOTES ---",
            "",
        ])
    if not context_blocks:
        parts.append("(no candidate context found; produce a careful, conservative draft)")
    for cb in context_blocks:
        parts.append(f"--- BEGIN {cb.path} ---")
        parts.append(cb.text)
        parts.append(f"--- END {cb.path} ---")
        parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Context retrieval
# ---------------------------------------------------------------------------

@dataclass
class ContextBlock:
    path: str
    text: str


@dataclass
class PageJob:
    slug: str
    type: str  # "concept" | "topic"
    aliases: list[str] = field(default_factory=list)
    cfa_topic: str = ""

    @property
    def title(self) -> str:
        return humanize(self.slug)

    @property
    def queries(self) -> list[str]:
        terms = [self.title, self.slug.replace("_", " ")]
        terms.extend(self.aliases)
        if self.cfa_topic:
            terms.append(self.cfa_topic.replace("_", " "))
        # de-dup, keep order
        seen: set[str] = set()
        out: list[str] = []
        for t in terms:
            t = (t or "").strip()
            key = t.lower()
            if t and key not in seen:
                seen.add(key)
                out.append(t)
        return out


def _grep_context(job: PageJob, max_chars: int) -> list[ContextBlock]:
    """Plain substring scan of staging/markdown/cfa/. Zero deps."""
    if not STAGING_DIR.exists():
        return []

    blocks: list[ContextBlock] = []
    total = 0
    radius = 4  # lines before and after each hit

    for md_path in sorted(STAGING_DIR.rglob("*.md")):
        if not md_path.is_file():
            continue
        try:
            lines = md_path.read_text(encoding="utf-8").splitlines()
        except Exception:  # noqa: BLE001
            continue
        lower_lines = [ln.lower() for ln in lines]
        hit_ranges: list[tuple[int, int]] = []
        for query in job.queries:
            q = query.lower()
            if not q:
                continue
            for idx, ln in enumerate(lower_lines):
                if q in ln:
                    hit_ranges.append((max(0, idx - radius), min(len(lines), idx + radius + 1)))
        if not hit_ranges:
            continue
        # merge overlapping ranges
        hit_ranges.sort()
        merged: list[list[int]] = []
        for s, e in hit_ranges:
            if merged and s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        snippets: list[str] = []
        for s, e in merged[:5]:  # cap snippets per file
            snippets.append("\n".join(lines[s:e]))
        block_text = "\n...\n".join(snippets)
        rel_path = md_path.relative_to(PROJECT_ROOT).as_posix()
        if total + len(block_text) > max_chars:
            block_text = block_text[: max(0, max_chars - total)]
        if block_text:
            blocks.append(ContextBlock(path=rel_path, text=block_text))
            total += len(block_text)
        if total >= max_chars:
            break
    return blocks


def _qmd_context(job: PageJob, max_chars: int) -> list[ContextBlock]:
    """Use the optional `qmd` CLI as a search surface over staging/ and wiki/.

    Falls back to grep on any error (qmd is not a hard dependency).
    """
    qmd = shutil.which("qmd")
    if not qmd:
        print(
            "[err] qmd CLI not found. Install qmd or rerun with --context-mode grep.",
            file=sys.stderr,
        )
        return []

    query = " ".join(job.queries[:4]) or job.title
    paths_seen: list[str] = []
    for target in (STAGING_DIR, WIKI_DIR):
        if not target.exists():
            continue
        try:
            proc = subprocess.run(
                [qmd, "search", query, str(target)],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] qmd failed for {target}: {exc}; falling back to grep", file=sys.stderr)
            return _grep_context(job, max_chars)
        if proc.returncode != 0:
            print(
                f"[warn] qmd returned code {proc.returncode} for {target}; "
                "skipping that target",
                file=sys.stderr,
            )
            continue
        # Conservative parse: pick out tokens that look like file paths.
        for line in proc.stdout.splitlines():
            for tok in line.split():
                tok = tok.strip().strip(":,;")
                if tok.endswith(".md") and tok not in paths_seen:
                    paths_seen.append(tok)

    if not paths_seen:
        # No usable hits — fall back rather than starving the LLM.
        return _grep_context(job, max_chars)

    blocks: list[ContextBlock] = []
    total = 0
    for raw in paths_seen[:8]:
        p = Path(raw)
        if not p.is_absolute():
            p = (PROJECT_ROOT / p).resolve()
        if not p.exists() or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        budget = max_chars - total
        if budget <= 0:
            break
        snippet = text[: min(2000, budget)]
        try:
            rel = p.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            rel = raw
        blocks.append(ContextBlock(path=rel, text=snippet))
        total += len(snippet)
    return blocks


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------

def _render_concept_md(slug: str, payload: dict, candidate_paths: set[str]) -> str:
    title = humanize(slug)
    sources = _coerce_sources(payload.get("sources", []), candidate_paths)
    related = _coerce_slug_list(payload.get("related_concepts", []))
    cfa_topic = str(payload.get("cfa_topic") or "")

    fm = {
        "id": f"concept_{slug}",
        "type": "concept",
        "cfa_topic": cfa_topic,
        "status": "draft",
        "title": title,
        "updated": today_iso(),
    }
    if related:
        fm["related_concepts"] = related
    if sources:
        fm["sources"] = [
            {"path": s["path"], "query": s.get("query", ""), "evidence": s["evidence"]}
            for s in sources
        ]

    body_lines = [
        f"# {title}",
        "",
        "## Definition",
        "",
        str(payload.get("definition", "")).strip() or "_(missing)_",
        "",
        "## Why it matters",
        "",
        str(payload.get("why_it_matters", "")).strip() or "_(missing)_",
        "",
    ]
    key_points = _coerce_str_list(payload.get("key_points", []))
    if key_points:
        body_lines.append("## Key points")
        body_lines.append("")
        body_lines.extend(f"- {kp}" for kp in key_points)
        body_lines.append("")
    confusions = _coerce_str_list(payload.get("common_confusions", []))
    if confusions:
        body_lines.append("## Common confusions")
        body_lines.append("")
        body_lines.extend(f"- {c}" for c in confusions)
        body_lines.append("")
    if related:
        body_lines.append("## Related concepts")
        body_lines.append("")
        body_lines.extend(f"- [[{r}]]" for r in related)
        body_lines.append("")
    if sources:
        body_lines.append("## Sources")
        body_lines.append("")
        for s in sources:
            body_lines.append(f"- `{s['path']}` — {s['evidence']}")
        body_lines.append("")

    post = frontmatter.Post(content="\n".join(body_lines).rstrip() + "\n", **fm)
    return frontmatter.dumps(post) + "\n"


def _render_topic_md(slug: str, payload: dict, candidate_paths: set[str]) -> str:
    title = humanize(slug)
    sources = _coerce_sources(payload.get("sources", []), candidate_paths)
    important = _coerce_slug_list(payload.get("important_concepts", []))

    fm = {
        "id": f"topic_{slug}",
        "type": "topic",
        "cfa_topic": slug,
        "status": "draft",
        "title": title,
        "updated": today_iso(),
    }
    if important:
        fm["related_concepts"] = important
    if sources:
        fm["sources"] = [
            {"path": s["path"], "query": s.get("query", ""), "evidence": s["evidence"]}
            for s in sources
        ]

    body_lines = [
        f"# {title}",
        "",
        "## Scope",
        "",
        str(payload.get("scope", "")).strip() or "_(missing)_",
        "",
    ]
    core = _coerce_str_list(payload.get("core_ideas", []))
    if core:
        body_lines.append("## Core ideas")
        body_lines.append("")
        body_lines.extend(f"- {c}" for c in core)
        body_lines.append("")
    if important:
        body_lines.append("## Important concepts")
        body_lines.append("")
        body_lines.extend(f"- [[{c}]]" for c in important)
        body_lines.append("")
    relevance = str(payload.get("relevance", "")).strip()
    if relevance:
        body_lines.append("## Relevance")
        body_lines.append("")
        body_lines.append(relevance)
        body_lines.append("")
    if sources:
        body_lines.append("## Sources")
        body_lines.append("")
        for s in sources:
            body_lines.append(f"- `{s['path']}` — {s['evidence']}")
        body_lines.append("")

    post = frontmatter.Post(content="\n".join(body_lines).rstrip() + "\n", **fm)
    return frontmatter.dumps(post) + "\n"


def _coerce_str_list(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _coerce_slug_list(raw) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in _coerce_str_list(raw):
        slug = item.lower().replace("-", "_").replace(" ", "_")
        slug = "".join(ch for ch in slug if ch.isalnum() or ch == "_").strip("_")
        if slug and slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


def _coerce_sources(raw, candidate_paths: set[str]) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        evidence = str(item.get("evidence", "")).strip()
        if not path or not evidence:
            continue
        # Trim hallucinated paths to those we actually fed in.
        if candidate_paths and path not in candidate_paths:
            continue
        # Hard cap evidence length (~25 words).
        words = evidence.split()
        if len(words) > 25:
            evidence = " ".join(words[:25]) + "…"
        out.append({"path": path, "evidence": evidence})
    return out


# ---------------------------------------------------------------------------
# Job loading
# ---------------------------------------------------------------------------

def _load_concept_jobs(slug_filter: str | None) -> list[PageJob]:
    data = load_yaml(CONCEPT_SEEDS)
    slugs = data.get("concepts", []) or []
    aliases_map = data.get("aliases", {}) or {}
    if not isinstance(aliases_map, dict):
        aliases_map = {}
    jobs: list[PageJob] = []
    for slug in slugs:
        slug = str(slug).strip()
        if not slug:
            continue
        if slug_filter and slug != slug_filter:
            continue
        aliases = aliases_map.get(slug, []) or []
        if not isinstance(aliases, list):
            aliases = []
        jobs.append(
            PageJob(
                slug=slug,
                type="concept",
                aliases=[str(a) for a in aliases if str(a).strip()],
            )
        )
    if slug_filter and not jobs:
        jobs.append(PageJob(slug=slug_filter, type="concept"))
    return jobs


def _load_topic_jobs(slug_filter: str | None) -> list[PageJob]:
    data = load_yaml(TOPIC_SEEDS)
    slugs = data.get("topics", []) or []
    aliases_map = data.get("aliases", {}) or {}
    if not isinstance(aliases_map, dict):
        aliases_map = {}
    jobs: list[PageJob] = []
    for slug in slugs:
        slug = str(slug).strip()
        if not slug:
            continue
        if slug_filter and slug != slug_filter:
            continue
        aliases = aliases_map.get(slug, []) or []
        if not isinstance(aliases, list):
            aliases = []
        jobs.append(
            PageJob(
                slug=slug,
                type="topic",
                aliases=[str(a) for a in aliases if str(a).strip()],
                cfa_topic=slug,
            )
        )
    if slug_filter and not jobs:
        jobs.append(PageJob(slug=slug_filter, type="topic", cfa_topic=slug_filter))
    return jobs


def _is_stub(target_path: Path) -> bool:
    if not target_path.exists():
        return True
    try:
        post = read_markdown(target_path)
    except Exception:  # noqa: BLE001
        return False
    body = post.content or ""
    # Heuristic: the seed templates contain underscored-italic placeholders.
    placeholder_markers = (
        "_One sentence. Plain language._",
        "_Half a paragraph.",
        "_What is this topic about?",
        "_Why does the CFA exam care?",
        "_(missing)_",
        "[[slug_1]]",
        "[[concept_slug_1]]",
    )
    return any(m in body for m in placeholder_markers)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slug", help="Slug of a single page to draft.")
    parser.add_argument(
        "--type",
        choices=("concept", "topic"),
        help="Page type. Required with --slug.",
    )
    parser.add_argument(
        "--all-stubs",
        action="store_true",
        help="Process every seeded page that is still a stub in wiki/.",
    )
    parser.add_argument(
        "--context-mode",
        choices=("grep", "qmd"),
        default="grep",
        help="How to gather staging context (default: grep).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=8000,
        help="Total character budget for context candidates (default: 8000).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=WIKI_DRAFTS_DIR,
        help=f"Output directory (default: {WIKI_DRAFTS_DIR}).",
    )
    parser.add_argument(
        "--force-draft",
        action="store_true",
        help="Overwrite an existing draft page if present.",
    )
    parser.add_argument(
        "--polish",
        action="store_true",
        help=(
            "Read the existing wiki/<type>/<slug>.md and feed its body to the "
            "LLM as 'preserve voice, refine wording, add sources'. Output "
            "still goes to wiki_drafts/ for human review."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write any draft file; print what would happen.",
    )
    return parser.parse_args()


def _gather_context(job: PageJob, mode: str, max_chars: int) -> list[ContextBlock]:
    if mode == "qmd":
        return _qmd_context(job, max_chars)
    return _grep_context(job, max_chars)


def _draft_target(out_dir: Path, job: PageJob) -> Path:
    sub = "concepts" if job.type == "concept" else "topics"
    return out_dir / sub / f"{job.slug}.md"


def _process(job: PageJob, args: argparse.Namespace) -> str:
    target = _draft_target(args.out, job)
    if target.exists() and not args.force_draft and not args.dry_run:
        return f"[skip] {job.type}/{job.slug}: draft exists (use --force-draft to overwrite)"

    blocks = _gather_context(job, args.context_mode, args.max_chars)
    if not blocks:
        print(f"[warn] {job.type}/{job.slug}: no context candidates found", file=sys.stderr)

    if args.dry_run:
        paths = ", ".join(b.path for b in blocks) or "(none)"
        return f"[dry-run] {job.type}/{job.slug}: {len(blocks)} block(s) — {paths}"

    candidate_paths = {b.path for b in blocks}
    existing_body: str | None = None
    if args.polish:
        wiki_target = (CONCEPTS_DIR if job.type == "concept" else TOPICS_DIR) / f"{job.slug}.md"
        if wiki_target.exists():
            try:
                existing_body = read_markdown(wiki_target).content or ""
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] {job.type}/{job.slug}: cannot read existing page for polish: {exc}",
                      file=sys.stderr)
        else:
            print(f"[warn] {job.type}/{job.slug}: --polish set but no existing wiki page",
                  file=sys.stderr)

    try:
        if job.type == "concept":
            payload = call_llm_concept(job.slug, job.title, blocks, existing_body)
            rendered = _render_concept_md(job.slug, payload, candidate_paths)
        else:
            payload = call_llm_topic(job.slug, job.title, blocks, existing_body)
            rendered = _render_topic_md(job.slug, payload, candidate_paths)
    except Exception as exc:  # noqa: BLE001
        return f"[err] {job.type}/{job.slug}: LLM failed: {exc}"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    return f"[ok] {job.type}/{job.slug}: wrote {target.relative_to(PROJECT_ROOT)} (sources={len(candidate_paths)})"


def main() -> int:
    args = parse_args()

    if not args.slug and not args.all_stubs:
        print("[err] specify --slug ... --type ... or --all-stubs", file=sys.stderr)
        return 2

    jobs: list[PageJob] = []
    if args.slug:
        if not args.type:
            print("[err] --type is required with --slug", file=sys.stderr)
            return 2
        if args.type == "concept":
            jobs = _load_concept_jobs(args.slug)
        else:
            jobs = _load_topic_jobs(args.slug)
    elif args.all_stubs:
        kinds = (args.type,) if args.type else ("topic", "concept")
        for kind in kinds:
            loaded = _load_concept_jobs(None) if kind == "concept" else _load_topic_jobs(None)
            for job in loaded:
                wiki_target = (CONCEPTS_DIR if kind == "concept" else TOPICS_DIR) / f"{job.slug}.md"
                if _is_stub(wiki_target):
                    jobs.append(job)

    if not jobs:
        print("[info] no jobs to process")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "concepts").mkdir(parents=True, exist_ok=True)
    (args.out / "topics").mkdir(parents=True, exist_ok=True)

    written = 0
    for job in jobs:
        line = _process(job, args)
        print(line)
        if line.startswith("[ok]"):
            written += 1

    if written and not args.dry_run:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(
                f"- `{now_iso()}` ingest_wiki: +{written} draft(s) "
                f"(context_mode={args.context_mode})\n"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
