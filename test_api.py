import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from api.index import backfill_bilingual_article, canonical_url, collect_website, country_from_language, country_from_url, delete_article, extract_wechat_article, import_wechat_article, normalize_wechat_url, public_subscriptions, retranslate_article, run_daily_digest, save_public_subscription, supabase_service, translate_article, translate_backfill_article, translate_bilingual_article, validate_subscription


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

    @patch("api.index.load_blob_json")
    @patch("api.index.load_config")
    def test_unknown_scheduled_source_is_rejected(self, load_config, load_blob):
        load_config.return_value = {"target_language":"zh","subscriptions":[{"id":"known","enabled":True}]}
        load_blob.side_effect = lambda _path, default: default
        with self.assertRaisesRegex(ValueError, "Unknown or disabled source"):
            run_daily_digest("missing")

    def test_public_subscriptions_only_returns_enabled_safe_fields(self):
        result = public_subscriptions({"subscriptions":[
            {"id":"one","name":"One","country":"fr","url":"https://one.test","feed_url":"https://one.test/feed","source_type":"rss","mode":"summary","enabled":True},
            {"id":"two","name":"Two","country":"de","url":"https://two.test","enabled":False},
        ]})
        self.assertEqual(result, [{"id":"one","name":"One","country":"fr","url":"https://one.test","source_type":"rss","mode":"summary"}])
        self.assertNotIn("feed_url", result[0])

    @patch("api.index.run_daily_digest")
    @patch("api.index.save_blob_json")
    @patch("api.index.validate_subscription")
    @patch("api.index.load_config")
    def test_saving_public_subscription_immediately_processes_it(self, load_config, validate, save, run):
        load_config.return_value = {"subscriptions":[]}
        validate.return_value = {"id":"new","name":"New","country":"fr","url":"https://new.test","feed_url":"https://new.test/feed","source_type":"rss","mode":"summary","enabled":True}
        run.return_value = {"processed":1,"items":1,"errors":[],"source":"new"}
        result = save_public_subscription({"url":"https://new.test"})
        run.assert_called_once_with("new")
        self.assertEqual(result["update"]["processed"], 1)
        self.assertEqual(save.call_args.args[0], "byelingua/config.json")

    @patch("api.index.supabase_settings", return_value=("https://project.supabase.co", "public", "sb_secret_test"))
    @patch("api.index.SESSION.request")
    def test_supabase_secret_uses_server_user_agent(self, request, _settings):
        request.return_value = Mock(ok=True, content=b"[]", json=Mock(return_value=[]))
        supabase_service("GET", "/rest/v1/profiles")
        headers = request.call_args.kwargs["headers"]
        self.assertEqual(headers["User-Agent"], "Byelingua-Server/3.0")
        self.assertNotIn("Authorization", headers)

    @patch("api.index.OpenAI")
    def test_title_and_content_use_one_translation_call(self, openai):
        response = Mock(output_text='{"title":"Translated title","content":"Translated content"}')
        openai.return_value.responses.create.return_value = response
        result = translate_article("Original body", "en", "translate", "Original title")
        self.assertEqual(result, {"title":"Translated title","content":"Translated content"})
        openai.return_value.responses.create.assert_called_once()

    @patch("api.index.OpenAI")
    def test_future_public_article_translates_both_languages_once(self, openai):
        response = Mock(output_text='{"titles":{"zh":"中文标题","en":"English title"},"contents":{"zh":"中文正文","en":"English body"}}')
        openai.return_value.responses.create.return_value = response
        result = translate_bilingual_article("Original body", "Original title", "translate")
        self.assertEqual(result["titles"]["en"], "English title")
        self.assertEqual(result["contents"]["zh"], "中文正文")
        openai.return_value.responses.create.assert_called_once()

    @patch("api.index.OpenAI")
    def test_backfill_translation_returns_titles_and_english_body_once(self, openai):
        response = Mock(output_text='{"titles":{"zh":"中文标题","en":"English title"},"content_en":"English body"}')
        openai.return_value.responses.create.return_value = response
        result = translate_backfill_article("已有中文正文", "Original title")
        self.assertEqual(result["content_en"], "English body")
        openai.return_value.responses.create.assert_called_once()

    @patch("api.index.translate_backfill_article")
    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_backfill_preserves_existing_chinese_body(self, load, save, translate):
        load.return_value = {"updated_at":"","articles":[{"id":"old","title":"Original","result":"已有中文正文"}]}
        translate.return_value = {"titles":{"zh":"中文标题","en":"English title"},"content_en":"English body"}
        result = backfill_bilingual_article()
        saved = save.call_args.args[1]["articles"][0]
        self.assertEqual(saved["contents"], {"zh":"已有中文正文","en":"English body"})
        self.assertEqual(saved["result"], "已有中文正文")
        self.assertEqual(result["remaining"], 0)

    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_delete_and_resync_removes_article_and_seen_url(self, load, save):
        load.side_effect = [
            {"updated_at":"","articles":[{"id":"old","url":"https://example.com/story"}]},
            {"urls":["https://example.com/story","https://example.com/other"]},
        ]
        result = delete_article("old", True)
        self.assertTrue(result["resync_allowed"])
        self.assertEqual(save.call_args_list[0].args[1]["articles"], [])
        self.assertEqual(save.call_args_list[1].args[1]["urls"], ["https://example.com/other"])

    @patch("api.index.translate_bilingual_article")
    @patch("api.index.extract_article")
    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_retranslate_refetches_and_overwrites_bilingual_content(self, load, save, extract, translate):
        load.return_value = {"articles":[{"id":"old","url":"https://example.com/story","title":"Old","result":"旧内容","mode":"summary"}]}
        extract.return_value = ("Fresh original text", "")
        translate.return_value = {"titles":{"zh":"新标题","en":"New title"},"contents":{"zh":"新正文","en":"New body"}}
        result = retranslate_article("old")
        self.assertTrue(result["retranslated"])
        saved = save.call_args.args[1]["articles"][0]
        self.assertEqual(saved["contents"]["en"], "New body")
        translate.assert_called_once_with("Fresh original text", "Old", "summary")


if __name__ == "__main__":
    unittest.main()
