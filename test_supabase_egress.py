import re
import unittest
from pathlib import Path


API = Path("api/index.py").read_text(encoding="utf-8")
INDEX = Path("index.html").read_text(encoding="utf-8")
LEGACY_INDEX = Path("index-complete-bilingual.html").read_text(encoding="utf-8")


class SupabaseEgressRegressionTests(unittest.TestCase):
    def test_public_article_list_is_explicit_and_excludes_full_json_columns(self):
        block = API.split("PUBLIC_ARTICLE_LIST_SELECT", 1)[1].split("PUBLIC_ARTICLE_ARTIST_CONTEXT_SELECT", 1)[0]
        self.assertNotIn('"select": "*"', block)
        self.assertNotIn("raw_data", block)
        self.assertNotIn("contents", block)
        self.assertNotIn("translations", block)
        self.assertNotIn("translation_jobs", block)
        self.assertNotIn(",result,", block)
        self.assertNotIn("summaries,", block)
        self.assertIn("summary_zh:summaries->>zh", block)
        self.assertIn("summary_en:summaries->>en", block)

    def test_public_payload_uses_list_path_and_detail_keeps_full_row_separate(self):
        payload_body = API.split("def public_payload():", 1)[1].split("def supabase_settings():", 1)[0]
        self.assertIn("load_public_article_list()", payload_body)
        detail_body = API.split("def get_article(", 1)[1].split("def save_public_articles", 1)[0]
        self.assertIn("PUBLIC_ARTICLE_DETAIL_SELECT", detail_body)
        public_detail = detail_body.split("public_rows =", 1)[1].split("if public_rows:", 1)[0]
        self.assertNotIn('"select": "*"', public_detail)

    def test_artist_context_uses_json_paths_instead_of_full_raw_data(self):
        block = API.split("def artist_context(", 1)[1].split("def entity_options", 1)[0]
        self.assertIn("PUBLIC_ARTICLE_ARTIST_CONTEXT_SELECT", block)
        self.assertNotIn('"raw_data"', block)
        self.assertIn("raw_title:raw_data->>title", API)

    def test_catalog_paths_have_explicit_projections(self):
        self.assertIn("EVENT_CATALOG_LIST_SELECT", API)
        self.assertIn("EVENT_CHARACTER_CATALOG_SELECT", API)
        catalog_calls = re.findall(r'"/rest/v1/event_catalog_v1".{0,260}', API, flags=re.S)
        self.assertGreaterEqual(len(catalog_calls), 5)
        self.assertTrue(all('"select":' in call or "EVENT_CATALOG_LIST_SELECT" in call for call in catalog_calls))
        self.assertNotIn('"select": "*", "character_id"', API)

    def test_event_identity_lookups_are_bounded(self):
        helper = API.split("def event_keys_for_internal_ids", 1)[1].split("def event_rows_for_keys", 1)[0]
        self.assertIn("range(0, len(unique_ids), 100)", helper)
        self.assertIn('"limit": "100"', helper)
        self.assertIn("def event_rows_for_keys", API)
        self.assertIn("batch_size=50", API)

    def test_public_cache_headers_and_feed_clients_allow_server_cache(self):
        self.assertIn('"public, s-maxage=120, stale-while-revalidate=60"', API)
        self.assertIn('fetch("/api");', INDEX)
        self.assertIn('fetch("/api");', LEGACY_INDEX)


if __name__ == "__main__":
    unittest.main()
