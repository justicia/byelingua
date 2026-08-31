import unittest
from pathlib import Path


ROOT = Path(__file__).parent


class Phase2PlannerContractTests(unittest.TestCase):
    def setUp(self):
        self.editor = (ROOT / "schedule-editor.html").read_text(encoding="utf-8")
        self.builder = (ROOT / "schedule.html").read_text(encoding="utf-8")
        self.summary = (ROOT / "schedule-summary.html").read_text(encoding="utf-8")
        self.header = (ROOT / "shared-header.js").read_text(encoding="utf-8")

    def test_schedule_load_and_authenticated_edit_gate(self):
        for marker in (
            "schedule_id",
            "action:'get_schedule'",
            "function showAuthGate",
            "if(!token()){showAuthGate();return}",
            "Sign in required",
        ):
            self.assertIn(marker, self.editor)

    def test_selected_events_are_grouped_and_chronological(self):
        for marker in (
            "function eventSortKey",
            "99:99",
            "const groups=new Map()",
            "class=\"schedule-group\"",
            "class=\"schedule-group-title\"",
            "event-time",
            "event-location",
        ):
            self.assertIn(marker, self.editor)
        self.assertNotIn("draggable=\"true\"", self.editor)
        self.assertNotIn("action:'reorder_schedule_events'", self.editor)

    def test_planner_exposes_schedule_status_only(self):
        self.assertNotIn("data-intent", self.editor)
        self.assertNotIn('class="intent"', self.editor)
        self.assertNotIn("intentFilter", self.editor)
        self.assertIn("status==='planned'", self.editor)
        self.assertIn("确认行程", self.editor)

    def test_remove_is_membership_only_and_alternatives_are_idempotent(self):
        self.assertIn("action:'remove_event_from_schedule'", self.editor)
        self.assertIn("action:'add_event_to_schedule'", self.editor)
        self.assertIn("if(rows.some(r=>String(r.event_key)===String(key)))return", self.editor)
        self.assertNotIn("action:'delete_event'", self.editor)
        self.assertIn("scheduled=new Set(rows.map(row=>String(row.event_key)))", self.editor)
        self.assertIn("scheduled.has(key)", self.editor)

    def test_same_date_alternatives_have_date_navigation_and_deterministic_sort(self):
        for marker in (
            "date_from:date,date_to:date",
            "dateOf(item)!==date",
            "id=\"previousDate\"",
            "id=\"nextDate\"",
            "timeOf(a).localeCompare(timeOf(b))||titleOf(a).localeCompare(titleOf(b))",
        ):
            self.assertIn(marker, self.editor)
        self.assertNotIn("id=\"searchTab\"", self.editor)

    def test_conflict_only_uses_same_start_or_explicit_interval(self):
        for marker in (
            "function explicitEndMinutes",
            "e.end_time",
            "e.duration_minutes",
            "candidateStart===start",
            "Potential conflict",
        ):
            self.assertIn(marker, self.editor)
        self.assertNotIn("start+120", self.editor)
        self.assertNotIn("start+2*60", self.editor)

    def test_shared_detail_renderer_and_read_only_reviews(self):
        self.assertIn("window.ByelinguaEventDetail", self.header)
        self.assertIn("window.ByelinguaEventDetail.render", self.editor)
        for marker in ("Programme", "Cast", "Artistic Team", "Ensembles", "Official source", "Reviews", "No reviews yet."):
            self.assertIn(marker, self.header + self.editor)
        for marker in ("节目", "演员", "主创团队", "乐团与合唱团", "评论", "暂无评论"):
            self.assertIn(marker, self.editor)
        for marker in ("noProgramme", "noCast", "noTeam", "noEnsembles", "暂无节目内容", "暂无演员信息", "暂无主创团队信息", "暂无乐团与合唱团信息"):
            self.assertIn(marker, self.editor)
        for marker in ("stage director", "conductor", "lighting", "costumes", "set designer", "chorus master", "dramaturgy", "舞台导演", "指挥", "灯光", "服装", "舞美设计", "合唱指挥", "戏剧构作"):
            self.assertIn(marker, self.editor)

    def test_language_and_navigation_copy_are_consistent(self):
        for marker in ("Back to Performance Search", "返回演出搜索", "Other performances", "其他演出", "Find performances", "查找演出", "时间可能冲突"):
            self.assertIn(marker, self.editor)

    def test_generate_flow_and_mobile_auxiliary_drawers_remain(self):
        for marker in (
            "action:'create_schedule'",
            "action:'add_event_to_schedule'",
            "/schedule-editor.html?schedule_id=",
            "setContextOpen",
            "ByelinguaOverlay?.lock",
            "max-width:800px",
            "classList.contains('open')",
            "event.key==='Escape'",
        ):
            self.assertIn(marker, self.editor + self.builder)

    def test_existing_outputs_consume_the_current_schedule(self):
        for marker in (
            "action:'get_schedule'",
            "downloadCalendarImage",
            "action:'export_schedule_ics'",
            "action:'send_schedule_email'",
            "rows=d.events||[]",
        ):
            self.assertIn(marker, self.summary)


if __name__ == "__main__":
    unittest.main()
