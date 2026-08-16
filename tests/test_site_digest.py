import unittest

from src.models import Paper
from src.pipeline import (
    _build_site_digest,
    _period_top,
    _runtime_ai_config,
    _select_ai_papers,
)


class TestSiteDigest(unittest.TestCase):
    def test_site_digest_keeps_source_and_featured_split(self):
        papers = []
        for index in range(40):
            paper = Paper(
                source="pubmed" if index < 30 else "biorxiv",
                source_id=str(index),
                title=f"Paper {index}",
                url=f"https://example.org/{index}",
            )
            paper.extra["ai"] = {
                "score": 100 - index,
                "summary": f"Summary {index}",
                "digest_pick": True,
            }
            papers.append(paper)

        payload = {
            "date": "2026-08-16",
            "generated_at": "2026-08-16T12:00:00+00:00",
            "raw_count": 207,
            "retrieved_source_counts": {
                "pubmed": 150,
                "biorxiv": 57,
                "medrxiv": 1,
                "arxiv": 0,
            },
            "featured_count": 25,
            "errors": {},
            "ai": {
                "enabled": True,
                "ranked_count": 40,
                "billing": {},
            },
        }

        digest = _build_site_digest(payload, papers)
        self.assertEqual(digest["total_count"], 207)
        self.assertEqual(digest["featured_count"], 25)
        self.assertEqual(digest["additional_count"], 15)
        self.assertEqual(len(digest["papers"]), 40)
        self.assertEqual(digest["papers"][0]["source"], "pubmed")
        self.assertEqual(digest["retrieved_source_counts"]["biorxiv"], 57)

    def test_monthly_top_is_limited_and_deduplicated(self):
        payloads = []
        for day in ("2026-08-15", "2026-08-16"):
            papers = []
            for index in range(8):
                papers.append({
                    "source": "pubmed",
                    "source_id": str(index),
                    "title": f"Paper {index}",
                    "url": f"https://example.org/{index}",
                    "extra": {"ai": {"score": 90 - index}},
                })
            payloads.append({"date": day, "papers": papers})

        top = _period_top(payloads, 30, 5)
        self.assertEqual(len(top), 5)
        self.assertEqual([item["score"] for item in top], [90, 89, 88, 87, 86])

    def test_ai_analysis_limit_is_independent_from_prefilter_size(self):
        prefiltered = [
            Paper(source="pubmed", source_id=str(index), title=f"Paper {index}")
            for index in range(80)
        ]
        selected, configured_limit = _select_ai_papers(
            prefiltered,
            {"ai": {"max_analyzed": 50}},
        )
        self.assertEqual(configured_limit, 50)
        self.assertEqual(len(selected), 50)
        self.assertEqual(selected[-1].source_id, "49")

    def test_ai_analysis_limit_cannot_exceed_available_shortlist(self):
        prefiltered = [
            Paper(source="pubmed", source_id=str(index), title=f"Paper {index}")
            for index in range(12)
        ]
        selected, configured_limit = _select_ai_papers(
            prefiltered,
            {"ai": {"max_analyzed": 40}},
        )
        self.assertEqual(configured_limit, 40)
        self.assertEqual(len(selected), 12)

    def test_runtime_ai_config_summarizes_every_analyzed_paper(self):
        config = {
            "ai": {
                "max_analyzed": 50,
                "provider": "deepseek",
            }
        }
        runtime = _runtime_ai_config(config, 50)
        self.assertEqual(runtime["ai"]["digest_min"], 50)
        self.assertEqual(runtime["ai"]["digest_max"], 50)
        self.assertEqual(runtime["ai"]["digest_score_threshold"], 0)
        self.assertNotIn("digest_min", config["ai"])


if __name__ == "__main__":
    unittest.main()
