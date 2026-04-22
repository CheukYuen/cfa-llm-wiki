# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is (and is not)

This is a **Karpathy-style local LLM-wiki** for CFA Level I study notes. It is
**not a PDF-RAG**. There is no vector store, no embedding pipeline, no web
server, no database, and no retrieval layer. The product is a set of
hand-written markdown pages under `wiki/`, synthesised by the human author.

If a task tempts you toward any of those rejected directions, push back
before implementing. Read `schema/AGENTS.md` for the full ruleset — it is the
canonical spec for what belongs in this repo and what does not.

## Three-layer architecture

| Layer       | Role                                | Mutability                              |
|-------------|-------------------------------------|-----------------------------------------|
| `raw/cfa/`  | Original CFA PDFs (source of truth) | Read-only. Never write or modify.       |
| `staging/markdown/cfa/` | MarkItDown output from `raw/` | Regeneratable cache. Safe to wipe.      |
| `wiki/`     | Synthesised notes (topics, concepts, qa) | The **only** layer humans edit.   |

Data flows one way: `raw/` → `staging/` (via `ingest_markitdown.py`) →
(author's brain) → `wiki/`. Tooling creates skeleton pages in `wiki/` but
MUST NOT overwrite existing page bodies.

## Frontmatter schema (enforced)

Every wiki page has exactly these four required frontmatter fields:

```yaml
id: <string>          # primary key; equals filename stem (after stripping topic_/concept_/qa_ prefix)
type: topic | concept | qa | meta
cfa_topic: <string>   # CFA topic slug; empty string allowed, but the key must be present
status: draft | reviewed | locked
```

Other fields (`title`, `created`, `updated`, `related_concepts`, `sources`,
`related_pages`) are optional and not schema-validated. Do not add new
required fields without updating `tools/build_wiki.py` and
`schema/AGENTS.md` together.

Validation happens in `build_wiki.py` and emits `[warn]` (does not block).

## Tool surface

Each tool is independently runnable via `python tools/<name>.py --help`.

- `tools/utils.py` — shared helpers (paths, slugify, frontmatter I/O, YAML,
  template rendering). No Jinja; trivial `{{var}}` substitution only.
- `tools/ingest_markitdown.py` — PDF → staging markdown. Incremental by
  mtime; `--force` to rebuild. Lazy-imports `markitdown`.
- `tools/build_wiki.py --mode init` — creates missing pages from seed
  YAMLs, regenerates `wiki/index.md`, appends to `wiki/log.md`, validates
  frontmatter. Only tool allowed to write into `wiki/` during normal use.
- `tools/extract_concepts.py` — LLM proposes new concept slugs. All
  provider-specific code lives in one function: `call_llm(text, max_new)`.
  Swapping providers (Anthropic, DeepSeek, internal gateway) means editing
  that function only. Supports `--dry-run`. Uses `OPENAI_API_KEY`,
  `OPENAI_BASE_URL` (optional), `OPENAI_MODEL` (optional, default
  `gpt-4o-mini`). Never writes wiki pages — only appends slugs to
  `data/concept_seed_list.yaml`.
- `tools/search_wiki.py` — substring search over `wiki/` only. Modes:
  `any|name|title|body`. Excludes `index.md` and `log.md`.

## The LLM boundary

There is **one** place in this codebase that calls an LLM:
`tools/extract_concepts.py::call_llm()`. That function is the provider
boundary — do not scatter LLM calls elsewhere. If you add another LLM use
case, add another boundary function, keep the pattern, do not inline.

The LLM contract is strict: JSON-only output, `{"concepts": [...]}`,
`response_format={"type": "json_object"}`, `temperature=0`. Any drift means
output is rejected.

## Common commands

```bash
# Setup (Python 3.11+)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Full regenerate loop
python tools/ingest_markitdown.py           # PDFs -> staging
python tools/build_wiki.py --mode init      # seeds -> wiki skeleton

# LLM-assisted concept expansion
export OPENAI_API_KEY=sk-...
python tools/extract_concepts.py --dry-run  # preview candidates
python tools/extract_concepts.py            # commit to seed YAML
python tools/build_wiki.py --mode init      # create pages for new slugs

# Search
python tools/search_wiki.py duration
python tools/search_wiki.py "yield curve" --in body
```

There are no unit tests, no linter configuration, and no build step. The
"test" is running `build_wiki.py --mode init` and confirming `0 warning(s)`.

## Hard rules (violating these breaks the project's contract)

- ❌ Do not paste PDF text into any `wiki/` page. Paraphrase.
- ❌ Do not edit anything under `raw/`.
- ❌ Do not hand-edit `wiki/index.md`. It is regenerated from the filesystem.
- ❌ Do not hand-edit past lines of `wiki/log.md`. Append-only via tooling.
- ❌ Do not add new top-level subdirectories under `wiki/` without also
  updating `tools/build_wiki.py` (indexing) and `schema/AGENTS.md` (rules).
- ❌ Do not introduce Jinja, Flask, FastAPI, SQLAlchemy, or any
  vector/embedding dependency. The four pinned deps
  (`markitdown[pdf]`, `PyYAML`, `python-frontmatter`, `openai`) are the
  whole dependency surface.
- ✅ Obsidian usage: open the **project root** as the vault (not just
  `wiki/`), so staging and schema are available for cross-reference.

## When extending

- New concept/topic slugs → edit `data/*.yaml`, then re-run
  `build_wiki.py --mode init`.
- New page type → update `ALLOWED_TYPES` in `build_wiki.py`, add a template
  under `schema/page_templates/`, document it in `schema/AGENTS.md`.
- New tool → put it in `tools/`, make it `--help`-able, import from
  `tools/utils.py` for paths and helpers, do not duplicate path constants.
