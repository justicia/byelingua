import unittest

from jobs.build_character_master_phase2 import (
    _classify_row,
    _identity_key,
    reclassify_work_rows,
    simulate_credit_impact,
)
from normalization.characters import parse_source_label, resolve_character


class CharacterMasterPhase2Tests(unittest.TestCase):
    def test_unlinked_legacy_relation_is_safe_new_and_preserves_work_row(self):
        result = _classify_row(
            {"id": "wc-1", "work_id": "work-1", "canonical_name": "Hermann"},
            {"work_title": "Tannhäuser", "composer": "Richard Wagner", "canonical_roles": ["Hermann"], "aliases": {}, "evidence_sources": [{"url": "https://example.test"}]},
            {"work_characters": [{"id": "wc-1", "work_id": "work-1", "canonical_name": "Hermann", "character_uid": None}], "characters": []},
        )
        self.assertEqual(result["primary_classification"], "SAFE_NEW_CHARACTER")
        self.assertEqual(result["work_character_id"], "wc-1")
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

    def test_hermann_is_work_scoped_against_unrelated_global_name(self):
        master = {
            "characters": [{"id": "queen-hermann", "canonical_name": "Hermann"}],
            "character_aliases": [],
            "work_characters": [{"work_id": "queen", "character_uid": "queen-hermann", "canonical_name": "Hermann"}],
        }
        tann = {"work_title": "Tannhäuser", "composer": "Richard Wagner", "canonical_roles": ["Hermann, Landgraf von Thüringen"], "aliases": {}, "evidence_sources": []}
        queen = {"work_title": "The Queen of Spades", "composer": "Pyotr Ilyich Tchaikovsky", "canonical_roles": ["Hermann"], "aliases": {}, "evidence_sources": []}
        tann_row = _classify_row({"id": "t", "work_id": "tann", "canonical_name": "Hermann"}, tann, master)
        queen_row = _classify_row({"id": "q", "work_id": "queen", "canonical_name": "Hermann"}, queen, master)
        self.assertIn(tann_row["primary_classification"], {"SAFE_NEW_CHARACTER", "SAFE_NEW_ALIAS"})
        self.assertEqual(queen_row["primary_classification"], "SAFE_LINK_EXISTING")
        self.assertNotEqual(tann_row["candidate_key"], queen_row["candidate_key"])

    def test_same_name_unrelated_work_does_not_auto_merge_or_block_safe_new(self):
        master = {
            "characters": [{"id": "old", "canonical_name": "Figaro"}],
            "character_aliases": [],
            "work_characters": [{"work_id": "barbiere", "character_uid": "old", "canonical_name": "Figaro"}],
        }
        catalog = {"work_title": "Le nozze di Figaro", "composer": "Wolfgang Amadeus Mozart", "canonical_roles": ["Figaro"], "aliases": {}, "evidence_sources": []}
        result = _classify_row({"id": "f", "work_id": "figaro", "canonical_name": "Figaro"}, catalog, master)
        self.assertEqual(result["primary_classification"], "SAFE_NEW_CHARACTER")
        self.assertEqual(result["proposed_character_id"], result["candidate_key"])

    def test_verified_wotan_shared_identity_can_reuse_global_character(self):
        master = {
            "characters": [{"id": "wotan", "canonical_name": "Wotan"}],
            "character_aliases": [{"character_id": "wotan", "alias": "Der Wanderer"}],
            "work_characters": [{"work_id": "walkure", "character_uid": "wotan", "canonical_name": "Wotan"}],
            "verified_shared_identity": [{"character_uid": "wotan", "work_ids": ["siegfried"]}],
        }
        catalog = {"work_title": "Siegfried", "composer": "Richard Wagner", "canonical_roles": ["Der Wanderer"], "aliases": {}, "evidence_sources": []}
        result = _classify_row({"id": "w", "work_id": "siegfried", "canonical_name": "Der Wanderer"}, catalog, master)
        self.assertEqual(result["primary_classification"], "SAFE_LINK_EXISTING")
        self.assertEqual(result["proposed_character_id"], "wotan")

    def test_same_work_relationship_is_safe_link_existing(self):
        master = {
            "characters": [{"id": "figaro-id", "canonical_name": "Figaro"}],
            "character_aliases": [],
            "work_characters": [{"work_id": "figaro", "character_uid": "figaro-id", "canonical_name": "Figaro"}],
        }
        catalog = {"work_title": "Le nozze di Figaro", "composer": "Wolfgang Amadeus Mozart", "canonical_roles": ["Figaro"], "aliases": {}, "evidence_sources": []}
        result = _classify_row({"id": "f", "work_id": "figaro", "canonical_name": "Figaro"}, catalog, master)
        self.assertEqual(result["primary_classification"], "SAFE_LINK_EXISTING")
        self.assertEqual(result["proposed_character_id"], "figaro-id")

    def test_figaro_aliases_are_safe_new_alias_when_canonical_is_safe(self):
        rows = [
            {"id": "c", "work_id": "figaro", "canonical_name": "Count Almaviva"},
            {"id": "g", "work_id": "figaro", "canonical_name": "Graf Almaviva"},
        ]
        catalog = {
            "canonical_roles": ["Il Conte Almaviva", "La Contessa Almaviva"],
            "aliases": {
                "Il Conte Almaviva": ["Count Almaviva", "Graf Almaviva"],
                "La Contessa Almaviva": ["Countess Almaviva", "Gräfin Almaviva"],
            },
            "evidence_sources": [{"url": "https://example.test/figaro"}],
        }
        results = reclassify_work_rows(rows, "Le nozze di Figaro", "Wolfgang Amadeus Mozart", catalog, {})
        self.assertEqual([row["primary_classification"] for row in results], ["SAFE_NEW_ALIAS", "SAFE_NEW_ALIAS"])
        self.assertEqual(results[0]["proposed_character_id"], results[1]["proposed_character_id"])

    def test_credit_impact_uses_event_credit_occurrences_not_work_rows(self):
        staged = [
            {"work_character_id": "a", "primary_classification": "SAFE_NEW_CHARACTER"},
            {"work_character_id": "b", "primary_classification": "SAFE_NEW_ALIAS"},
        ]
        event_credits = [
            {"work_character_id": "a", "character_review": True},
            {"work_character_id": "b", "resolution_status": "review"},
            {"work_character_id": "x", "character_review": True},
        ]
        self.assertEqual(simulate_credit_impact(event_credits, staged), {
            "event_credit_character_review_before": 3,
            "event_credit_unlockable_after_character_staging": 2,
            "event_credit_character_review_after": 1,
        })


if __name__ == "__main__":
    unittest.main()
