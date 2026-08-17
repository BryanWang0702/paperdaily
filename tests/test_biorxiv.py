import unittest
from unittest.mock import Mock

from src.fetch_biorxiv import _decode_json_response, _parse_authors


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


class TestPreprintSourceDiagnostics(unittest.TestCase):
    def test_valid_empty_collection_is_not_an_error(self):
        response = Mock()
        response.status_code = 200
        response.text = '{"collection": [], "messages": [{"total": 0}]}'
        response.json.return_value = {"collection": [], "messages": [{"total": 0}]}
        payload = _decode_json_response(response, "https://example.test")
        self.assertEqual(payload["collection"], [])

    def test_empty_body_has_clear_error(self):
        response = Mock()
        response.status_code = 200
        response.text = "   "
        with self.assertRaisesRegex(RuntimeError, "empty response body"):
            _decode_json_response(response, "https://example.test")

    def test_html_body_has_clear_invalid_json_error(self):
        response = Mock()
        response.status_code = 200
        response.text = "<html>temporary upstream error</html>"
        response.headers = {"Content-Type": "text/html"}
        response.json.side_effect = ValueError("not json")
        with self.assertRaisesRegex(RuntimeError, "invalid JSON response"):
            _decode_json_response(response, "https://example.test")


if __name__ == "__main__":
    unittest.main()
