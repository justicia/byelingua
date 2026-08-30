import unittest
from pathlib import Path


ROOT = Path(__file__).parent


class Phase1ShellContractTests(unittest.TestCase):
    def setUp(self):
        self.header = (ROOT / "shared-header.js").read_text(encoding="utf-8")
        self.css = (ROOT / "shared-ui.css").read_text(encoding="utf-8")
        self.pages = {
            name: (ROOT / name).read_text(encoding="utf-8")
            for name in (
                "index.html",
                "index-complete-bilingual.html",
                "article.html",
                "schedule.html",
                "schedule-editor.html",
                "schedule-summary.html",
                "account.html",
                "reviews.html",
            )
        }

    def test_shared_header_has_only_phase1_primary_navigation_and_mobile_menu(self):
        for label in ("Reading", "Schedule", "Reviews", "Search", "Account", "Menu"):
            self.assertIn(label, self.header)
        for forbidden in ("Discover", "Events", "Dashboard"):
            self.assertNotIn(f'>{forbidden}<', self.header)
        self.assertIn("data-shared-account", self.header)
        self.assertIn("data-shared-signout", self.header)
        self.assertIn("byelinguaMobileMenu", self.header)

    def test_shared_tokens_fonts_and_accessibility_contract(self):
        for token in (
            "--paper: #f5f2e9",
            "--forest: #214d3a",
            "--ink: #17201b",
            "--muted: #68716b",
            "--card: #fffdf8",
            "--line: #d7d7ce",
            "--space-",
            "--header-height",
            "--content-max-width",
            "--radius-",
            "--focus-ring",
            "--button-height",
            "--drawer-width",
            "--transition-fast",
            "Cinzel Decorative",
            "Poppins",
            "Noto Sans SC",
            ":focus-visible",
        ):
            self.assertIn(token, self.css)
        self.assertIn("fonts.googleapis.com", self.header)
        self.assertIn("--font-body", self.css)
        self.assertIn("font-family: var(--font-heading)", self.css)
        self.assertNotIn("Georgia,serif", self.header)

    def test_global_pages_load_shared_shell_and_reading_home_sections(self):
        for name, page in self.pages.items():
            self.assertTrue("shared-header.js" in page or name == "reviews.html", name)
        home = self.pages["index.html"]
        for marker in ("readingSection", "Latest Reading", "Performance Search", "Recent Reviews", "focus=search"):
            self.assertIn(marker, home + self.header)
        self.assertIn("reading-filters", self.header)
        self.assertIn("main.contains(countryNav)", self.header)

    def test_account_tabs_and_reviews_are_read_only_shells(self):
        account = self.pages["account.html"]
        for tab in ("Profile", "Reading", "Schedules", "Invitations", "Settings", "accountTabs"):
            self.assertIn(tab, account)
        reviews = self.pages["reviews.html"]
        self.assertIn("No reviews yet", reviews)
        self.assertNotIn("<form", reviews.lower())
        self.assertNotIn("submit", reviews.lower())

    def test_schedule_and_drawer_boundaries_remain_present(self):
        schedule = self.pages["schedule.html"]
        for marker in (
            "dateFrom",
            "dateTo",
            "eventType",
            "locationSearch",
            "characterQuery",
            "entitySearch",
            "persistentEventDetail",
            "data-close-persistent",
        ):
            self.assertIn(marker, schedule)
        self.assertIn("ByelinguaOverlay?.lock", schedule)
        self.assertIn("ByelinguaOverlay?.lock", self.pages["schedule-editor.html"])

    def test_performance_search_completion_contract(self):
        schedule = self.pages["schedule.html"]
        for marker in (
            "phase1-three-column",
            "phase1-results-column",
            "phase1-detail-empty",
            "phase1-filter-trigger",
            "Sign in to save",
            "Sign in to generate",
            "data-reviews-placeholder",
            "No reviews yet.",
        ):
            self.assertIn(marker, schedule)

    def test_authenticated_home_modules_use_existing_user_data(self):
        for name in ("index.html", "index-complete-bilingual.html"):
            page = self.pages[name]
            for marker in ("Saved Performances", "My Schedules", "get_event_relations", "list_schedules"):
                self.assertIn(marker, page, name)
        self.assertNotIn("nearby performances", self.pages["index.html"].lower())
        self.assertNotIn("trending performances", self.pages["index.html"].lower())


if __name__ == "__main__":
    unittest.main()
