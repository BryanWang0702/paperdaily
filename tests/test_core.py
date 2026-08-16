import unittest

from src.deduplicate import deduplicate, paper_key
from src.models import Paper
from src.pipeline import _period_top
from src.utils import matches_terms, normalize_doi


class CoreTests(unittest.TestCase):
    def test_normalize_doi(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1000/ABC"), "10.1000/abc")
        self.assertEqual(normalize_doi("doi: 10.1000/XYZ"), "10.1000/xyz")

    def test_keyword_matching_is_case_insensitive(self):
        self.assertTrue(matches_terms("NREM sleep and EEG dynamics", ["nrem"]))
        self.assertFalse(matches_terms("plant root development", ["sleep", "EEG"]))

    def test_deduplicate_cross_source_by_doi(self):
        a = Paper(source="pubmed", source_id="1", title="A", doi="10.1/Test")
        b = Paper(source="biorxiv", source_id="2", title="A preprint", doi="https://doi.org/10.1/test")
        result = deduplicate([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(paper_key(result[0]), "doi:10.1/test")

    def test_period_top_deduplicates_and_sorts_by_score(self):
        days = [
            {
                "date": "2026-08-16",
                "papers": [
                    {"source": "pubmed", "source_id": "1", "doi": "10.1/a", "title": "Paper A", "url": "https://a", "extra": {"ai": {"score": 90}}},
                    {"source": "pubmed", "source_id": "2", "title": "Paper B", "url": "https://b", "extra": {"ai": {"score": 96}}},
                ],
            },
            {
                "date": "2026-08-15",
                "papers": [
                    {"source": "biorxiv", "source_id": "x", "doi": "10.1/a", "title": "Paper A duplicate", "url": "https://a2", "extra": {"ai": {"score": 92}}},
                ],
            },
        ]
        ranked = _period_top(days, 7, 10)
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["title"], "Paper B")
        self.assertEqual(ranked[1]["score"], 92)


if __name__ == "__main__":
    unittest.main()
