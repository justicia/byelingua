import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "global-entities"


def doc(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


class DeferredResolutionTest(unittest.TestCase):
    def test_input_partition_and_backlog_buckets(self):
        s = doc("auditorio-event-programme-deferred-resolution-summary.json")
        self.assertEqual(s["input_deferred_events"], 78)
        self.assertEqual(s["input_remaining_review_rows"], 219)
        self.assertEqual(s["second_batch_deterministic_events"] + s["final_residual_backlog_events"], 78)

    def test_deterministic_scope_excludes_closed_batch(self):
        s = doc("auditorio-event-programme-deferred-resolution-summary.json")
        first = doc("auditorio-event-programme-cleanup-summary.json")
        self.assertTrue(set(s["second_batch_event_ids"]).isdisjoint(first["cleanup_event_ids"]))

    def test_expected_counts_and_no_writes(self):
        s = doc("auditorio-event-programme-deferred-resolution-summary.json")
        self.assertEqual(s["baseline"]["auditorio_events"], 583)
        self.assertEqual(s["baseline"]["auditorio_event_programme"], 2862)
        self.assertEqual(s["expected_after"], 2829)
        self.assertEqual(s["database_writes"], 0)
        self.assertTrue(s["no_sql_executed"])

    def test_sql_batches_are_explicitly_typed(self):
        rx = re.compile(r"\('[0-9a-f-]{36}'::uuid, '[0-9a-f-]{36}'::uuid, \d+::integer, '[^']+'::text\)")
        for name in ("auditorio-event-programme-deferred-cleanup-production-apply.sql", "auditorio-event-programme-deferred-cleanup-production-validation.sql"):
            sql = (OUT / name).read_text(encoding="utf-8")
            self.assertGreaterEqual(len(rx.findall(sql)), 45)
            self.assertNotRegex(sql, r"\('[0-9a-f-]{36}', '[0-9a-f-]{36}'")
            self.assertIn("event_id,work_id,programme_order,source_occurrence_id", sql)

    def test_only_event_programme_mutation_and_set_validation(self):
        sql = (OUT / "auditorio-event-programme-deferred-cleanup-production-apply.sql").read_text(encoding="utf-8").upper()
        self.assertEqual(sql.count("DELETE FROM PUBLIC.EVENT_PROGRAMME"), 1)
        self.assertNotIn("DELETE FROM PUBLIC.WORKS", sql)
        self.assertNotIn("UPDATE PUBLIC.EVENTS", sql)
        validation = (OUT / "auditorio-event-programme-deferred-cleanup-production-validation.sql").read_text(encoding="utf-8").upper()
        self.assertIn("CURRENT_MINUS_DESIRED", validation)
        self.assertIn("DESIRED_MINUS_CURRENT", validation)
        self.assertIn("MISSING_EVENT_TARGETS", validation)
        self.assertIn("MISSING_WORK_TARGETS", validation)

    def test_residual_reasons_are_explicit(self):
        b = doc("auditorio-event-programme-final-residual-backlog.json")
        allowed = {"event_identity_unresolved", "parser_structure_unresolved", "source_attribution_unresolved", "ambiguous_existing_work_review", "canonical_gap_review", "parent_excerpt_unresolved", "relationship_evidence_insufficient", "canonical_master_defect_review"}
        for e in b["events"]:
            self.assertEqual(e["bucket"], "FINAL_RESIDUAL_BACKLOG")
            self.assertIn(e["primary_reason"], allowed)
            self.assertIn(e["priority"], {"P1", "P2", "P3"})

    def test_source_completeness_report_is_event_level(self):
        s = doc("auditorio-event-programme-deferred-resolution-summary.json")
        self.assertEqual(s["candidate_events_reviewed"], 28)
        self.assertGreaterEqual(len(s["completeness_report"]), 28)
        self.assertEqual(s["same_event_same_work_duplicates"], 0)
        self.assertTrue(all(x["final_bucket"] in {"SECOND_BATCH_DETERMINISTIC", "FINAL_RESIDUAL_BACKLOG"} for x in s["completeness_report"]))

    def test_microfix_exact_work_repairs_and_residual_moves(self):
        desired = doc("auditorio-event-programme-deferred-desired-state.json").get("rows", [])
        summary = doc("auditorio-event-programme-deferred-resolution-summary.json")
        for eid in {"0f78b159-c511-4a60-b976-ebabf9217d1e", "642c41c0-723c-4d11-98f5-8ac7d0f9f2a6", "e7b0abe1-be1f-442f-a954-925be3dd920f"}:
            rows = [r for r in desired if r["event_id"] == eid]
            self.assertIn("21e99c87-798c-412d-9f9d-9e95e788dfc5", [r["work_id"] for r in rows])
            self.assertNotIn("3a0a42ca-35d0-4a2d-b273-58ab01bde2b5", [r["work_id"] for r in rows])
        rows = [r for r in desired if r["event_id"] == "724a01df-5cdd-4ae3-b04d-639f620e54da"]
        self.assertIn("8c31da8d-1038-4117-9ee9-486132c25df0", [r["work_id"] for r in rows])
        self.assertNotIn("b78744eb-51b9-48e3-9f44-ffd939c7d215", [r["work_id"] for r in rows])
        rows = [r for r in desired if r["event_id"] == "b6261109-846e-4d47-b6cb-2cbc3bb4455b"]
        self.assertEqual([(r["order"], r["work_id"]) for r in rows], [(1, "18999bca-ba78-4658-b63d-123701cdcd60")])
        self.assertEqual(summary["second_batch_deterministic_events"], 11)
        self.assertEqual(summary["current_rows"], 69)
        self.assertEqual(summary["desired_rows"], 36)
        self.assertEqual(summary["expected_after"], 2829)

    def test_microfix_moved_events_are_absent_from_sql_and_backlog_reasons_are_exact(self):
        backlog = doc("auditorio-event-programme-final-residual-backlog.json")
        by_id = {x["event_id"]: x for x in backlog["events"]}
        self.assertEqual(by_id["072264f4-b6b0-44f5-9bd6-4c711f6f8e30"]["primary_reason"], "canonical_master_defect_review")
        self.assertEqual(by_id["bf7d7437-5c71-4911-a5d6-a0beb8078af6"]["primary_reason"], "parser_structure_unresolved")
        apply = (OUT / "auditorio-event-programme-deferred-cleanup-production-apply.sql").read_text(encoding="utf-8")
        for eid in ("072264f4-b6b0-44f5-9bd6-4c711f6f8e30", "bf7d7437-5c71-4911-a5d6-a0beb8078af6"):
            self.assertNotIn(eid, apply)
        self.assertIn("unapproved same Event+Work duplicate", apply)

    def test_post_apply_verified_state_and_closure_bookkeeping(self):
        summary = doc("auditorio-event-programme-deferred-resolution-summary.json")
        desired = doc("auditorio-event-programme-deferred-desired-state.json")["rows"]
        backlog = doc("auditorio-event-programme-final-residual-backlog.json")["events"]
        closed = set(summary["second_batch_event_ids"])
        residual = {x["event_id"] for x in backlog}
        self.assertEqual(summary["baseline"]["auditorio_events"], 583)
        self.assertEqual(summary["expected_after"], 2829)
        self.assertEqual(len(desired), 36)
        self.assertEqual(len(closed), 11)
        self.assertEqual(len(residual), 67)
        self.assertTrue(closed.isdisjoint(residual))
        self.assertEqual(summary["residual_primary_reason_counts"], {"parser_structure_unresolved": 60, "relationship_evidence_insufficient": 6, "canonical_master_defect_review": 1})
        self.assertEqual(summary["residual_priority_counts"], {"P1": 67})
        self.assertEqual({x["event_id"] for x in summary["completeness_report"] if x["final_bucket"] == "SECOND_BATCH_DETERMINISTIC"}, closed)

    def test_post_apply_canonical_counts_are_unchanged_metadata(self):
        verified = doc("auditorio-event-programme-deferred-resolution-summary.json")["post_apply_verified_production"]
        self.assertEqual({k: verified[k] for k in ("auditorio_events", "auditorio_event_programme", "works", "work_aliases", "composers", "composer_aliases")}, {"auditorio_events": 583, "auditorio_event_programme": 2829, "works": 3229, "work_aliases": 99, "composers": 376, "composer_aliases": 82})
        self.assertEqual(verified["production_batch_md5"], "6cdeee1295fa375b4c31091cc7401a72")


if __name__ == "__main__":
    unittest.main()
