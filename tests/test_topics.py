import tempfile
import unittest
from pathlib import Path

from src.topics import build_shared_fetch_config, load_topic_profiles


class TestTopics(unittest.TestCase):
    def test_old_config_stays_single_topic_without_explicit_enablement(self):
        profiles, default_id = load_topic_profiles({"site": {"title": "Legacy"}})
        self.assertEqual(default_id, "default")
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["label"], "Legacy")

    def test_profiles_override_filter_collections_and_union_fetch_terms(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            topics = root / "topics"
            topics.mkdir()
            (topics / "a.yaml").write_text(
                "id: a\nlabel: Topic A\ndiscovery_terms: [sleep, NREM]\nprefilter:\n  anchors: [sleep]\n  weights: {sleep: 10}\nai:\n  interest_profile: A\n",
                encoding="utf-8",
            )
            (topics / "b.yaml").write_text(
                "id: b\nlabel: Topic B\ndiscovery_terms: [EEG, signal processing]\nprefilter:\n  anchors: [EEG]\n  weights: {EEG: 12}\nai:\n  interest_profile: B\n",
                encoding="utf-8",
            )
            base = {
                "topics": {"enabled": True, "directory": "topics", "default": "b"},
                "discovery_terms": ["legacy"],
                "prefilter": {"anchors": ["legacy"], "weights": {"legacy": 99}},
                "arxiv": {"categories": ["q-bio.NC"]},
                "ai": {"provider": "deepseek", "interest_profile": "legacy"},
            }
            profiles, default_id = load_topic_profiles(base, root=root)
            self.assertEqual(default_id, "b")
            self.assertEqual([profile["id"] for profile in profiles], ["a", "b"])
            self.assertEqual(profiles[0]["config"]["prefilter"]["weights"], {"sleep": 10})
            self.assertEqual(profiles[1]["config"]["prefilter"]["weights"], {"EEG": 12})
            shared = build_shared_fetch_config(base, profiles)
            self.assertEqual(shared["discovery_terms"], ["sleep", "NREM", "EEG", "signal processing"])


if __name__ == "__main__":
    unittest.main()
