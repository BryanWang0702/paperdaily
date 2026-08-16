from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_THEME = "khaki"
THEME_KEYS = ("background", "surface", "text", "muted", "border", "accent", "accent_text")


def build_site_settings(config: dict[str, Any]) -> dict[str, Any]:
    site = config.get("site", {}) or {}
    theme = str(site.get("theme", DEFAULT_THEME)).strip().lower() or DEFAULT_THEME
    custom_raw = site.get("custom_theme", {}) or {}
    custom = {
        key: str(custom_raw.get(key, "")).strip()
        for key in THEME_KEYS
        if str(custom_raw.get(key, "")).strip()
    }
    return {
        "theme": {
            "preset": theme,
            "custom": custom,
        },
        "billing": {
            "show": bool(site.get("show_billing", False)),
        },
    }


def write_site_settings(config: dict[str, Any], path: Path = Path("site/data/settings.json")) -> dict[str, Any]:
    payload = build_site_settings(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return payload
