# cfa-llm-wiki

A Karpathy-style **local LLM-wiki** for CFA Level I — not a PDF-RAG.

The product is a set of **hand-written, human-reviewed markdown pages** under
`wiki/`. PDFs are kept only as a read-only source of truth. LLMs help draft
and polish pages; they never write directly into `wiki/`. Every reviewed page
carries explicit `sources` pointing at staging markdown.

---

## Architecture (4 layers)

| Layer            | Contents                                       | Mutability                          |
|------------------|------------------------------------------------|-------------------------------------|
| `raw/cfa/`       | Original CFA PDFs                              | Read-only. Never edit.              |
| `staging/markdown/cfa/` | MarkItDown output of `raw/`             | Regeneratable cache. Safe to wipe.  |
| `wiki_drafts/`   | LLM-generated drafts awaiting human review     | Disposable review buffer.           |
| `wiki/`          | Reviewed synthesised notes (the product)       | Final knowledge layer.              |

Data flow:

```
raw/  ──ingest_markitdown──▶  staging/  ──ingest_wiki──▶  wiki_drafts/  ──review_wiki──▶  wiki/
                              (LLM context)                              (human gate)
```

LLMs touch the middle two arrows. Humans control the last arrow. `wiki/` is
never written by an LLM directly.

---

## Directory layout

```
cfa-llm-wiki/
├── raw/cfa/                       # drop PDFs here (git-ignored)
├── staging/markdown/cfa/          # MarkItDown output (git-ignored)
├── wiki_drafts/
│   ├── concepts/                  # LLM concept drafts awaiting review
│   └── topics/                    # LLM topic drafts awaiting review
├── wiki/
│   ├── index.md                   # auto-generated navigation
│   ├── log.md                     # append-only evolution log
│   ├── overview.md                # hand-written project overview
│   ├── topics/                    # one page per CFA topic
│   ├── concepts/                  # one page per concept
│   └── qa/                        # reserved for P1; not generated in P0
├── schema/
│   ├── AGENTS.md                  # rules for humans + LLMs
│   └── page_templates/            # topic / concept / qa templates
├── data/
│   ├── topic_seed_list.yaml
│   └── concept_seed_list.yaml
├── docs/
│   └── qmd.md                     # optional local search surface
└── tools/
    ├── ingest_markitdown.py       # PDF → staging markdown
    ├── build_wiki.py              # seeds → wiki skeleton + index + log
    ├── extract_concepts.py        # LLM proposes new concept slugs
    ├── ingest_wiki.py             # LLM drafts/polishes pages → wiki_drafts/
    ├── review_wiki.py             # human-in-the-loop promote → wiki/
    ├── lint_wiki.py               # health check
    ├── search_wiki.py             # substring search over wiki/
    └── utils.py
```

---

## Install

Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Optional: install [`qmd`](docs/qmd.md) separately if you want hybrid local
search over staging+wiki. Not in `requirements.txt` — the repo works without
it via the `grep` fallback.

LLM credentials (DashScope / Bailian, OpenAI-compatible):

```bash
# .env in project root (auto-loaded by python-dotenv)
DASHSCOPE_API_KEY=sk-...
# DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1   # optional
# DASHSCOPE_MODEL=qwen3.6-max-preview                                    # optional
```

---

## Use cases

Pick the scenario closest to what you're doing.

### A. Bootstrap from PDFs (first run)

```bash
# 1. Drop PDFs into raw/cfa/  (subdirs are fine)

# 2. Convert PDFs → staging markdown (incremental by default; --force to redo)
python tools/ingest_markitdown.py

# 3. Build the wiki skeleton from seed YAMLs
python tools/build_wiki.py --mode init
```

`build_wiki.py` creates missing topic/concept stub pages, regenerates
`wiki/index.md`, appends to `wiki/log.md`, and validates frontmatter. It
**never** overwrites an existing page body.

### B. Add a new concept to the wiki via LLM

```bash
# 1. (optional) Let an LLM propose new concept slugs from staging
python tools/extract_concepts.py --dry-run     # preview
python tools/extract_concepts.py               # commit to data/concept_seed_list.yaml

# 2. Create skeleton pages for any new slugs
python tools/build_wiki.py --mode init

# 3. Have the LLM draft a real concept page
python tools/ingest_wiki.py --slug duration --type concept --dry-run   # preview
python tools/ingest_wiki.py --slug duration --type concept             # writes wiki_drafts/concepts/duration.md

# 4. Review the draft
python tools/review_wiki.py --slug duration --type concept --show

# 5. Promote into wiki/ (status flips draft → reviewed; log appended)
python tools/review_wiki.py --slug duration --type concept --promote

# 6. Refresh index
python tools/build_wiki.py --mode init

# 7. Health check
python tools/lint_wiki.py --include-drafts
```

The draft step uses `--context-mode grep` by default (zero deps). To use qmd
hybrid search instead:

```bash
python tools/ingest_wiki.py --slug duration --type concept --context-mode qmd
```

If `qmd` isn't installed, the tool prints a clear hint and you fall back to
grep — nothing crashes.

### C. Polish an existing human-authored page (add `sources`, refine)

This is for pages you already wrote (e.g. an old `reviewed` page that's
missing `sources`, or a stub you handcrafted in your own voice).

```bash
# 1. LLM polishes wiki/concepts/volatility.md → wiki_drafts/concepts/volatility.md
#    Preserves your language (Chinese stays Chinese), voice, and structure.
#    Adds Key points / Common confusions if missing, and attaches sources.
python tools/ingest_wiki.py --slug volatility --type concept --polish --force-draft

# 2. Diff the polished draft against your current page
python tools/review_wiki.py --slug volatility --type concept --show

# 3. If you like it, promote. Overwriting a reviewed page requires --force.
python tools/review_wiki.py --slug volatility --type concept --promote --force

# 4. Refresh index + lint
python tools/build_wiki.py --mode init
python tools/lint_wiki.py --include-drafts
```

`--polish` is the right tool when you don't want a wholesale rewrite — only
gap-filling and source attribution. The LLM gets your existing body as
`EXISTING_AUTHOR_NOTES` with explicit instructions not to translate or
restructure.

### D. Batch draft all concept stubs

```bash
python tools/ingest_wiki.py --all-stubs --type concept           # all stub concepts
python tools/ingest_wiki.py --all-stubs --type topic             # all stub topics
python tools/ingest_wiki.py --all-stubs --type concept --context-mode qmd
```

Errors on individual pages are printed as `[err]` and skipped — the batch
keeps going.

### E. Review and promote a backlog of drafts

```bash
python tools/review_wiki.py --all --promote                      # promote every reviewable draft
```

Refused conditions (per draft, batch continues):

- draft has no `sources` → refused.
- target wiki page is `locked` → refused outright (no override).
- target wiki page is `reviewed` → refused unless `--force`.

### F. Search

```bash
# Substring search over wiki/ only
python tools/search_wiki.py duration
python tools/search_wiki.py "yield curve" --in body

# Optional: hybrid local search over staging + wiki via qmd (see docs/qmd.md)
qmd index staging/markdown/cfa wiki
qmd search "duration convexity" wiki
```

### G. Health check

```bash
python tools/lint_wiki.py                          # wiki/ only
python tools/lint_wiki.py --include-drafts         # also flag pending drafts
python tools/lint_wiki.py --strict                 # warnings → exit 1
```

Checks:

- stub pages (template placeholders still present)
- missing `sources` (error on `reviewed`, warn on `draft`)
- broken `[[wikilinks]]`
- pages absent from `wiki/index.md`
- pending drafts under `wiki_drafts/`
- drafts targeting `locked` pages

---

## Frontmatter contract

Every wiki page has these four required fields:

```yaml
id: <string>          # equals filename stem (after stripping topic_/concept_/qa_)
type: topic | concept | qa | meta
cfa_topic: <string>   # CFA topic slug; empty string allowed but key required
status: draft | reviewed | locked
```

Recommended optional fields: `title`, `created`, `updated`, `related_concepts`,
`sources`, `related_pages`. `sources` is the provenance trail and looks like:

```yaml
sources:
  - path: staging/markdown/cfa/<file>.md
    evidence: short paraphrased hint, ≤25 words
    query: <optional search term that surfaced this path>
```

A page with `status: reviewed` **must** have at least one source. `lint_wiki`
treats this as an error.

---

## Hard rules

- ❌ Do not paste PDF text into any `wiki/` page. Paraphrase.
- ❌ Do not edit anything under `raw/`.
- ❌ Do not hand-edit `wiki/index.md` (auto-generated) or past lines of
  `wiki/log.md` (append-only).
- ❌ LLM-generated content must land in `wiki_drafts/` first; only
  `review_wiki.py --promote` writes into `wiki/`.
- ❌ Reviewed pages must carry `sources`. Drafts without sources cannot be
  promoted.
- ❌ `locked` pages are never overwritten by any tool.
- ❌ No web framework, no ORM, no database, no embedding/vector/RAG layer.
- ℹ️ `qmd` is allowed only as a local search surface — never a service, never
  a knowledge layer. See [docs/qmd.md](docs/qmd.md).
- ℹ️ Q&A generation is **P1, not P0**. `wiki/qa/` and the `qa` type stay in
  the schema for forward compatibility, but no tool generates Q&A in P0.

See [schema/AGENTS.md](schema/AGENTS.md) for the canonical ruleset.

---

## Using with Obsidian

Open the **project root** as your vault — not just `wiki/` — so staging,
drafts, and schema are all available for cross-reference. `[[wikilinks]]`
between concept pages just work. The `.obsidian/` workspace dir is git-ignored.

---

## Things this project deliberately does NOT do

- ❌ No vector database, no embeddings, no similarity search.
- ❌ No web server, no FastAPI, no UI beyond Obsidian / your editor.
- ❌ No PDF-RAG pipeline — PDFs are references, not retrieval targets.
- ❌ No ORM, no database. Frontmatter + files are the whole state.
- ❌ No autonomous agents writing into `wiki/`. LLMs draft; humans review.
- ❌ No Q&A generation in P0.

If you want any of the above, fork and rename. This repo's identity is
"local plain-text knowledge base reviewed by a human."
