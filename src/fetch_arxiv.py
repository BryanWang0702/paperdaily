from __future__ import annotations

from urllib.parse import quote

import feedparser
import requests

from .models import Paper
from .utils import compact_text, normalize_doi


ARXIV_API = "https://export.arxiv.org/api/query"


def fetch_arxiv(config: dict, limit: int = 150) -> list[Paper]:
    terms = config.get("discovery_terms", [])
    categories = config.get("arxiv", {}).get("categories", [])
    pieces = [f'all:"{term}"' for term in terms]
    pieces.extend(f"cat:{category}" for category in categories)
    if not pieces:
        return []

    search_query = " OR ".join(pieces)
    response = requests.get(
        ARXIV_API,
        params={
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        },
        headers={"User-Agent": "PaperDaily/0.1"},
        timeout=45,
    )
    response.raise_for_status()
    feed = feedparser.loads(response.text)

    papers: list[Paper] = []
    for entry in feed.entries:
        source_id = entry.id.rsplit("/", 1)[-1]
        doi = normalize_doi(getattr(entry, "arxiv_doi", ""))
        categories_entry = [tag.term for tag in getattr(entry, "tags", [])]
        authors = [author.name for author in getattr(entry, "authors", [])]
        papers.append(Paper(
            source="arxiv",
            source_id=source_id,
            title=compact_text(getattr(entry, "title", "")),
            abstract=compact_text(getattr(entry, "summary", "")),
            authors=authors,
            published_date=getattr(entry, "published", "")[:10],
            indexed_date=getattr(entry, "updated", "")[:10],
            journal="arXiv",
            doi=doi,
            url=getattr(entry, "link", ""),
            categories=categories_entry,
        ))

    return papers
