from __future__ import annotations

import time

import requests

from .models import Paper
from .utils import compact_text, matches_terms, normalize_doi


API_ROOT = "https://api.biorxiv.org/details"


def _get_json_with_retry(url: str, attempts: int = 3) -> dict:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, timeout=(10, 45))
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    assert last_error is not None
    raise last_error


def _fetch_server(
    server: str,
    start_date: str,
    end_date: str,
    limit: int,
    terms: list[str],
) -> list[Paper]:
    papers: list[Paper] = []
    cursor = 0

    while len(papers) < limit:
        url = f"{API_ROOT}/{server}/{start_date}/{end_date}/{cursor}"
        payload = _get_json_with_retry(url)
        collection = payload.get("collection", [])
        if not collection:
            break

        for item in collection:
            title = compact_text(item.get("title", ""))
            abstract = compact_text(item.get("abstract", ""))
            category = compact_text(item.get("category", ""))
            if terms and not matches_terms(f"{title} {abstract} {category}", terms):
                continue

            doi = normalize_doi(item.get("doi", ""))
            authors_raw = item.get("authors", "") or ""
            authors = [x.strip() for x in authors_raw.replace(";", ",").split(",") if x.strip()]
            papers.append(Paper(
                source=server,
                source_id=doi or f"{server}:{item.get('date', '')}:{title}",
                title=title,
                abstract=abstract,
                authors=authors,
                published_date=item.get("date", "") or "",
                indexed_date=item.get("date", "") or "",
                journal=server,
                doi=doi,
                url=f"https://doi.org/{doi}" if doi else "",
                categories=[category] if category else [],
                publication_types=["Preprint"],
                extra={"version": item.get("version", ""), "published": item.get("published", "")},
            ))
            if len(papers) >= limit:
                break

        messages = payload.get("messages", [])
        total = 0
        if messages:
            try:
                total = int(messages[0].get("total", 0))
            except (TypeError, ValueError):
                total = 0
        cursor += len(collection)
        if not total or cursor >= total:
            break

    return papers


def fetch_biorxiv(config: dict, start_date: str, end_date: str, limit: int = 150) -> list[Paper]:
    return _fetch_server("biorxiv", start_date, end_date, limit, config.get("discovery_terms", []))


def fetch_medrxiv(config: dict, start_date: str, end_date: str, limit: int = 150) -> list[Paper]:
    return _fetch_server("medrxiv", start_date, end_date, limit, config.get("discovery_terms", []))
