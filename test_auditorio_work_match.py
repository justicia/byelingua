import tempfile
import unittest
from pathlib import Path

from jobs.auditorio_work_match_dry_run import build_work_indexes, choose_work, is_not_a_work, is_parser_contamination, normalize


class AuditorioWorkMatcherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master = {
            "works": [
                {"id": "beethoven-5", "title": "Symphony No. 5 in C minor, Op. 67", "composer_id": "beethoven", "composer": "Ludwig van Beethoven"},
                {"id": "bach-air", "title": "Air on the G String", "composer_id": "bach", "composer": "Johann Sebastian Bach"},
                {"id": "chopin-1", "title": "Piano Concerto No. 1 in E minor, Op. 11", "composer_id": "chopin", "composer": "Frédéric Chopin"},
                {"id": "beethoven-23", "title": "Sonata para piano n.º 23 «Appassionata», Op. 57", "composer_id": "beethoven", "composer": "Ludwig van Beethoven"},
                {"id": "bach-582", "title": "Prelude and Fugue in C minor, BWV 582", "composer_id": "bach", "composer": "Johann Sebastian Bach"},
                {"id": "same-a", "title": "Prelude", "composer_id": "a", "composer": "Composer A"},
                {"id": "same-b", "title": "Prelude", "composer_id": "b", "composer": "Composer B"},
                {"id": "review-null-composer", "title": "La catedral sumergida", "composer_id": None, "composer": "Claude Debussy", "normalization_status": "review_required"},
            ],
            "aliases": [{"id": "alias-1", "work_id": "beethoven-5", "alias": "Sinfonía n.º 5 en do menor, op. 67", "language": "es", "source": "test"}],
        }
        cls.indexes, _ = build_work_indexes(cls.master)

    def test_exact_canonical_match(self):
        result = choose_work({"raw_work_title": "Symphony No. 5 in C minor, Op. 67", "resolved_composer_id": "beethoven"}, self.indexes)
        self.assertEqual(result["status"], "exact")

    def test_alias_match(self):
        result = choose_work({"raw_work_title": "Sinfonía n.º 5 en do menor, op. 67", "resolved_composer_id": "beethoven"}, self.indexes)
        self.assertEqual(result["status"], "alias")

    def test_translated_title_is_not_canonical_without_evidence(self):
        self.assertNotEqual(normalize("Sinfonía n.º 5 en do menor"), normalize("Symphony No. 5 in C minor"))

    def test_same_title_uses_composer_scope(self):
        result = choose_work({"raw_work_title": "Prelude", "resolved_composer_id": "b"}, self.indexes)
        self.assertEqual(result["existing_work_id"], "same-b")

    def test_ambiguous_title_collision(self):
        result = choose_work({"raw_work_title": "Prelude", "resolved_composer_id": None}, self.indexes)
        self.assertEqual(result["status"], "ambiguous")

    def test_non_work_false_positive(self):
        self.assertEqual(is_not_a_work("Piano: Jane Doe", {}, None), "instrument_or_role_label")

    def test_movement_not_promoted(self):
        self.assertEqual(is_not_a_work("II. Adagio", {}, {"canonical_composer_id": "bach"}), "movement_or_numbered_fragment")

    def test_catalogue_number_disambiguates_title(self):
        result = choose_work({"raw_work_title": "para órgano en do menor, BWV 582", "resolved_composer_id": "bach", "catalogue_numbers": ["BWV 582"]}, self.indexes)
        self.assertEqual(result["status"], "catalogue_match")

    def test_generic_title_word_does_not_block_strong_catalogue_match(self):
        result = choose_work({"raw_work_title": "Sonata n.º 23 en fa menor, op. 57", "resolved_composer_id": "beethoven", "catalogue_numbers": ["Sonata", "op. 57"]}, self.indexes)
        self.assertEqual(result["status"], "catalogue_match")

    def test_review_required_existing_work_is_recovered(self):
        result = choose_work({"raw_work_title": "La catedral sumergida", "resolved_composer_id": "debussy"}, self.indexes)
        self.assertEqual(result["existing_work_id"], "review-null-composer")

    def test_existing_work_with_null_composer_is_not_new_work(self):
        result = choose_work({"raw_work_title": "La catedral sumergida", "resolved_composer_id": "debussy"}, self.indexes)
        self.assertEqual(result["status"], "composer_title_match")

    def test_duplicate_work_candidate_is_reviewed(self):
        duplicated = dict(self.master)
        duplicated["works"] = list(self.master["works"]) + [{"id": "same-c", "title": "Prelude", "composer_id": "b", "composer": "Composer B"}]
        indexes, _ = build_work_indexes(duplicated)
        result = choose_work({"raw_work_title": "Prelude", "resolved_composer_id": "b"}, indexes)
        self.assertEqual(result["status"], "ambiguous")

    def test_canonical_and_alias_hits_for_one_work_are_not_ambiguous(self):
        duplicated_alias = dict(self.master)
        duplicated_alias["aliases"] = list(self.master["aliases"]) + [{"id": "alias-2", "work_id": "beethoven-5", "alias": "Symphony No. 5 in C minor, Op. 67", "language": "en", "source": "test"}]
        indexes, _ = build_work_indexes(duplicated_alias)
        result = choose_work({"raw_work_title": "Symphony No. 5 in C minor, Op. 67", "resolved_composer_id": "beethoven"}, indexes)
        self.assertEqual(result["existing_work_id"], "beethoven-5")
        self.assertNotEqual(result["status"], "ambiguous")

    def test_attribution_contamination_is_not_a_work_identity(self):
        self.assertTrue(is_parser_contamination("Leoš Janáček (1854-1928)", {"x": True}))


if __name__ == "__main__":
    unittest.main()
