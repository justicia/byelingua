import unittest

from jobs.build_character_master_phase2 import _classify_row, _identity_key
from normalization.characters import parse_source_label, resolve_character


class CharacterMasterPhase2Tests(unittest.TestCase):
    def test_unknown_label_never_uses_raw_fallback(self):
        result = resolve_character("Un Joven Pastor", "Richard Wagner", "Tannhäuser", registry={"characters": {}})
        self.assertEqual(result["kind"], "review")
        self.assertIsNone(result["canonical_name"])
        self.assertIsNone(result["identity_key"])

    def test_count_and_graf_are_same_work_catalog_candidate(self):
        catalog = {
            "work_title": "Le nozze di Figaro",
            "canonical_roles": ["Il Conte Almaviva"],
            "aliases": {"Il Conte Almaviva": ["Count Almaviva", "Graf Almaviva"]},
            "evidence_sources": [{"url": "https://example.test/evidence"}],
        }
        first = _classify_row({"id": "a", "work_id": "w", "canonical_name": "Count Almaviva"}, catalog)
        second = _classify_row({"id": "b", "work_id": "w", "canonical_name": "Graf Almaviva"}, catalog)
        self.assertEqual(first["candidate_key"], second["candidate_key"])
        self.assertEqual(first["canonical_character_name"], "Il Conte Almaviva")
        self.assertEqual(second["canonical_character_name"], "Il Conte Almaviva")

    def test_performer_variant_strips_casting_descriptor(self):
        self.assertEqual(parse_source_label("Belmonte - Schauspieler")["class"], "PERFORMER_VARIANT")
        self.assertEqual(parse_source_label("Belmonte - Schauspieler")["lookup"], "Belmonte")

    def test_descriptor_label_strips_descriptor(self):
        parsed = parse_source_label("Escamillo, Toreador")
        self.assertEqual(parsed["class"], "DESCRIPTOR_CHARACTER")
        self.assertEqual(parsed["lookup"], "Escamillo")

    def test_trailing_slash_is_lookup_only(self):
        parsed = parse_source_label("Zuàne /")
        self.assertEqual(parsed["lookup"], "Zuàne")
        self.assertEqual(parsed["raw"], "Zuàne /")

    def test_composite_requires_catalog_proof(self):
        catalog = {
            "canonical_roles": ["Dr. Schön", "Jack the Ripper"],
            "aliases": {},
            "evidence_sources": [{"url": "https://example.test/evidence"}],
        }
        result = _classify_row({"id": "a", "work_id": "w", "canonical_name": "Dr. Schön/Jack the Ripper"}, catalog)
        self.assertEqual(result["primary_classification"], "SAFE_COMPOSITE_EXPANSION")
        self.assertEqual(result["canonical_character_name"], ["Dr. Schön", "Jack the Ripper"])

    def test_same_name_in_unrelated_works_has_different_identity_scope(self):
        self.assertNotEqual(
            _identity_key("Pyotr Tchaikovsky", "The Queen of Spades", "Hermann"),
            _identity_key("Richard Wagner", "Tannhäuser", "Hermann"),
        )

    def test_production_role_and_voice_type_are_not_characters(self):
        self.assertEqual(parse_source_label("Stage Director")["class"], "PRODUCTION_ROLE")
        self.assertEqual(parse_source_label("Tenor")["class"], "VOICE_TYPE")
        self.assertEqual(_classify_row({"id": "a", "work_id": "w", "canonical_name": "Stage Director"}, None)["primary_classification"], "NON_CHARACTER_CONTAMINATION")
        self.assertEqual(_classify_row({"id": "b", "work_id": "w", "canonical_name": "Tenor"}, None)["primary_classification"], "NON_CHARACTER_CONTAMINATION")

    def test_unknown_catalog_label_remains_review(self):
        result = _classify_row({"id": "a", "work_id": "w", "canonical_name": "Unknown label"}, {"canonical_roles": [], "aliases": []})
        self.assertEqual(result["primary_classification"], "REVIEW_CANONICAL_SOURCE")


if __name__ == "__main__":
    unittest.main()
