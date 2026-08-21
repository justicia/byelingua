import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "global-entities"


def read(name):
    return (OUT / name).read_text(encoding="utf-8")


class AuditorioEventProgrammeCleanupTest(unittest.TestCase):
    def test_event_level_target_reconstruction_counts(self):
        summary = json.loads(read("auditorio-event-programme-cleanup-summary.json"))
        self.assertEqual(summary["production_baseline"]["auditorio_event_programme"], 2922)
        self.assertEqual(summary["fully_deterministic_events"], 34)
        self.assertEqual(summary["deferred_events"], 78)
        self.assertEqual(summary["rows_current_in_cleanup_events"], 164)
        self.assertEqual(summary["desired_rows_after_cleanup"], 104)
        self.assertEqual(summary["expected_event_programme_after"], 2862)

    def test_cleanup_uses_event_level_replacement_not_chained_update(self):
        sql = read("auditorio-event-programme-cleanup-production-apply.sql").upper()
        self.assertIn("DELETE FROM PUBLIC.EVENT_PROGRAMME", sql)
        self.assertIn("INSERT INTO PUBLIC.EVENT_PROGRAMME", sql)
        self.assertNotIn("UPDATE PUBLIC.EVENT_PROGRAMME", sql)
        self.assertNotIn("ORDER = ORDER", sql)

    def test_current_snapshot_guard_catches_missing_and_extra_rows(self):
        sql = read("auditorio-event-programme-cleanup-production-apply.sql")
        self.assertIn("Cleanup current snapshot missing or changed", sql)
        self.assertIn("Cleanup current snapshot has unexpected extra row", sql)
        self.assertIn("DELETE FROM public.event_programme ep\nUSING", sql)

    def test_deferred_events_are_not_in_cleanup_sql(self):
        staging = json.loads(read("auditorio-event-programme-final-production-staging.json"))
        summary = json.loads(read("auditorio-event-programme-cleanup-summary.json"))
        deferred = {
            r["event_id"] for r in staging["candidates"]
            if r["status"] in {"existing_relationship_order_review", "event_programme_conflict_review", "repeated_work_occurrence_review"}
        } - set(summary["cleanup_event_ids"])
        sql = read("auditorio-event-programme-cleanup-production-apply.sql")
        self.assertTrue(deferred)
        self.assertTrue(all(event_id not in sql for event_id in deferred))

    def test_repeated_occurrence_requires_approval(self):
        summary = json.loads(read("auditorio-event-programme-cleanup-summary.json"))
        self.assertEqual(summary["approved_repeated_work_occurrence"], 0)
        self.assertEqual(summary["rejected_repeated_work_occurrence"], 1)

    def test_only_event_programme_is_mutated(self):
        sql = read("auditorio-event-programme-cleanup-production-apply.sql").upper()
        self.assertEqual(sql.count("DELETE FROM PUBLIC.EVENT_PROGRAMME"), 1)
        self.assertNotIn("DELETE FROM PUBLIC.WORKS", sql)
        self.assertNotIn("DELETE FROM PUBLIC.EVENTS", sql)
        self.assertNotIn("DELETE FROM PUBLIC.COMPOSERS", sql)
        self.assertNotIn("UPDATE PUBLIC.WORKS", sql)
        self.assertNotIn("UPDATE PUBLIC.EVENT_CREDITS", sql)

    def test_sql_batches_are_explicitly_typed(self):
        typed = re.compile(r"\('[0-9a-f-]{36}'::uuid, \d+::integer, '[0-9a-f-]{36}'::uuid, '[^']+'::text\)")
        self.assertGreaterEqual(len(typed.findall(read("auditorio-event-programme-cleanup-production-apply.sql"))), 104)
        self.assertGreaterEqual(len(typed.findall(read("auditorio-event-programme-cleanup-production-validation.sql"))), 104)
        for name in ("auditorio-event-programme-cleanup-production-apply.sql", "auditorio-event-programme-cleanup-production-validation.sql"):
            sql = read(name)
            self.assertNotRegex(sql, r"\('[0-9a-f-]{36}', '[0-9a-f-]{36}', '[^']+'")

    def test_validation_uses_set_equality(self):
        sql = read("auditorio-event-programme-cleanup-production-validation.sql").upper()
        self.assertIn("CURRENT_MINUS_DESIRED", sql)
        self.assertIn("DESIRED_MINUS_CURRENT", sql)
        self.assertIn("EXCEPT SELECT", sql)
        self.assertIn("INVALID_EVENT_FK", sql)
        self.assertIn("INVALID_WORK_FK", sql)


if __name__ == "__main__":
    unittest.main()
