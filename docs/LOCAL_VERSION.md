# PaperDaily Local / Standalone Edition

PaperDaily can run without GitHub Actions or GitHub Pages. The recommended option for Windows users is the frozen standalone release: no Python installation, Git, or source-code editing is required.

## Windows standalone: simplest setup

Download `PaperDaily-Windows.zip` from the latest GitHub release and extract it:

```text
PaperDaily-Windows/
├── PaperDaily.exe
├── config.yaml
├── api_token.txt
├── topics/
│   ├── sleep-homeostasis.yaml
│   └── eeg-methods.yaml
├── README.md
└── README.zh-CN.md
```

Normal users edit only configuration files, never source code:

- `config.yaml` — shared API, retrieval limits, schedule, theme, and display settings.
- `topics/*.yaml` — one small profile per research project, including discovery terms, prefilter rules, optional per-topic limits, and AI interest profile.
- `api_token.txt` — the AI API token on the first line.

Run `PaperDaily.exe`. It creates its own `data/` and `site/` runtime folders automatically and opens the dashboard in the default browser.

## Multiple research topics

PaperDaily 0.6 supports several independent projects in one installation. Enable them in `config.yaml`:

```yaml
topics:
  enabled: true
  directory: topics
  default: sleep-homeostasis
```

The dashboard provides a Topic selector. A single refresh retrieves the union of enabled topics from the external sources once, then applies an independent shortlist and AI relevance ranking to every topic. Each topic gets its own daily archive, Monthly Top 5, and daily 25 + additional-paper view.

Copy an existing topic YAML to add another project. Saving either `config.yaml` or `topics/*.yaml` is detected by the local watcher and triggers a refresh in scheduled mode.

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
  refresh_on_config_change: true
```

Times use the top-level `timezone` setting. The included example uses `Asia/Shanghai`.

At startup, PaperDaily checks the latest refresh slot that should already have completed. If that slot is recorded in `local_state.json`, it opens existing HTML immediately and makes no literature or AI calls. If the slot has not completed, it refreshes first.

When PaperDaily stays open, the background scheduler checks future slots. A successful refresh is recorded only after retrieval and analysis complete. Failed refreshes remain pending and are retried later instead of being marked complete.

The browser checks the archive timestamp periodically and reloads after a successful background refresh.

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

Themes are selectable directly in the webpage. Built-in presets are Khaki, Black, Navy, Forest, and Burgundy. `config.yaml` defines the initial default and may also contain a custom palette.

## Billing display

The homepage can optionally show:

```text
Last run ¥... · Total ¥... · ~¥.../year
```

`Last run` is the most recent individual AI run, `Total` is recorded lifetime API spend, and the yearly estimate uses a representative per-run cost multiplied by the configured daily refresh slots. Development/debug runs are excluded from the scheduled reference cost once production history exists.

Billing remains tracked even when hidden. It is hidden by default:

```yaml
site:
  show_billing: false
```

## Security

The API token remains on the Python/EXE side. It is never written into HTML or JavaScript. Do not share `api_token.txt`.

The standalone release does not contain the author's historical paper archive, API token, GitHub secrets, or editable Python source tree.

## Python-based local edition

A Python-based ZIP is also produced for developers and advanced users. It requires Python 3.11+ and exposes the source tree. For normal Windows users, prefer the frozen `PaperDaily.exe` release.
