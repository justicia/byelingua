import unittest
from pathlib import Path

from jobs.auditorio_composer_match_dry_run import build_indexes, resolve_component, false_positive_reason, sanitize_inline


class GlobalComposerMatcherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.indexes = build_indexes({
            "composers": [
                {"id": "bach", "canonical_name": "Johann Sebastian Bach"},
                {"id": "beethoven", "canonical_name": "Ludwig van Beethoven"},
                {"id": "mozart", "canonical_name": "Wolfgang Amadeus Mozart"},
                {"id": "brahms", "canonical_name": "Johannes Brahms"},
                {"id": "sibelius", "canonical_name": "Jean Sibelius"},
                {"id": "falla", "canonical_name": "Manuel de Falla"},
                {"id": "mudarra", "canonical_name": "Alonso Mudarra"},
                {"id": "debussy", "canonical_name": "Claude Debussy"},
                {"id": "turina", "canonical_name": "José Luis Turina"},
                {"id": "haydn", "canonical_name": "Joseph Haydn"},
                {"id": "vivaldi", "canonical_name": "Antonio Vivaldi"},
                {"id": "mahler", "canonical_name": "Gustav Mahler"},
                {"id": "elgar", "canonical_name": "Edward Elgar"},
                {"id": "bernstein", "canonical_name": "Leonard Bernstein"},
                {"id": "piazzolla", "canonical_name": "Astor Piazzolla"},
                {"id": "shostakovich", "canonical_name": "Dmitri Shostakovich"},
                {"id": "stravinski", "canonical_name": "Igor Stravinski"},
                {"id": "rameau", "canonical_name": "Jean-Philippe Rameau"},
                {"id": "ginastera", "canonical_name": "Alberto Ginastera"},
                {"id": "marquez", "canonical_name": "Arturo Márquez"},
                {"id": "asis_marquez", "canonical_name": "Asís Márquez"},
                {"id": "villa", "canonical_name": "Heitor Villa-Lobos"},
                {"id": "albeniz", "canonical_name": "Isaac Albéniz"},
            ],
            "aliases": [
                {"composer_id": "bach", "alias": "J. S. Bach"},
                {"composer_id": "bach", "alias": "J.S. Bach"},
                {"composer_id": "beethoven", "alias": "Beethoven"},
                {"composer_id": "beethoven", "alias": "BEETHOVEN"},
                {"composer_id": "mozart", "alias": "Mozart"},
                {"composer_id": "mozart", "alias": "MOZART"},
                {"composer_id": "brahms", "alias": "J. Brahms"},
                {"composer_id": "brahms", "alias": "BRAHMS"},
                {"composer_id": "sibelius", "alias": "Sibelius"},
                {"composer_id": "falla", "alias": "M. de Falla"},
                {"composer_id": "stravinski", "alias": "Igor Stravinsky"},
                {"composer_id": "marquez", "alias": "A. Márquez"},
                {"composer_id": "rameau", "alias": "J.-P. Rameau"},
            ],
        })

    def test_required_global_alias_reuse(self):
        for raw, expected in {
            "J. S. Bach": "bach", "J.S. Bach": "bach", "Johann Sebastian Bach": "bach",
            "Beethoven": "beethoven", "BEETHOVEN": "beethoven", "Ludwig van Beethoven": "beethoven",
            "Mozart": "mozart", "MOZART": "mozart", "Wolfgang Amadeus Mozart": "mozart",
            "J. Brahms": "brahms", "BRAHMS": "brahms", "Johannes Brahms": "brahms",
            "Sibelius": "sibelius", "Jean Sibelius": "sibelius",
            "M. de Falla": "falla", "Manuel de Falla": "falla",
        }.items():
            self.assertEqual(resolve_component(raw, self.indexes)["canonical_composer_id"], expected, raw)

    def test_matcher_is_not_bound_to_historical_venue_artifact(self):
        source = Path("jobs/auditorio_composer_match_dry_run.py").read_text(encoding="utf-8").casefold()
        self.assertIn("public.composers", source)
        self.assertIn("public.composer_aliases", source)
        self.assertNotIn("paris-opera-programme-match-dry-run.json", source)

    def test_multi_composer_components_are_independent(self):
        self.assertEqual(resolve_component("Claude Debussy", self.indexes)["canonical_composer_id"], "debussy")
        self.assertEqual(resolve_component("José Luis Turina", self.indexes)["canonical_composer_id"], "turina")

    def test_deterministic_existing_identity_recovery(self):
        for raw, expected in {
            "W. A. Mozart": "mozart", "L. van Beethoven": "beethoven", "L. V. Beethoven": "beethoven",
            "J. Haydn": "haydn", "A. Vivaldi": "vivaldi", "MAHLER": "mahler", "ELGAR": "elgar",
            "Bernstein": "bernstein", "Piazzolla": "piazzolla", "SHOSTAKÓVICH": "shostakovich",
            "Stravinsky": "stravinski",
        }.items():
            self.assertEqual(resolve_component(raw, self.indexes)["canonical_composer_id"], expected, raw)

    def test_inline_and_work_first_sanitation(self):
        for item, expected, work in [
            ({"classification_source": "inline_composer_work", "raw_composer_text": "BEETHOVEN Sinfonía núm. 6 en Fa Mayor", "raw_component_text": "BEETHOVEN Sinfonía núm. 6 en Fa Mayor"}, "BEETHOVEN", "Sinfonía núm. 6 en Fa Mayor"),
            ({"classification_source": "inline_composer_work", "raw_composer_text": "Milonga, Op. 2, No. 1. Alberto Ginastera (1916–1983)", "raw_component_text": "2, No. 1. Alberto Ginastera (1916–1983)"}, "Alberto Ginastera (1916–1983)", "Milonga, Op. 2, No. 1"),
            ({"classification_source": "inline_composer_work", "raw_composer_text": "Valsa da Dor, W. 316. Heitor Villa-Lobos (1887 -1959)", "raw_component_text": "316. Heitor Villa-Lobos (1887 -1959)"}, "Heitor Villa-Lobos (1887 -1959)", "Valsa da Dor, W. 316"),
        ]:
            sanitized, extracted_work, _ = sanitize_inline(item, self.indexes)
            self.assertEqual(sanitized, expected)
            self.assertEqual(extracted_work, work)

    def test_initial_groups_and_catalogue_values_are_safe(self):
        self.assertEqual(resolve_component("J.-P. Rameau", self.indexes)["canonical_composer_id"], "rameau")
        for value in ("III", "LX", "LXVI", "A.S.C.H."):
            self.assertNotEqual(resolve_component(value, self.indexes)["match_status"], "high_confidence")

    def test_phase33_residual_sanitation_cases(self):
        cases = [
            ({"classification_source": "inline_composer_work", "raw_composer_text": "Ballet La Estancia, Op. 8 (A. Ginastera)", "raw_component_text": "8 (A. Ginastera)", "page_artist_names": set()}, "A. Ginastera", "Ballet La Estancia, Op. 8"),
            ({"classification_source": "inline_composer_work", "raw_composer_text": "I. Albéniz: Asturias (Leyenda)", "raw_component_text": "Leyenda", "page_artist_names": set()}, "I. Albéniz", "Asturias (Leyenda)"),
            ({"classification_source": "inline_composer_work", "raw_composer_text": "para órgano en do menor, BWV 582, de J. S. Bach ** (2018)", "raw_component_text": "S. Bach ** (2018)", "page_artist_names": set()}, "J. S. Bach", "para órgano en do menor, BWV 582,"),
            ({"classification_source": "inline_composer_work", "raw_composer_text": "Danzón No. 2 (A. Márquez)", "raw_component_text": "2 (A. Márquez)", "page_artist_names": set()}, "A. Márquez", "Danzón No. 2"),
        ]
        for item, expected_composer, expected_work in cases:
            composer, work, _ = sanitize_inline(item, self.indexes)
            self.assertEqual(composer, expected_composer)
            self.assertEqual(work, expected_work)
        performer = {"classification_source": "inline_composer_work", "raw_composer_text": "«E lucevan le stelle» de «Tosca» de G. Puccini (Eduardo Sandoval)", "raw_component_text": "Eduardo Sandoval", "page_artist_names": {"eduardo sandoval"}}
        _, _, reason = sanitize_inline(performer, self.indexes)
        self.assertEqual(reason, "performer_attribution")

    def test_malformed_and_ambiguous_are_not_guessed(self):
        self.assertEqual(resolve_component("Ludwig van Universo Beethoven (1770-1827)", self.indexes)["match_status"], "unmatched")
        self.assertIn(resolve_component("Luigi Maurizio", self.indexes)["match_status"], {"unmatched", "ambiguous"})

    def test_structural_false_positive_backstop(self):
        for raw, context in (("JOCAN", "ensemble"), ("OBC", "ensemble"), ("Agrippina", "cast"), ("Tenor", "role"), ("Piano", "role"), ("Palacio Real de Madrid", "attribution"), ("Xácara de Reyes", "work")):
            item = {"classification_source": "composer_candidate", "classification_signals": [context]}
            self.assertIsNotNone(false_positive_reason(raw, item), raw)

    def test_traditional_does_not_enter_person_matching(self):
        item = {"classification_source": "composer_attribution", "classification_signals": []}
        self.assertEqual(false_positive_reason("Tradicional de Venezuela", item), "non_person_attribution")
        self.assertIsNone(false_positive_reason("Alonso Mudarra", item))


if __name__ == "__main__":
    unittest.main()
