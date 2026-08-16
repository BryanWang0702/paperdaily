# PaperDaily UI Specification

## Homepage

Each daily archive card shows:

- English-formatted date and weekday;
- total number of unique papers discovered;
- number of highlighted papers;
- number of additional papers;
- latest update time;
- Top 5 titles for that date.

The homepage sidebar contains only **Monthly Top 5**, based on the highest AI relevance scores over the past 30 days.

Internal pipeline terms such as the deterministic 40-paper prefilter are not shown on homepage cards.

## Daily page

The daily page shows:

- English-formatted date and weekday;
- total number of unique papers discovered;
- latest update time;
- PubMed, bioRxiv, medRxiv, and arXiv retrieval totals;
- papers sorted from highest to lowest AI relevance;
- source, relevance score, title, compact summary, and link for every displayed paper.

The first 25 papers are expanded by default. Ranks 26-40 are contained in a collapsed section.

## Language

All PaperDaily interface text and generated presentation metadata should be English. Publication titles are preserved as supplied by the original source and are not translated automatically.
