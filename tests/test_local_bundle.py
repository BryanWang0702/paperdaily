import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.build_local_bundle import build


class TestLocalBundle(unittest.TestCase):
    def test_bundle_contains_launchers_but_never_private_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "PaperDaily-local.zip"
            build(output)
            self.assertTrue(output.exists())
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())

            self.assertIn("PaperDaily-local/config.yaml", names)
            self.assertIn("PaperDaily-local/local_app.py", names)
            self.assertIn("PaperDaily-local/api_token.example.txt", names)
            self.assertIn("PaperDaily-local/START_PAPERDAILY_WINDOWS.bat", names)
            self.assertIn("PaperDaily-local/site/index.html", names)
            self.assertIn("PaperDaily-local/README_LOCAL.md", names)
            self.assertIn("PaperDaily-local/README_LOCAL.zh-CN.md", names)
            self.assertFalse(any(name.endswith("api_token.txt") for name in names))
            self.assertFalse(any(name.endswith("local_state.json") for name in names))


if __name__ == "__main__":
    unittest.main()
