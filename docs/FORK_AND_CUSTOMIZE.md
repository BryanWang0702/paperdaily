# Fork and Customize PaperDaily

PaperDaily is designed to be forked and adapted to another research field without changing the core Python pipeline.

This guide shows how to create your own literature radar, connect an AI provider, customize the scientific domain, and publish the result with GitHub Pages.

## 1. Fork the repository

1. Open the PaperDaily repository on GitHub.
2. Click **Fork**.
3. Choose your account or organization.
4. Keep the repository name `paperdaily`, or rename it if you prefer.

GitHub may disable Actions in a new fork until you explicitly enable them. Open the **Actions** tab and enable workflows if prompted.

## 2. Enable GitHub Pages

Open:

**Settings -> Pages -> Build and deployment**

Set **Source** to **GitHub Actions**.

For a normal project repository named `paperdaily`, the default site URL is typically:

```text
https://YOUR_GITHUB_USERNAME.github.io/paperdaily/
```

If your GitHub user site already uses a custom domain, GitHub Pages can serve the project under that domain as a subpath, for example:

```text
https://example.com/paperdaily/
```

## 3. Add the AI API key

PaperDaily currently supports:

- DeepSeek, which is the default provider.
- OpenAI.
- Other OpenAI-compatible Chat Completions endpoints with minor configuration.

### DeepSeek

Create this repository secret:

```text
DEEPSEEK_API_KEY
```

Add it under:

**Settings -> Secrets and variables -> Actions -> Repository secrets**

The default `config.yaml` already points to this secret.

### OpenAI

Change the AI section in `config.yaml`:

```yaml
ai:
  enabled: true
  provider: openai
  model: YOUR_MODEL_NAME
  api_key_env: OPENAI_API_KEY
```

Then add this repository secret:

```text
OPENAI_API_KEY
```

### Other OpenAI-compatible providers

Use a generic secret:

```text
LLM_API_KEY
```

Then configure:

```yaml
ai:
  enabled: true
  provider: custom
  model: YOUR_MODEL_NAME
  base_url: https://YOUR_PROVIDER.example/v1
  api_key_env: LLM_API_KEY
```

The GitHub Actions workflow already exposes `LLM_API_KEY` to the pipeline.

Never commit API keys to `config.yaml`, Python files, or the repository history.

## 4. Optional PubMed credentials

PubMed works without an NCBI API key at the current PaperDaily request volume. For a larger fork, the following repository secrets are recommended:

```text
NCBI_API_KEY
PUBMED_EMAIL
```

`PUBMED_EMAIL` can simply contain your contact email address.

bioRxiv, medRxiv, and arXiv do not require API keys for the current implementation.

## 5. Change the research domain

Most domain customization now happens in `config.yaml`.

There are four important layers.

### A. Discovery terms

These terms control the broad retrieval stage:

```yaml
discovery_terms:
  - pancreatic cancer
  - tumor microenvironment
  - immunotherapy
  - single-cell
```

Keep this stage relatively broad. It is better to retrieve some extra papers and let later stages remove them than to miss important papers entirely.

### B. arXiv categories

Change the arXiv categories to match your field:

```yaml
arxiv:
  categories:
    - q-bio.BM
    - q-bio.GN
    - stat.ML
```

If arXiv is not useful for your field, you can keep a narrow category list and rely more heavily on PubMed and preprint servers.

### C. Deterministic prefilter

The prefilter reduces hundreds of retrieved papers to a manageable candidate pool before the AI call.

Example oncology configuration:

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

The fields mean:

- `max_candidates`: maximum number of papers sent to the AI ranking stage.
- `min_score`: minimum deterministic score required to survive the prefilter.
- `title_multiplier`: makes important terms in titles count more than terms found only in abstracts.
- `anchors`: core field terms. Papers without any anchor can receive a penalty.
- `weights`: transparent keyword weights used by the local filter.
- `boosts`: optional bonuses for useful combinations of concepts.

No Python edit is required for these domain rules.

### D. AI interest profile

This is the most important personalization field.

Write it as if you were briefing a research assistant about what matters to you:

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
```

The AI score is not intended to measure general scientific quality. It measures relevance to this profile.

## 6. Choose the daily digest size

The default configuration ranks up to 40 candidates and summarizes roughly 25-30 papers:

```yaml
ai:
  rank_batch_size: 20
  summary_batch_size: 5
  digest_min: 25
  digest_max: 30
  digest_score_threshold: 45
```

A smaller field can use lower values. A broad field can increase the candidate cap and digest size, but this will increase API usage.

## 7. Set the timezone and schedule

Set your local timezone in `config.yaml`:

```yaml
timezone: Europe/London
```

The current GitHub Actions cron schedule is written in UTC in `.github/workflows/daily.yml`.

If you change the timezone and want different run times, update the cron expression as well.

By default, PaperDaily runs twice per day. AI results are cached, so an unchanged paper is not repeatedly paid for during the second run.

## 8. Run the pipeline manually once

Before waiting for the schedule:

1. Open **Actions**.
2. Select **Daily literature refresh**.
3. Click **Run workflow**.
4. Wait for the workflow to finish.
5. Confirm that **Deploy GitHub Pages** also finishes successfully.

The workflow includes a credential preflight. It reports only whether each secret is `SET` or `MISSING`; it never prints secret values.

## 9. Local development

Create a Python environment:

```bash
python -m venv .venv
```

Activate it and install dependencies:

```bash
pip install -r requirements.txt
```

Run the pipeline:

```bash
python -m src.pipeline --days 3
```

Serve the site locally:

```bash
python -m http.server 8000 -d site
```

Then open:

```text
http://localhost:8000
```

For local AI calls, set the relevant API key as an environment variable before running the pipeline.

## 10. What gets stored

PaperDaily keeps two layers of data:

- `data/`: the complete backend research record, including abstracts, ranking metadata, caches, and source recovery data.
- `site/data/`: compact public JSON used by the website. It contains only the fields needed for fast browsing, such as title, score, short summary, and link.

This separation keeps the public site fast while preserving enough backend information for debugging and future reranking.

## 11. Weekly and monthly rankings

The homepage includes rolling:

- Past 7 days Top 10.
- Past 30 days Top 10.

These lists reuse the existing AI relevance scores and therefore do not create additional API cost. Duplicate papers across overlapping fetch windows are removed before ranking.

## 12. Troubleshooting

### The site is empty

Check the **Daily literature refresh** workflow first. If it succeeded, check **Deploy GitHub Pages**.

### AI ranking says the key is missing

Verify that the repository secret name exactly matches `ai.api_key_env` in `config.yaml`.

### GitHub Pages returns 404

Confirm that **Settings -> Pages -> Source** is set to **GitHub Actions**.

### A literature source temporarily fails

PaperDaily retries transient bioRxiv/medRxiv failures and keeps a last-good source cache. The daily workflow can still complete while exposing the source warning in its metadata.

### Too many irrelevant papers

Increase the weight of field-specific terms, add stronger anchors, increase `missing_anchor_penalty`, or make the AI interest profile more explicit.

### Important papers are being missed

Broaden `discovery_terms`, lower the deterministic `min_score`, or increase `max_candidates`. Recall should be fixed before making the AI filter stricter.

## 13. Recommended customization workflow

A good way to tune a new fork is:

1. Run it for one week with broad retrieval.
2. Inspect false positives and missed papers.
3. Adjust deterministic weights and anchors.
4. Refine the AI interest profile.
5. Only then change digest size or score thresholds.

The goal is not to create a universally correct paper ranking. The goal is to create a reproducible literature radar that is useful for one researcher or one research group.
