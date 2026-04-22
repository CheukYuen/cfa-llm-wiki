# AGENTS.md — operating rules for humans and LLMs

## Mission

This repository is a **synthesised knowledge layer**, not a document
reproduction layer. The wiki exists to capture understanding in the author's
own voice, with dense cross-links and compact pages. It is not a PDF viewer,
not a search index over textbooks, and not a corpus for retrieval.

If a task tempts you to paste large chunks of source text into `wiki/`, the
task belongs elsewhere (or does not belong at all).

## Source of truth

| Directory  | Role                                  | Mutability              |
|------------|---------------------------------------|-------------------------|
| `raw/`     | Original CFA PDFs                     | Read-only. Never edit.  |
| `staging/` | MarkItDown output derived from `raw/` | Regeneratable. Safe to wipe. |
| `wiki/`    | Synthesised notes                     | The **only** editable layer. |

`raw/` is ground truth. `staging/` is a disposable cache. `wiki/` is the
product. Tooling MUST NOT write into `raw/`. Tooling MAY rewrite `staging/`.
Tooling SHOULD create skeleton pages in `wiki/` but MUST NOT overwrite
existing wiki bodies.

## Allowed page types

A wiki page's `type` frontmatter field must be one of:

- `topic` — a CFA Level I study topic (broad area).
- `concept` — a single idea (one concept per page).
- `qa` — a question the author answered for themselves.
- `meta` — reserved for `index.md`, `log.md`, `overview.md`.

`meta` is infrastructure; it does not count as a "business" page and is
excluded from normal authoring workflows.

## Frontmatter schema

Every wiki page MUST include these four fields, no more, no fewer, as the
required set:

```yaml
id: <string>          # primary key; matches filename stem
type: topic | concept | qa | meta
cfa_topic: <string>   # CFA topic slug ("" allowed for meta/concept)
status: draft | reviewed | locked
```

Other fields (`title`, `created`, `updated`, `related_concepts`, `sources`,
`related_pages`) are optional and recommended but not schema-enforced.

Validation rules (enforced by `build_wiki.py`):

- Any missing required field → `[warn]`.
- `type` value not in the allowed set → `[warn]`.
- `status` value not in the allowed set → `[warn]`.
- `id` missing or not equal to the filename stem (ignoring `topic_` /
  `concept_` / `qa_` prefix) → `[warn]`.
- `cfa_topic` key missing → `[warn]`. Empty string value is allowed.

Warnings do not block the run. Fix them when you see them.

## Writing principles

- **Do not copy PDF text.** Paraphrase. If you cannot paraphrase, you do not
  understand it yet.
- **One concept per page.** If a page grows two headings of unrelated ideas,
  split it.
- **Update before you create.** If an existing page covers the idea, extend
  it. Do not create near-duplicates.
- **Link densely.** Every concept page should link to at least one related
  concept. Every topic page should list its important concepts.
- **Keep pages short.** Concept pages under ~300 words. Q&A answers start
  small, then revise.
- **Status flow.** New pages start `draft`. Once re-read and trusted,
  promote to `reviewed`. Freeze rarely-changing pages with `locked`.

## Ingest rules (`tools/ingest_markitdown.py`)

- Input: `raw/cfa/**/*.pdf`.
- Output: `staging/markdown/cfa/<same relative path>.md`.
- Output is regeneratable and may be overwritten on each run.
- `wiki/` is not touched by this tool.
- Incremental by default; `--force` reconverts everything.

## Build rules (`tools/build_wiki.py`)

- Reads `data/topic_seed_list.yaml` and `data/concept_seed_list.yaml`.
- Creates missing topic/concept pages from templates.
- **Never overwrites** an existing page body.
- Regenerates `wiki/index.md` from the current filesystem.
- Appends a single dated entry to `wiki/log.md`.
- Validates frontmatter on every wiki page and prints warnings.

## Extract rules (`tools/extract_concepts.py`)

- LLM receives a bounded slice of `staging/` markdown and must return **only
  a list of snake_case concept slugs** as JSON.
- The tool appends new slugs to `data/concept_seed_list.yaml` (deduplicated,
  preserving existing order).
- The LLM **never** writes into `wiki/`, never modifies templates, never
  generates page bodies. Those are the author's job.
- `--dry-run` prints candidates without writing anything.

## Query rules (`tools/search_wiki.py`)

- Searches `wiki/**/*.md` only. Never `staging/`, never `raw/`.
- Excludes `index.md` and `log.md` from results.
- Match modes: `name`, `title`, `body`, or `any` (default).

## Naming rules

- Filenames: lowercase `snake_case` with `.md` suffix.
- Slugs: characters `[a-z0-9_]` only. No hyphens, no accents, no spaces.
- Frontmatter `id` MUST equal the filename stem.
- Topic pages are stored as `wiki/topics/<slug>.md` with `id: topic_<slug>`.
  Wait — to be precise: the filename stem is `<slug>`; the `id` is
  `topic_<slug>`. Validation strips the `topic_` / `concept_` / `qa_`
  prefix from `id` before comparing to the filename stem.

## Forbidden

- ❌ Pasting PDF text into any `wiki/` page.
- ❌ Editing anything under `raw/`.
- ❌ Hand-editing `wiki/index.md`. It is auto-generated.
- ❌ Hand-editing `wiki/log.md`'s existing lines. Append-only via tooling.
- ❌ Adding new top-level directories under `wiki/` without simultaneously
  updating this file **and** `tools/build_wiki.py` to know about them.
- ❌ Introducing a vector store, embedding pipeline, web server, or database
  to this repository. This is a plain-text knowledge base. Keep it that way.
