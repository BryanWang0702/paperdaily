import unittest

from src.models import Paper
from src.prefilter import prefilter_papers, relevance_score


SLEEP_PREFILTER = {
    "title_multiplier": 3,
    "missing_anchor_penalty": 18,
    "anchors": ["sleep", "nrem", "rem sleep"],
    "weights": {
        "sleep homeostasis": 14,
        "sleep deprivation": 14,
        "nrem": 14,
        "eeg": 7,
    },
    "boosts": [
        {"any_terms": ["mouse", "mice", "rat"], "bonus": 4, "require_anchor": True},
    ],
}


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
        self.assertGreater(
            relevance_score(sleep, SLEEP_PREFILTER),
            relevance_score(generic, SLEEP_PREFILTER),
        )

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
        config = {
            "prefilter": {
                **SLEEP_PREFILTER,
                "enabled": True,
                "max_candidates": 7,
                "min_score": 0,
            }
        }
        result = prefilter_papers(papers, config)
        self.assertEqual(len(result), 7)

    def test_domain_can_be_reconfigured_without_source_changes(self):
        sleep_paper = Paper(
            source="pubmed",
            source_id="sleep",
            title="Sleep homeostasis in mice",
            abstract="NREM recovery after deprivation.",
        )
        cancer_paper = Paper(
            source="pubmed",
            source_id="cancer",
            title="Single-cell biomarkers of pancreatic cancer",
            abstract="Tumor microenvironment and immunotherapy response were analyzed.",
        )
        oncology_config = {
            "anchors": ["cancer", "tumor", "oncology"],
            "missing_anchor_penalty": 20,
            "weights": {
                "pancreatic cancer": 15,
                "tumor microenvironment": 12,
                "immunotherapy": 10,
                "single-cell": 8,
            },
        }
        self.assertGreater(
            relevance_score(cancer_paper, oncology_config),
            relevance_score(sleep_paper, oncology_config),
        )


if __name__ == "__main__":
    unittest.main()
