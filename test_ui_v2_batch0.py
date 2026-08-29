import unittest
from pathlib import Path


ROOT = Path(__file__).parent


class FrontendContractTests(unittest.TestCase):
    def setUp(self):
        self.article = (ROOT / "article.html").read_text(encoding="utf-8")
        self.home = (ROOT / "index.html").read_text(encoding="utf-8")
        self.schedule = (ROOT / "schedule.html").read_text(encoding="utf-8")
        self.editor = (ROOT / "schedule-editor.html").read_text(encoding="utf-8")
        self.api = (ROOT / "api" / "index.py").read_text(encoding="utf-8")

    def test_article_route_uses_persistent_id_and_stable_error_codes(self):
        self.assertIn("params.get(\"id\")", self.article)
        self.assertIn('action:"get_article"', self.article)
        self.assertIn("/article.html?id=", self.home)
        self.assertNotIn("localStorage.setItem(key", self.article)
        for code in ("ARTICLE_NOT_FOUND", "AUTH_REQUIRED", "TRANSLATION_NOT_AVAILABLE", "API_ERROR", "NETWORK_ERROR"):
            self.assertIn(code, self.article)
        for code in ("ARTICLE_NOT_FOUND", "AUTH_REQUIRED", "TRANSLATION_NOT_AVAILABLE"):
            self.assertIn(code, self.api)

    def test_compact_schedule_pagination_and_selection_contract(self):
        self.assertIn("function compactPageItems", self.schedule)
        self.assertIn("page-ellipsis", self.schedule)
        self.assertIn("data-page-prev", self.schedule)
        self.assertIn("data-page-next", self.schedule)
        self.assertIn("selectionStore.isSelected", self.schedule)
        self.assertNotIn("Array.from({length:totalPages},", self.schedule)

    def test_drawers_have_header_safe_scroll_and_shared_mobile_lock(self):
        for token in ("--byelingua-header-height", "overflow:auto", "z-index:39", "data-close-persistent", "ByelinguaOverlay?.lock", "event.key!=='Escape'"):
            self.assertIn(token, self.schedule)
        self.assertIn("ByelinguaOverlay?.lock", self.editor)

    def test_credit_and_country_rendering_contracts_do_not_mutate_data(self):
        self.assertIn("credits.filter(x=>x.character)", self.schedule)
        self.assertIn("_ensembleRole", self.schedule)
        self.assertIn("Artistic Team", self.schedule)
        for city in ("Madrid", "Rome", "Milan", "Zürich", "Basel"):
            self.assertIn(f'"{city}"', self.api)
        self.assertIn("SCHEDULE_CITY_COUNTRY_CODES", self.api)
        self.assertIn('"country_code"', self.api)
        self.assertIn('"country": SCHEDULE_COUNTRY_NAMES', self.api)


if __name__ == "__main__":
    unittest.main()
