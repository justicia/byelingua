import unittest
from pathlib import Path


ROOT = Path(__file__).parent


class GlobalEventDetailRendererTests(unittest.TestCase):
    def setUp(self):
        self.shared = (ROOT / "shared-i18n.js").read_text(encoding="utf-8")
        self.schedule = (ROOT / "schedule.html").read_text(encoding="utf-8")
        self.editor = (ROOT / "schedule-editor.html").read_text(encoding="utf-8")

    def test_shared_renderer_is_the_single_credit_contract(self):
        self.assertIn("window.ByelinguaCredits={render:renderCredits}", self.shared)
        self.assertGreaterEqual(self.schedule.count("window.ByelinguaCredits.render"), 1)
        self.assertIn("window.ByelinguaCredits.render", self.editor)
        self.assertNotIn("Artists / " + "Artistic Team", self.shared + self.schedule + self.editor)

    def test_schedule_has_no_event_type_credit_classifier(self):
        self.assertNotIn("if(!opera)", self.schedule)
        self.assertNotIn("['opera','operetta']", self.schedule)
        self.assertNotIn("normalizedUi(event.event_type)", self.schedule)
        self.assertIn("function renderPresentationCredits(event){return window.ByelinguaCredits.render", self.schedule)

    def test_editor_has_no_independent_credit_classifier(self):
        self.assertNotIn("const cast=(e.credits||[]).filter", self.editor)
        self.assertNotIn("const team=(e.credits||[]).filter", self.editor)
        self.assertIn("function credits(e){return window.ByelinguaCredits.render", self.editor)

    def test_character_bearing_other_event_uses_shared_renderer_contract(self):
        fixture = {
            "event_type": "other",
            "credits": [
                {"character": "Leonora", "artist_name": "Marina Rebeka"},
                {"role": "conductor", "artist_name": "Nicola Luisotti"},
                {"role": "orchestra", "artist_name": "Orchestra del Teatro dell'Opera di Roma"},
            ],
        }
        self.assertEqual(fixture["event_type"], "other")
        self.assertTrue(any(row.get("character") for row in fixture["credits"]))
        self.assertIn("cast:rows.filter(creditCharacter)", self.shared)
        self.assertIn("ensembles:rows.filter(row=>!creditCharacter(row)&&isEnsembleRole(row))", self.shared)
        self.assertIn("artisticTeam:rows.filter(row=>!creditCharacter(row)&&!isEnsembleRole(row))", self.shared)

    def test_event_type_is_not_used_by_shared_classification(self):
        self.assertNotIn("event.event_type", self.shared)
        self.assertNotIn("event_type", self.shared.split("function renderCredits", 1)[1])


if __name__ == "__main__":
    unittest.main()
