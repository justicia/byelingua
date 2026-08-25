import unittest

from season_ingestion.contracts import GlobalEntitySnapshot
from season_ingestion.global_master import resolve_work


def snapshot(works, aliases=None):
    return GlobalEntitySnapshot(
        generated_at="2026-08-25T00:00:00Z", source="test", freshness_seconds=0,
        entities={"composer": [{"id": "c1", "canonical_name": "Composer One"}, {"id": "c2", "canonical_name": "Composer Two"}], "work": works, "character": [], "artist": []},
        work_aliases=aliases or [], health={"global_master_loaded": True},
    )


class OperationalWorkResolverTests(unittest.TestCase):
    composer = {"status": "existing", "entity_id": "c1"}

    def test_verified_composer_exact_title_is_existing(self):
        result = resolve_work("Original", self.composer, snapshot([{"id": "w1", "title": "Original", "composer_id": "c1", "normalization_status": "verified", "work_kind": "work"}]))
        self.assertEqual(result["status"], "existing")

    def test_resolved_composer_alias_is_existing(self):
        result = resolve_work("Localized", self.composer, snapshot([{"id": "w1", "title": "Original", "composer_id": "c1", "normalization_status": "resolved", "work_kind": "work"}], [{"id": "a1", "work_id": "w1", "alias": "Localized"}]))
        self.assertEqual(result["status"], "existing")

    def test_review_required_is_not_existing(self):
        result = resolve_work("Original", self.composer, snapshot([{"id": "w1", "title": "Original", "composer_id": "c1", "normalization_status": "review_required", "work_kind": "work"}]))
        self.assertEqual((result["status"], result["reason"]), ("review_required", "LEGACY_REVIEW_WORK_MATCH"))

    def test_duplicate_eligible_works_review(self):
        result = resolve_work("Original", self.composer, snapshot([{"id": "w1", "title": "Original", "composer_id": "c1", "normalization_status": "verified", "work_kind": "work"}, {"id": "w2", "title": "Original", "composer_id": "c1", "normalization_status": "resolved", "work_kind": "work"}]))
        self.assertEqual(result["reason"], "DUPLICATE_WORK_IDENTITY")

    def test_same_title_different_composer_is_composer_scoped(self):
        result = resolve_work("Original", self.composer, snapshot([{"id": "w1", "title": "Original", "composer_id": "c2", "normalization_status": "verified", "work_kind": "work"}]))
        self.assertEqual(result["status"], "review_required")

    def test_missing_composer_never_auto_matches(self):
        missing = resolve_work("Original", None, snapshot([{ "id": "w1", "title": "Original", "composer_id": None, "normalization_status": "verified", "work_kind": "work"}]))
        self.assertEqual(missing["status"], "review_required")

    def test_programme_container_never_auto_matches(self):
        programme = resolve_work("Programme", self.composer, snapshot([{ "id": "w1", "title": "Programme", "composer_id": "c1", "normalization_status": "verified", "work_kind": "programme_container"}]))
        self.assertNotEqual(programme["status"], "existing")


if __name__ == "__main__":
    unittest.main()
