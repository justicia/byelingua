import unittest
from pathlib import Path


ROOT = Path(__file__).parent


class ScheduleFrontendTests(unittest.TestCase):
    def setUp(self):
        self.editor = (ROOT / "schedule-editor.html").read_text(encoding="utf-8")
        self.summary = (ROOT / "schedule-summary.html").read_text(encoding="utf-8")
        self.account = (ROOT / "account.html").read_text(encoding="utf-8")
        self.schedule = (ROOT / "schedule.html").read_text(encoding="utf-8")
        self.i18n = (ROOT / "shared-i18n.js").read_text(encoding="utf-8")

    def test_confirm_redirects_only_after_success(self):
        self.assertIn("await api({action:'update_schedule_status'", self.editor)
        self.assertIn("location.href=`/schedule-summary.html?schedule_id=", self.editor)
        self.assertIn("button.disabled=false", self.editor)

    def test_summary_groups_by_date_and_sorts_by_time(self):
        self.assertIn("groups[dateOf(r.event||{})]", self.summary)
        self.assertIn("sort((a,b)=>timeOf(a.event||{}).localeCompare(timeOf(b.event||{})))", self.summary)

    def test_summary_exports_full_canvas_and_reuses_ics_endpoint(self):
        self.assertIn("canvas.height=height*scale", self.summary)
        self.assertIn("action:'export_schedule_ics'", self.summary)

    def test_planned_account_entry_points_to_summary(self):
        self.assertIn("row.status==='planned'?`/schedule-summary.html?schedule_id=", self.account)
        self.assertIn("data-export-ics", self.account)

    def test_search_and_same_day_keep_separate_modes_and_search_state(self):
        self.assertIn("explorerMode='same-day'", self.editor)
        self.assertIn("searchState={query:'',startDate:'',endDate:'',city:'',venue:'',eventType:'',time:''}", self.editor)
        self.assertIn("action:'schedule_events'", self.editor)
        self.assertIn("data-add", self.editor)

    def test_account_schedule_actions_use_unified_button_hierarchy(self):
        self.assertIn("schedule-action primary", self.account)
        self.assertIn("schedule-action secondary", self.account)
        self.assertIn("schedule-action danger", self.account)
        self.assertIn("schedule-action archive", self.account)
        self.assertIn("data-confirm-id", self.account)
        self.assertIn("data-archive-id", self.account)
        self.assertIn("<h3>Confirmed</h3>", self.account)

    def test_shared_i18n_has_language_priority_and_formatters(self):
        self.assertIn("url.searchParams.get('lang')", self.i18n)
        self.assertIn("window.__byelinguaPreferredLanguage", self.i18n)
        self.assertIn("formatDateRange", self.i18n)
        self.assertIn("formatEventCount", self.i18n)
        self.assertIn("localizeApiError", self.i18n)
        self.assertIn("en-GB", self.i18n)

    def test_schedule_pages_load_shared_i18n(self):
        for name in ("account.html", "schedule-editor.html", "schedule-summary.html", "schedule.html", "article.html"):
            self.assertIn("shared-i18n.js", (ROOT / name).read_text(encoding="utf-8"))

    def test_api_errors_have_stable_codes(self):
        api = (ROOT / "api" / "index.py").read_text(encoding="utf-8")
        self.assertIn('"permission_denied"', api)
        self.assertIn('"network_error"', api)

    def test_bilingual_account_copy_and_direct_confirmed_edit(self):
        self.assertIn("Change password", self.account)
        self.assertIn("Simplified Chinese", self.account)
        self.assertIn("Generate Brief and send by email", self.account)
        self.assertIn("Edit schedule", self.account)
        self.assertIn("Review and confirm", self.account)
        self.assertIn("data-confirm-id", self.account)

    def test_intention_uses_stable_codes_and_renders_bilingually(self):
        self.assertIn("optional", self.editor)
        self.assertIn("formatIntent", self.i18n)
        self.assertIn("Must attend", self.i18n)
        self.assertIn("一定要去", self.i18n)

    def test_confirmed_content_changes_keep_confirmed_and_mark_reconfirmation(self):
        api = (ROOT / "api" / "index.py").read_text(encoding="utf-8")
        self.assertIn('payload={"needs_reconfirmation": True', api)
        self.assertIn("mark_schedule_needs_confirmation(headers, schedule_id)", api)
        self.assertIn("needs_reconfirmation", self.account)
        self.assertIn("confirmUpdated", self.editor)

    def test_opera_cast_uses_readable_role_artist_columns(self):
        self.assertIn("grid-template-columns:minmax(0,42%) minmax(0,58%)", self.schedule)
        self.assertIn(".cast-list .artist-link{display:inline;text-align:left", self.schedule)
        self.assertIn("@media(max-width:420px){.cast-list li{grid-template-columns:1fr", self.schedule)


if __name__ == "__main__":
    unittest.main()
