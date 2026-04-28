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

## Architecture

| Layer                    | Role                                            | Mutability                          |
|--------------------------|-------------------------------------------------|-------------------------------------|
| `raw/cfa/`               | Original CFA PDFs (source of truth)             | Read-only. Never write or modify.   |
| `staging/markdown/cfa/`  | MarkItDown output from `raw/`                   | Regeneratable cache. Safe to wipe.  |
| `wiki_drafts/`           | LLM-generated draft pages awaiting human review | Disposable review buffer.           |
| `wiki/`                  | Reviewed synthesised notes                      | The **only** final knowledge layer. |

Data flow: `raw/` → `staging/` (via `ingest_markitdown.py`) → LLM-assisted
draft (via `ingest_wiki.py`) → `wiki_drafts/` → human review (via
`review_wiki.py`) → `wiki/`. Tooling MUST NOT overwrite existing page
bodies in `wiki/`. Only `review_wiki.py` may promote a draft into `wiki/`,
and never over a `locked` page.

`wiki_drafts/` is a buffer, not a knowledge layer. It is disposable.

## Optional search surface: qmd

`qmd` is an optional local markdown search CLI used as a search surface
over `staging/` and `wiki/`. It is **not** a new knowledge layer, does
not write content, and does not replace the wiki — search results are
only candidates for LLM-assisted synthesis. qmd is **not** pinned in
`requirements.txt`; the repo must work without it via the `grep`
fallback in `ingest_wiki.py` and via `search_wiki.py`. See `docs/qmd.md`.

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
  Swapping providers (Anthropic, DeepSeek, OpenAI, internal gateway) means
  editing that function only. Supports `--dry-run`. Current provider is
  Alibaba Cloud DashScope (Bailian) in OpenAI-compatible mode, reusing the
  pinned `openai` SDK. Reads `DASHSCOPE_API_KEY` (required),
  `DASHSCOPE_BASE_URL` (optional, default
  `https://dashscope.aliyuncs.com/compatible-mode/v1`), and
  `DASHSCOPE_MODEL` (optional, default `qwen3.6-max-preview`). A project-
  root `.env` file is auto-loaded via `python-dotenv` (`override=False`,
  so real environment variables still win). Never writes wiki pages —
  only appends slugs to `data/concept_seed_list.yaml`.
- `tools/search_wiki.py` — substring search over `wiki/` only. Modes:
  `any|name|title|body`. Excludes `index.md` and `log.md`.
- `tools/ingest_wiki.py` — LLM-assisted draft synthesis for concept and
  topic pages. Gathers staging context (`--context-mode grep` default,
  `--context-mode qmd` optional), calls the LLM, and writes the rendered
  page into `wiki_drafts/`. Never writes into `wiki/`. Output pages have
  `status: draft` and a `sources` frontmatter list whose `path` values
  are constrained to the candidate context paths actually supplied.
  Provider details live in `call_llm_concept` / `call_llm_topic` (same
  DashScope/OpenAI-compatible setup as `extract_concepts.py`).
- `tools/review_wiki.py` — human-in-the-loop promotion. `--show` prints
  draft frontmatter, sources, body excerpt, and a diff against the
  current `wiki/` page (if any). `--promote` writes the draft into
  `wiki/`, flips `status` to `reviewed`, sets `updated` to today, and
  appends a line to `wiki/log.md`. Refuses to promote drafts that have
  no sources. Refuses to overwrite `locked` pages outright. Refuses to
  overwrite `reviewed` pages without `--force`.
- `tools/lint_wiki.py` — health check: stub pages, missing sources
  (`reviewed` without sources is an error; `draft` is a warning),
  broken `[[wikilinks]]`, pages absent from `wiki/index.md`, pending
  drafts in `wiki_drafts/`, and drafts targeting `locked` pages. Use
  `--include-drafts` to lint the draft layer too. `--strict` makes
  warnings exit non-zero.

`tools/qa_generate.py` is intentionally **not** part of P0. Q&A
generation is deferred. The `qa` `type` value and `wiki/qa/` directory
are kept in the schema for forward compatibility, but no tool generates
them and `lint_wiki.py` does not require pages there.

## The LLM boundary

LLM calls are confined to two boundary modules:

- `tools/extract_concepts.py::call_llm()` — proposes concept slugs.
- `tools/ingest_wiki.py::call_llm_concept()` / `call_llm_topic()` —
  drafts a concept or topic page as strict JSON.

Do not scatter LLM calls elsewhere. New LLM use cases get new boundary
functions; do not inline. All boundary functions enforce
`response_format={"type": "json_object"}`, `temperature=0`, and reject
any output that does not match the declared JSON shape.

## Common commands

```bash
# Setup (Python 3.11+)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Full regenerate loop
python tools/ingest_markitdown.py           # PDFs -> staging
python tools/build_wiki.py --mode init      # seeds -> wiki skeleton

# LLM-assisted concept expansion (DashScope / Bailian, qwen3.6-max-preview)
# Put DASHSCOPE_API_KEY in .env (auto-loaded), or export it in the shell.
python tools/extract_concepts.py --dry-run  # preview candidates
python tools/extract_concepts.py            # commit to seed YAML
python tools/build_wiki.py --mode init      # create pages for new slugs

# Search
python tools/search_wiki.py duration
python tools/search_wiki.py "yield curve" --in body

# LLM-assisted draft synthesis (writes wiki_drafts/, never wiki/)
python tools/ingest_wiki.py --slug duration --type concept --dry-run
python tools/ingest_wiki.py --slug duration --type concept
python tools/ingest_wiki.py --all-stubs --type concept
python tools/ingest_wiki.py --slug duration --type concept --context-mode qmd

# Human-in-the-loop review
python tools/review_wiki.py --slug duration --type concept --show
python tools/review_wiki.py --slug duration --type concept --promote
python tools/review_wiki.py --all --promote

# Health check
python tools/lint_wiki.py --include-drafts
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
- ❌ Do not introduce a web framework (Flask, FastAPI, Django, ...), an
  ORM / database driver (SQLAlchemy, psycopg, ...), a templating engine
  (Jinja, Mako, ...), or any vector / embedding / RAG dependency. These
  are banned on architectural grounds — they contradict the project's
  "local plain-text knowledge base, not a PDF-RAG" identity, not because
  of any dependency-count budget.
- ℹ️ Dependencies are kept minimal by default but **not frozen**. Adding
  a small, well-scoped library (e.g. `python-dotenv`, `httpx`, `rich`) is
  allowed when it replaces hand-rolled code or materially improves a
  tool. When you add one: pin it in `requirements.txt` with a sensible
  floor, mention it in the relevant tool's docstring, and — if it
  affects the LLM path — note it in this file's "Tool surface" section.
- ❌ Do not let LLM-generated content land directly in `wiki/`. It must
  go to `wiki_drafts/` and pass `tools/review_wiki.py --promote` first.
- ❌ Do not promote a draft that lacks `sources`. Reviewed pages must
  carry source provenance pointing at `staging/` paths.
- ❌ Do not overwrite `locked` pages from any tool, ever.
- ❌ Do not treat `qmd` as PDF-RAG infrastructure. It is a local search
  surface, optional, never a service. See `docs/qmd.md`.
- ℹ️ Q&A generation is P1, not P0. Do not implement `qa_generate.py`.
- ✅ Obsidian usage: open the **project root** as the vault (not just
  `wiki/`), so staging, drafts, and schema are available for
  cross-reference.

## When extending

- New concept/topic slugs → edit `data/*.yaml`, then re-run
  `build_wiki.py --mode init`.
- New page type → update `ALLOWED_TYPES` in `build_wiki.py`, add a template
  under `schema/page_templates/`, document it in `schema/AGENTS.md`.
- New tool → put it in `tools/`, make it `--help`-able, import from
  `tools/utils.py` for paths and helpers, do not duplicate path constants.
