from __future__ import annotations

import json
import os
import re
import shutil
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from src.runtime_pipeline import run
from src.site_settings import write_site_settings
from src.utils import load_config


FROZEN = bool(getattr(sys, "frozen", False))
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
TOKEN_FILE = ROOT / "api_token.txt"
STATE_FILE = ROOT / "local_state.json"
SITE_DIR = ROOT / "site"
LATEST_SITE_DATA = SITE_DIR / "data" / "latest.json"
LOCAL_STATUS_FILE = SITE_DIR / "data" / "local_status.json"
DEFAULT_REFRESH_TIMES = ["05:30", "20:30"]
DEFAULT_VERSION_URL = "https://raw.githubusercontent.com/BryanWang0702/paperdaily/master/standalone_version.json"
STATIC_SITE_FILES = ("index.html", "day.html", "app.js", "day.js", "style.css", "theme.js")
REFRESH_LOCK = threading.Lock()


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
        TOKEN_FILE.write_text("PASTE_YOUR_API_TOKEN_HERE\n", encoding="utf-8")
        raise RuntimeError(
            "api_token.txt was created next to PaperDaily. Paste your API token on the first line, save it, and start again."
        )

    lines = TOKEN_FILE.read_text(encoding="utf-8").strip().splitlines()
    token = lines[0].strip() if lines else ""
    if not token or token.upper().startswith("PASTE_"):
        raise RuntimeError(
            "api_token.txt does not contain an API token yet. Paste the token on the first line and save the file."
        )

    os.environ[key_env] = token
    return key_env


def _open_browser(url: str) -> None:
    time.sleep(0.8)
    webbrowser.open(url)


def _ensure_site_assets() -> None:
    source_dir = BUNDLE_ROOT / "site"
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    for name in STATIC_SITE_FILES:
        source = source_dir / name
        target = SITE_DIR / name
        if not source.exists() or source.resolve() == target.resolve():
            continue
        shutil.copy2(source, target)


def _app_version() -> str:
    for path in (BUNDLE_ROOT / "VERSION", ROOT / "VERSION"):
        try:
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            continue
    return "dev"


def _version_tuple(value: str) -> tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", str(value))]
    return tuple(numbers or [0])


def _write_local_status(payload: dict) -> None:
    LOCAL_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_STATUS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _check_version(config: dict) -> dict:
    current = _app_version()
    local_config = config.get("local", {}) or {}
    if not bool(local_config.get("version_check", True)):
        payload = {
            "check_status": "disabled",
            "current_version": current,
            "latest_version": current,
            "update_available": False,
        }
        _write_local_status(payload)
        return payload

    url = str(local_config.get("version_manifest_url", DEFAULT_VERSION_URL)).strip() or DEFAULT_VERSION_URL
    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        manifest = response.json()
        latest = str(manifest.get("latest_version", current)).strip() or current
        payload = {
            "check_status": "ok",
            "checked_at": datetime.utcnow().isoformat() + "Z",
            "current_version": current,
            "latest_version": latest,
            "update_available": _version_tuple(latest) > _version_tuple(current),
            "download_url": str(manifest.get("download_url", "")),
            "release_page": str(manifest.get("release_page", "")),
            "message": str(manifest.get("message", "")),
        }
        _write_local_status(payload)
        return payload
    except Exception as exc:
        payload = {
            "check_status": "error",
            "checked_at": datetime.utcnow().isoformat() + "Z",
            "current_version": current,
            "latest_version": current,
            "update_available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        _write_local_status(payload)
        return payload


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
    payload = _load_state()
    payload.update({
        "last_successful_slot": slot.isoformat(),
        "last_successful_refresh_at": datetime.now(slot.tzinfo).isoformat(),
    })
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


def _perform_refresh(config: dict, due_slot: datetime, *, run_kind: str = "local_scheduled") -> bool:
    if not REFRESH_LOCK.acquire(blocking=False):
        return False
    try:
        version = _check_version(config)
        if version.get("check_status") == "ok":
            if version.get("update_available"):
                print(
                    f"Update available: {version.get('current_version')} -> {version.get('latest_version')}. "
                    f"{version.get('release_page') or version.get('download_url')}"
                )
            else:
                print(f"Version check: {_app_version()} is up to date.")
        else:
            print("Version check unavailable; continuing with literature refresh.")

        key_env = _load_local_token(config)
        os.environ["PAPERDAILY_RUN_KIND"] = run_kind
        print(f"AI credential: {key_env} loaded from local environment/token file")
        print(f"Refreshing literature for slot {due_slot.strftime('%Y-%m-%d %H:%M')}...")
        result = run()
        _save_state(due_slot)
        print(
            f"Refresh complete: {result.get('raw_count', 0)} discovered, "
            f"{result.get('analyzed_count', 0)} AI-analyzed."
        )
        return True
    except Exception as exc:
        print(f"Refresh failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("The local dashboard remains available with the most recently successful data.")
        return False
    finally:
        REFRESH_LOCK.release()


def _scheduler_loop(stop_event: threading.Event) -> None:
    next_retry_at: datetime | None = None
    while not stop_event.is_set():
        try:
            config = load_config(ROOT / "config.yaml")
            write_site_settings(config, SITE_DIR / "data" / "settings.json")
            local_config = config.get("local", {}) or {}
            check_seconds = max(10, int(local_config.get("scheduler_check_seconds", 30) or 30))
            if not bool(local_config.get("scheduler_enabled", True)):
                stop_event.wait(check_seconds)
                continue
            if str(local_config.get("refresh_mode", "scheduled")).strip().lower() != "scheduled":
                stop_event.wait(check_seconds)
                continue

            timezone_name = str(config.get("timezone", "Asia/Shanghai"))
            now = datetime.now(ZoneInfo(timezone_name))
            should_refresh, due_slot, reason = _refresh_decision(config, now)
            if should_refresh and (next_retry_at is None or now >= next_retry_at):
                print(f"Scheduler: {reason}")
                success = _perform_refresh(config, due_slot, run_kind="local_scheduled")
                if success:
                    next_retry_at = None
                else:
                    retry_minutes = max(1, int(local_config.get("scheduler_retry_minutes", 10) or 10))
                    next_retry_at = now + timedelta(minutes=retry_minutes)
            stop_event.wait(check_seconds)
        except Exception as exc:
            print(f"Scheduler warning: {type(exc).__name__}: {exc}", file=sys.stderr)
            stop_event.wait(30)


def main() -> None:
    os.chdir(ROOT)
    _ensure_site_assets()
    config = load_config(ROOT / "config.yaml")
    write_site_settings(config, SITE_DIR / "data" / "settings.json")
    local_config = config.get("local", {}) or {}
    port = int(local_config.get("port", 8765))
    should_refresh, due_slot, reason = _refresh_decision(config)

    print(f"PaperDaily standalone/local edition v{_app_version()}")
    print(f"Refresh check: {reason}")

    if should_refresh:
        _perform_refresh(config, due_slot, run_kind="local_scheduled")
    else:
        print("No refresh needed. Opening the existing local dashboard without API calls.")

    handler = partial(SimpleHTTPRequestHandler, directory=str(SITE_DIR))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        raise RuntimeError(
            f"Could not start the local web server on port {port}. Change local.port in config.yaml and try again."
        ) from exc

    stop_event = threading.Event()
    if bool(local_config.get("scheduler_enabled", True)):
        threading.Thread(target=_scheduler_loop, args=(stop_event,), daemon=True).start()
        times = ", ".join(str(value) for value in local_config.get("refresh_times", DEFAULT_REFRESH_TIMES))
        print(f"Background scheduler enabled for: {times}")

    url = f"http://127.0.0.1:{port}/"
    print(f"Opening {url}")
    print("Keep this window/app running for scheduled refreshes. Press Ctrl+C to stop.")
    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping PaperDaily.")
    finally:
        stop_event.set()
        server.server_close()


if __name__ == "__main__":
    main()
