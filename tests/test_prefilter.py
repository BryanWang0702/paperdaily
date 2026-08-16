import unittest

from src.models import Paper
from src.prefilter import prefilter_papers, relevance_score


class TestPrefilter(unittest.TestCase):
    def test_sleep_homeostasis_outranks_generic_eeg(self):
        sleep = Paper(
            source="pubmed",
            source_id="1",
            title="NREM sleep homeostasis after sleep deprivation in mice",
            abstract="Slow-wave activity and NREM rebound were measured after deprivation.",
        )
        generic = Paper(
            source="pubmed",
            source_id="2",
            title="EEG biomarkers in epilepsy",
            abstract="Electroencephalography was recorded in patients with seizures.",
        )
        self.assertGreater(relevance_score(sleep), relevance_score(generic))

    def test_candidate_cap(self):
        papers = [
            Paper(
                source="pubmed",
                source_id=str(i),
                title=f"Sleep homeostasis and NREM study {i}",
                abstract="sleep deprivation delta power mouse",
            )
            for i in range(20)
        ]
        result = prefilter_papers(papers, {"prefilter": {"max_candidates": 7, "min_score": 0}})
        self.assertEqual(len(result), 7)


if __name__ == "__main__":
    unittest.main()
