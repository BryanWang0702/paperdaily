import unittest

from src.fetch_biorxiv import _parse_authors


class TestPreprintAuthorParsing(unittest.TestCase):
    def test_semicolon_separated_names_preserve_internal_commas(self):
        raw = "Brendstrup-Brix, K.; Iversen, O. B.; Ferdinando, H."
        self.assertEqual(
            _parse_authors(raw),
            ["Brendstrup-Brix, K.", "Iversen, O. B.", "Ferdinando, H."],
        )

    def test_single_author_is_preserved(self):
        self.assertEqual(_parse_authors("Smith, J."), ["Smith, J."])

    def test_empty_author_string(self):
        self.assertEqual(_parse_authors(""), [])


if __name__ == "__main__":
    unittest.main()
