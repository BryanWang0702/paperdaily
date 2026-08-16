from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import yaml


DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)


def load_config(path: str | Path = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    return DOI_PREFIX_RE.sub("", value.strip()).lower()


def date_window(days: int) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=max(days - 1, 0))
    return start.isoformat(), end.isoformat()


def compact_text(text: str | None) -> str:
    return " ".join((text or "").split())


def chunks(values: Iterable[str], size: int) -> Iterable[list[str]]:
    batch: list[str] = []
    for value in values:
        batch.append(value)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
