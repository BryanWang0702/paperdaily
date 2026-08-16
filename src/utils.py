from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import yaml


DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)


def load_config(path: str | Path = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    return DOI_PREFIX_RE.sub("", value.strip()).lower()


def local_date(timezone_name: str = "UTC"):
    return datetime.now(ZoneInfo(timezone_name)).date()


def date_window(days: int, timezone_name: str = "UTC") -> tuple[str, str]:
    end = local_date(timezone_name)
    start = end - timedelta(days=max(days - 1, 0))
    return start.isoformat(), end.isoformat()


def compact_text(text: str | None) -> str:
    return " ".join((text or "").split())


def matches_terms(text: str, terms: Iterable[str]) -> bool:
    haystack = text.casefold()
    return any(term.casefold() in haystack for term in terms if term)


def chunks(values: Iterable[str], size: int) -> Iterable[list[str]]:
    batch: list[str] = []
    for value in values:
        batch.append(value)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
