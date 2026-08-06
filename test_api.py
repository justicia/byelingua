import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from api.index import canonical_url, collect_website, country_from_language, country_from_url, extract_wechat_article, import_wechat_article, normalize_wechat_url, validate_subscription


class ApiTests(unittest.TestCase):
    def test_canonical_url_removes_tracking(self):
        self.assertEqual(canonical_url("https://example.com/news/?utm_source=x#top"), "https://example.com/news")

    def test_wechat_url_retains_legacy_article_query(self):
        url = "https://mp.weixin.qq.com/s?__biz=abc&mid=123#wechat_redirect"
        self.assertEqual(normalize_wechat_url(url), "https://mp.weixin.qq.com/s?__biz=abc&mid=123")

    def test_wechat_url_rejects_other_hosts(self):
        with self.assertRaises(ValueError):
            normalize_wechat_url("https://example.com/article")

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

    @patch("api.index.fetch")
    def test_extracts_wechat_article(self, fetch):
        body = "This is a sufficiently long WeChat article body for extraction testing. " * 8
        html = f'''<html><head><meta property="og:title" content="Test article">
        <meta name="author" content="Test account"></head><body><div id="js_content">{body}</div></body></html>'''
        fetch.return_value = Mock(content=html.encode("utf-8"))
        article = extract_wechat_article("https://mp.weixin.qq.com/s/example")
        self.assertEqual(article["title"], "Test article")
        self.assertEqual(article["source"], "Test account")
        self.assertGreater(len(article["text"]), 200)

    @patch("api.index.translate_article")
    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_existing_wechat_translation_reuses_result(self, load, save, translate):
        url = "https://mp.weixin.qq.com/s/example"
        existing = {"id":"x","url":url,"translations":{"fr":"already translated"}}
        load.return_value = {"updated_at":"","articles":[existing]}
        result = import_wechat_article({"url":url,"language":"fr"})
        self.assertTrue(result["reused"])
        translate.assert_not_called()
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
