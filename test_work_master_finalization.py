import unittest

from jobs.work_master_finalization import audit_work_master
from jobs.work_master_operational_freeze import build_freeze


class WorkMasterFinalizationTests(unittest.TestCase):
    def base(self, works, aliases=None):
        return {"works": works, "work_aliases": aliases or [], "composers": [{"id": "c1", "canonical_name": "Composer One"}, {"id": "c2", "canonical_name": "Composer Two"}]}

    def test_original_language_canonical_and_english_alias(self):
        summary, staging = audit_work_master(self.base([{"id": "w1", "title": "Die Zauberflöte", "composer_id": "c1"}], [{"id": "a1", "work_id": "w1", "alias": "The Magic Flute", "language": "en"}]))
        self.assertEqual(summary["safe_existing"], 1)
        self.assertEqual(staging["works"][0]["aliases"][0]["alias"], "The Magic Flute")

    def test_accentless_alias_and_soft_hyphen_equivalence(self):
        summary, _ = audit_work_master(self.base([{"id": "w1", "title": "Die Zauber\u00adflöte", "composer_id": "c1"}], [{"id": "a1", "work_id": "w1", "alias": "Die Zauberflote"}]))
        self.assertEqual(summary["safe_canonical_fix"], 1)

    def test_same_title_different_composer_is_not_same_work(self):
        summary, staging = audit_work_master(self.base([{"id": "w1", "title": "Symphony", "composer_id": "c1"}, {"id": "w2", "title": "Symphony", "composer_id": "c2"}]))
        self.assertEqual(summary["hard_conflicts"], 1)
        self.assertEqual({row["classification"] for row in staging["works"]}, {"REVIEW_IDENTITY"})

    def test_same_composer_translated_title_is_alias_not_global_merge(self):
        summary, staging = audit_work_master(self.base([{"id": "w1", "title": "Die Zauberflöte", "composer_id": "c1"}], [{"id": "a1", "work_id": "w1", "alias": "The Magic Flute", "language": "en"}]))
        self.assertEqual(summary["works_total"], 1)
        self.assertEqual(staging["works"][0]["classification"], "SAFE_EXISTING")

    def test_composite_programme_is_not_automatic_work(self):
        summary, staging = audit_work_master(self.base([{"id": "w1", "title": "Gala Programme", "composer_id": "c1", "work_kind": "composite_programme"}]))
        self.assertEqual(summary["review_composite"], 1)
        self.assertEqual(staging["works"][0]["classification"], "REVIEW_COMPOSITE")

    def test_missing_composer_is_not_fabricated(self):
        summary, staging = audit_work_master(self.base([{"id": "w1", "title": "Living Legacies", "composer_id": None}]))
        self.assertEqual(summary["works_missing_composer"], 1)
        self.assertEqual(staging["works"][0]["classification"], "REVIEW_COMPOSER")

    def test_review_required_never_enters_operational_master(self):
        summary, manifest = build_freeze(self.base([{"id": "w1", "title": "Work", "composer_id": "c1", "normalization_status": "review_required"}]))
        self.assertEqual(summary["auto_match_eligible"], 0)
        self.assertEqual(manifest["works"][0]["exclusion_reason"], "LEGACY_REVIEW_CANDIDATE")

    def test_verified_unique_work_enters_operational_master(self):
        summary, manifest = build_freeze(self.base([{"id": "w1", "title": "Work", "composer_id": "c1", "normalization_status": "verified"}]))
        self.assertEqual(summary["auto_match_eligible"], 1)
        self.assertTrue(manifest["works"][0]["auto_match_eligible"])


if __name__ == "__main__":
    unittest.main()
