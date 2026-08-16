#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
export PYTHONUTF8=1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.11 or newer, then run this script again."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating local Python environment..."
  python3 -m venv .venv
fi

if [ ! -f "api_token.txt" ]; then
  cp api_token.example.txt api_token.txt
  echo "Created api_token.txt. Paste your DeepSeek/OpenAI-compatible API token into the first line, save it, then run this script again."
  exit 0
fi

echo "Checking Python dependencies..."
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt

echo "Starting PaperDaily..."
.venv/bin/python local_app.py
