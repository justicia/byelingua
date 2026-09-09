import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
API = (ROOT / "api" / "index.py").read_text(encoding="utf-8")
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
LEGACY_INDEX = (ROOT / "index-complete-bilingual.html").read_text(encoding="utf-8")
ARTICLE = (ROOT / "article.html").read_text(encoding="utf-8")


def inline_scripts_removed(html):
    return re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S)


class SupabaseEgressRegressionTests(unittest.TestCase):
    def test_public_list_projection_excludes_body_like_fields(self):
        block = API.split("PUBLIC_ARTICLE_LIST_SELECT", 1)[1].split(
            "PUBLIC_ARTICLE_ARTIST_CONTEXT_SELECT", 1
        )[0]
        self.assertNotIn('"select": "*"', block)
        for field in (
            "contents", "content", "translations", "translation_jobs", "raw_data",
            "result", "titles", "translated_titles", "summaries",
        ):
            self.assertNotIn(f'"{field}"', block)
        for field in (
            "title_zh:titles->>zh", "title_en:titles->>en",
            "title_fr:titles->>fr", "title_es:titles->>es",
            "title_de:titles->>de", "title_it:titles->>it",
            "title_pt:titles->>pt", "title_ja:titles->>ja",
            "translated_title_zh:translated_titles->>zh",
            "translated_title_en:translated_titles->>en",
            "translated_title_fr:translated_titles->>fr",
            "translated_title_es:translated_titles->>es",
            "translated_title_de:translated_titles->>de",
            "translated_title_it:translated_titles->>it",
            "translated_title_pt:translated_titles->>pt",
            "translated_title_ja:translated_titles->>ja",
            "summary_zh:summaries->>zh", "summary_en:summaries->>en",
            "summary_fr:summaries->>fr", "summary_es:summaries->>es",
            "summary_de:summaries->>de", "summary_it:summaries->>it",
            "summary_pt:summaries->>pt", "summary_ja:summaries->>ja",
        ):
            self.assertIn(field, block)

    def test_list_loader_has_scalar_only_compatibility_fallback(self):
        block = API.split("def load_public_article_list():", 1)[1].split(
            "def get_article(", 1
        )[0]
        self.assertIn("PUBLIC_ARTICLE_LIST_SELECT", block)
        self.assertNotIn('"select": "*"', block)
        self.assertNotIn('"result"', block)
        self.assertNotIn("contents", block.split("fallback_select", 1)[1])
        self.assertNotIn("raw_data", block.split("fallback_select", 1)[1])

    def test_missing_summary_never_falls_back_to_body(self):
        mapper = API.split("def public_article_list_from_row", 1)[1].split(
            "def public_article_to_row", 1
        )[0]
        self.assertNotIn("row.get(\"result\")", mapper)
        self.assertNotIn("raw_data", mapper)
        for page in (INDEX, LEGACY_INDEX):
            self.assertIn("item.excerpts?.[code]||\"\"", page)
            self.assertNotIn("item.excerpts?.[code]||item.summaries", page)

    def test_public_detail_is_explicit_complete_public_lookup(self):
        detail = API.split("def get_article(", 1)[1].split(
            "def save_public_articles", 1
        )[0]
        self.assertIn('"/rest/v1/public_articles"', detail)
        self.assertIn('"id": f"eq.{identifier}"', detail)
        self.assertIn('"published": "eq.true"', detail)
        self.assertIn('"limit": "1"', detail)
        self.assertIn("PUBLIC_ARTICLE_DETAIL_SELECT", detail)
        self.assertNotIn("user_articles", detail)
        self.assertNotIn("authenticated_user", detail)
        self.assertNotIn('"select": "*"', detail)
        detail_columns = API.split("PUBLIC_ARTICLE_COLUMNS = (", 1)[1].split(")", 1)[0]
        self.assertIn('"result"', detail_columns)
        self.assertIn('"contents"', detail_columns)

    def test_private_detail_path_is_not_exposed(self):
        handler = API.split("if action == \"get_article\":", 1)[1].split(
            "if action == \"translate_wechat\":", 1
        )[0]
        self.assertIn('if scope == "private": raise ValueError', handler)
        self.assertIn("get_article(data.get(\"id\"))", handler)
        self.assertNotIn("private=", handler)
        detail = API.split("def get_article(", 1)[1].split("def save_public_articles", 1)[0]
        self.assertNotIn("user_articles", detail)
        self.assertNotIn("authenticated_user", detail)
        self.assertNotIn("ArticleAuthRequiredError", API)

    def test_public_detail_is_not_shared_cached(self):
        detail = API.split("def get_article(", 1)[1].split(
            "def save_public_articles", 1
        )[0]
        self.assertNotIn("READ_CACHE", detail)
        handler = API.split("class handler", 1)[1]
        self.assertIn('cache_control="no-store"', handler)
        self.assertIn('self.send_json(200, result)', handler)

    def test_catalog_reads_have_explicit_projections(self):
        self.assertIn("EVENT_CATALOG_LIST_SELECT", API)
        self.assertIn("EVENT_CHARACTER_CATALOG_SELECT", API)
        self.assertNotIn('"select": "*", "character_id"', API)
        self.assertGreaterEqual(len(re.findall(r"EVENT_CATALOG_LIST_SELECT", API)), 5)

    def test_public_cache_headers_are_narrow(self):
        self.assertIn('"public, s-maxage=120, stale-while-revalidate=60"', API)
        handler = API.split("class handler", 1)[1]
        self.assertIn('cache_control="no-store"', handler)
        self.assertIn(
            'action == "get_public": self.send_json(200, public_payload(), "public, s-maxage=120, stale-while-revalidate=60")',
            handler,
        )

    def test_public_and_private_homepage_paths_are_separate(self):
        for page in (INDEX, LEGACY_INDEX):
            self.assertNotIn('fetch("/api", {cache:"no-store"})', page)
            self.assertIn("if(!mine){window.open(`article.html?id=", page)
            self.assertIn("localStorage.setItem(key,JSON.stringify", page)
            self.assertIn("window.open(`article.html?key=", page)
            self.assertNotIn("scope=private", page)
            self.assertIn("item.excerpts?.[code]||\"\"", page)

    def test_article_supports_public_id_and_legacy_key_without_private_api(self):
        self.assertIn(
            'const params=new URLSearchParams(location.search),articleId=params.get("id"),legacyKey=params.get("key")',
            ARTICLE,
        )
        self.assertIn('request({action:"get_article",id:articleId})', ARTICLE)
        self.assertIn("else if(legacyKey)", ARTICLE)
        self.assertIn("localStorage.getItem(legacyKey)", ARTICLE)
        self.assertNotIn("scope=private", ARTICLE)
        self.assertNotIn("privateScope", ARTICLE)
        self.assertNotIn("includeAuth);article=result.article", ARTICLE)
        self.assertIn("article.content||article.result", ARTICLE)

    def test_legacy_key_fixture_contract_is_local_only(self):
        self.assertIn("legacyKey", ARTICLE)
        self.assertIn("localStorage.getItem(legacyKey)", ARTICLE)
        self.assertIn("article.content", ARTICLE)
        self.assertIn("article=JSON.parse(raw)", ARTICLE)
        self.assertNotIn("user_articles", ARTICLE)

    def test_public_translation_supports_all_non_chinese_languages(self):
        self.assertIn("PUBLIC_TRANSLATION_LANGUAGES = set(LANGUAGES) - {\"zh\"}", API)
        for language in ("en", "fr", "es", "de", "it", "pt", "ja"):
            self.assertIn(f'"{language}"', API.split("LANGUAGES =", 1)[1].split("\n", 1)[0])

    def test_subscription_translation_uses_one_row_supabase_path(self):
        start = API.index("def translate_public_article(")
        end = API.index("def translate_wechat_article(", start)
        block = API[start:end]
        self.assertIn("_public_translation_row(identifier)", block)
        self.assertIn("_patch_public_translation(identifier", block)
        self.assertIn('"limit": "1"', API.split("def _public_translation_row", 1)[1].split("def _patch_public_translation", 1)[0])
        self.assertNotIn("load_blob_json", block)
        self.assertNotIn("save_blob_json", block)
        self.assertNotIn("load_public_articles", block)
        self.assertNotIn("is_wechat_article", block)
        self.assertIn('"contents,translations,titles,translated_titles,summaries,translation_jobs,result"', API)

    def test_subscription_languages_start_without_wechat_guard(self):
        start = API.index("def translate_public_article(")
        end = API.index("def translate_wechat_article(", start)
        block = API[start:end]
        for language in ("fr", "de", "es", "it", "pt", "ja"):
            self.assertNotIn(f'language == "{language}"', block)
        self.assertIn("contents.get(\"zh\") or translations.get(\"zh\") or item.get(\"result\")", block)
        self.assertIn("titles.get(\"zh\") or translated_titles.get(\"zh\")", block)
        self.assertNotIn("kind", block.split("def translate_public_article", 1)[1].split("def poll_public_article_translation", 1)[0])

    def test_existing_translation_reuses_without_new_job(self):
        start = API.index("def translate_public_article(")
        end = API.index("def poll_public_article_translation(", start)
        block = API[start:end]
        self.assertIn("if contents.get(language) or translations.get(language):", block)
        self.assertIn('"reused":True', block)
        self.assertIn("def poll_public_article_translation", API)

    def test_public_translation_persistence_is_targeted(self):
        patch = API.split("def _patch_public_translation", 1)[1].split("def _public_translation_result", 1)[0]
        self.assertIn('"PATCH", "/rest/v1/public_articles"', patch)
        self.assertIn('"id": f"eq.{str(identifier or \'\').strip()}"', patch)
        self.assertIn('"published": "eq.true"', patch)
        for field in ("contents", "translations", "titles", "translated_titles", "summaries", "translation_jobs", "processed_at"):
            self.assertIn(f'"{field}"', API)

    def test_public_translation_actions_and_legacy_aliases_exist(self):
        self.assertIn('action == "translate_public_article"', API)
        self.assertIn('action == "poll_public_article_translation"', API)
        self.assertIn("return translate_public_article(identifier, language)", API)
        self.assertIn("return poll_public_article_translation(identifier, language)", API)

    def test_article_page_exposes_all_languages_and_generic_actions(self):
        for language in ("zh", "en", "fr", "es", "de", "it", "pt", "ja"):
            self.assertIn(f'{language}:', ARTICLE)
        self.assertIn('publicArticle?"translate_public_article":"translate_wechat"', ARTICLE)
        self.assertIn('publicArticle?"poll_public_article_translation":"poll_wechat_translation"', ARTICLE)

if __name__ == "__main__":
    unittest.main()
