# PaperDaily

PaperDaily is a lightweight personal research radar that collects newly indexed literature, normalizes metadata, removes duplicates, and publishes a static daily dashboard.

## v0.1 scope

Daily sources:

- PubMed
- bioRxiv
- medRxiv
- arXiv

Planned weekly sources:

- Science / Nature news
- commentary / opinion
- careers

The first milestone intentionally does **not** use an LLM. It validates the ingestion pipeline first: fetch -> normalize -> deduplicate -> archive -> render.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.pipeline --days 3
```

Then open `site/index.html` or serve the directory locally:

```bash
python -m http.server 8000 -d site
```

Visit `http://localhost:8000`.

## Configuration

Edit `config.yaml` to change search terms, source limits, timezone, and dashboard settings.

PubMed uses a Create Date (`[crdt]`) overlap window rather than publication date alone. The pipeline stores stable identifiers and deduplicates by DOI/PMID/source ID so overlapping daily runs do not create duplicates.

## Automation

`.github/workflows/daily.yml` runs twice per day and commits refreshed JSON back to the repository. `.github/workflows/deploy-pages.yml` publishes the `site/` folder to GitHub Pages after changes reach `master`.

After the first merge, enable **Settings -> Pages -> Source: GitHub Actions** if GitHub does not enable it automatically.

## Next milestone

v0.2 will add relevance ranking, structured AI summaries, topic labels, and a weekly Science/Nature digest.
