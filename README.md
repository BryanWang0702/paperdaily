# PaperDaily

**Language:** English | [中文](README.zh-CN.md)

PaperDaily is a lightweight personal research radar that collects newly indexed literature, removes duplicates, applies a transparent deterministic prefilter, ranks papers against a researcher-specific profile, generates compact summaries, and publishes a persistent daily archive with GitHub Pages.

The default configuration is tuned for sleep neuroscience, but the retrieval, prefilter, AI analysis size, and interest profile are configurable so the project can be forked for other research fields.

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
                ↓
           GitHub Pages
```

## Current features

- Daily retrieval from PubMed, bioRxiv, medRxiv, and arXiv.
- PubMed retrieval based on Create Date overlap rather than publication date alone.
- Cross-source deduplication.
- Configurable deterministic prefilter before any paid AI call.
- Independently configurable local-shortlist size and AI-analysis size.
- DeepSeek as the default AI provider.
- OpenAI support and support for other OpenAI-compatible Chat Completions endpoints.
- Separate ranking and summarization stages for stable relevance scores.
- AI caching so unchanged papers are not repeatedly paid for.
- Source metadata plus AI enrichment for authors, 3-5 scientific keywords, and normalized scientific paper type.
- Configurable number of papers expanded on the daily page, with the remainder collapsed.
- Source label and relevance score on every public paper card.
- Per-source retrieval totals on every daily page.
- Persistent daily issues.
- Top 5 paper titles shown directly on each homepage date card.
- Monthly Top 5 sidebar based on AI relevance score.
- Per-run and cumulative token/cost tracking.
- Source retry and last-good cache behavior for transient failures.
- GitHub Actions credential preflight.
- GitHub Pages deployment.
- English user interface and explicit English date formatting.

## Paper metadata enrichment

PaperDaily uses a metadata-first approach rather than asking the AI to guess everything from scratch:

- **Authors:** preserved from the source record.
- **Keywords:** official/source keywords are retained when available; the AI produces a compact normalized set of 3-5 scientific keywords for each analyzed paper.
- **Paper type:** source publication types are used as strong evidence, then normalized into scientific-content labels such as `Research Article`, `Review`, `Systematic Review`, `Meta-analysis`, `Methods/Resource`, `Clinical Study`, `Clinical Trial`, `Case Report`, `Protocol`, `Commentary/Perspective`, `Editorial`, or `Other`.

`Preprint` is treated as publication status rather than scientific paper type. A bioRxiv, medRxiv, or arXiv paper is therefore still classified by content, for example as `Research Article`, `Review`, or `Methods/Resource`; its source already indicates that it is a preprint.

This enrichment runs with the summary stage, so it does not change the dedicated relevance-ranking prompt.

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

The three most important paper-count controls are:

```yaml
prefilter:
  # Free local shortlist size after deterministic relevance filtering.
  max_candidates: 40

ai:
  # Maximum number of shortlisted papers actually sent to the AI.
  # Every analyzed paper is ranked, summarized, keyworded, and classified.
  max_analyzed: 40

site:
  # Number of analyzed papers expanded by default on the daily page.
  # Remaining analyzed papers are placed in a collapsed section.
  featured_count: 25
```

With the default `40 -> 40 -> 25` configuration, PaperDaily keeps up to 40 papers after the free local prefilter, sends up to 40 to the AI for ranking and enrichment, shows the highest-ranked 25 immediately, and keeps the remaining 15 collapsed.

You can change the stages independently. For example:

```yaml
prefilter:
  max_candidates: 80

ai:
  max_analyzed: 50

site:
  featured_count: 20
```

This creates an 80-paper local shortlist, analyzes the top 50 of that shortlist, shows the best 20 immediately, and collapses the remaining 30 analyzed papers.

If `ai.max_analyzed` is larger than `prefilter.max_candidates`, the actual AI-analysis count is naturally limited by the available local shortlist.

Other configurable fields include:

- timezone;
- broad discovery terms;
- arXiv categories;
- deterministic prefilter anchors, weights, penalties, and boosts;
- AI provider and model;
- researcher interest profile;
- token pricing used by the cost dashboard.

See `config.template.yaml` for a generic starting configuration.

## Homepage behavior

Each date card shows:

- the total number of unique papers discovered that day;
- the configured featured/additional-paper split;
- the latest update time;
- the Top 5 paper titles for that date.

The sidebar contains only **Monthly Top 5**, calculated from the highest AI relevance scores over the past 30 days.

## Daily page behavior

A daily page shows:

- total unique papers discovered;
- PubMed, bioRxiv, medRxiv, and arXiv retrieval totals;
- update time;
- papers sorted from highest to lowest relevance;
- the configured number of featured papers expanded;
- remaining analyzed papers collapsed by default;
- source, paper type, relevance score, title, authors, 3-5 keywords, compact AI summary, and source link for each paper.

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
