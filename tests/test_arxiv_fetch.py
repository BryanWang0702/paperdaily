import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from src import fetch_arxiv as arxiv_module


class TestArxivFetch(unittest.TestCase):
    def test_same_window_uses_persisted_source_cache_without_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "arxiv.json"
            cache_path.write_text(
                json.dumps({
                    "window": {"start": "2026-08-15", "end": "2026-08-17"},
                    "papers": [
                        {
                            "source": "arxiv",
                            "source_id": "2608.12345v1",
                            "title": "Cached paper",
                            "abstract": "Cached abstract",
                            "authors": ["A. Author"],
                            "published_date": "2026-08-16",
                            "indexed_date": "2026-08-16",
                            "journal": "arXiv",
                            "url": "https://arxiv.org/abs/2608.12345",
                            "publication_types": ["Preprint"],
                        }
                    ],
                }),
                encoding="utf-8",
            )
            config = {
                "discovery_terms": ["sleep"],
                "arxiv": {"categories": ["q-bio.NC"], "reuse_same_window": True},
            }
            with patch.object(arxiv_module, "ARXIV_SOURCE_CACHE", cache_path), patch.object(arxiv_module.requests, "get") as get:
                papers = arxiv_module.fetch_arxiv(config, "2026-08-15", "2026-08-17")
            self.assertEqual(len(papers), 1)
            self.assertEqual(papers[0].title, "Cached paper")
            get.assert_not_called()

    def test_429_retries_and_honors_retry_after(self):
        throttled = Mock()
        throttled.status_code = 429
        throttled.headers = {"Retry-After": "7"}
        throttled.text = ""

        success = Mock()
        success.status_code = 200
        success.headers = {}
        success.text = "<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'></feed>"
        success.raise_for_status.return_value = None

        with patch.object(arxiv_module.requests, "get", side_effect=[throttled, success]) as get, patch.object(arxiv_module.time, "sleep") as sleep:
            response = arxiv_module._request_arxiv({}, {"User-Agent": "test"}, 10, [10])

        self.assertIs(response, success)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(7)

    def test_timeout_retries_before_success(self):
        success = Mock()
        success.status_code = 200
        success.headers = {}
        success.text = "<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'></feed>"
        success.raise_for_status.return_value = None

        timeout = requests.ReadTimeout("arXiv timed out")
        with patch.object(arxiv_module.requests, "get", side_effect=[timeout, success]) as get, patch.object(arxiv_module.time, "sleep") as sleep:
            response = arxiv_module._request_arxiv({}, {"User-Agent": "test"}, 10, [10])

        self.assertIs(response, success)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(10)

    def test_retry_delay_never_goes_below_three_seconds(self):
        response = Mock()
        response.headers = {"Retry-After": "1"}
        self.assertEqual(arxiv_module._retry_delay(response, 10), 3)


if __name__ == "__main__":
    unittest.main()
