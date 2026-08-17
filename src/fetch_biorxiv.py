from __future__ import annotations

import time

import requests

from .models import Paper
from .utils import compact_text, matches_terms, normalize_doi


API_ROOT = "https://api.biorxiv.org/details"


def _decode_json_response(response: requests.Response, url: str) -> dict:
    text = response.text.strip()
    if not text:
        raise RuntimeError(
            f"empty response body from bioRxiv API (HTTP {response.status_code}; {url})"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        content_type = str(response.headers.get("Content-Type", "unknown"))
        preview = compact_text(text[:120])
        raise RuntimeError(
            "invalid JSON response from bioRxiv API "
            f"(HTTP {response.status_code}; content-type {content_type}; body starts {preview!r})"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"unexpected JSON payload from bioRxiv API: {type(payload).__name__}"
        )
    return payload


def _get_json_with_retry(url: str, attempts: int = 3) -> dict:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, timeout=(10, 45))
            response.raise_for_status()
            return _decode_json_response(response, url)
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                delay = 2 ** attempt
                print(
                    f"bioRxiv API: {type(exc).__name__}; retrying in {delay}s "
                    f"({attempt + 1}/{attempts - 1})"
                )
                time.sleep(delay)
    assert last_error is not None
    raise last_error


def _parse_authors(value: object) -> list[str]:
    """Parse bioRxiv/medRxiv author strings without splitting surname initials.

    The API commonly separates authors with semicolons while individual names
    may themselves contain commas, for example ``Smith, J.; Jones, A. B.``.
    """
    raw = str(value or "").strip()
    if not raw:
        return []
    if ";" in raw:
        return [part.strip() for part in raw.split(";") if part.strip()]
    return [raw]


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
            # A valid JSON response with an empty collection is the normal
            # representation of "no records", not a source error.
            break

        for item in collection:
            title = compact_text(item.get("title", ""))
            abstract = compact_text(item.get("abstract", ""))
            category = compact_text(item.get("category", ""))
            if terms and not matches_terms(f"{title} {abstract} {category}", terms):
                continue

            doi = normalize_doi(item.get("doi", ""))
            authors = _parse_authors(item.get("authors", ""))
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
