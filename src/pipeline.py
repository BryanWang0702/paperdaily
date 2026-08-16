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
    if not digest_papers:
        digest_papers = [
            p for p in papers
            if (((p.get("extra") or {}).get("ai") or {}).get("top_pick"))
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


def _period_top(day_payloads: list[dict], period_days: int, limit: int = 10) -> list[dict]:
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
        digest_count = int(ai.get("digest_count", 0) or 0)
        if not digest_count:
            digest_count = min(int(payload.get("count", 0) or 0), 30)
        days.append({
            "date": payload.get("date") or path.stem,
            "generated_at": payload.get("generated_at", ""),
            "count": digest_count,
            "candidate_count": payload.get("count", 0),
            "raw_count": payload.get("raw_count", payload.get("count", 0)),
            "top_titles": _top_titles(payload),
            "errors": payload.get("errors", {}),
            "window": payload.get("window", {}),
            "ai": {
                "enabled": ai.get("enabled", False),
                "provider": ai.get("provider", ""),
                "model": ai.get("model", ""),
                "digest_count": digest_count,
                "ranked_count": ai.get("ranked_count", 0),
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
            "weekly": {
                "label": "Past 7 days",
                "papers": _period_top(day_payloads, 7, 10),
            },
            "monthly": {
                "label": "Past 30 days",
                "papers": _period_top(day_payloads, 30, 10),
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


def _build_site_digest(payload: dict, papers: list[Paper]) -> dict:
    selected: list[dict] = []
    for paper in papers:
        ai = (paper.extra.get("ai") or {}) if paper.extra else {}
        if payload.get("ai", {}).get("enabled") and not ai.get("digest_pick"):
            continue
        selected.append({
            "title": paper.title,
            "url": paper.url,
            "score": int(ai.get("score", 0)) if ai else None,
            "summary": str(ai.get("summary", "")) if ai else "",
        })

    if not selected:
        selected = [
            {"title": p.title, "url": p.url, "score": None, "summary": ""}
            for p in papers[:30]
        ]

    ai = payload.get("ai", {}) or {}
    billing = ai.get("billing", {}) or {}
    site_ai = {
        "enabled": ai.get("enabled", False),
        "provider": ai.get("provider", ""),
        "model": ai.get("model", ""),
        "status": ai.get("status", ""),
        "ranked_count": ai.get("ranked_count", 0),
        "digest_count": len(selected),
        "errors": ai.get("errors", []),
        "billing": billing,
    }
    return {
        "date": payload.get("date"),
        "generated_at": payload.get("generated_at"),
        "window": payload.get("window", {}),
        "raw_count": payload.get("raw_count", 0),
        "candidate_count": payload.get("count", 0),
        "count": len(selected),
        "errors": payload.get("errors", {}),
        "ai": site_ai,
        "papers": selected,
    }


def run(days: int | None = None) -> dict:
    config = load_config()
    timezone_name = str(config.get("timezone", "UTC"))
    current_day = local_date(timezone_name).isoformat()
    lookback_days = days or int(config.get("lookback_days", 3))
    start_date, end_date = date_window(lookback_days, timezone_name)
    limit = int(config.get("max_per_source", 150))

    fetched: list[Paper] = []
    errors: dict[str, str] = {}
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
            _save_source_cache(name, items, start_date, end_date)
            print(f"{name}: {len(items)} records")
        except Exception as exc:
            cached = _load_source_cache(name)
            if cached:
                fetched.extend(cached)
                errors[name] = f"{type(exc).__name__}: {exc} · reused {len(cached)} cached records"
                print(f"{name}: ERROR, reused {len(cached)} cached records")
            else:
                errors[name] = f"{type(exc).__name__}: {exc}"
                print(f"{name}: ERROR {errors[name]}")

    raw_unique = deduplicate(fetched)
    raw_unique.sort(key=lambda p: (p.indexed_date or p.published_date, p.title), reverse=True)
    raw_counts = Counter(p.source for p in raw_unique)

    unique = prefilter_papers(raw_unique, config)
    print(f"prefilter: {len(raw_unique)} -> {len(unique)} candidates")

    ai_meta = _attach_daily_billing(current_day, apply_ai_ranking(unique, config))
    if ai_meta.get("ranked_count"):
        unique.sort(
            key=lambda p: (
                int((p.extra.get("ai") or {}).get("score", -1)),
                p.indexed_date or p.published_date,
                p.title,
            ),
            reverse=True,
        )

    counts = Counter(p.source for p in unique)
    payload = {
        "date": current_day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start": start_date, "end": end_date},
        "raw_count": len(raw_unique),
        "raw_source_counts": dict(raw_counts),
        "count": len(unique),
        "source_counts": dict(counts),
        "errors": errors,
        "ai": ai_meta,
        "papers": [p.to_dict() for p in unique],
    }

    DATA_DIR.mkdir(exist_ok=True)
    archive_path = DATA_DIR / f"{current_day}.json"
    latest_path = DATA_DIR / "latest.json"
    _write_json(archive_path, payload)
    _write_json(latest_path, payload)

    site_payload = _build_site_digest(payload, unique)
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
    print(f"filtered candidates: {result['count']}")
    print(f"digest papers: {result.get('ai', {}).get('digest_count', 0)}")
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
