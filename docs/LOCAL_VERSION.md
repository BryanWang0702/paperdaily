# PaperDaily Local Edition

The local edition is for researchers who want PaperDaily without GitHub Actions or GitHub Pages. It uses the same retrieval, filtering, AI ranking, summaries, archive, and HTML interface as the hosted version.

## What you need

- Windows, macOS, or Linux.
- Python 3.11 or newer.
- Internet access for PubMed, bioRxiv, medRxiv, arXiv, and your AI provider.
- One API token, such as a DeepSeek API key.

## The two files you normally edit

### 1. `config.yaml`

Use this file to configure your research field, discovery terms, prefilter rules, AI analysis size, display size, provider/model, timezone, and local refresh schedule.

The included `config.yaml` is the sleep-neuroscience example. `config.template.yaml` is a generic starting point for another field.

### 2. `api_token.txt`

Copy `api_token.example.txt` to `api_token.txt`, then replace the placeholder with your API token on the first line.

`api_token.txt` is ignored by Git and should never be shared.

## Windows: easiest start

Double-click:

```text
START_PAPERDAILY_WINDOWS.bat
```

On the first run it creates a private Python virtual environment, installs dependencies, and asks for an API token when a refresh is actually needed.

## macOS / Linux

From Terminal inside the PaperDaily folder:

```bash
bash START_PAPERDAILY_MAC_LINUX.sh
```

## Smart refresh behavior

The local edition does **not** fetch and call the AI every time it opens.

By default, it uses the same two Beijing-time refresh slots as the hosted edition:

```text
05:30
20:30
```

At startup PaperDaily determines the most recent scheduled slot that should already have happened, then checks `local_state.json`.

Example behavior:

- Open at 04:00: the latest due slot is the previous day's 20:30 slot.
- Open at 06:00: the latest due slot is today's 05:30 slot.
- Open at 19:00: the latest due slot is still today's 05:30 slot.
- Open at 21:00: the latest due slot is today's 20:30 slot.

If that slot has already completed successfully on this computer, PaperDaily opens the existing dashboard immediately with **no source requests and no AI API call**.

If that slot has not completed, PaperDaily runs retrieval + filtering + AI analysis once. Only after a successful run does it record the slot in `local_state.json`.

If the refresh fails, the slot is not marked complete, so the next launch can retry it. The previously generated dashboard still opens when available.

On the very first launch, if `site/data/latest.json` does not exist yet, PaperDaily forces one refresh regardless of the current clock time.

The token is only loaded when a refresh is actually required. Opening already-current local data therefore does not require an API call.

## Local refresh configuration

```yaml
local:
  port: 8765

  # scheduled | always | never
  refresh_mode: scheduled

  refresh_times:
    - "05:30"
    - "20:30"
```

`refresh_times` are interpreted in the top-level `timezone` from `config.yaml`.

Modes:

- `scheduled`: recommended; refresh only when the latest slot has not completed locally.
- `always`: refresh every time PaperDaily opens.
- `never`: never fetch on startup; only browse existing data.

`local_state.json` is machine-local, ignored by Git, and not included in the downloadable ZIP.

## Local address

The default address is:

```text
http://127.0.0.1:8765/
```

Keep the terminal/command window open while browsing. Press `Ctrl+C` to stop the local server.

## Downloadable ZIP

The hosted PaperDaily site automatically builds a synchronized local ZIP during GitHub Pages deployment:

```text
https://bryanwang.cn/paperdaily/downloads/PaperDaily-local.zip
```

The ZIP does not contain any API token, local refresh state, GitHub secret, historical backend data, or virtual environment.

## Build the ZIP yourself

```bash
python tools/build_local_bundle.py
```

The default output is `dist/PaperDaily-local.zip`.

## Security

Do not put the API token into HTML or JavaScript. The local launcher keeps it on the Python side, so it is not exposed to the browser page.

Do not upload `api_token.txt` when sharing the local folder.
