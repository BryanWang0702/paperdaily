from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


TOPICS_DIR = Path("topics")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in {"id", "label", "description", "enabled"}:
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _topic_config(base_config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_merge(base_config, payload)

    # These collections describe one topic rather than incremental global rules.
    # Replacing them keeps an EEG profile from inheriting sleep-homeostasis terms.
    prefilter_override = payload.get("prefilter", {}) or {}
    merged_prefilter = merged.get("prefilter", {}) or {}
    for key in ("anchors", "weights", "boosts"):
        if key in prefilter_override:
            merged_prefilter[key] = deepcopy(prefilter_override[key])
    merged["prefilter"] = merged_prefilter

    arxiv_override = payload.get("arxiv", {}) or {}
    if "categories" in arxiv_override:
        merged_arxiv = merged.get("arxiv", {}) or {}
        merged_arxiv["categories"] = deepcopy(arxiv_override["categories"])
        merged["arxiv"] = merged_arxiv
    return merged


def _safe_topic_id(value: object, fallback: str) -> str:
    raw = str(value or fallback).strip().lower()
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in raw)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-_") or fallback


def load_topic_profiles(base_config: dict[str, Any], root: Path | None = None) -> tuple[list[dict[str, Any]], str]:
    topic_settings = base_config.get("topics", {}) or {}
    if topic_settings.get("enabled", True) is False:
        return [_fallback_profile(base_config)], "default"

    directory = Path(str(topic_settings.get("directory", "topics")))
    if root is not None and not directory.is_absolute():
        directory = root / directory

    profiles: list[dict[str, Any]] = []
    if directory.exists():
        for path in sorted(directory.glob("*.yaml")):
            try:
                payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(payload, dict) or payload.get("enabled", True) is False:
                continue
            topic_id = _safe_topic_id(payload.get("id"), path.stem)
            label = str(payload.get("label") or topic_id.replace("-", " ").title()).strip()
            description = str(payload.get("description") or "").strip()
            profiles.append({
                "id": topic_id,
                "label": label,
                "description": description,
                "path": str(path),
                "config": _topic_config(base_config, payload),
            })

    if not profiles:
        fallback = _fallback_profile(base_config)
        return [fallback], fallback["id"]

    ids = {profile["id"] for profile in profiles}
    requested_default = _safe_topic_id(topic_settings.get("default"), profiles[0]["id"])
    default_id = requested_default if requested_default in ids else profiles[0]["id"]
    return profiles, default_id


def _fallback_profile(base_config: dict[str, Any]) -> dict[str, Any]:
    label = str((base_config.get("site", {}) or {}).get("title") or "PaperDaily")
    return {
        "id": "default",
        "label": label,
        "description": "",
        "path": "config.yaml",
        "config": deepcopy(base_config),
    }


def build_shared_fetch_config(base_config: dict[str, Any], profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """Build one source-query config from the union of all enabled topics."""
    result = deepcopy(base_config)
    terms: list[str] = []
    categories: list[str] = []
    seen_terms: set[str] = set()
    seen_categories: set[str] = set()

    for profile in profiles:
        config = profile["config"]
        for value in config.get("discovery_terms", []) or []:
            term = str(value).strip()
            marker = term.casefold()
            if term and marker not in seen_terms:
                seen_terms.add(marker)
                terms.append(term)
        for value in ((config.get("arxiv", {}) or {}).get("categories", []) or []):
            category = str(value).strip()
            if category and category not in seen_categories:
                seen_categories.add(category)
                categories.append(category)

    result["discovery_terms"] = terms
    arxiv = dict(result.get("arxiv", {}) or {})
    arxiv["categories"] = categories
    result["arxiv"] = arxiv
    return result


def topic_manifest(profiles: list[dict[str, Any]], default_id: str) -> dict[str, Any]:
    return {
        "default_topic": default_id,
        "topics": [
            {
                "id": profile["id"],
                "label": profile["label"],
                "description": profile["description"],
            }
            for profile in profiles
        ],
    }
