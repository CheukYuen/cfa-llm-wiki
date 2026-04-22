"""Shared helpers for cfa-llm-wiki tools.

Keep this module dependency-light: only `PyYAML` and `python-frontmatter` from
the project's pinned requirements. No Jinja, no templating engine.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter
import yaml

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

RAW_DIR: Path = PROJECT_ROOT / "raw" / "cfa"
STAGING_DIR: Path = PROJECT_ROOT / "staging" / "markdown" / "cfa"

WIKI_DIR: Path = PROJECT_ROOT / "wiki"
TOPICS_DIR: Path = WIKI_DIR / "topics"
CONCEPTS_DIR: Path = WIKI_DIR / "concepts"
QA_DIR: Path = WIKI_DIR / "qa"

INDEX_PATH: Path = WIKI_DIR / "index.md"
LOG_PATH: Path = WIKI_DIR / "log.md"

SCHEMA_DIR: Path = PROJECT_ROOT / "schema"
TEMPLATES_DIR: Path = SCHEMA_DIR / "page_templates"

DATA_DIR: Path = PROJECT_ROOT / "data"
TOPIC_SEEDS: Path = DATA_DIR / "topic_seed_list.yaml"
CONCEPT_SEEDS: Path = DATA_DIR / "concept_seed_list.yaml"


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def today_iso() -> str:
    """Return today's UTC date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 timestamp ending in Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Normalise arbitrary text into a snake_case ASCII slug."""
    normalised = unicodedata.normalize("NFKD", text)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")
    lower = ascii_only.lower()
    replaced = _SLUG_NON_ALNUM.sub("_", lower)
    return replaced.strip("_")


def humanize(slug: str) -> str:
    """Render a slug as a human-readable Title Case string."""
    return " ".join(part.capitalize() for part in slug.split("_") if part)


# ---------------------------------------------------------------------------
# Markdown / frontmatter helpers
# ---------------------------------------------------------------------------

def read_markdown(path: Path) -> frontmatter.Post:
    """Load a markdown file with frontmatter into a Post object."""
    with path.open("r", encoding="utf-8") as fh:
        return frontmatter.load(fh)


def write_markdown(path: Path, post: frontmatter.Post) -> None:
    """Write a Post back to disk, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(frontmatter.dumps(post))
        fh.write("\n")


_TEMPLATE_VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_template(template_path: Path, **context: Any) -> str:
    """Render a template with trivial `{{ var }}` substitution.

    No loops, no conditionals, no filters. Missing variables are left as the
    original placeholder so problems are easy to spot by eye.
    """
    raw = template_path.read_text(encoding="utf-8")

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            return str(context[key])
        return match.group(0)

    return _TEMPLATE_VAR.sub(_sub, raw)


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file. Returns `{}` if the file is missing or empty."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level mapping in {path}, got {type(data).__name__}")
    return data


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a YAML file with project-standard formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            data,
            fh,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )


__all__ = [
    "PROJECT_ROOT",
    "RAW_DIR",
    "STAGING_DIR",
    "WIKI_DIR",
    "TOPICS_DIR",
    "CONCEPTS_DIR",
    "QA_DIR",
    "INDEX_PATH",
    "LOG_PATH",
    "SCHEMA_DIR",
    "TEMPLATES_DIR",
    "DATA_DIR",
    "TOPIC_SEEDS",
    "CONCEPT_SEEDS",
    "today_iso",
    "now_iso",
    "slugify",
    "humanize",
    "read_markdown",
    "write_markdown",
    "render_template",
    "load_yaml",
    "dump_yaml",
]
