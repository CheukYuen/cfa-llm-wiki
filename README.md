# cfa-llm-wiki

A Karpathy-style **local LLM-wiki** for CFA Level I — not a PDF-RAG.

The goal is a personal, synthesised knowledge base written in your own words,
with PDFs kept only as a read-only source of truth. LLMs help seed topics and
concepts; they do not write wiki pages for you.

---

## Why this is not a PDF-RAG

| Layer       | Contents                              | Who writes it        | Editable?        |
|-------------|---------------------------------------|----------------------|------------------|
| `raw/`      | Original CFA PDFs                     | Publisher (immutable)| No — read-only   |
| `staging/`  | Markdown converted from PDFs (MarkItDown) | Tooling (regen)  | Regeneratable    |
| `wiki/`     | Your synthesised notes (topics, concepts, Q&A) | You + LLM seeds | **Yes — the only layer you edit** |

Rules of thumb:

- `raw/` is a museum. Never modify it.
- `staging/` is scratch paper. You may delete it anytime and rebuild.
- `wiki/` is the product. It must be **your** synthesis, not copy-pasted PDF text.

---

## Directory layout

```
cfa-llm-wiki/
├── raw/cfa/                    # drop PDFs here (git-ignored)
├── staging/markdown/cfa/       # MarkItDown output (git-ignored)
├── wiki/
│   ├── index.md                # auto-generated navigation
│   ├── log.md                  # auto-appended evolution log
│   ├── overview.md             # hand-written project overview
│   ├── topics/                 # one page per CFA topic
│   ├── concepts/               # one page per concept
│   └── qa/                     # one page per question
├── schema/
│   ├── AGENTS.md               # rules for humans + LLMs
│   └── page_templates/         # topic / concept / qa templates
├── data/
│   ├── topic_seed_list.yaml
│   └── concept_seed_list.yaml
└── tools/
    ├── ingest_markitdown.py    # PDF -> staging markdown
    ├── build_wiki.py           # seeds -> wiki pages + index + log
    ├── extract_concepts.py     # LLM proposes new concept slugs
    ├── search_wiki.py          # simple grep over wiki/
    └── utils.py
```

---

## Install

Python 3.11+ is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Workflow

### 1. Drop PDFs

Put your CFA PDFs into `raw/cfa/`. Subdirectories are fine.

### 2. Convert PDFs to staging markdown

```bash
python tools/ingest_markitdown.py
```

Incremental by default — only reconverts files whose PDF is newer than the
staging markdown. Use `--force` to reconvert everything. The output goes to
`staging/markdown/cfa/` and mirrors the input tree.

This tool **never** writes into `wiki/`.

### 3. Build the wiki skeleton

```bash
python tools/build_wiki.py --mode init
```

This:

- creates missing topic pages from `data/topic_seed_list.yaml`
- creates missing concept pages from `data/concept_seed_list.yaml`
- regenerates `wiki/index.md` (navigation)
- appends a dated line to `wiki/log.md`
- validates frontmatter on every wiki page

Existing pages are **not** overwritten.

### 4. Propose new concepts with an LLM (optional)

```bash
export OPENAI_API_KEY=sk-...
# optional:
# export OPENAI_BASE_URL=https://your-gateway/v1
# export OPENAI_MODEL=gpt-4o-mini

# Preview without writing:
python tools/extract_concepts.py --dry-run

# Commit the new slugs to data/concept_seed_list.yaml:
python tools/extract_concepts.py
```

The LLM only proposes `snake_case` concept slugs. It never writes a wiki page.
After running, re-run `build_wiki.py --mode init` to create skeleton pages for
the new concepts.

### 5. Search your wiki

```bash
python tools/search_wiki.py duration
python tools/search_wiki.py "yield curve" --in body
```

Search only reads `wiki/`. It ignores `staging/` and `raw/`.

---

## Using with Obsidian

Open the **project root `cfa-llm-wiki/` as your vault** — not just `wiki/`.

Why the whole repo, not just `wiki/`:

- You can cross-reference `staging/markdown/cfa/` from notes while writing.
- You can read `schema/AGENTS.md` and page templates inline.
- `[[wikilinks]]` to concept pages just work because all wiki files sit under
  one vault root.

The `.obsidian/` workspace directory is git-ignored.

---

## Things this project deliberately does NOT do

- ❌ No vector database, no embeddings, no similarity search.
- ❌ No web server, no FastAPI, no UI beyond Obsidian / your editor.
- ❌ No PDF-RAG pipeline — PDFs are references, not retrieval targets.
- ❌ No database. Frontmatter + files are the whole state.
- ❌ No autonomous agents writing pages. LLMs seed; humans synthesise.

If you find yourself wanting any of the above, you are building a different
project. Fork this one and rename it.
