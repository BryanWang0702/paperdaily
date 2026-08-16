from __future__ import annotations

import feedparser
import requests

from .models import Paper
from .utils import compact_text, normalize_doi


ARXIV_API = "https://export.arxiv.org/api/query"


def fetch_arxiv(
    config: dict,
    start_date: str,
    end_date: str,
    limit: int = 150,
) -> list[Paper]:
    terms = config.get("discovery_terms", [])
    categories = config.get("arxiv", {}).get("categories", [])
    if not terms:
        return []

    term_query = " OR ".join(f'all:"{term}"' for term in terms)
    query_parts = [f"({term_query})"]
    if categories:
        category_query = " OR ".join(f"cat:{category}" for category in categories)
        query_parts.append(f"({category_query})")

    start_stamp = start_date.replace("-", "") + "0000"
    end_stamp = end_date.replace("-", "") + "2359"
    query_parts.append(f"submittedDate:[{start_stamp} TO {end_stamp}]")
    search_query = " AND ".join(query_parts)

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
