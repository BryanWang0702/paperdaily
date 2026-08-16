from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.pipeline import run
from src.utils import load_config


ROOT = Path(__file__).resolve().parent
TOKEN_FILE = ROOT / "api_token.txt"
SITE_DIR = ROOT / "site"


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


def main() -> None:
    os.chdir(ROOT)
    config = load_config(ROOT / "config.yaml")
    key_env = _load_local_token(config)
    local_config = config.get("local", {}) or {}
    port = int(local_config.get("port", 8765))
    refresh_on_start = bool(local_config.get("refresh_on_start", True))

    print("PaperDaily local edition")
    print(f"AI credential: {key_env} loaded from local environment/token file")

    if refresh_on_start:
        print("Refreshing literature before opening the dashboard...")
        try:
            result = run()
            print(
                f"Refresh complete: {result.get('raw_count', 0)} discovered, "
                f"{result.get('analyzed_count', 0)} AI-analyzed."
            )
        except Exception as exc:
            print(f"Refresh failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            print("The local dashboard will still open with the most recently available data.")

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
