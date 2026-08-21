import unittest

from jobs.auditorio_composer_match_dry_run import (
    build_indexes,
    collect_inputs,
    match_inputs,
    resolve_component,
)


class AuditorioComposerMatcherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.indexes = build_indexes({
            "composers": [
                {"id": "bach-id", "canonical_name": "Johann Sebastian Bach"},
                {"id": "handel-id", "canonical_name": "Georg Friedrich Händel"},
                {"id": "saint-id", "canonical_name": "Camille Saint-Saëns"},
                {"id": "mozart-id", "canonical_name": "Wolfgang Amadeus Mozart"},
                {"id": "verdi-id", "canonical_name": "Giuseppe Verdi"},
                {"id": "debussy-id", "canonical_name": "Claude Debussy"},
                {"id": "turina-id", "canonical_name": "José Luis Turina"},
                {"id": "falla-id", "canonical_name": "Manuel de Falla"},
                {"id": "halffter-id", "canonical_name": "Ernesto Halffter"},
                {"id": "brahms-id", "canonical_name": "Johannes Brahms"},
                {"id": "schoenberg-id", "canonical_name": "Arnold Schönberg"},
                {"id": "mudarra-id", "canonical_name": "Alonso Mudarra"},
            ],
            "composer_aliases": [
                {"composer_id": "bach-id", "alias": "J. S. Bach"},
                {"composer_id": "bach-id", "alias": "J.S. Bach"},
                {"composer_id": "handel-id", "alias": "Haendel"},
                {"composer_id": "handel-id", "alias": "Handel"},
                {"composer_id": "handel-id", "alias": "Händel"},
                {"composer_id": "handel-id", "alias": "Georg Friedrich Handel"},
                {"composer_id": "saint-id", "alias": "C. Saint-Saëns"},
                {"composer_id": "debussy-id", "alias": "C. Debussy"},
                {"composer_id": "mudarra-id", "alias": "Alonso Mudarra"},
            ],
        })

    def test_existing_alias_and_canonical_precedence(self):
        self.assertEqual(resolve_component("Johann Sebastian Bach", self.indexes)["match_status"], "exact")
        self.assertEqual(resolve_component("J. S. Bach", self.indexes)["match_status"], "alias")
        self.assertEqual(resolve_component("J.S. Bach", self.indexes)["canonical_composer_id"], "bach-id")
        self.assertEqual(resolve_component("C. Saint-Saëns", self.indexes)["match_status"], "alias")

    def test_variant_and_initial_regressions(self):
        for raw, expected in {
            "Haendel": "handel-id", "Händel": "handel-id", "Handel": "handel-id",
            "C. Debussy": "debussy-id", "G. Verdi": None, "W. A. Mozart": None,
            "Serguéi Rajmáninov": None, "Piotr Ilich Chaikovski": None,
            "Ígor Stravinski": None,
        }.items():
            result = resolve_component(raw, self.indexes)
            if expected:
                self.assertEqual(result["canonical_composer_id"], expected, raw)
            else:
                self.assertNotEqual(result["match_status"], "high_confidence", raw)

    def test_multi_composer_components_match_independently(self):
        inputs = [{
            "source_url": "u", "raw_title": "t", "raw_composer_text": "Claude Debussy / José Luis Turina",
            "raw_component_text": "Claude Debussy", "classification_source": "composer_candidate",
            "block_order": 0, "line_order": 0,
        }, {
            "source_url": "u", "raw_title": "t", "raw_composer_text": "Claude Debussy / José Luis Turina",
            "raw_component_text": "José Luis Turina", "classification_source": "composer_candidate",
            "block_order": 0, "line_order": 0,
        }]
        results, _ = match_inputs(inputs, self.indexes)
        self.assertEqual([row["canonical_composer_id"] for row in results], ["debussy-id", "turina-id"])

    def test_malformed_and_non_person_inputs_are_not_repaired(self):
        malformed = resolve_component("Ludwig van Universo Beethoven (1770-1827)", self.indexes)
        self.assertEqual(malformed["match_status"], "unmatched")
        luigi = resolve_component("Luigi Maurizio", self.indexes)
        self.assertIn(luigi["match_status"], {"unmatched", "ambiguous"})

    def test_phase2_input_contract_uses_fragments_only(self):
        inputs = collect_inputs("artifacts/auditorio-nacional/auditorio-structure-classification.json")
        edgar = [row for row in inputs if row["raw_composer_text"] == "Edward Elgar Variaciones"]
        self.assertEqual([row["raw_component_text"] for row in edgar], ["Edward Elgar"])
        traditional = [row for row in inputs if "Tradicional de Venezuela" in row["raw_composer_text"]]
        self.assertEqual([row["raw_component_text"] for row in traditional], ["Alonso Mudarra (ca. 1510-1580)"])
        self.assertNotIn("Tradicional de Venezuela", [row["raw_component_text"] for row in inputs])


if __name__ == "__main__":
    unittest.main()
