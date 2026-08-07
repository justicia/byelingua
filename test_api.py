import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from api.index import backfill_bilingual_article, canonical_url, collect_website, country_from_language, country_from_url, delete_article, extract_wechat_article, fetch_wechat_from_exporter, fetch_wechat_from_proxy, import_wechat_article, normalize_wechat_url, paris_schedule_due, public_subscriptions, retranslate_article, run_daily_digest, run_personal_digest, save_public_subscription, set_public_subscription_enabled, supabase_service, translate_article, translate_backfill_article, translate_bilingual_article, validate_subscription


class ApiTests(unittest.TestCase):
    def test_paris_schedule_handles_summer_and_winter_time(self):
        self.assertTrue(paris_schedule_due(datetime(2026, 8, 6, 7, 30, tzinfo=timezone.utc)))
        self.assertFalse(paris_schedule_due(datetime(2026, 8, 6, 8, 30, tzinfo=timezone.utc)))
        self.assertTrue(paris_schedule_due(datetime(2026, 1, 6, 8, 30, tzinfo=timezone.utc)))

    @patch("api.index.translate_article")
    @patch("api.index.extract_article")
    @patch("api.index.collect_new_articles")
    @patch("api.index.supabase_service")
    @patch("api.index.personal_payload")
    def test_personal_digest_processes_three_articles_in_saved_language(self, payload, service, collect, extract, translate):
        subscriptions = [{"id":str(i),"name":f"Source {i}","country":"fr","language":"zh","mode":"translate","enabled":True} for i in range(3)]
        personal = {"profile":{"status":"active","preferred_language":"fr","daily_update_limit":1,"monthly_character_limit":100000,"used_characters":0},"subscriptions":subscriptions,"articles":[]}
        payload.side_effect = [personal, personal]
        service.return_value = []
        collect.side_effect = lambda subscription, _seen, _limit: [{"title":f"Article {subscription['id']}","url":f"https://example.com/{subscription['id']}","published":"","feed_text":""}]
        extract.return_value = ("A sufficiently long article body for translation. " * 8, "")
        translate.return_value = {"title":"Titre","content":"Contenu"}
        result = run_personal_digest("user", article_limit=3)
        self.assertEqual(result["processed"], 3)
        self.assertEqual(translate.call_count, 3)
        self.assertTrue(all(call.args[1] == "fr" for call in translate.call_args_list))

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

    @patch("api.index.fetch_wechat_from_exporter")
    @patch("api.index.fetch")
    def test_wechat_uses_exporter_when_direct_page_has_no_article(self, fetch, exporter):
        fetch.return_value = Mock(content=b"<html><body>blocked</body></html>")
        body = "Exporter recovered this sufficiently long WeChat article body. " * 8
        exporter.return_value = f'''<meta property="og:title" content="Recovered title">
        <meta name="author" content="Recovered account"><div id="js_content">{body}</div>'''.encode()
        article = extract_wechat_article("https://mp.weixin.qq.com/s/example")
        self.assertEqual(article["title"], "Recovered title")
        self.assertEqual(article["source"], "Recovered account")
        exporter.assert_called_once()

    @patch.dict("api.index.os.environ", {"WECHAT_EXPORTER_AUTH_KEY":"secret"})
    @patch("api.index.SESSION.get")
    def test_exporter_request_encodes_url_and_sends_optional_auth(self, get):
        get.return_value = Mock(content=b"ok")
        fetch_wechat_from_exporter("https://mp.weixin.qq.com/s?__biz=a&mid=1")
        request_url = get.call_args.args[0]
        self.assertIn("url=https%3A%2F%2Fmp.weixin.qq.com%2Fs%3F__biz%3Da%26mid%3D1", request_url)
        self.assertEqual(get.call_args.kwargs["headers"], {"X-Auth-Key":"secret"})

    @patch.dict("api.index.os.environ", {
        "WECHAT_EXPORTER_CF_ACCESS_CLIENT_ID":"client-id",
        "WECHAT_EXPORTER_CF_ACCESS_CLIENT_SECRET":"client-secret",
    }, clear=False)
    @patch("api.index.SESSION.get")
    def test_exporter_request_supports_cloudflare_access_service_token(self, get):
        get.return_value = Mock(content=b"ok")
        fetch_wechat_from_exporter("https://mp.weixin.qq.com/s/example")
        headers = get.call_args.kwargs["headers"]
        self.assertEqual(headers["CF-Access-Client-Id"], "client-id")
        self.assertEqual(headers["CF-Access-Client-Secret"], "client-secret")

    @patch.dict("api.index.os.environ", {"WECHAT_PROXY_URL":"https://wx.bye-lingua.site"})
    @patch("api.index.SESSION.get")
    def test_private_proxy_request_uses_mp_preset(self, get):
        get.return_value = Mock(content=b"ok")
        fetch_wechat_from_proxy("https://mp.weixin.qq.com/s?__biz=a&mid=1")
        request_url = get.call_args.args[0]
        self.assertTrue(request_url.startswith("https://wx.bye-lingua.site?url="))
        self.assertIn("%26mid%3D1", request_url)
        self.assertTrue(request_url.endswith("&preset=mp"))

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

    @patch("api.index.extract_wechat_article")
    @patch("api.index.translate_article")
    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_wechat_keeps_chinese_source_and_custom_english_translation(self, load, save, translate, extract):
        load.return_value = {"updated_at":"","articles":[]}
        extract.return_value = {"title":"中文标题","source":"原公众号","url":"https://mp.weixin.qq.com/s/example","published":"","cover":"","text":"中文全文" * 100}
        translate.return_value = {"title":"English title","content":"English full text"}
        result = import_wechat_article({"url":"https://mp.weixin.qq.com/s/example","language":"en","author_label":"作者甲","category":"歌剧","published":"2026-08-01T20:00:00","translation_instruction":"Use British English"})
        article = result["article"]
        self.assertEqual(article["contents"]["zh"], "中文全文" * 100)
        self.assertEqual(article["contents"]["en"], "English full text")
        self.assertEqual(article["author_label"], "作者甲")
        self.assertEqual(article["category"], "歌剧")
        translate.assert_called_once_with("中文全文" * 100, "en", "translate", "中文标题", "Use British English")

    @patch("api.index.extract_wechat_article")
    @patch("api.index.translate_article")
    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_existing_wechat_adds_language_from_archived_chinese(self, load, save, translate, extract):
        url = "https://mp.weixin.qq.com/s/example"
        existing = {"id":"x","kind":"wechat","url":url,"original_title":"Chinese title","translations":{"zh":"Archived Chinese body"},"translated_titles":{"zh":"Chinese title"}}
        load.return_value = {"updated_at":"","articles":[existing]}
        translate.return_value = {"title":"French title","content":"French body"}
        result = import_wechat_article({"url":url,"language":"fr"})
        extract.assert_not_called()
        translate.assert_called_once_with("Archived Chinese body", "fr", "translate", "Chinese title", "")
        self.assertEqual(result["article"]["translations"]["fr"], "French body")

    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_existing_wechat_metadata_can_be_edited_without_retranslation(self, load, save):
        existing = {"id":"x","url":"https://mp.weixin.qq.com/s/example","translations":{"en":"English"},"source":"Old"}
        load.return_value = {"updated_at":"","articles":[existing]}
        result = import_wechat_article({"url":existing["url"],"language":"en","author_label":"New label","category":"评论"})
        self.assertTrue(result["reused"])
        self.assertEqual(existing["author_label"], "New label")
        self.assertEqual(existing["category"], "评论")
        save.assert_called_once()

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
        run.assert_called_once_with(subscription_override=validate.return_value)
        self.assertEqual(result["update"]["processed"], 1)
        self.assertEqual(save.call_args.args[0], "byelingua/config.json")

    @patch("api.index.save_blob_json")
    @patch("api.index.load_config")
    def test_admin_can_disable_public_subscription(self, load_config, save):
        load_config.return_value = {"subscriptions":[{"id":"source","enabled":True}]}
        result = set_public_subscription_enabled("source", False)
        self.assertFalse(result["enabled"])
        self.assertFalse(save.call_args.args[1]["subscriptions"][0]["enabled"])

    @patch("api.index.run_daily_digest")
    @patch("api.index.save_blob_json")
    @patch("api.index.validate_subscription")
    @patch("api.index.load_config")
    def test_editing_public_subscription_replaces_old_id(self, load_config, validate, save, run):
        load_config.return_value = {"subscriptions":[{"id":"old","name":"Old"},{"id":"keep","name":"Keep"}]}
        validate.return_value = {"id":"new","name":"New","country":"fr","url":"https://new.test","feed_url":"https://new.test/feed","source_type":"rss","mode":"summary","enabled":True}
        run.return_value = {"processed":0,"items":0,"errors":[],"source":"new"}
        save_public_subscription({"url":"https://new.test"}, "old")
        ids = [item["id"] for item in save.call_args.args[1]["subscriptions"]]
        self.assertEqual(ids, ["keep", "new"])

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

    @patch("api.index.extract_wechat_article")
    @patch("api.index.translate_bilingual_article")
    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_retranslate_wechat_uses_archived_chinese_without_refetch(self, load, save, translate, extract):
        load.return_value = {"articles":[{"id":"wx","kind":"wechat","url":"https://mp.weixin.qq.com/s/example","original_title":"Chinese title","translations":{"zh":"Archived Chinese body"},"result":"Archived Chinese body"}]}
        translate.return_value = {"titles":{"zh":"Chinese title","en":"English title"},"contents":{"zh":"Archived Chinese body","en":"English body"}}
        retranslate_article("wx")
        extract.assert_not_called()
        translate.assert_called_once_with("Archived Chinese body", "Chinese title", "translate")


if __name__ == "__main__":
    unittest.main()
