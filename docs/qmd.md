# qmd in this project

`qmd` is an optional local markdown search CLI. We use it as a search
*surface* over `staging/markdown/cfa/` and `wiki/`. It is **not** a new
knowledge layer, **not** a service, and **not** a PDF-RAG.

## Boundaries

- qmd reads local markdown only — `staging/` and `wiki/`.
- qmd does not write any file in this repo.
- qmd does not replace the wiki. The wiki is still the only knowledge layer.
- qmd does not introduce a persistent retrieval service.
- qmd search results are *candidates* for LLM-assisted synthesis. The
  synthesised page must still be authored as plain markdown under
  `wiki_drafts/` and reviewed by a human before promotion to `wiki/`.
- qmd is **not** a hard dependency. It is intentionally absent from
  `requirements.txt`. The repo must work end-to-end via the `grep`
  fallback (`tools/ingest_wiki.py --context-mode grep`,
  `tools/search_wiki.py`).

## Who needs it

- **Knowledge synthesisers** — anyone who runs `tools/ingest_wiki.py`
  with `--context-mode qmd` and wants better recall over the staging
  layer. Recommended.
- **Reviewers and markdown editors** — do not need qmd. Use
  `tools/search_wiki.py` and `tools/review_wiki.py` directly.

## Install

Follow the upstream qmd install instructions. Do not pin qmd in this
repo's `requirements.txt`; it is an external CLI.

## Recommended usage

```bash
# Index the project's markdown surfaces
qmd index staging/markdown/cfa wiki

# Search for a concept across both surfaces
qmd search "duration convexity fixed income"

# Search staging only (raw context for synthesis)
qmd search "time value of money present value future value" staging/markdown/cfa

# Search wiki only (existing synthesised notes)
qmd search "duration convexity" wiki
```

## How `tools/ingest_wiki.py` uses it

```bash
# Default — zero deps, plain substring scan of staging
python tools/ingest_wiki.py --slug duration --type concept --context-mode grep --dry-run

# Optional — let qmd pick context candidates
python tools/ingest_wiki.py --slug duration --type concept --context-mode qmd --dry-run
```

Behaviour:

- The tool calls qmd via `subprocess`. If qmd is missing, it prints a
  clear error and tells you to use `--context-mode grep`. It does not
  crash.
- If qmd returns nothing usable for a given page, the tool falls back
  to grep for that page rather than starving the LLM.
- qmd output parsing is intentionally conservative: tokens that look
  like `*.md` paths are kept, everything else is ignored. We do not
  pin qmd's output format.

## What qmd is NOT used for

- Not used to write into `wiki/` or `wiki_drafts/`.
- Not used to ingest PDFs or modify `staging/`.
- Not used as a runtime retrieval layer for any chat or web service.
- Not exposed to end users of the wiki — readers open `.md` files
  directly (or via Obsidian).
