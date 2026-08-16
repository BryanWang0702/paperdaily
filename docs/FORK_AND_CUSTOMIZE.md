# Fork and Customize PaperDaily

PaperDaily is designed to be forked and adapted to another research field without changing the core Python pipeline.

This guide shows how to create your own literature radar, connect an AI provider, customize the scientific domain, and publish the result with GitHub Pages.

## 1. Fork the repository

1. Open the PaperDaily repository on GitHub.
2. Click **Fork**.
3. Choose your account or organization.
4. Keep the repository name `paperdaily`, or rename it if you prefer.
5. Open the **Actions** tab and enable workflows if GitHub asks you to do so.

## 2. Enable GitHub Pages

Open:

**Settings -> Pages -> Build and deployment**

Set **Source** to **GitHub Actions**.

A project repository named `paperdaily` will normally be available at:

```text
https://YOUR_GITHUB_USERNAME.github.io/paperdaily/
```

If your GitHub user site already uses a custom domain, the project can be served under that domain as a subpath.

## 3. Add an AI API key

PaperDaily supports:

- DeepSeek, the default provider;
- OpenAI;
- other OpenAI-compatible Chat Completions endpoints.

### DeepSeek

Create this repository secret:

```text
DEEPSEEK_API_KEY
```

Add it under:

**Settings -> Secrets and variables -> Actions -> Repository secrets**

### OpenAI

Change `config.yaml`:

```yaml
ai:
  enabled: true
  provider: openai
  model: YOUR_MODEL_NAME
  api_key_env: OPENAI_API_KEY
```

Then add the repository secret:

```text
OPENAI_API_KEY
```

### Other OpenAI-compatible providers

Use a generic secret:

```text
LLM_API_KEY
```

and configure:

```yaml
ai:
  enabled: true
  provider: custom
  model: YOUR_MODEL_NAME
  base_url: https://YOUR_PROVIDER.example/v1
  api_key_env: LLM_API_KEY
```

Never commit API keys to the repository.

## 4. Optional PubMed credentials

PubMed works without an NCBI API key at the current PaperDaily request volume. For larger installations, these repository secrets are recommended:

```text
NCBI_API_KEY
PUBMED_EMAIL
```

bioRxiv, medRxiv, and arXiv do not require API keys for the current implementation.

## 5. Start from the generic configuration

The repository includes:

```text
config.template.yaml
```

Use it as a reference when replacing the default sleep-neuroscience profile.

## 6. Change the research domain

Most scientific customization happens in `config.yaml`.

### Discovery terms

Keep retrieval reasonably broad:

```yaml
discovery_terms:
  - pancreatic cancer
  - tumor microenvironment
  - immunotherapy
  - single-cell
```

### arXiv categories

Choose categories relevant to your field:

```yaml
arxiv:
  categories:
    - q-bio.BM
    - q-bio.GN
    - stat.ML
```

### Deterministic prefilter

The prefilter reduces the broad retrieval pool before any paid AI call.

Example:

```yaml
prefilter:
  enabled: true
  max_candidates: 40
  min_score: 8
  title_multiplier: 3
  missing_anchor_penalty: 18

  anchors:
    - cancer
    - tumor
    - oncology

  weights:
    pancreatic cancer: 15
    tumor microenvironment: 12
    immunotherapy: 10
    single-cell: 8
    spatial transcriptomics: 8

  boosts:
    - any_terms: [mouse, mice, organoid, patient-derived]
      bonus: 4
      require_anchor: true
```

No Python edit is required for these domain rules.

### AI interest profile

Write the interest profile as if you were briefing a research assistant:

```yaml
ai:
  interest_profile: |
    Primary focus: pancreatic cancer biology and translational tumor immunology.

    Highest-priority topics include tumor microenvironment, therapy resistance,
    immune evasion, single-cell and spatial profiling, organoid models, and
    biomarkers that can guide treatment selection.

    Prefer mechanistic studies and transferable methods. Give lower scores to
    broad epidemiology unless it introduces a particularly useful dataset,
    causal result, or analytical method.

    Use English for all generated topic labels, relevance reasons, and scientific descriptions.
```

The AI score measures relevance to this profile, not general scientific quality.

## 7. Configure the daily reading size

The current default is:

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

This gives the following public layout:

```text
40 ranked and summarized papers
├── ranks 1-25: visible immediately
└── ranks 26-40: collapsed by default
```

If you want a smaller installation, reduce both `max_candidates` and the AI digest size.

## 8. What the homepage shows

Each daily archive card contains:

- total unique papers discovered;
- the visible / collapsed paper split;
- update time;
- Top 5 titles for that date.

The sidebar contains only **Monthly Top 5**, based on the highest AI relevance scores over the past 30 days.

## 9. What each daily page shows

The daily page includes:

- total unique papers discovered;
- per-source retrieval totals for PubMed, bioRxiv, medRxiv, and arXiv;
- update time;
- papers sorted from highest to lowest relevance;
- source label, relevance score, title, compact AI summary, and source link;
- Top 25 visible by default;
- the remaining 15 papers in a collapsed section.

The public site does not ship full abstracts. Full paper metadata remains in `data/` for ranking, caching, debugging, and future reranking.

## 10. Set the timezone and schedule

Set your local timezone in `config.yaml`:

```yaml
timezone: Europe/London
```

GitHub Actions cron expressions are written in UTC, so update `.github/workflows/daily.yml` if you want different local run times.

The default installation runs twice per day. AI results are cached, so unchanged papers are not repeatedly paid for.

## 11. Run the pipeline manually once

Before waiting for the schedule:

1. Open **Actions**.
2. Select **Daily literature refresh**.
3. Click **Run workflow**.
4. Wait for the workflow to finish.
5. Confirm that **Deploy GitHub Pages** also finishes successfully.

The workflow includes a credential preflight. It reports only whether each required secret is present; it never prints secret values.

## 12. Local development

```bash
python -m venv .venv
pip install -r requirements.txt
python -m src.pipeline --days 3
python -m http.server 8000 -d site
```

Then open:

```text
http://localhost:8000
```

For local AI calls, set the relevant API key as an environment variable before running the pipeline.

## 13. Data layout

PaperDaily keeps two layers:

- `data/`: complete backend records, abstracts, ranking metadata, AI cache, billing data, and source recovery data;
- `site/data/`: compact public JSON for fast browsing.

This separation keeps the website fast while preserving enough backend information for debugging and future reranking.

## 14. Troubleshooting

### The site is empty

Check **Daily literature refresh** first. If it succeeds, check **Deploy GitHub Pages**.

### AI ranking says the key is missing

Verify that the repository secret name exactly matches `ai.api_key_env` in `config.yaml`.

### GitHub Pages returns 404

Confirm that **Settings -> Pages -> Source** is set to **GitHub Actions**.

### A literature source temporarily fails

PaperDaily retries transient bioRxiv/medRxiv failures and can reuse a recent last-good source cache.

### Too many irrelevant papers

Increase field-specific weights, add stronger anchors, increase `missing_anchor_penalty`, or make the AI interest profile more explicit.

### Important papers are being missed

Broaden `discovery_terms`, lower `min_score`, or increase `max_candidates`. Improve recall before making AI ranking stricter.

## 15. Recommended tuning workflow

1. Run the fork for one week with broad retrieval.
2. Inspect false positives and missed papers.
3. Adjust deterministic weights and anchors.
4. Refine the AI interest profile.
5. Adjust the daily paper count only after retrieval quality is satisfactory.

The goal is a reproducible literature radar that is useful for one researcher or one research group.
