from __future__ import annotations

import hashlib
import re

from .models import Paper
from .utils import normalize_doi


NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _title_fingerprint(title: str) -> str:
    normalized = NON_ALNUM.sub(" ", title.lower()).strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def paper_key(paper: Paper) -> str:
    doi = normalize_doi(paper.doi)
    if doi:
        return f"doi:{doi}"
    if paper.source_id:
        return f"{paper.source}:{paper.source_id.lower()}"
    return f"title:{_title_fingerprint(paper.title)}"


def deduplicate(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    output: list[Paper] = []
    for paper in papers:
        key = paper_key(paper)
        if key in seen:
            continue
        seen.add(key)
        output.append(paper)
    return output
