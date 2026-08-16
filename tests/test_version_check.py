import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import local_app


class TestVersionCheck(unittest.TestCase):
    def test_semantic_version_comparison(self):
        self.assertGreater(local_app._version_tuple("0.5.1"), local_app._version_tuple("0.5.0"))
        self.assertEqual(local_app._version_tuple("v0.5.0"), local_app._version_tuple("0.5.0"))

    def test_update_manifest_marks_newer_version(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "latest_version": "0.6.0",
            "download_url": "https://example.test/PaperDaily-Windows.zip",
        }
        config = {"local": {"version_check": True, "version_manifest_url": "https://example.test/version.json"}}
        with tempfile.TemporaryDirectory() as temp:
            status_file = Path(temp) / "local_status.json"
            with patch.object(local_app, "LOCAL_STATUS_FILE", status_file), \
                 patch.object(local_app, "_app_version", return_value="0.5.0"), \
                 patch.object(local_app.requests, "get", return_value=response):
                result = local_app._check_version(config)
            self.assertTrue(result["update_available"])
            saved = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["latest_version"], "0.6.0")

    def test_version_failure_is_non_blocking_status(self):
        config = {"local": {"version_check": True}}
        with tempfile.TemporaryDirectory() as temp:
            status_file = Path(temp) / "local_status.json"
            with patch.object(local_app, "LOCAL_STATUS_FILE", status_file), \
                 patch.object(local_app, "_app_version", return_value="0.5.0"), \
                 patch.object(local_app.requests, "get", side_effect=RuntimeError("offline")):
                result = local_app._check_version(config)
            self.assertEqual(result["check_status"], "error")
            self.assertFalse(result["update_available"])


if __name__ == "__main__":
    unittest.main()
