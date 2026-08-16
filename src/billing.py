from __future__ import annotations

from typing import Any


USAGE_KEYS = (
    "requests",
    "prompt_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "completion_tokens",
    "total_tokens",
)


def empty_usage() -> dict[str, int]:
    return {key: 0 for key in USAGE_KEYS}


def normalize_usage(raw: dict[str, Any] | None) -> dict[str, int]:
    raw = raw or {}
    usage = empty_usage()
    usage["requests"] = int(raw.get("requests", 0) or 0)
    for key in USAGE_KEYS[1:]:
        usage[key] = int(raw.get(key, 0) or 0)

    # Older/compatible providers may only return prompt_tokens. Keep the
    # accounting conservative by treating unclassified prompt tokens as misses.
    classified = usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"]
    if usage["prompt_tokens"] > classified:
        usage["prompt_cache_miss_tokens"] += usage["prompt_tokens"] - classified
    if not usage["total_tokens"]:
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    return usage


def add_usage(*items: dict[str, Any] | None) -> dict[str, int]:
    total = empty_usage()
    for item in items:
        normalized = normalize_usage(item)
        for key in USAGE_KEYS:
            total[key] += normalized[key]
    return total


def calculate_cost_cny(usage: dict[str, Any], pricing: dict[str, Any]) -> float:
    usage = normalize_usage(usage)
    hit_price = float(pricing.get("input_cache_hit", 0.02) or 0.0)
    miss_price = float(pricing.get("input_cache_miss", 1.0) or 0.0)
    output_price = float(pricing.get("output", 2.0) or 0.0)
    cost = (
        usage["prompt_cache_hit_tokens"] * hit_price
        + usage["prompt_cache_miss_tokens"] * miss_price
        + usage["completion_tokens"] * output_price
    ) / 1_000_000
    return round(cost, 6)


def pricing_snapshot(ai_config: dict[str, Any]) -> dict[str, Any]:
    pricing = ai_config.get("pricing_cny_per_million", {}) or {}
    return {
        "currency": "CNY",
        "unit_tokens": 1_000_000,
        "input_cache_hit": float(pricing.get("input_cache_hit", 0.02)),
        "input_cache_miss": float(pricing.get("input_cache_miss", 1.0)),
        "output": float(pricing.get("output", 2.0)),
    }
