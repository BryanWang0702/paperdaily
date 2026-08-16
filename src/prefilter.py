from __future__ import annotations

from .models import Paper


TITLE_MULTIPLIER = 3

DEFAULT_WEIGHTS: dict[str, int] = {
    "sleep homeostasis": 14,
    "sleep deprivation": 14,
    "nrem": 14,
    "non-rapid eye movement": 14,
    "sleep rebound": 13,
    "recovery sleep": 13,
    "sleep pressure": 12,
    "process s": 12,
    "slow wave activity": 12,
    "slow-wave activity": 12,
    "rem sleep": 10,
    "delta power": 10,
    "slow wave": 9,
    "slow-wave": 9,
    "sleep staging": 10,
    "sleep scoring": 10,
    "sleep state": 9,
    "vigilance state": 9,
    "circadian": 8,
    "electroencephalography": 8,
    "eeg": 7,
    "theta": 6,
    "sigma": 6,
    "spindle": 6,
    "fragmentation": 6,
    "environmental enrichment": 9,
    "mouse": 4,
    "mice": 4,
    "rat": 4,
    "rodent": 4,
    "animal": 2,
    "computational": 3,
    "modeling": 3,
    "modelling": 3,
}

SLEEP_ANCHORS = (
    "sleep",
    "nrem",
    "rem sleep",
    "non-rapid eye movement",
    "slow wave activity",
    "slow-wave activity",
    "sleep state",
    "vigilance state",
)


def _term_score(text: str, weights: dict[str, int]) -> int:
    haystack = text.casefold()
    return sum(weight for term, weight in weights.items() if term.casefold() in haystack)


def relevance_score(paper: Paper, weights: dict[str, int] | None = None) -> int:
    weights = weights or DEFAULT_WEIGHTS
    title_score = _term_score(paper.title or "", weights)
    abstract_score = _term_score(paper.abstract or "", weights)
    category_score = _term_score(" ".join(paper.categories), weights)
    score = TITLE_MULTIPLIER * title_score + abstract_score + category_score

    combined = f"{paper.title} {paper.abstract}".casefold()
    has_sleep_anchor = any(anchor in combined for anchor in SLEEP_ANCHORS)
    if not has_sleep_anchor:
        score -= 18

    # Prefer papers that connect EEG/neural signals to sleep rather than generic EEG studies.
    if ("eeg" in combined or "electroencephal" in combined) and has_sleep_anchor:
        score += 6
    if any(x in combined for x in ("mouse", "mice", "rat", "rodent")) and has_sleep_anchor:
        score += 4
    return score


def prefilter_papers(papers: list[Paper], config: dict) -> list[Paper]:
    cfg = config.get("prefilter", {}) or {}
    enabled = bool(cfg.get("enabled", True))
    if not enabled:
        return papers

    max_candidates = max(1, int(cfg.get("max_candidates", 40)))
    min_score = int(cfg.get("min_score", 8))

    scored: list[tuple[Paper, int]] = []
    for paper in papers:
        score = relevance_score(paper)
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
