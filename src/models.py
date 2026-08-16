from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Paper:
    source: str
    source_id: str
    title: str
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    published_date: str = ""
    indexed_date: str = ""
    journal: str = ""
    doi: str = ""
    url: str = ""
    categories: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    publication_types: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
