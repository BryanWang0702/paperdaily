import os
import unittest
from unittest.mock import patch

from src.ai_rank import _extract_output_text, apply_ai_ranking
from src.models import Paper


class TestAIRanking(unittest.TestCase):
    def test_missing_key_is_safe_fallback(self):
        papers = [Paper(source="pubmed", source_id="1", title="Sleep homeostasis")]
        config = {"ai": {"enabled": True, "interest_profile": "sleep", "model": "gpt-5.6"}}
        with patch.dict(os.environ, {}, clear=True):
            meta = apply_ai_ranking(papers, config)
        self.assertFalse(meta["enabled"])
        self.assertEqual(meta["status"], "missing_api_key")
        self.assertNotIn("ai", papers[0].extra)

    def test_extract_output_text(self):
        payload = {
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": '{"items": []}'}]}
            ]
        }
        self.assertEqual(_extract_output_text(payload), '{"items": []}')


if __name__ == "__main__":
    unittest.main()
