from __future__ import annotations

from typing import Any

from .models import Paper


DEFAULT_TITLE_MULTIPLIER = 3
DEFAULT_MISSING_ANCHOR_PENALTY = 0


def _term_score(text: str, weights: dict[str, int]) -> int:
    haystack = text.casefold()
    return sum(weight for term, weight in weights.items() if term.casefold() in haystack)


def _normalize_weights(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    weights: dict[str, int] = {}
    for term, value in raw.items():
        try:
            weights[str(term)] = int(value)
        except (TypeError, ValueError):
            continue
    return weights


def _has_anchor(text: str, anchors: list[str]) -> bool:
    if not anchors:
        return True
    haystack = text.casefold()
    return any(str(anchor).casefold() in haystack for anchor in anchors if str(anchor).strip())


def _boost_score(text: str, boosts: list[dict], has_anchor: bool) -> int:
    haystack = text.casefold()
    total = 0
    for boost in boosts:
        if not isinstance(boost, dict):
            continue
        if bool(boost.get("require_anchor", False)) and not has_anchor:
            continue
        terms = boost.get("any_terms", []) or []
        if not isinstance(terms, list):
            continue
        if any(str(term).casefold() in haystack for term in terms if str(term).strip()):
            try:
                total += int(boost.get("bonus", 0))
            except (TypeError, ValueError):
                continue
    return total


def relevance_score(paper: Paper, prefilter_config: dict | None = None) -> int:
    """Compute the deterministic prefilter score from configuration only.

    This layer is intentionally cheap and transparent. Domain-specific terms,
    anchors, penalties, and boosts live in config.yaml so forks can adapt the
    project without editing Python source code.
    """
    cfg = prefilter_config or {}
    weights = _normalize_weights(cfg.get("weights", {}))
    title_multiplier = int(cfg.get("title_multiplier", DEFAULT_TITLE_MULTIPLIER))
    missing_anchor_penalty = int(cfg.get("missing_anchor_penalty", DEFAULT_MISSING_ANCHOR_PENALTY))
    anchors = [str(value) for value in (cfg.get("anchors", []) or [])]
    boosts = cfg.get("boosts", []) or []
    if not isinstance(boosts, list):
        boosts = []

    title_score = _term_score(paper.title or "", weights)
    abstract_score = _term_score(paper.abstract or "", weights)
    category_score = _term_score(" ".join(paper.categories), weights)
    score = title_multiplier * title_score + abstract_score + category_score

    combined = f"{paper.title} {paper.abstract} {' '.join(paper.categories)}"
    has_anchor = _has_anchor(combined, anchors)
    if anchors and not has_anchor:
        score -= missing_anchor_penalty

    score += _boost_score(combined, boosts, has_anchor)
    return score


def prefilter_papers(papers: list[Paper], config: dict) -> list[Paper]:
    cfg = config.get("prefilter", {}) or {}
    enabled = bool(cfg.get("enabled", True))
    if not enabled:
        return papers

    max_candidates = max(1, int(cfg.get("max_candidates", 40)))
    min_score = int(cfg.get("min_score", 0))

    scored: list[tuple[Paper, int]] = []
    for paper in papers:
        score = relevance_score(paper, cfg)
        paper.extra["prefilter_score"] = score
        if score >= min_score:
            scored.append((paper, score))

    scored.sort(
        key=lambda pair: (
            pair[1],
            pair[0].indexed_date or pair[0].published_date,
            pair[0].title,
        ),
        reverse=True,
    )
    return [paper for paper, _score in scored[:max_candidates]]
