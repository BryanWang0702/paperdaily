from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .billing import add_usage, empty_usage
from .multi_topic_pipeline import run as core_run
from .site_settings import write_site_settings
from .topics import load_topic_profiles
from .utils import load_config


DATA_DIR = Path("data")
LEDGER_PATH = DATA_DIR / "billing_ledger.json"
SITE_ARCHIVE_PATH = Path("site/data/archive.json")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any], *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")


def _bootstrap_ledger() -> dict[str, Any]:
    total_cost = 0.0
    total_usage = empty_usage()
    for path in sorted(DATA_DIR.glob("20??-??-??.json")):
        payload = _read_json(path)
        billing = ((payload.get("ai") or {}).get("billing") or {})
        if not billing:
            continue
        total_cost += float(billing.get("daily_cost_cny", 0.0) or 0.0)
        total_usage = add_usage(total_usage, billing.get("daily_usage", {}) or {})
    return {
        "version": 1,
        "total_cost_cny": round(total_cost, 6),
        "total_usage": total_usage,
        "run_count": 0,
        "recent_runs": [],
    }


def _load_ledger() -> dict[str, Any]:
    payload = _read_json(LEDGER_PATH)
    return payload if payload else _bootstrap_ledger()


def _planned_runs_per_day(config: dict[str, Any]) -> int:
    values = ((config.get("local") or {}).get("refresh_times") or ["05:30", "20:30"])
    if not isinstance(values, list):
        return 2
    valid = {str(value).strip() for value in values if ":" in str(value)}
    return max(1, len(valid))


def _expected_requests_per_full_run(config: dict[str, Any]) -> int:
    profiles, _ = load_topic_profiles(config)
    total = 0
    for profile in profiles:
        ai = (profile.get("config") or {}).get("ai", {}) or {}
        analyzed = max(1, int(ai.get("max_analyzed", 40) or 40))
        rank_batch = max(1, int(ai.get("rank_batch_size", 20) or 20))
        summary_batch = max(1, int(ai.get("summary_batch_size", 5) or 5))
        total += math.ceil(analyzed / rank_batch) + math.ceil(analyzed / summary_batch)
    return max(1, total)


def _historical_reference_cost(ledger: dict[str, Any], config: dict[str, Any]) -> float:
    total_cost = float(ledger.get("total_cost_cny", 0.0) or 0.0)
    total_requests = int(((ledger.get("total_usage") or {}).get("requests", 0)) or 0)
    if total_cost <= 0 or total_requests <= 0:
        return 0.0
    expected_requests = _expected_requests_per_full_run(config)
    equivalent_runs = max(1.0, total_requests / expected_requests)
    return total_cost / equivalent_runs


def _has_ai_requests(item: dict[str, Any]) -> bool:
    return int(((item.get("usage") or {}).get("requests", 0)) or 0) > 0


def _reference_run_cost(recent_runs: list[dict[str, Any]], fallback: float = 0.0) -> float:
    # Fully cached scheduled refreshes are valid production runs, but a ¥0 run with
    # zero AI requests should not define the representative cost of a future full
    # refresh. Use scheduled runs that actually called the AI; otherwise fall back
    # to other non-development active runs, then to the historical bootstrap.
    scheduled = [
        float(item.get("cost_cny", 0.0) or 0.0)
        for item in recent_runs
        if str(item.get("kind", "")) in {"scheduled", "local_scheduled"}
        and _has_ai_requests(item)
    ]
    if scheduled:
        values = scheduled[-20:]
    else:
        active = [
            float(item.get("cost_cny", 0.0) or 0.0)
            for item in recent_runs
            if str(item.get("kind", "")) != "development"
            and _has_ai_requests(item)
        ]
        values = active[-20:]
    if not values:
        return max(0.0, float(fallback or 0.0))
    return sum(values) / len(values)


def _update_billing_ledger(
    ledger: dict[str, Any], result: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    billing = ((result.get("ai") or {}).get("billing") or {})
    usage = billing.get("run_usage", {}) or {}
    run_cost = float(billing.get("run_cost_cny", 0.0) or 0.0)
    run_kind = str(os.getenv("PAPERDAILY_RUN_KIND", "unspecified") or "unspecified")
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "kind": run_kind,
        "cost_cny": round(run_cost, 6),
        "usage": usage,
    }

    recent_runs = list(ledger.get("recent_runs", []) or [])
    recent_runs.append(record)
    recent_runs = recent_runs[-100:]
    total_cost = float(ledger.get("total_cost_cny", 0.0) or 0.0) + run_cost
    total_usage = add_usage(ledger.get("total_usage", {}) or {}, usage)
    run_count = int(ledger.get("run_count", 0) or 0) + 1
    provisional = {
        "total_cost_cny": total_cost,
        "total_usage": total_usage,
    }
    bootstrap_reference = _historical_reference_cost(provisional, config)
    average_run_cost = _reference_run_cost(recent_runs, bootstrap_reference)
    runs_per_day = _planned_runs_per_day(config)

    updated = {
        "version": 1,
        "updated_at": record["at"],
        "total_cost_cny": round(total_cost, 6),
        "total_usage": total_usage,
        "run_count": run_count,
        "last_run_cost_cny": round(run_cost, 6),
        "last_run_kind": run_kind,
        "average_run_cost_cny": round(average_run_cost, 6),
        "planned_runs_per_day": runs_per_day,
        "annual_estimate_cny": round(average_run_cost * runs_per_day * 365, 2),
        "recent_runs": recent_runs,
    }
    _write_json(LEDGER_PATH, updated)
    return updated


def _public_billing(ledger: dict[str, Any]) -> dict[str, Any]:
    return {
        "currency": "CNY",
        "last_run_cost_cny": float(ledger.get("last_run_cost_cny", 0.0) or 0.0),
        "total_cost_cny": float(ledger.get("total_cost_cny", 0.0) or 0.0),
        "average_run_cost_cny": float(ledger.get("average_run_cost_cny", 0.0) or 0.0),
        "annual_estimate_cny": float(ledger.get("annual_estimate_cny", 0.0) or 0.0),
        "planned_runs_per_day": int(ledger.get("planned_runs_per_day", 2) or 2),
        "run_count": int(ledger.get("run_count", 0) or 0),
    }


def _patch_public_archives(ledger: dict[str, Any]) -> None:
    billing = _public_billing(ledger)
    paths = [SITE_ARCHIVE_PATH, *Path("site/data/topics").glob("*/archive.json")]
    for path in paths:
        archive = _read_json(path)
        if not archive:
            continue
        archive["billing"] = billing
        _write_json(path, archive, compact=True)


def run(days: int | None = None) -> dict[str, Any]:
    config = load_config()
    ledger = _load_ledger()
    result = core_run(days)
    updated = _update_billing_ledger(ledger, result, config)
    write_site_settings(config)
    _patch_public_archives(updated)
    result["billing_ledger"] = _public_billing(updated)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PaperDaily with runtime accounting and site settings")
    parser.add_argument("--days", type=int, default=None, help="Override lookback window")
    args = parser.parse_args()
    result = run(args.days)
    print(f"shared raw unique: {result.get('raw_count', 0)}")
    topic_results = result.get("topic_results", {}) or {}
    for topic_id, topic in topic_results.items():
        print(
            f"topic {topic_id}:",
            f"matching {topic.get('raw_count', 0)}",
            f"prefiltered {topic.get('prefiltered_count', 0)}",
            f"AI analyzed {topic.get('analyzed_count', 0)}",
        )
    print("AI:", (result.get("ai") or {}).get("status", "unknown"))
    billing = result.get("billing_ledger", {}) or {}
    if billing:
        print(
            "Billing:",
            f"last run ¥{billing.get('last_run_cost_cny', 0):.6f}",
            f"total ¥{billing.get('total_cost_cny', 0):.6f}",
            f"annual ~¥{billing.get('annual_estimate_cny', 0):.2f}",
        )


if __name__ == "__main__":
    main()
