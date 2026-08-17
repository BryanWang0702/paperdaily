from __future__ import annotations

import json
import time
from pathlib import Path

import feedparser
import requests

from .models import Paper
from .utils import compact_text, normalize_doi


ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_QUERY_CACHE = Path("data/source_cache/arxiv_query.json")
DEFAULT_RETRY_DELAYS = [10, 30]
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _read_query_cache(start_date: str, end_date: str) -> str:
    try:
        payload = json.loads(ARXIV_QUERY_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    window = payload.get("window") or {}
    if window.get("start") != start_date or window.get("end") != end_date:
        return ""
    return str(payload.get("response_text") or "")


def _write_query_cache(start_date: str, end_date: str, response_text: str) -> None:
    ARXIV_QUERY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "window": {"start": start_date, "end": end_date},
        "response_text": response_text,
    }
    ARXIV_QUERY_CACHE.write_text(json.dumps(payload), encoding="utf-8")


def _retry_delay(response: requests.Response, fallback: int) -> int:
    retry_after = str(response.headers.get("Retry-After", "")).strip()
    if retry_after.isdigit():
        return max(3, int(retry_after))
    return max(3, fallback)


def _request_arxiv(params: dict, headers: dict, timeout: int, retry_delays: list[int]) -> requests.Response:
    attempts = len(retry_delays) + 1
    last_response: requests.Response | None = None
    for attempt in range(attempts):
        response = requests.get(
            ARXIV_API,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        last_response = response
        if response.status_code not in RETRYABLE_STATUS_CODES:
            response.raise_for_status()
            return response
        if attempt >= len(retry_delays):
            response.raise_for_status()
        delay = _retry_delay(response, retry_delays[attempt])
        print(
            f"arxiv: HTTP {response.status_code}; retrying in {delay}s "
            f"({attempt + 1}/{len(retry_delays)})"
        )
        time.sleep(delay)

    assert last_response is not None
    last_response.raise_for_status()
    return last_response


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

    # arXiv explicitly recommends caching identical queries because the legacy API
    # result set updates on a daily cycle. The morning and evening PaperDaily runs
    # therefore share the same successful response for a given date window.
    if bool(arxiv_config.get("reuse_same_window", True)):
        cached_text = _read_query_cache(start_date, end_date)
        if cached_text:
            print("arxiv: reusing cached response for the current retrieval window")
            return _parse_feed(cached_text)

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
    user_agent = "PaperDaily/0.5.1 (+https://github.com/BryanWang0702/paperdaily)"
    if contact:
        user_agent = f"PaperDaily/0.5.1 ({contact}; +https://github.com/BryanWang0702/paperdaily)"

    configured_delays = arxiv_config.get("retry_delays_seconds", DEFAULT_RETRY_DELAYS)
    retry_delays = []
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

    if bool(arxiv_config.get("reuse_same_window", True)):
        _write_query_cache(start_date, end_date, response.text)
    return _parse_feed(response.text)
