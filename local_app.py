from __future__ import annotations

import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

from src.pipeline import run
from src.utils import load_config


ROOT = Path(__file__).resolve().parent
TOKEN_FILE = ROOT / "api_token.txt"
STATE_FILE = ROOT / "local_state.json"
SITE_DIR = ROOT / "site"
LATEST_SITE_DATA = SITE_DIR / "data" / "latest.json"
DEFAULT_REFRESH_TIMES = ["05:30", "20:30"]


def _api_key_env(config: dict) -> str:
    ai = config.get("ai", {}) or {}
    explicit = str(ai.get("api_key_env", "")).strip()
    if explicit:
        return explicit
    provider = str(ai.get("provider", "deepseek")).strip().lower()
    return "OPENAI_API_KEY" if provider == "openai" else "DEEPSEEK_API_KEY"


def _load_local_token(config: dict) -> str:
    key_env = _api_key_env(config)
    existing = os.getenv(key_env, "").strip()
    if existing:
        return key_env

    if not TOKEN_FILE.exists():
        raise RuntimeError(
            "api_token.txt was not found. Copy api_token.example.txt to api_token.txt, "
            "paste your API token on the first line, and start PaperDaily again."
        )

    token = TOKEN_FILE.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    if not token or token.upper().startswith("PASTE_"):
        raise RuntimeError(
            "api_token.txt does not contain an API token yet. Paste the token on the first line and save the file."
        )

    os.environ[key_env] = token
    return key_env


def _open_browser(url: str) -> None:
    time.sleep(0.8)
    webbrowser.open(url)


def _parse_refresh_times(values: object) -> list[tuple[int, int]]:
    raw_values = values if isinstance(values, list) else DEFAULT_REFRESH_TIMES
    parsed: set[tuple[int, int]] = set()
    for value in raw_values:
        text = str(value).strip()
        try:
            hour_text, minute_text = text.split(":", 1)
            hour, minute = int(hour_text), int(minute_text)
        except (ValueError, TypeError):
            continue
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            parsed.add((hour, minute))
    return sorted(parsed) or [(5, 30), (20, 30)]


def _latest_due_slot(now: datetime, refresh_times: object) -> datetime:
    times = _parse_refresh_times(refresh_times)
    candidates: list[datetime] = []
    for day_offset in (0, -1):
        day = (now + timedelta(days=day_offset)).date()
        for hour, minute in times:
            slot = datetime(day.year, day.month, day.day, hour, minute, tzinfo=now.tzinfo)
            if slot <= now:
                candidates.append(slot)
    return max(candidates)


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(slot: datetime) -> None:
    payload = {
        "last_successful_slot": slot.isoformat(),
        "last_successful_refresh_at": datetime.now(slot.tzinfo).isoformat(),
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _slot_already_completed(slot: datetime) -> bool:
    state = _load_state()
    value = str(state.get("last_successful_slot", "")).strip()
    if not value:
        return False
    try:
        completed = datetime.fromisoformat(value)
    except ValueError:
        return False
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=slot.tzinfo)
    return completed >= slot


def _refresh_decision(config: dict, now: datetime | None = None) -> tuple[bool, datetime, str]:
    timezone_name = str(config.get("timezone", "Asia/Shanghai"))
    current = now or datetime.now(ZoneInfo(timezone_name))
    local_config = config.get("local", {}) or {}
    refresh_times = local_config.get("refresh_times", DEFAULT_REFRESH_TIMES)
    slot = _latest_due_slot(current, refresh_times)
    mode = str(local_config.get("refresh_mode", "scheduled")).strip().lower()

    if not LATEST_SITE_DATA.exists():
        return True, slot, "no local dashboard data exists yet"
    if mode == "always":
        return True, slot, "local.refresh_mode is always"
    if mode == "never":
        return False, slot, "local.refresh_mode is never"
    if _slot_already_completed(slot):
        return False, slot, f"scheduled slot {slot.strftime('%Y-%m-%d %H:%M')} already completed"
    return True, slot, f"scheduled slot {slot.strftime('%Y-%m-%d %H:%M')} has not been completed"


def main() -> None:
    os.chdir(ROOT)
    config = load_config(ROOT / "config.yaml")
    local_config = config.get("local", {}) or {}
    port = int(local_config.get("port", 8765))
    should_refresh, due_slot, reason = _refresh_decision(config)

    print("PaperDaily local edition")
    print(f"Refresh check: {reason}")

    if should_refresh:
        key_env = _load_local_token(config)
        print(f"AI credential: {key_env} loaded from local environment/token file")
        print(f"Refreshing literature for slot {due_slot.strftime('%Y-%m-%d %H:%M')}...")
        try:
            result = run()
            _save_state(due_slot)
            print(
                f"Refresh complete: {result.get('raw_count', 0)} discovered, "
                f"{result.get('analyzed_count', 0)} AI-analyzed."
            )
        except Exception as exc:
            print(f"Refresh failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            print("The local dashboard will still open with the most recently available data.")
    else:
        print("No refresh needed. Opening the existing local dashboard without API calls.")

    handler = partial(SimpleHTTPRequestHandler, directory=str(SITE_DIR))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        raise RuntimeError(
            f"Could not start the local web server on port {port}. "
            "Change local.port in config.yaml and try again."
        ) from exc

    url = f"http://127.0.0.1:{port}/"
    print(f"Opening {url}")
    print("Keep this window open while using PaperDaily. Press Ctrl+C to stop.")
    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping PaperDaily.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
