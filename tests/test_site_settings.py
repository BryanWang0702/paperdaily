import unittest

from src.site_settings import build_site_settings


class TestSiteSettings(unittest.TestCase):
    def test_defaults_hide_billing_and_use_khaki(self):
        settings = build_site_settings({"site": {}})
        self.assertFalse(settings["billing"]["show"])
        self.assertEqual(settings["theme"]["preset"], "khaki")

    def test_custom_theme_passes_supported_palette_fields(self):
        settings = build_site_settings({
            "site": {
                "show_billing": True,
                "theme": "custom",
                "custom_theme": {
                    "background": "#000000",
                    "surface": "#111111",
                    "text": "#ffffff",
                    "ignored": "value",
                },
            }
        })
        self.assertTrue(settings["billing"]["show"])
        self.assertEqual(settings["theme"]["preset"], "custom")
        self.assertEqual(settings["theme"]["custom"]["background"], "#000000")
        self.assertNotIn("ignored", settings["theme"]["custom"])


if __name__ == "__main__":
    unittest.main()
