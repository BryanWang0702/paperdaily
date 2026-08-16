from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .ai_rank import apply_ai_ranking
from .billing import add_usage
from .deduplicate import deduplicate
from .fetch_arxiv import fetch_arxiv
from .fetch_biorxiv import fetch_biorxiv, fetch_medrxiv
from .fetch_pubmed import fetch_pubmed
from .models import Paper
from .prefilter import prefilter_papers
from .utils import date_window, load_config, local_date


DATA_DIR = Path("data")
SITE_DATA_DIR = Path("site/data")
SOURCE_CACHE_DIR = DATA_DIR / "source_cache"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_compact_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _paper_from_dict(item: dict) -> Paper:
    return Paper(
        source=str(item.get("source", "")),
        source_id=str(item.get("source_id", "")),
        title=str(item.get("title", "")),
        abstract=str(item.get("abstract", "")),
        authors=[str(x) for x in (item.get("authors") or [])],
        published_date=str(item.get("published_date", "")),
        indexed_date=str(item.get("indexed_date", "")),
        journal=str(item.get("journal", "")),
        doi=str(item.get("doi", "")),
        url=str(item.get("url", "")),
        categories=[str(x) for x in (item.get("categories") or [])],
        keywords=[str(x) for x in (item.get("keywords") or [])],
        publication_types=[str(x) for x in (item.get("publication_types") or [])],
        extra=dict(item.get("extra") or {}),
    )


def _save_source_cache(name: str, papers: list[Paper], start_date: str, end_date: str) -> None:
    _write_json(
        SOURCE_CACHE_DIR / f"{name}.json",
        {
            "source": name,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "window": {"start": start_date, "end": end_date},
            "count": len(papers),
            "papers": [paper.to_dict() for paper in papers],
        },
    )


def _load_source_cache(name: str, max_age_days: int = 7) -> list[Paper]:
    payload = _read_json(SOURCE_CACHE_DIR / f"{name}.json")
    if not payload:
        return []
    fetched_at = str(payload.get("fetched_at", ""))
    try:
        stamp = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - stamp > timedelta(days=max_age_days):
            return []
    except ValueError:
        return []

    papers: list[Paper] = []
    for item in payload.get("papers", []) or []:
        if not isinstance(item, dict):
            continue
        try:
            paper = _paper_from_dict(item)
        except (TypeError, ValueError):
            continue
        if paper.title:
            papers.append(paper)
    return papers


def _attach_daily_billing(current_day: str, ai_meta: dict) -> dict:
    previous = _read_json(DATA_DIR / f"{current_day}.json")
    previous_billing = ((previous.get("ai") or {}).get("billing") or {})

    run_usage = ai_meta.get("usage", {}) or {}
    run_cost = float(ai_meta.get("run_cost_cny", 0.0) or 0.0)
    previous_usage = previous_billing.get("daily_usage", {}) or {}
    previous_cost = float(previous_billing.get("daily_cost_cny", 0.0) or 0.0)

    ai_meta["billing"] = {
        "currency": "CNY",
        "run_usage": run_usage,
        "run_cost_cny": round(run_cost, 6),
        "daily_usage": add_usage(previous_usage, run_usage),
        "daily_cost_cny": round(previous_cost + run_cost, 6),
        "pricing_cny_per_million": ai_meta.get("pricing_cny_per_million", {}),
    }
    return ai_meta


def _top_titles(payload: dict, limit: int = 5) -> list[str]:
    papers = payload.get("papers", []) or []
    digest_papers = [
        p for p in papers
        if (((p.get("extra") or {}).get("ai") or {}).get("digest_pick"))
    ]
    preview = digest_papers or papers
    return [str(p.get("title", "")).strip() for p in preview[:limit] if p.get("title")]


def _parse_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _paper_identity(paper: dict) -> str:
    doi = str(paper.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    source = str(paper.get("source") or "").strip().lower()
    source_id = str(paper.get("source_id") or "").strip().lower()
    if source and source_id:
        return f"{source}:{source_id}"
    url = str(paper.get("url") or "").strip().lower()
    if url:
        return f"url:{url}"
    return f"title:{str(paper.get('title') or '').strip().lower()}"


def _period_top(day_payloads: list[dict], period_days: int, limit: int = 5) -> list[dict]:
    dated_payloads = [
        (parsed, payload)
        for payload in day_payloads
        if (parsed := _parse_date(payload.get("date"))) is not None
    ]
    if not dated_payloads:
        return []

    latest_day = max(parsed for parsed, _ in dated_payloads)
    cutoff = latest_day - timedelta(days=period_days - 1)
    best: dict[str, dict] = {}

    for day_value, payload in dated_payloads:
        if day_value < cutoff:
            continue
        for paper in payload.get("papers", []) or []:
            ai = ((paper.get("extra") or {}).get("ai") or {})
            if "score" not in ai:
                continue
            try:
                score = int(ai.get("score", 0))
            except (TypeError, ValueError):
                continue
            title = str(paper.get("title") or "").strip()
            url = str(paper.get("url") or "").strip()
            if not title or not url:
                continue
            candidate = {
                "title": title,
                "url": url,
                "score": max(0, min(100, score)),
                "date": day_value.isoformat(),
                "source": str(paper.get("source") or ""),
            }
            key = _paper_identity(paper)
            previous = best.get(key)
            if previous is None or (candidate["score"], candidate["date"]) > (previous["score"], previous["date"]):
                best[key] = candidate

    ranked = sorted(
        best.values(),
        key=lambda item: (item["score"], item["date"], item["title"].lower()),
        reverse=True,
    )
    return ranked[:limit]


def _build_archive_manifest() -> dict:
    days: list[dict] = []
    tracked_costs: list[float] = []
    day_payloads: list[dict] = []

    for path in sorted(DATA_DIR.glob("20??-??-??.json"), reverse=True):
        payload = _read_json(path)
        if not payload:
            continue
        day_payloads.append(payload)
        ai = payload.get("ai", {}) or {}
        billing = ai.get("billing", {}) or {}
        has_billing = bool(billing)
        day_cost = float(billing.get("daily_cost_cny", 0.0) or 0.0)
        if has_billing:
            tracked_costs.append(day_cost)

        ranked_count = int(ai.get("ranked_count", payload.get("analyzed_count", payload.get("count", 0))) or 0)
        featured_count = min(
            int(payload.get("featured_count", 25) or 25),
            ranked_count,
        )
        additional_count = max(0, ranked_count - featured_count)
        days.append({
            "date": payload.get("date") or path.stem,
            "generated_at": payload.get("generated_at", ""),
            "total_count": payload.get("raw_count", payload.get("count", 0)),
            "ranked_count": ranked_count,
            "featured_count": featured_count,
            "additional_count": additional_count,
            "top_titles": _top_titles(payload),
            "retrieved_source_counts": payload.get("retrieved_source_counts", payload.get("raw_source_counts", {})),
            "errors": payload.get("errors", {}),
            "window": payload.get("window", {}),
            "ai": {
                "enabled": ai.get("enabled", False),
                "provider": ai.get("provider", ""),
                "model": ai.get("model", ""),
                "status": ai.get("status", ""),
                "daily_cost_cny": day_cost if has_billing else None,
                "daily_usage": billing.get("daily_usage", {}) if has_billing else {},
            },
        })

    tracked_days = len(tracked_costs)
    total_cost = round(sum(tracked_costs), 6)
    average_daily = total_cost / tracked_days if tracked_days else 0.0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "rankings": {
            "monthly": {
                "label": "Past 30 days",
                "papers": _period_top(day_payloads, 30, 5),
            },
        },
        "billing": {
            "currency": "CNY",
            "tracked_days": tracked_days,
            "total_cost_cny": total_cost,
            "average_daily_cost_cny": round(average_daily, 6),
            "monthly_estimate_cny": round(average_daily * 30, 2),
            "annual_estimate_cny": round(average_daily * 365, 2),
        },
    }


def _fallback_paper_type(paper: Paper) -> str:
    joined = " ".join(paper.publication_types).casefold()
    if "meta-analysis" in joined:
        return "Meta-analysis"
    if "systematic review" in joined:
        return "Systematic Review"
    if "review" in joined:
        return "Review"
    if "clinical trial" in joined or "randomized controlled trial" in joined:
        return "Clinical Trial"
    if "case report" in joined:
        return "Case Report"
    if "protocol" in joined:
        return "Protocol"
    if "editorial" in joined:
        return "Editorial"
    if "comment" in joined:
        return "Commentary/Perspective"
    if "journal article" in joined:
        return "Research Article"
    if "preprint" in joined:
        return "Preprint"
    return "Other"


def _public_paper(paper: Paper) -> dict:
    ai = (paper.extra.get("ai") or {}) if paper.extra else {}
    keywords = ai.get("keywords") or paper.keywords
    return {
        "title": paper.title,
        "url": paper.url,
        "source": paper.source,
        "journal": paper.journal,
        "authors": paper.authors,
        "paper_type": str(ai.get("paper_type") or _fallback_paper_type(paper)),
        "keywords": [str(value) for value in (keywords or [])][:5],
        "score": int(ai.get("score", 0)) if ai else None,
        "summary": str(ai.get("summary", "")) if ai else "",
    }


def _build_site_digest(payload: dict, papers: list[Paper]) -> dict:
    selected: list[dict] = []
    for paper in papers:
        ai = (paper.extra.get("ai") or {}) if paper.extra else {}
        if payload.get("ai", {}).get("enabled") and not ai.get("digest_pick"):
            continue
        selected.append(_public_paper(paper))

    if not selected:
        selected = [_public_paper(paper) for paper in papers]

    ai = payload.get("ai", {}) or {}
    billing = ai.get("billing", {}) or {}
    featured_count = min(int(payload.get("featured_count", 25) or 25), len(selected))
    site_ai = {
        "enabled": ai.get("enabled", False),
        "provider": ai.get("provider", ""),
        "model": ai.get("model", ""),
        "status": ai.get("status", ""),
        "ranked_count": ai.get("ranked_count", 0),
        "summarized_count": len(selected),
        "errors": ai.get("errors", []),
        "billing": billing,
    }
    return {
        "date": payload.get("date"),
        "generated_at": payload.get("generated_at"),
        "window": payload.get("window", {}),
        "total_count": payload.get("raw_count", 0),
        "retrieved_source_counts": payload.get("retrieved_source_counts", payload.get("raw_source_counts", {})),
        "ranked_count": len(selected),
        "featured_count": featured_count,
        "additional_count": max(0, len(selected) - featured_count),
        "errors": payload.get("errors", {}),
        "ai": site_ai,
        "papers": selected,
    }


def _select_ai_papers(prefiltered: list[Paper], config: dict) -> tuple[list[Paper], int]:
    ai_config = config.get("ai", {}) or {}
    configured_limit = max(1, int(ai_config.get("max_analyzed", 40)))
    return prefiltered[:configured_limit], configured_limit


def _runtime_ai_config(config: dict, analyzed_count: int) -> dict:
    runtime = dict(config)
    runtime_ai = dict(config.get("ai", {}) or {})
    target = max(1, analyzed_count)
    runtime_ai["digest_min"] = target
    runtime_ai["digest_max"] = target
    runtime_ai["digest_score_threshold"] = 0
    runtime["ai"] = runtime_ai
    return runtime


def run(days: int | None = None) -> dict:
    config = load_config()
    timezone_name = str(config.get("timezone", "UTC"))
    current_day = local_date(timezone_name).isoformat()
    lookback_days = days or int(config.get("lookback_days", 3))
    start_date, end_date = date_window(lookback_days, timezone_name)
    limit = int(config.get("max_per_source", 150))
    featured_target = max(1, int((config.get("site", {}) or {}).get("featured_count", 25)))

    fetched: list[Paper] = []
    errors: dict[str, str] = {}
    retrieved_source_counts = {"pubmed": 0, "biorxiv": 0, "medrxiv": 0, "arxiv": 0}
    sources = [
        ("pubmed", lambda: fetch_pubmed(config, start_date, end_date, limit)),
        ("biorxiv", lambda: fetch_biorxiv(config, start_date, end_date, limit)),
        ("medrxiv", lambda: fetch_medrxiv(config, start_date, end_date, limit)),
        ("arxiv", lambda: fetch_arxiv(config, start_date, end_date, limit)),
    ]

    for name, loader in sources:
        try:
            items = loader()
            fetched.extend(items)
            retrieved_source_counts[name] = len(items)
            _save_source_cache(name, items, start_date, end_date)
            print(f"{name}: {len(items)} records")
        except Exception as exc:
            cached = _load_source_cache(name)
            if cached:
                fetched.extend(cached)
                retrieved_source_counts[name] = len(cached)
                errors[name] = f"{type(exc).__name__}: {exc} · reused {len(cached)} cached records"
                print(f"{name}: ERROR, reused {len(cached)} cached records")
            else:
                errors[name] = f"{type(exc).__name__}: {exc}"
                print(f"{name}: ERROR {errors[name]}")

    raw_unique = deduplicate(fetched)
    raw_unique.sort(key=lambda p: (p.indexed_date or p.published_date, p.title), reverse=True)
    raw_counts = Counter(p.source for p in raw_unique)

    prefiltered = prefilter_papers(raw_unique, config)
    analyzed, configured_ai_limit = _select_ai_papers(prefiltered, config)
    print(f"prefilter: {len(raw_unique)} -> {len(prefiltered)} candidates")
    print(f"AI selection: {len(prefiltered)} -> {len(analyzed)} papers (configured max {configured_ai_limit})")

    ai_runtime_config = _runtime_ai_config(config, len(analyzed))
    ai_meta = _attach_daily_billing(current_day, apply_ai_ranking(analyzed, ai_runtime_config))
    ai_meta["configured_max_analyzed"] = configured_ai_limit
    ai_meta["analyzed_count"] = len(analyzed)

    if ai_meta.get("ranked_count"):
        analyzed.sort(
            key=lambda p: (
                int((p.extra.get("ai") or {}).get("score", -1)),
                p.indexed_date or p.published_date,
                p.title,
            ),
            reverse=True,
        )

    counts = Counter(p.source for p in analyzed)
    payload = {
        "date": current_day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start": start_date, "end": end_date},
        "raw_count": len(raw_unique),
        "retrieved_source_counts": retrieved_source_counts,
        "raw_source_counts": dict(raw_counts),
        "prefiltered_count": len(prefiltered),
        "analyzed_count": len(analyzed),
        "configured_max_analyzed": configured_ai_limit,
        "count": len(analyzed),
        "featured_count": min(featured_target, len(analyzed)),
        "source_counts": dict(counts),
        "errors": errors,
        "ai": ai_meta,
        "papers": [p.to_dict() for p in analyzed],
    }

    DATA_DIR.mkdir(exist_ok=True)
    archive_path = DATA_DIR / f"{current_day}.json"
    latest_path = DATA_DIR / "latest.json"
    _write_json(archive_path, payload)
    _write_json(latest_path, payload)

    site_payload = _build_site_digest(payload, analyzed)
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _write_compact_json(SITE_DATA_DIR / "latest.json", site_payload)
    _write_compact_json(SITE_DATA_DIR / "days" / f"{current_day}.json", site_payload)
    _write_compact_json(SITE_DATA_DIR / "archive.json", _build_archive_manifest())
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch, filter, rank, and archive PaperDaily sources")
    parser.add_argument("--days", type=int, default=None, help="Override lookback window")
    args = parser.parse_args()
    result = run(args.days)
    print(f"raw unique: {result['raw_count']}")
    print(f"prefiltered candidates: {result['prefiltered_count']}")
    print(f"AI analyzed: {result['analyzed_count']}")
    print(f"summarized papers: {result.get('ai', {}).get('digest_count', 0)}")
    print("AI:", result.get("ai", {}).get("status", "unknown"))
    billing = (result.get("ai", {}).get("billing") or {})
    if billing:
        print(
            "AI billing:",
            f"run ¥{billing.get('run_cost_cny', 0):.6f}",
            f"today ¥{billing.get('daily_cost_cny', 0):.6f}",
            billing.get("run_usage", {}),
        )
    if result["errors"]:
        print("source errors:", result["errors"])


if __name__ == "__main__":
    main()
