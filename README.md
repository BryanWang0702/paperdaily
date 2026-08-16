# PaperDaily

PaperDaily is a lightweight personal research radar that collects newly indexed literature, removes duplicates, applies a transparent deterministic prefilter, ranks papers against a researcher-specific profile, generates compact summaries, and publishes a persistent daily archive with GitHub Pages.

The default configuration is tuned for sleep neuroscience, but the retrieval, prefilter, and AI profile are configurable so the project can be forked for other research fields.

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
       all 40 compactly summarized
                ↓
     Top 25 visible + 15 collapsed
                ↓
      daily archive + Monthly Top 5
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
- Separate ranking and summarization stages for stable relevance scores.
- AI caching so unchanged papers are not repeatedly paid for.
- Up to 40 ranked and summarized papers per day.
- Top 25 papers shown immediately, with ranks 26-40 collapsed by default.
- Source label on every public paper card.
- Per-source retrieval totals on every daily page.
- Persistent daily issues.
- Top 5 paper titles shown directly on each homepage date card.
- Monthly Top 5 sidebar based on AI relevance score.
- Per-run and cumulative token/cost tracking.
- Source retry and last-good cache behavior for transient failures.
- GitHub Actions credential preflight.
- GitHub Pages deployment.
- English user interface and explicit English date formatting.

## AI ranking

The default configuration uses DeepSeek. Add this repository secret:

```text
DEEPSEEK_API_KEY
```

Add it under:

**Settings -> Secrets and variables -> Actions -> Repository secrets**

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

Then open `http://localhost:8000`.

## Configuration

Edit `config.yaml` to change:

- timezone;
- broad discovery terms;
- arXiv categories;
- deterministic prefilter anchors, weights, penalties, and boosts;
- maximum AI candidate count;
- AI provider and model;
- researcher interest profile;
- daily visible paper count;
- token pricing used by the cost dashboard.

The default site configuration uses:

```yaml
prefilter:
  max_candidates: 40

ai:
  digest_min: 40
  digest_max: 40
  digest_score_threshold: 0

site:
  featured_count: 25
```

This means 40 papers are ranked and summarized, the first 25 are shown immediately, and the remaining 15 are available in a collapsed section.

## Homepage behavior

Each date card shows:

- the total number of unique papers discovered that day;
- the configured Top 25 / additional-paper split;
- the latest update time;
- the Top 5 paper titles for that date.

The sidebar contains only **Monthly Top 5**, calculated from the highest AI relevance scores over the past 30 days.

## Daily page behavior

A daily page shows:

- total unique papers discovered;
- PubMed, bioRxiv, medRxiv, and arXiv retrieval totals;
- update time;
- papers sorted from highest to lowest relevance;
- Top 25 papers expanded;
- ranks 26-40 collapsed by default;
- source, relevance score, title, compact AI summary, and source link for each paper.

Full abstracts remain backend-only and are not shipped to the public website.

## Automation

`.github/workflows/daily.yml` currently runs at 07:15 and 20:15 UTC+8 and also supports manual dispatch. It commits refreshed data back to the repository.

`.github/workflows/deploy-pages.yml` deploys the static site after successful refreshes and after direct website changes.

`.github/workflows/ci.yml` compiles the Python source and runs the unit tests for pull requests.

## Forking PaperDaily for another field

See:

**[Fork and Customize PaperDaily](docs/FORK_AND_CUSTOMIZE.md)**

A generic starting configuration is also included at `config.template.yaml`.

## Design principle

PaperDaily is not intended to produce a universal ranking of scientific quality. It is a reproducible personal relevance system: broad enough to avoid missing useful work, cheap enough to run continuously, and transparent enough to tune when recommendations are wrong.
