# PaperDaily Local / Standalone Edition

PaperDaily can run without GitHub Actions or GitHub Pages. The recommended option for Windows users is the frozen standalone release: no Python installation, Git, or source-code editing is required.

## Windows standalone: simplest setup

Download `PaperDaily-Windows.zip` from the latest GitHub release, extract it, and keep these files together:

```text
PaperDaily-Windows/
├── PaperDaily.exe
├── config.yaml
├── api_token.txt
├── README.md
└── README.zh-CN.md
```

The only two files a normal user needs to edit are:

- `config.yaml` — research field, retrieval/filter limits, AI settings, schedule, theme, and display options.
- `api_token.txt` — the AI API token on the first line.

Run `PaperDaily.exe`. It creates its own `data/` and `site/` runtime folders automatically and opens the dashboard in the default browser.

## Smart refresh schedule

The default local configuration is:

```yaml
local:
  refresh_mode: scheduled
  refresh_times:
    - "05:30"
    - "20:30"
  scheduler_enabled: true
  scheduler_check_seconds: 30
```

Times use the top-level `timezone` setting. The sleep-neuroscience example uses `Asia/Shanghai`.

At startup, PaperDaily checks the latest refresh slot that should already have completed. If that slot is recorded in `local_state.json`, it opens existing HTML immediately and makes no literature or AI calls. If the slot has not completed, it refreshes first.

When PaperDaily stays open, the background scheduler keeps checking the configured slots. A successful refresh is recorded only after retrieval and analysis complete. Failed refreshes remain pending and are retried later instead of being marked complete.

The browser checks the archive timestamp once per minute and reloads automatically after a successful background refresh.

Refresh modes:

```yaml
refresh_mode: scheduled  # recommended
refresh_mode: always     # refresh on every launch
refresh_mode: never      # browse existing data only
```

## Version update check

Before every real literature refresh, the standalone app reads the small `standalone_version.json` manifest maintained in this repository. It compares the installed `VERSION` with the current release.

If a newer version is available, the dashboard shows an update notice and download link. If the version lookup fails, PaperDaily continues retrieving literature normally; version checking never blocks the research pipeline.

## Themes

Built-in themes are:

```yaml
site:
  theme: khaki      # warm paper / current default
  # theme: black    # minimal black
  # theme: navy     # classic academic blue
  # theme: forest   # muted green
  # theme: burgundy # warm wine red
  # theme: custom
```

For a custom palette:

```yaml
site:
  theme: custom
  custom_theme:
    background: "#f2efe5"
    surface: "#fffdf8"
    text: "#1f2723"
    muted: "#6b7068"
    border: "#d8d3c5"
    accent: "#75684d"
    accent_text: "#ffffff"
```

## Billing display

The homepage can show:

```text
Last run ¥... · Total ¥... · ~¥.../year
```

`Last run` is the most recent individual AI run, not the accumulated cost for the current day. `Total` is the recorded lifetime API spend. The yearly estimate is based on a representative per-run cost multiplied by the configured number of daily refresh slots. Once scheduled production runs exist, development/debug runs are excluded from that reference cost.

Turn the display off with:

```yaml
site:
  show_billing: false
```

## Research-field configuration

Important settings in `config.yaml` include:

- `discovery_terms`
- `prefilter.max_candidates`
- `prefilter.anchors`, `weights`, and `boosts`
- `ai.max_analyzed`
- `ai.interest_profile`
- `site.featured_count`
- `local.refresh_times`

The included `config.yaml` is the sleep-neuroscience example. `config.template.yaml` in the repository is a generic template for another field.

## Security

The API token remains on the Python/EXE side. It is never written into HTML or JavaScript. Do not share `api_token.txt`.

The standalone release does not contain the author's historical paper archive, API token, GitHub secrets, or editable Python source tree.

## Python-based local edition

A Python-based ZIP is also produced for developers and advanced users. It requires Python 3.11+ and exposes the source tree. For normal Windows users, prefer the frozen `PaperDaily.exe` release.
