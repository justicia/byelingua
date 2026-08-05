import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from api.index import canonical_url, collect_website, country_from_language, country_from_url, validate_subscription


class ApiTests(unittest.TestCase):
    def test_canonical_url_removes_tracking(self):
        self.assertEqual(canonical_url("https://example.com/news/?utm_source=x#top"), "https://example.com/news")

    def test_country_detection(self):
        self.assertEqual(country_from_url("https://scherzo.es/news"), "es")
        self.assertEqual(country_from_url("https://example.co.uk/news"), "gb")
        self.assertEqual(country_from_url("https://example.com/news"), "other")
        self.assertEqual(country_from_language("de-DE"), "de")

    @patch("api.index.fetch")
    def test_plain_website_is_accepted(self, fetch):
        fetch.return_value = Mock(content=b"<html><head></head><body></body></html>", text="<html></html>", headers={})
        result = validate_subscription({"url": "https://example.de/", "country": "auto", "mode": "summary"})
        self.assertEqual(result["source_type"], "website")
        self.assertEqual(result["country"], "de")

    @patch("api.index.fetch")
    def test_website_candidates_are_same_domain_and_unique(self, fetch):
        fetch.return_value = Mock(content=b'''<article><h2><a href="/one/">A valid music article title</a></h2></article>
        <h2><a href="/one/?ref=home">A valid music article title</a></h2><h2><a href="https://bad.test/x">External music article title</a></h2>''')
        subscription = {"url": "https://example.com/", "source_type": "website"}
        items = collect_website(subscription, set(), 5)
        self.assertEqual([item["url"] for item in items], ["https://example.com/one"])


if __name__ == "__main__":
    unittest.main()
