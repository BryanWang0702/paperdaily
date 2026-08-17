# Multiple research topics

PaperDaily 0.6 can maintain several independent research interests in one installation.

## Configuration layout

`config.yaml` contains settings shared by the whole installation: API provider, schedule, source limits, theme, and default AI batch sizes.

Each research project lives in `topics/`:

```text
config.yaml
topics/
  sleep-homeostasis.yaml
  eeg-methods.yaml
  your-next-project.yaml
```

Enable the feature in `config.yaml`:

```yaml
topics:
  enabled: true
  directory: topics
  default: sleep-homeostasis
```

A topic file only needs to describe what differs from the shared configuration. Typical fields are:

```yaml
id: my-topic
label: My Topic
description: Short dashboard description.

discovery_terms:
  - important phrase
  - another phrase

prefilter:
  anchors: [important phrase]
  weights:
    important phrase: 15

ai:
  max_analyzed: 40
  interest_profile: |
    Explain the research questions and ranking preferences for this project.
```

`prefilter.max_candidates`, `ai.max_analyzed`, and other settings may be overridden independently by a topic.

## How the pipeline works

PaperDaily builds the union of discovery terms and arXiv categories from all enabled topics, retrieves each external source once per refresh, and deduplicates the shared result set once. It then creates an independent matching pool, deterministic shortlist, and AI relevance ranking for every topic.

A paper can therefore receive different relevance scores in different projects. AI caches are isolated by topic so one project's ranking never overwrites another project's ranking.

The shared source result limit can scale with the number of topics:

```yaml
topics:
  scale_source_limit: true
  max_shared_source_results: 500
```

This reduces the risk that one broad topic crowds another topic out of the shared retrieval set.

## Dashboard behavior

The homepage and daily pages include a Topic selector. Switching topics changes:

- the daily archive cards;
- Monthly Top 5;
- daily relevance ordering;
- the highlighted/additional paper split;
- keyword shortcuts and search context;
- topic-matching source totals.

The selected topic is remembered in that browser.

## Adding another project

Copy one of the existing files in `topics/`, give it a unique `id`, and edit its discovery terms, prefilter rules, and AI interest profile. A committed `topics/*.yaml` change immediately triggers the hosted refresh. In the standalone edition, the background watcher also fingerprints topic files and refreshes after a saved change.

## Backward compatibility

Multi-topic behavior is opt-in. Repositories whose `config.yaml` does not explicitly contain `topics.enabled: true` continue to run as a single-topic PaperDaily installation.
