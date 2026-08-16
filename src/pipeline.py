from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from .deduplicate import deduplicate
from .fetch_arxiv import fetch_arxiv
from .fetch_biorxiv import fetch_biorxiv, fetch_medrxiv
from .fetch_pubmed import fetch_pubmed
from .models import Paper
from .utils import date_window, load_config


DATA_DIR = Path("data")
SITE_DATA_DIR = Path("site/data")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(days: int | None = None) -> dict:
    config = load_config()
    lookback_days = days or int(config.get("lookback_days", 3))
    start_date, end_date = date_window(lookback_days)
    limit = int(config.get("max_per_source", 150))

    fetched: list[Paper] = []
    errors: dict[str, str] = {}

    sources = [
        ("pubmed", lambda: fetch_pubmed(config, start_date, end_date, limit)),
        ("biorxiv", lambda: fetch_biorxiv(start_date, end_date, limit)),
        ("medrxiv", lambda: fetch_medrxiv(start_date, end_date, limit)),
        ("arxiv", lambda: fetch_arxiv(config, limit)),
    ]

    for name, loader in sources:
        try:
            items = loader()
            fetched.extend(items)
            print(f"{name}: {len(items)} records")
        except Exception as exc:  # keep other sources alive if one provider is down
            errors[name] = f"{type(exc).__name__}: {exc}"
            print(f"{name}: ERROR {errors[name]}")

    unique = deduplicate(fetched)
    unique.sort(key=lambda p: (p.indexed_date or p.published_date, p.title), reverse=True)
    counts = Counter(p.source for p in unique)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start": start_date, "end": end_date},
        "count": len(unique),
        "source_counts": dict(counts),
        "errors": errors,
        "papers": [p.to_dict() for p in unique],
    }

    DATA_DIR.mkdir(exist_ok=True)
    archive_path = DATA_DIR / f"{date.today().isoformat()}.json"
    latest_path = DATA_DIR / "latest.json"
    _write_json(archive_path, payload)
    _write_json(latest_path, payload)

    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(latest_path, SITE_DATA_DIR / "latest.json")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and normalize PaperDaily sources")
    parser.add_argument("--days", type=int, default=None, help="Override lookback window")
    args = parser.parse_args()
    result = run(args.days)
    print(f"total unique: {result['count']}")
    if result["errors"]:
        print("source errors:", result["errors"])


if __name__ == "__main__":
    main()
