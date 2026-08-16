# PaperDaily

**Language:** English | [中文](README.zh-CN.md)

PaperDaily is a lightweight personal research radar that collects newly indexed literature, removes duplicates, applies a transparent deterministic prefilter, ranks papers against a researcher-specific profile, generates compact summaries, and publishes a persistent daily archive.

The default configuration is tuned for sleep neuroscience, but retrieval, filtering, AI analysis size, presentation, themes, and the research profile are configurable for other fields.

## Live workflow

```text
PubMed + bioRxiv + medRxiv + arXiv
                ↓
       overlapping retrieval window
                ↓
          DOI / source deduplication
                ↓
      configurable local prefilter
      prefilter.max_candidates
                ↓
     configurable AI analysis set
          ai.max_analyzed
                ↓
 rank + summarize + classify analyzed papers
                ↓
   site.featured_count shown first
     remaining papers collapsed
                ↓
      daily archive + Monthly Top 5
```

## Current features

- Daily retrieval from PubMed, bioRxiv, medRxiv, and arXiv.
- PubMed Create Date overlap for newly indexed papers.
- Cross-source deduplication.
- Configurable deterministic prefilter before paid AI calls.
- Independently configurable shortlist, AI-analysis, and expanded-display sizes.
- DeepSeek as the default AI provider, with OpenAI and OpenAI-compatible endpoint support.
- Separate relevance ranking and summarization/enrichment stages.
- AI caching so unchanged papers are not repeatedly paid for.
- Authors, journal metadata, 3-5 keywords, normalized paper type, relevance score, short summary, and source link on each paper card.
- Per-source retrieval totals and keyword quick filters on daily pages.
- Top 5 titles on each homepage date card.
- Monthly Top 5 sidebar based on AI relevance score.
- Per-run billing ledger: `Last run`, lifetime `Total`, and estimated yearly cost.
- Configurable billing visibility with `site.show_billing`.
- Built-in `khaki`, `black`, `navy`, `forest`, and `burgundy` themes plus a custom palette.
- Source retry and last-good cache behavior.
- GitHub Actions credential preflight and GitHub Pages deployment.
- English web UI with timestamps normalized to Beijing time (`Asia/Shanghai`).
- Python-based local edition.
- Frozen Windows standalone release with no Python installation required.
- Smart local scheduler that refreshes at configured slots while the app remains open.
- Standalone version check before each real literature refresh.

## AI ranking

The default configuration uses DeepSeek. Add this repository secret for the hosted version:

```text
DEEPSEEK_API_KEY
```

Add it under **Settings -> Secrets and variables -> Actions -> Repository secrets**.

Optional PubMed secrets:

```text
NCBI_API_KEY
PUBMED_EMAIL
```

## Hosted quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.runtime_pipeline --days 3
```

Serve the static site:

```bash
python -m http.server 8000 -d site
```

## Windows standalone

For non-GitHub users, the recommended Windows package is the frozen standalone release. A normal user only needs to edit:

```text
config.yaml
api_token.txt
```

and run:

```text
PaperDaily.exe
```

The EXE contains the application code and static UI. It creates its own runtime `data/` and `site/` folders. The public standalone ZIP does not include the author's historical archive, API credentials, GitHub secrets, or an editable Python source tree.

The default local schedule is 05:30 and 20:30 in the configured timezone. If a slot has already completed on that computer, reopening the app uses the existing local dashboard without source or AI calls. If PaperDaily remains open, a background scheduler triggers future due slots automatically.

Before each real refresh, the app checks the repository's `standalone_version.json`. A newer version produces an update notice in the dashboard. Version-check failure never blocks literature retrieval.

See **[PaperDaily Local / Standalone Edition](docs/LOCAL_VERSION.md)**.

## Python-based local edition

A synchronized developer-friendly ZIP is also published at:

```text
https://bryanwang.cn/paperdaily/downloads/PaperDaily-local.zip
```

This version requires Python 3.11+ and exposes the source tree. It is intended for development, debugging, and macOS/Linux users until frozen builds for those platforms are added.

## Configuration

The three core paper-count controls are:

```yaml
prefilter:
  max_candidates: 40

ai:
  max_analyzed: 40

site:
  featured_count: 25
```

The default `40 -> 40 -> 25` flow keeps up to 40 papers after free local filtering, analyzes up to 40 with AI, shows the top 25 immediately, and collapses the remaining 15.

Billing and themes are controlled in the same file:

```yaml
site:
  show_billing: true
  theme: khaki  # khaki | black | navy | forest | burgundy | custom

  custom_theme:
    background: "#f2efe5"
    surface: "#fffdf8"
    text: "#1f2723"
    muted: "#6b7068"
    border: "#d8d3c5"
    accent: "#75684d"
    accent_text: "#ffffff"
```

Local scheduling:

```yaml
local:
  refresh_mode: scheduled
  refresh_times:
    - "05:30"
    - "20:30"
  scheduler_enabled: true
  scheduler_check_seconds: 30
  version_check: true
```

See `config.template.yaml` for a generic field template.

## Billing semantics

The homepage billing line is intentionally based on individual runs rather than the accumulated cost of the current day:

```text
Last run ¥... · Total ¥... · ~¥.../year
```

- `Last run`: cost of the most recent individual pipeline run.
- `Total`: actual recorded lifetime spend.
- `Estimated/year`: representative per-run cost × configured daily refresh slots × 365.

Once scheduled production runs exist, development/debug-triggered runs are excluded from the reference per-run cost used for the yearly estimate. They still remain part of the truthful lifetime total.

## Daily page

Each daily page shows total unique papers, source totals, update time, keyword shortcuts, full-text search, and papers sorted by relevance. Paper cards include source, paper type, score, title, journal when available, authors, keywords, short AI summary, and the paper link. Full abstracts remain backend-only.

## Automation

- `.github/workflows/daily.yml`: hosted refresh at **05:30 and 20:30 Beijing time** plus manual/development runs.
- `.github/workflows/deploy-pages.yml`: deploys the static site and Python local ZIP.
- `.github/workflows/build-standalone.yml`: builds and publishes the versioned Windows `PaperDaily.exe` release when `VERSION` changes.
- `.github/workflows/ci.yml`: Python/JavaScript tests plus a real PyInstaller Windows smoke build.

## Forking PaperDaily for another field

See **[Fork and Customize PaperDaily](docs/FORK_AND_CUSTOMIZE.md)**. A generic `config.template.yaml` is included.

## Design principle

PaperDaily is not a universal ranking of scientific quality. It is a reproducible personal relevance system: broad enough to avoid missing useful work, cheap enough to run continuously, and transparent enough to tune when recommendations are wrong.
