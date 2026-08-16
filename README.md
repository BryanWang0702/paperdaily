# PaperDaily

PaperDaily is a lightweight personal research radar that collects newly indexed literature, removes duplicates, applies a transparent deterministic prefilter, ranks papers against a researcher-specific profile, generates compact summaries, and publishes a persistent daily archive with GitHub Pages.

The default configuration is tuned for sleep neuroscience, but the filtering and AI profile are fully configurable so the project can be forked for other research fields.

## Live workflow

```text
PubMed + bioRxiv + medRxiv + arXiv
                ↓
       overlapping retrieval window
                ↓
          DOI / source deduplication
                ↓
      configurable local prefilter
                ↓
        up to 40 AI-ranked papers
                ↓
        25-30 compact summaries
                ↓
  daily archive + weekly/monthly Top 10
                ↓
           GitHub Pages
```

## Current features

- Daily retrieval from PubMed, bioRxiv, medRxiv, and arXiv.
- PubMed retrieval based on Create Date overlap rather than publication date alone.
- Cross-source deduplication.
- Configurable deterministic prefilter before any paid AI call.
- DeepSeek as the default AI provider.
- OpenAI support and support for other OpenAI-compatible Chat Completions endpoints.
- Separate ranking and summarization stages for more stable relevance scores.
- AI caching so unchanged papers are not repeatedly paid for.
- Compact public JSON with no full abstracts, for faster page loading.
- Persistent daily issues.
- Top 5 titles shown directly on each daily archive card.
- Rolling Past 7 Days Top 10 and Past 30 Days Top 10 rankings.
- Per-run and cumulative token/cost tracking.
- Source retry and last-good cache behavior for transient failures.
- GitHub Actions credential preflight.
- GitHub Pages deployment.

## Daily sources

- PubMed
- bioRxiv
- medRxiv
- arXiv

Planned weekly sources include selected Science/Nature news, commentary, opinion, and career content.

## Daily archive

Every calendar day is stored as `data/YYYY-MM-DD.json`. The homepage loads a compact archive manifest, and each date opens a dedicated daily digest.

The backend keeps the complete research record in `data/`, while the public website uses compact files under `site/data/` containing only the information needed for browsing: title, relevance score, short AI summary, and source link.

## AI ranking

The default configuration uses DeepSeek.

For GitHub Actions, add this repository secret:

```text
DEEPSEEK_API_KEY
```

Add it under:

**Settings -> Secrets and variables -> Actions -> Repository secrets**

The pipeline first ranks the filtered candidates, then summarizes only the daily digest. Ranking and summary caches are versioned independently so changing summary style does not force every paper to be re-ranked.

Optional PubMed secrets:

```text
NCBI_API_KEY
PUBMED_EMAIL
```

These are not required at the current request volume.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.pipeline --days 3
```

Serve the static site locally:

```bash
python -m http.server 8000 -d site
```

Then open:

```text
http://localhost:8000
```

## Configuration

Edit `config.yaml` to change:

- timezone;
- broad discovery terms;
- arXiv categories;
- deterministic prefilter anchors, weights, penalties, and boosts;
- maximum AI candidate count;
- AI provider and model;
- researcher interest profile;
- digest size and score threshold;
- token pricing used by the cost dashboard.

The prefilter contains no mandatory sleep-specific logic in Python. The sleep rules in the default installation live in `config.yaml` and can be replaced for another field.

## Automation

`.github/workflows/daily.yml` currently runs at 07:15 and 20:15 UTC+8 and also supports manual dispatch. It commits refreshed data back to the repository.

`.github/workflows/deploy-pages.yml` deploys the static site after successful refreshes and after direct website changes.

`.github/workflows/ci.yml` compiles the Python source and runs the unit tests for pull requests.

## Forking PaperDaily for another field

See the complete guide:

**[Fork and Customize PaperDaily](docs/FORK_AND_CUSTOMIZE.md)**

The guide covers GitHub Pages, secrets, AI providers, PubMed credentials, domain-specific retrieval terms, prefilter rules, interest profiles, schedule changes, local testing, and troubleshooting.

## Design principle

PaperDaily is not intended to produce a universal ranking of scientific quality. It is a reproducible personal relevance system: broad enough to avoid missing useful work, cheap enough to run continuously, and transparent enough to tune when the recommendations are wrong.
