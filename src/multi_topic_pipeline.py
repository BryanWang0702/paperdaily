from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .billing import add_usage, empty_usage
from .deduplicate import deduplicate
from .fetch_arxiv import fetch_arxiv
from .fetch_biorxiv import fetch_biorxiv, fetch_medrxiv
from .fetch_pubmed import fetch_pubmed
from .models import Paper
from .pipeline import (
    DATA_DIR,
    SITE_DATA_DIR,
    _build_site_digest,
    _load_source_cache,
    _period_top,
    _runtime_ai_config,
    _save_source_cache,
    _select_ai_papers,
    _top_titles,
    _write_compact_json,
    _write_json,
)
from .prefilter import prefilter_papers
from .topic_ai import apply_topic_ai_ranking
from .topics import build_shared_fetch_config, load_topic_profiles, topic_manifest
from .utils import date_window, load_config, local_date, matches_terms


TOPIC_DATA_DIR = DATA_DIR / "topics"
SITE_TOPIC_DATA_DIR = SITE_DATA_DIR / "topics"


def _topic_text(paper: Paper) -> str:
    return " ".join([
        paper.title,
        paper.abstract,
        paper.journal,
        " ".join(paper.categories),
        " ".join(paper.keywords),
    ])


def _topic_pool(papers: list[Paper], topic_config: dict[str, Any]) -> list[Paper]:
    terms = topic_config.get("discovery_terms", []) or []
    if not terms:
        return [deepcopy(paper) for paper in papers]
    return [deepcopy(paper) for paper in papers if matches_terms(_topic_text(paper), terms)]


def _attach_topic_daily_billing(topic_dir: Path, current_day: str, ai_meta: dict[str, Any]) -> dict[str, Any]:
    previous: dict[str, Any] = {}
    previous_path = topic_dir / f"{current_day}.json"
    try:
        import json
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}

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


def _topic_archive_manifest(topic_dir: Path) -> dict[str, Any]:
    days: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    for path in sorted(topic_dir.glob("20??-??-??.json"), reverse=True):
        try:
            import json
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not payload:
            continue
        payloads.append(payload)
        ai = payload.get("ai", {}) or {}
        ranked_count = int(ai.get("ranked_count", payload.get("analyzed_count", payload.get("count", 0))) or 0)
        featured_count = min(int(payload.get("featured_count", 25) or 25), ranked_count)
        days.append({
            "date": payload.get("date") or path.stem,
            "generated_at": payload.get("generated_at", ""),
            "total_count": payload.get("raw_count", payload.get("count", 0)),
            "ranked_count": ranked_count,
            "featured_count": featured_count,
            "additional_count": max(0, ranked_count - featured_count),
            "top_titles": _top_titles(payload),
            "retrieved_source_counts": payload.get("retrieved_source_counts", {}),
            "topic_source_counts": payload.get("raw_source_counts", {}),
            "errors": payload.get("errors", {}),
            "window": payload.get("window", {}),
            "topic": payload.get("topic", {}),
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topic": payloads[0].get("topic", {}) if payloads else {},
        "days": days,
        "rankings": {
            "monthly": {
                "label": "Past 30 days",
                "papers": _period_top(payloads, 30, 5),
            }
        },
    }


def _shared_source_limit(base_config: dict[str, Any], topic_count: int) -> int:
    base_limit = max(1, int(base_config.get("max_per_source", 150) or 150))
    settings = base_config.get("topics", {}) or {}
    if topic_count <= 1 or not bool(settings.get("scale_source_limit", True)):
        return base_limit
    cap = max(base_limit, int(settings.get("max_shared_source_results", 500) or 500))
    return min(cap, base_limit * topic_count)


def _fetch_shared(
    fetch_config: dict[str, Any],
    start_date: str,
    end_date: str,
    limit: int,
) -> tuple[list[Paper], dict[str, int], dict[str, str]]:
    fetched: list[Paper] = []
    errors: dict[str, str] = {}
    counts = {"pubmed": 0, "biorxiv": 0, "medrxiv": 0, "arxiv": 0}
    sources = [
        ("pubmed", lambda: fetch_pubmed(fetch_config, start_date, end_date, limit)),
        ("biorxiv", lambda: fetch_biorxiv(fetch_config, start_date, end_date, limit)),
        ("medrxiv", lambda: fetch_medrxiv(fetch_config, start_date, end_date, limit)),
        ("arxiv", lambda: fetch_arxiv(fetch_config, start_date, end_date, limit)),
    ]
    for name, loader in sources:
        try:
            items = loader()
            fetched.extend(items)
            counts[name] = len(items)
            _save_source_cache(name, items, start_date, end_date)
            print(f"{name}: {len(items)} records")
        except Exception as exc:
            cached = _load_source_cache(name)
            if cached:
                fetched.extend(cached)
                counts[name] = len(cached)
                errors[name] = f"{type(exc).__name__}: {exc} · reused {len(cached)} cached records"
                print(f"{name}: ERROR, reused {len(cached)} cached records")
            else:
                errors[name] = f"{type(exc).__name__}: {exc}"
                print(f"{name}: ERROR {errors[name]}")
    unique = deduplicate(fetched)
    unique.sort(key=lambda p: (p.indexed_date or p.published_date, p.title), reverse=True)
    return unique, counts, errors


def _process_topic(
    profile: dict[str, Any],
    raw_unique: list[Paper],
    current_day: str,
    start_date: str,
    end_date: str,
    retrieved_source_counts: dict[str, int],
    source_errors: dict[str, str],
) -> dict[str, Any]:
    topic_id = profile["id"]
    topic_config = profile["config"]
    topic_dir = TOPIC_DATA_DIR / topic_id
    site_topic_dir = SITE_TOPIC_DATA_DIR / topic_id
    featured_target = max(1, int((topic_config.get("site", {}) or {}).get("featured_count", 25)))

    pool = _topic_pool(raw_unique, topic_config)
    raw_counts = Counter(p.source for p in pool)
    prefiltered = prefilter_papers(pool, topic_config)
    analyzed, configured_ai_limit = _select_ai_papers(prefiltered, topic_config)
    print(
        f"topic {topic_id}: {len(pool)} matching -> {len(prefiltered)} candidates "
        f"-> {len(analyzed)} AI papers"
    )

    runtime_config = _runtime_ai_config(topic_config, len(analyzed))
    ai_meta = apply_topic_ai_ranking(analyzed, runtime_config, topic_id)
    ai_meta = _attach_topic_daily_billing(topic_dir, current_day, ai_meta)
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

    payload = {
        "date": current_day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start": start_date, "end": end_date},
        "topic": {
            "id": topic_id,
            "label": profile["label"],
            "description": profile["description"],
        },
        "raw_count": len(pool),
        "retrieved_source_counts": retrieved_source_counts,
        "raw_source_counts": dict(raw_counts),
        "prefiltered_count": len(prefiltered),
        "analyzed_count": len(analyzed),
        "configured_max_analyzed": configured_ai_limit,
        "count": len(analyzed),
        "featured_count": min(featured_target, len(analyzed)),
        "source_counts": dict(Counter(p.source for p in analyzed)),
        "errors": source_errors,
        "ai": ai_meta,
        "papers": [paper.to_dict() for paper in analyzed],
    }

    _write_json(topic_dir / f"{current_day}.json", payload)
    _write_json(topic_dir / "latest.json", payload)
    site_payload = _build_site_digest(payload, analyzed)
    site_payload["topic"] = payload["topic"]
    site_payload["topic_source_counts"] = payload["raw_source_counts"]
    _write_compact_json(site_topic_dir / "latest.json", site_payload)
    _write_compact_json(site_topic_dir / "days" / f"{current_day}.json", site_payload)
    _write_compact_json(site_topic_dir / "archive.json", _topic_archive_manifest(topic_dir))
    return payload


def _mirror_default_topic(payload: dict[str, Any], default_id: str) -> None:
    site_topic_dir = SITE_TOPIC_DATA_DIR / default_id
    current_day = str(payload.get("date"))
    _write_json(DATA_DIR / f"{current_day}.json", payload)
    _write_json(DATA_DIR / "latest.json", payload)

    for source, target in [
        (site_topic_dir / "latest.json", SITE_DATA_DIR / "latest.json"),
        (site_topic_dir / "days" / f"{current_day}.json", SITE_DATA_DIR / "days" / f"{current_day}.json"),
        (site_topic_dir / "archive.json", SITE_DATA_DIR / "archive.json"),
    ]:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass


def run(days: int | None = None) -> dict[str, Any]:
    base_config = load_config()
    profiles, default_id = load_topic_profiles(base_config)
    fetch_config = build_shared_fetch_config(base_config, profiles)
    timezone_name = str(base_config.get("timezone", "UTC"))
    current_day = local_date(timezone_name).isoformat()
    lookback_days = days or int(base_config.get("lookback_days", 3))
    start_date, end_date = date_window(lookback_days, timezone_name)
    limit = _shared_source_limit(base_config, len(profiles))

    raw_unique, retrieved_counts, source_errors = _fetch_shared(
        fetch_config, start_date, end_date, limit
    )
    print(f"shared retrieval: {len(raw_unique)} unique papers for {len(profiles)} topic(s)")

    results: dict[str, dict[str, Any]] = {}
    aggregate_usage = empty_usage()
    aggregate_cost = 0.0
    for profile in profiles:
        payload = _process_topic(
            profile,
            raw_unique,
            current_day,
            start_date,
            end_date,
            retrieved_counts,
            source_errors,
        )
        results[profile["id"]] = payload
        billing = ((payload.get("ai") or {}).get("billing") or {})
        aggregate_usage = add_usage(aggregate_usage, billing.get("run_usage", {}) or {})
        aggregate_cost += float(billing.get("run_cost_cny", 0.0) or 0.0)

    manifest = topic_manifest(profiles, default_id)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    _write_compact_json(SITE_DATA_DIR / "topics.json", manifest)
    _write_json(DATA_DIR / "topics.json", manifest)

    default_payload = results[default_id]
    _mirror_default_topic(default_payload, default_id)

    aggregate = deepcopy(default_payload)
    aggregate["topic_results"] = {
        topic_id: {
            "raw_count": payload.get("raw_count", 0),
            "prefiltered_count": payload.get("prefiltered_count", 0),
            "analyzed_count": payload.get("analyzed_count", 0),
            "ai_status": (payload.get("ai") or {}).get("status", ""),
        }
        for topic_id, payload in results.items()
    }
    aggregate["topics"] = manifest
    aggregate_ai = dict(aggregate.get("ai", {}) or {})
    aggregate_billing = dict((aggregate_ai.get("billing") or {}))
    aggregate_billing["run_usage"] = aggregate_usage
    aggregate_billing["run_cost_cny"] = round(aggregate_cost, 6)
    aggregate_ai["billing"] = aggregate_billing
    aggregate["ai"] = aggregate_ai
    aggregate["raw_count"] = len(raw_unique)
    return aggregate
