from __future__ import annotations

import requests

from .models import Paper
from .utils import compact_text, normalize_doi


API_ROOT = "https://api.biorxiv.org/details"


def _fetch_server(server: str, start_date: str, end_date: str, limit: int) -> list[Paper]:
    papers: list[Paper] = []
    cursor = 0

    while len(papers) < limit:
        url = f"{API_ROOT}/{server}/{start_date}/{end_date}/{cursor}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json()
        collection = payload.get("collection", [])
        if not collection:
            break

        for item in collection:
            doi = normalize_doi(item.get("doi", ""))
            title = compact_text(item.get("title", ""))
            authors_raw = item.get("authors", "") or ""
            authors = [x.strip() for x in authors_raw.replace(";", ",").split(",") if x.strip()]
            papers.append(Paper(
                source=server,
                source_id=doi or f"{server}:{item.get('date', '')}:{title}",
                title=title,
                abstract=compact_text(item.get("abstract", "")),
                authors=authors,
                published_date=item.get("date", "") or "",
                indexed_date=item.get("date", "") or "",
                journal=server,
                doi=doi,
                url=f"https://doi.org/{doi}" if doi else "",
                categories=[item.get("category", "")] if item.get("category") else [],
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


def fetch_biorxiv(start_date: str, end_date: str, limit: int = 150) -> list[Paper]:
    return _fetch_server("biorxiv", start_date, end_date, limit)


def fetch_medrxiv(start_date: str, end_date: str, limit: int = 150) -> list[Paper]:
    return _fetch_server("medrxiv", start_date, end_date, limit)
