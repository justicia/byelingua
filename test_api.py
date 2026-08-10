import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from api.index import backfill_bilingual_article, canonical_url, collect_website, country_from_language, country_from_url, delete_article, extract_wechat_article, fetch_wechat_direct, generate_invite_code, import_wechat_article, normalize_wechat_url, paris_schedule_due, poll_wechat_translation, public_article_from_row, public_article_to_row, public_subscriptions, register_with_invite, retranslate_article, run_daily_digest, run_personal_digest, run_scheduled_updates, save_public_articles, save_public_subscription, save_wechat_chinese, send_daily_digest, set_public_subscription_enabled, supabase_service, sync_wechat_article, translate_article, translate_backfill_article, translate_bilingual_article, translate_wechat_article, update_article_metadata, validate_subscription


class ApiTests(unittest.TestCase):
    @patch("api.index.supabase_service", return_value=[])
    def test_registration_rejects_invalid_invite(self, service):
        with self.assertRaisesRegex(ValueError, "邀请码无效"):
            register_with_invite("reader@example.com", "password", "invalid")
        service.assert_called_once()

    @patch("api.index.supabase_settings", return_value=("https://project.supabase.co", "public", "sb_secret_test"))
    @patch("api.index.SESSION.post")
    @patch("api.index.supabase_service")
    def test_registration_creates_user_and_claims_invite(self, service, post, _settings):
        service.side_effect = [
            [{"id":"invite-1","max_uses":10,"used_count":9,"child_prefix":"IDC"}],
            True,
        ]
        post.return_value = Mock(ok=True, json=Mock(return_value={"id":"user-1"}))
        result = register_with_invite("Reader@Example.com", "password", "dontaskme")
        self.assertEqual(result, {"status":"registered","user_id":"user-1"})
        self.assertEqual(post.call_args.kwargs["json"]["email"], "reader@example.com")
        self.assertEqual(post.call_args.kwargs["json"]["user_metadata"], {"invite_prefix":"IDC"})
        self.assertEqual(service.call_args_list[1].args[1], "/rest/v1/rpc/claim_invite_code")
        self.assertEqual(service.call_args_list[1].kwargs["payload"], {"p_code":"DONTASKME"})

    @patch("api.index.supabase_settings", return_value=("https://project.supabase.co", "public", "sb_secret_test"))
    @patch("api.index.SESSION.delete")
    @patch("api.index.SESSION.post")
    @patch("api.index.supabase_service")
    def test_exhausted_invite_removes_newly_created_user(self, service, post, delete, _settings):
        service.side_effect = [
            [{"id":"invite-1","max_uses":10,"used_count":9,"child_prefix":"IDC"}],
            False,
        ]
        post.return_value = Mock(ok=True, json=Mock(return_value={"id":"user-11"}))
        delete.return_value = Mock(ok=True)
        with self.assertRaisesRegex(ValueError, "邀请码无效"):
            register_with_invite("eleven@example.com", "password", "DONTASKME")
        self.assertIn("user-11", delete.call_args.args[0])

    @patch("api.index.secrets.choice", return_value="A")
    @patch("api.index.supabase_service")
    def test_generate_invite_decrements_credit_atomically(self, service, _choice):
        service.side_effect = [
            [{"invite_prefix":"IDC"}],
            [{"code":"IDC-AAAAAA","remaining_credits":1}],
        ]
        result = generate_invite_code("user-1")
        self.assertEqual(result, {"code":"IDC-AAAAAA","remaining_credits":1})
        self.assertEqual(service.call_args_list[1].kwargs["payload"]["p_user_id"], "user-1")

    def test_paris_schedule_handles_summer_and_winter_time(self):
        self.assertTrue(paris_schedule_due(datetime(2026, 8, 6, 7, 30, tzinfo=timezone.utc)))
        self.assertFalse(paris_schedule_due(datetime(2026, 8, 6, 8, 30, tzinfo=timezone.utc)))
        self.assertTrue(paris_schedule_due(datetime(2026, 1, 6, 8, 30, tzinfo=timezone.utc)))

    @patch.dict("os.environ", {"RESEND_API_KEY":"re_test","EMAIL_FROM":"Byelingua <news@example.com>"})
    @patch("api.index.SESSION.post")
    @patch("api.index.supabase_service")
    def test_daily_digest_sends_today_articles_to_profile_email(self, service, post):
        service.side_effect = [
            [{"email":"reader@example.com","preferred_language":"fr"}],
            [{"title":"Titre","canonical_url":"https://example.com/article","result":"Résumé","language":"fr","processed_at":"2026-08-10T08:00:00Z"}],
        ]
        post.return_value = Mock(ok=True, json=Mock(return_value={"id":"email_1"}))
        result = send_daily_digest("user-1")
        self.assertEqual(result, {"sent":True,"articles":1,"id":"email_1"})
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["to"], ["reader@example.com"])
        self.assertIn("Titre", payload["html"])
        self.assertIn("https://example.com/article", payload["html"])

    @patch.dict("os.environ", {"RESEND_API_KEY":"re_test","EMAIL_FROM":"Byelingua <news@example.com>"})
    @patch("api.index.SESSION.post")
    @patch("api.index.supabase_service")
    def test_daily_digest_skips_user_without_today_articles(self, service, post):
        service.side_effect = [
            [{"email":"reader@example.com","preferred_language":"en"}],
            [],
        ]
        self.assertEqual(send_daily_digest("user-1"), {"sent":False,"articles":0})
        post.assert_not_called()

    @patch("api.index.save_scheduled_state")
    @patch("api.index.load_scheduled_state", return_value={"paris_date":""})
    @patch("api.index.send_daily_digest")
    @patch("api.index.run_personal_digest", return_value={"processed":1,"errors":[]})
    @patch("api.index.run_daily_digest", return_value={"processed":0,"errors":[]})
    @patch("api.index.supabase_service")
    def test_scheduled_email_failure_does_not_stop_other_users(self, service, _public, _personal, send, _state, _save):
        service.return_value = [{"id":"user-a"},{"id":"user-b"}]
        send.side_effect = [ValueError("bad address"), {"sent":True,"articles":1,"id":"email_2"}]
        result = run_scheduled_updates()
        self.assertEqual(send.call_count, 2)
        self.assertEqual(result["users"], 2)
        self.assertTrue(any("user-a email" in error for error in result["errors"]))

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

    @patch("api.index.fetch_wechat_direct")
    def test_extracts_wechat_article(self, fetch):
        body = "This is a sufficiently long WeChat article body for extraction testing. " * 8
        html = f'''<html><head><meta property="og:title" content="Test article">
        <meta name="author" content="Test account"></head><body><div id="js_content">{body}</div></body></html>'''
        fetch.return_value = html.encode("utf-8")
        article = extract_wechat_article("https://mp.weixin.qq.com/s/example")
        self.assertEqual(article["title"], "Test article")
        self.assertEqual(article["source"], "Test account")
        self.assertGreater(len(article["text"]), 200)

    @patch("api.index.SESSION.get")
    def test_direct_wechat_request_uses_mobile_wechat_headers(self, get):
        get.return_value = Mock(content=b"<html>ok</html>", text="<html>ok</html>")
        fetch_wechat_direct("https://mp.weixin.qq.com/s?__biz=a&mid=1")
        headers = get.call_args.kwargs["headers"]
        self.assertIn("MicroMessenger", headers["User-Agent"])
        self.assertEqual(headers["Referer"], "https://mp.weixin.qq.com/")

    @patch("api.index.SESSION.get")
    def test_direct_wechat_request_detects_block_page(self, get):
        get.return_value = Mock(content="环境异常".encode(), text="环境异常")
        with self.assertRaisesRegex(ValueError, "微信拒绝"):
            fetch_wechat_direct("https://mp.weixin.qq.com/s/example")

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
        save.assert_called_once()
        self.assertEqual(existing["kind"], "wechat")
        self.assertEqual(existing["country"], "cn")

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

    @patch("api.index.import_wechat_article")
    def test_sync_wechat_saves_chinese_without_translating(self, import_article):
        import_article.return_value = {"article":{"translations":{"zh":"body"}}}
        result = sync_wechat_article({"url":"https://mp.weixin.qq.com/s/example","text":"body"})
        import_article.assert_called_once()
        self.assertEqual(import_article.call_args.args[0]["language"], "zh")
        self.assertEqual(result["article"]["translations"], {"zh":"body"})

    @patch("api.index.import_wechat_article")
    def test_admin_wechat_save_forces_chinese_only(self, import_article):
        import_article.return_value = {"article":{"translations":{"zh":"body"}}}
        save_wechat_chinese({"url":"https://mp.weixin.qq.com/s/example","language":"en"})
        self.assertEqual(import_article.call_args.args[0]["language"], "zh")

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

    @patch("api.index.load_public_articles")
    @patch("api.index.load_seen_urls", return_value=[])
    @patch("api.index.load_app_state", return_value={"next_source":0})
    @patch("api.index.load_config")
    def test_unknown_scheduled_source_is_rejected(self, load_config, _state, _seen, load_articles):
        load_config.return_value = {"target_language":"zh","subscriptions":[{"id":"known","enabled":True}]}
        load_articles.return_value = []
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
    @patch("api.index.save_app_state")
    @patch("api.index.validate_subscription")
    @patch("api.index.load_config")
    def test_saving_public_subscription_immediately_processes_it(self, load_config, validate, save, run):
        load_config.return_value = {"subscriptions":[]}
        validate.return_value = {"id":"new","name":"New","country":"fr","url":"https://new.test","feed_url":"https://new.test/feed","source_type":"rss","mode":"summary","enabled":True}
        run.return_value = {"processed":1,"items":1,"errors":[],"source":"new"}
        result = save_public_subscription({"url":"https://new.test"})
        run.assert_called_once_with(subscription_override=validate.return_value)
        self.assertEqual(result["update"]["processed"], 1)
        self.assertEqual(save.call_args.args[0], "config")

    @patch("api.index.save_app_state")
    @patch("api.index.load_config")
    def test_admin_can_disable_public_subscription(self, load_config, save):
        load_config.return_value = {"subscriptions":[{"id":"source","enabled":True}]}
        result = set_public_subscription_enabled("source", False)
        self.assertFalse(result["enabled"])
        self.assertFalse(save.call_args.args[1]["subscriptions"][0]["enabled"])

    @patch("api.index.run_daily_digest")
    @patch("api.index.save_app_state")
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

    @patch("api.index.remove_seen_url")
    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_delete_and_resync_removes_article_and_seen_url(self, load, save, remove_seen):
        load.return_value = {"updated_at":"","articles":[{"id":"old","url":"https://example.com/story"}]}
        result = delete_article("old", True)
        self.assertTrue(result["resync_allowed"])
        self.assertEqual(save.call_args.args[1]["articles"], [])
        remove_seen.assert_called_once_with("https://example.com/story")

    def test_supabase_article_mapping_preserves_legacy_runtime_shape(self):
        article = {"id":"a1","url":"https://example.com/a","published":"2026-08-01T10:00:00+00:00","translation_instruction":"British English","contents":{"zh":"正文"}}
        row = public_article_to_row(article, "2026-08-09T00:00:00+00:00")
        self.assertTrue(row["published"])
        self.assertEqual(row["published_at"], article["published"])
        restored = public_article_from_row(row)
        self.assertEqual(restored["published"], article["published"])
        self.assertEqual(restored["translation_instruction"], "British English")
        self.assertEqual(public_article_from_row({"id":"a2","published":True})["published"], "")

    @patch("api.index.supabase_service")
    def test_saving_public_articles_upserts_and_removes_stale_rows(self, service):
        service.side_effect = [[{"id":"old"}], None, None]
        save_public_articles([{"id":"new","url":"https://example.com/new"}])
        self.assertEqual(service.call_args_list[1].args[:2], ("POST", "/rest/v1/public_articles"))
        self.assertEqual(service.call_args_list[2].kwargs["params"], {"id":"eq.old"})

    @patch("api.index.supabase_service")
    def test_public_article_batch_rows_have_identical_keys_and_keep_json(self, service):
        service.side_effect = [[], None]
        first = {
            "id":"one",
            "url":"https://example.com/one",
            "contents":{"zh":"正文"},
            "titles":{"zh":"标题"},
            "summaries":{"en":"Summary"},
        }
        second = {
            "id":"two",
            "url":"https://example.com/two",
            "translations":{"zh":"中文全文"},
            "translated_titles":{"zh":"中文标题"},
            "translation_jobs":{"en":{"status":"queued"}},
        }

        save_public_articles([first, second])

        payload = service.call_args_list[1].kwargs["payload"]
        self.assertEqual(set(payload[0]), set(payload[1]))
        self.assertEqual(payload[0]["contents"], first["contents"])
        self.assertEqual(payload[0]["titles"], first["titles"])
        self.assertEqual(payload[0]["summaries"], first["summaries"])
        self.assertEqual(payload[1]["translations"], second["translations"])
        self.assertEqual(payload[1]["translated_titles"], second["translated_titles"])
        self.assertEqual(payload[1]["translation_jobs"], second["translation_jobs"])
        self.assertEqual(payload[0]["translations"], {})
        self.assertEqual(payload[1]["contents"], {})

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

    @patch("api.index.OpenAI")
    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_public_wechat_translation_starts_background_job(self, load, save, openai):
        article = {"id":"wx","kind":"wechat","country":"cn","result":"中文全文","translations":{"zh":"中文全文"},"translated_titles":{"zh":"中文标题"}}
        load.return_value = {"updated_at":"","articles":[article]}
        openai.return_value.responses.create.return_value = Mock(id="resp_1", status="queued")
        result = translate_wechat_article("wx", "de")
        self.assertFalse(result["reused"])
        self.assertEqual(result["status"], "queued")
        self.assertTrue(openai.return_value.responses.create.call_args.kwargs["background"])
        saved = save.call_args.args[1]["articles"][0]
        self.assertEqual(saved["translation_jobs"]["de"]["response_id"], "resp_1")

    @patch("api.index.OpenAI")
    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_legacy_wechat_record_is_accepted_by_url(self, load, save, openai):
        article = {"id":"legacy","url":"https://mp.weixin.qq.com/s/example","result":"中文全文","translations":{"zh":"中文全文"},"translated_titles":{"zh":"中文标题"}}
        load.return_value = {"updated_at":"","articles":[article]}
        openai.return_value.responses.create.return_value = Mock(id="resp_1", status="queued")
        result = translate_wechat_article("legacy", "en")
        self.assertEqual(result["status"], "queued")

    @patch("api.index.OpenAI")
    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_poll_completed_wechat_translation_persists_summary_and_full_text(self, load, save, openai):
        article = {"id":"wx","kind":"wechat","country":"cn","translations":{"zh":"中文全文"},"translated_titles":{"zh":"中文标题"},"translation_jobs":{"de":{"response_id":"resp_1","status":"queued"}}}
        load.return_value = {"updated_at":"","articles":[article]}
        openai.return_value.responses.retrieve.return_value = Mock(status="completed", output_text=json.dumps({"title":"Deutscher Titel","summary":"Kurze Zusammenfassung","content":"Deutscher Volltext"}))
        result = poll_wechat_translation("wx", "de")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(article["summaries"]["de"], "Kurze Zusammenfassung")
        self.assertEqual(article["contents"]["de"], "Deutscher Volltext")

    @patch("api.index.save_blob_json")
    @patch("api.index.load_blob_json")
    def test_admin_metadata_update_can_clear_category_and_date(self, load, save):
        article = {"id":"wx","author_label":"Old","category":"评论","published":"2026-01-01T00:00:00+00:00"}
        load.return_value = {"updated_at":"","articles":[article]}
        result = update_article_metadata("wx", {"author_label":"New author","category":"","published":""})
        self.assertTrue(result["updated"])
        self.assertEqual(article["author_label"], "New author")
        self.assertEqual(article["category"], "")
        self.assertEqual(article["published"], "")


if __name__ == "__main__":
    unittest.main()
