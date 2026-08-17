from __future__ import annotations

from pathlib import Path
from typing import Any

from . import ai_rank
from .models import Paper


TOPIC_AI_CACHE_DIR = Path("data/ai_cache/topics")


def apply_topic_ai_ranking(papers: list[Paper], config: dict[str, Any], topic_id: str) -> dict[str, Any]:
    """Run the existing ranking pipeline with a stable cache per topic profile.

    The legacy `default` profile keeps using data/ai_cache.json so old single-topic
    installations do not pay for a one-time reanalysis after upgrading. Explicit
    multi-topic profiles use isolated caches because their relevance scores are
    project-specific and must never overwrite one another.
    """
    previous_path = ai_rank.CACHE_PATH
    safe_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in topic_id)
    if topic_id != "default":
        ai_rank.CACHE_PATH = TOPIC_AI_CACHE_DIR / f"{safe_id or 'default'}.json"
    try:
        return ai_rank.apply_ai_ranking(papers, config)
    finally:
        ai_rank.CACHE_PATH = previous_path
