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
            "translated_title_zh:translated_titles->>zh",
            "translated_title_en:translated_titles->>en",
            "summary_zh:summaries->>zh", "summary_en:summaries->>en",
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

if __name__ == "__main__":
    unittest.main()
