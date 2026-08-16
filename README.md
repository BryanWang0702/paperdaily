# PaperDaily

PaperDaily is a lightweight personal research radar that collects newly indexed literature, removes duplicates, ranks papers for a specific research profile, and publishes a persistent daily archive.

## Daily sources

- PubMed
- bioRxiv
- medRxiv
- arXiv

Planned weekly sources:

- Science / Nature news
- commentary / opinion
- careers

## Daily archive

Every calendar day is stored as `data/YYYY-MM-DD.json`. The homepage loads a small archive manifest, and each date opens a dedicated daily digest. The twice-daily refresh updates the current day's issue while older issues remain unchanged.

## Personalized AI ranking (v0.2)

When an `OPENAI_API_KEY` environment variable is available, the pipeline uses the OpenAI Responses API with Structured Outputs to:

1. score every candidate 0-100 against the research profile in `config.yaml`;
2. label its topic and give a short relevance reason;
3. summarize only the daily top papers;
4. cache scores/summaries in `data/ai_cache.json`, so unchanged papers are not paid for again on the second daily run.

If no API key is present, the ingestion pipeline still succeeds and publishes the raw feed.

For GitHub Actions, add the key at **Settings -> Secrets and variables -> Actions -> New repository secret** with the name `OPENAI_API_KEY`. Do not put the key in `config.yaml` or commit it to the repository.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.pipeline --days 3
```

Then serve the static site locally:

```bash
python -m http.server 8000 -d site
```

Visit `http://localhost:8000`.

## Configuration

Edit `config.yaml` to change search terms, source limits, timezone, the researcher interest profile, the ranking model, and the number of top papers.

PubMed uses a Create Date (`[crdt]`) overlap window rather than publication date alone. The pipeline deduplicates by DOI/PMID/source ID so overlapping daily runs do not create duplicate records.

## Automation

`.github/workflows/daily.yml` runs at 08:15 and 20:15 Asia/Taipei and commits refreshed JSON back to the repository. `.github/workflows/deploy-pages.yml` publishes the site and date archives to GitHub Pages after successful refreshes.
