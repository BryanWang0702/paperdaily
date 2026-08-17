from __future__ import annotations

import json
import time
from pathlib import Path

import feedparser
import requests

from .models import Paper
from .utils import compact_text, normalize_doi


ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_SOURCE_CACHE = Path("data/source_cache/arxiv.json")
DEFAULT_RETRY_DELAYS = [10, 30]
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
PAPERDAILY_VERSION = "0.5.4"


def _paper_from_cache(item: dict) -> Paper:
    return Paper(
        source=str(item.get("source", "arxiv")),
        source_id=str(item.get("source_id", "")),
        title=str(item.get("title", "")),
        abstract=str(item.get("abstract", "")),
        authors=[str(value) for value in (item.get("authors") or [])],
        published_date=str(item.get("published_date", "")),
        indexed_date=str(item.get("indexed_date", "")),
        journal=str(item.get("journal", "arXiv")),
        doi=str(item.get("doi", "")),
        url=str(item.get("url", "")),
        categories=[str(value) for value in (item.get("categories") or [])],
        keywords=[str(value) for value in (item.get("keywords") or [])],
        publication_types=[str(value) for value in (item.get("publication_types") or ["Preprint"])],
        extra=dict(item.get("extra") or {}),
    )


def _read_same_window_cache(start_date: str, end_date: str) -> list[Paper] | None:
    try:
        payload = json.loads(ARXIV_SOURCE_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    window = payload.get("window") or {}
    if window.get("start") != start_date or window.get("end") != end_date:
        return None

    papers: list[Paper] = []
    for item in payload.get("papers", []) or []:
        if not isinstance(item, dict):
            continue
        try:
            paper = _paper_from_cache(item)
        except (TypeError, ValueError):
            continue
        if paper.title:
            papers.append(paper)
    return papers


def _retry_delay(response: requests.Response | None, fallback: int) -> int:
    if response is not None:
        retry_after = str(response.headers.get("Retry-After", "")).strip()
        if retry_after.isdigit():
            return max(3, int(retry_after))
    return max(3, fallback)


def _request_arxiv(params: dict, headers: dict, timeout: int, retry_delays: list[int]) -> requests.Response:
    attempts = len(retry_delays) + 1
    last_error: Exception | None = None

    for attempt in range(attempts):
        response: requests.Response | None = None
        try:
            response = requests.get(
                ARXIV_API,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            if response.status_code not in RETRYABLE_STATUS_CODES:
                response.raise_for_status()
                return response
            last_error = requests.HTTPError(
                f"HTTP {response.status_code} from arXiv",
                response=response,
            )
        except requests.RequestException as exc:
            last_error = exc

        if attempt >= len(retry_delays):
            assert last_error is not None
            raise last_error

        delay = _retry_delay(response, retry_delays[attempt])
        if response is not None:
            reason = f"HTTP {response.status_code}"
        else:
            reason = type(last_error).__name__ if last_error is not None else "request error"
        print(
            f"arxiv: {reason}; retrying in {delay}s "
            f"({attempt + 1}/{len(retry_delays)})"
        )
        time.sleep(delay)

    assert last_error is not None
    raise last_error


def _parse_feed(text: str) -> list[Paper]:
    feed = feedparser.parse(text)
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
            publication_types=["Preprint"],
        ))
    return papers


def fetch_arxiv(
    config: dict,
    start_date: str,
    end_date: str,
    limit: int = 150,
) -> list[Paper]:
    terms = config.get("discovery_terms", [])
    arxiv_config = config.get("arxiv", {}) or {}
    categories = arxiv_config.get("categories", [])
    if not terms:
        return []

    # arXiv recommends caching identical legacy-API queries because the result set
    # updates on a daily cycle. The persisted PaperDaily source cache is committed
    # between hosted runs, so the evening run can reuse the morning result.
    if bool(arxiv_config.get("reuse_same_window", True)):
        cached = _read_same_window_cache(start_date, end_date)
        if cached is not None:
            print(f"arxiv: reusing {len(cached)} cached records for the current retrieval window")
            return cached

    term_query = " OR ".join(f'all:"{term}"' for term in terms)
    query_parts = [f"({term_query})"]
    if categories:
        category_query = " OR ".join(f"cat:{category}" for category in categories)
        query_parts.append(f"({category_query})")

    start_stamp = start_date.replace("-", "") + "0000"
    end_stamp = end_date.replace("-", "") + "2359"
    query_parts.append(f"submittedDate:[{start_stamp} TO {end_stamp}]")
    search_query = " AND ".join(query_parts)

    contact = str(arxiv_config.get("contact_email") or config.get("pubmed", {}).get("email") or "").strip()
    user_agent = f"PaperDaily/{PAPERDAILY_VERSION} (+https://github.com/BryanWang0702/paperdaily)"
    if contact:
        user_agent = f"PaperDaily/{PAPERDAILY_VERSION} ({contact}; +https://github.com/BryanWang0702/paperdaily)"

    configured_delays = arxiv_config.get("retry_delays_seconds", DEFAULT_RETRY_DELAYS)
    retry_delays: list[int] = []
    if isinstance(configured_delays, list):
        for value in configured_delays:
            try:
                retry_delays.append(max(3, int(value)))
            except (TypeError, ValueError):
                continue
    if not retry_delays:
        retry_delays = DEFAULT_RETRY_DELAYS

    response = _request_arxiv(
        params={
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        },
        headers={"User-Agent": user_agent},
        timeout=int(arxiv_config.get("timeout_seconds", 45) or 45),
        retry_delays=retry_delays,
    )
    return _parse_feed(response.text)
