from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


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


def _build_archive_manifest() -> dict:
    days: list[dict] = []
    tracked_costs: list[float] = []
    for path in sorted(DATA_DIR.glob("20??-??-??.json"), reverse=True):
        payload = _read_json(path)
        if not payload:
            continue
        ai = payload.get("ai", {}) or {}
        billing = ai.get("billing", {}) or {}
        has_billing = bool(billing)
        day_cost = float(billing.get("daily_cost_cny", 0.0) or 0.0)
        if has_billing:
            tracked_costs.append(day_cost)
        days.append({
            "date": payload.get("date") or path.stem,
            "generated_at": payload.get("generated_at", ""),
            "count": payload.get("count", 0),
            "raw_count": payload.get("raw_count", payload.get("count", 0)),
            "source_counts": payload.get("source_counts", {}),
            "errors": payload.get("errors", {}),
            "window": payload.get("window", {}),
            "ai": {
                "enabled": ai.get("enabled", False),
                "provider": ai.get("provider", ""),
                "model": ai.get("model", ""),
                "top_n": ai.get("top_n", 0),
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
        "billing": {
            "currency": "CNY",
            "tracked_days": tracked_days,
            "total_cost_cny": total_cost,
            "average_daily_cost_cny": round(average_daily, 6),
            "monthly_estimate_cny": round(average_daily * 30, 2),
            "annual_estimate_cny": round(average_daily * 365, 2),
        },
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
            print(f"{name}: {len(items)} records")
        except Exception as exc:  # keep other sources alive if one provider is down
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

    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(latest_path, SITE_DATA_DIR / "latest.json")
    _write_json(SITE_DATA_DIR / "archive.json", _build_archive_manifest())
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch, filter, rank, and archive PaperDaily sources")
    parser.add_argument("--days", type=int, default=None, help="Override lookback window")
    args = parser.parse_args()
    result = run(args.days)
    print(f"raw unique: {result['raw_count']}")
    print(f"filtered candidates: {result['count']}")
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
