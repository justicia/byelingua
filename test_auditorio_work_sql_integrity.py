import tempfile
import unittest
from pathlib import Path

from jobs.auditorio_work_match_dry_run import _write_sql
from jobs.auditorio_work_residual_finalize import repair_actions


class AuditorioWorkSqlIntegrityTest(unittest.TestCase):
    def test_new_work_alias_inherits_created_uuid(self):
        actions = [
            {"action": "create_work", "id": "11111111-1111-1111-1111-111111111111", "title": "Test", "composer_id": "22222222-2222-2222-2222-222222222222", "identity_key": "work:test", "source_occurrence_id": 1},
            {"action": "create_work_alias", "work_id": None, "alias": "Prueba", "source_occurrence_id": 1},
        ]
        out = repair_actions(actions, [], {"works": [], "aliases": []})
        alias = next(a for a in out if a["action"] == "create_work_alias")
        self.assertEqual(alias["work_id"], "11111111-1111-1111-1111-111111111111")

    def test_null_alias_without_created_work_is_rejected(self):
        with self.assertRaises(AssertionError):
            repair_actions([{"action": "create_work_alias", "work_id": None, "alias": "x", "source_occurrence_id": 1}], [], {"works": [], "aliases": []})

    def test_conflicting_existing_identity_is_rejected_by_sql_writer(self):
        actions = [
            {"action": "update_existing_work_identity_key", "work_id": "11111111-1111-1111-1111-111111111111", "identity_key": "work:a"},
            {"action": "update_existing_work_identity_key", "work_id": "11111111-1111-1111-1111-111111111111", "identity_key": "work:b"},
        ]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(AssertionError):
                _write_sql(Path(td), {"works": [], "aliases": []}, actions)

    def test_original_language_title_recomputes_identity(self):
        actions = [{"action": "create_work", "id": "11111111-1111-1111-1111-111111111111", "title": "String Quintet in D major, G.339", "composer_id": "2306b0e9-58fb-4cc2-8061-0b6d49e1f310", "identity_key": "old", "source_occurrence_id": 1}]
        out = repair_actions(actions, [], {"works": [], "aliases": []})
        self.assertEqual(out[0]["title"], "Quintetto in Re maggiore, Op. 39 n. 3, G. 339")
        self.assertNotEqual(out[0]["identity_key"], "old")

    def test_boccherini_catalogue_identities_are_not_swapped(self):
        actions = [
            {"action": "create_work", "id": "11111111-1111-1111-1111-111111111111", "title": "String Quintet in D major, G.339", "composer_id": "2306b0e9-58fb-4cc2-8061-0b6d49e1f310", "identity_key": "old1", "source_occurrence_id": 24},
            {"action": "create_work", "id": "33333333-3333-3333-3333-333333333333", "title": "String Quintet in A major, G. 511", "composer_id": "2306b0e9-58fb-4cc2-8061-0b6d49e1f310", "identity_key": "old2", "source_occurrence_id": 808},
        ]
        out = repair_actions(actions, [], {"works": [], "aliases": []})
        self.assertIn("Re maggiore", out[0]["title"])
        self.assertIn("Sinfonia", out[1]["title"])
        self.assertNotIn("Quintetto", out[1]["title"])


if __name__ == "__main__":
    unittest.main()
