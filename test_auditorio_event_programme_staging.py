import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "global-entities"


def load():
    return json.loads((OUT / "auditorio-event-programme-final-production-staging.json").read_text(encoding="utf-8"))


class AuditorioEventProgrammeStagingTest(unittest.TestCase):
  def test_shared_detail_url_keeps_two_performance_ids(self):
    report = load()["reused_detail_url_regression"]
    self.assertEqual(report["reused_detail_urls"], 24)
    self.assertTrue(report["two_independent_event_uuids"])
    self.assertEqual(len(report["film_symphony_odisea_event_ids"]), 2)


  def test_executable_rows_have_event_work_and_order(self):
    rows = load()["candidates"]
    executable = [r for r in rows if r["action"] in {"insert_event_programme", "existing_event_programme_noop"}]
    self.assertTrue(executable)
    self.assertTrue(all(r["event_id"] and r["resolved_work_id"] and r["stable_programme_order"] is not None for r in executable))


  def test_review_classifications_are_excluded_from_executable_staging(self):
    rows = load()["candidates"]
    excluded = {"unresolved_work", "ambiguous_work", "parent_work_excerpt_review",
                "source_attribution_review", "parser_issue", "not_a_work",
                "event_identity_review", "event_programme_conflict_review"}
    allowed_review_actions = {None, "event_programme_conflict_review", "legacy_order_contamination_review", "existing_relationship_order_review", "repeated_work_occurrence_review"}
    self.assertTrue(all(r["action"] in allowed_review_actions for r in rows if r["status"] in excluded))


  def test_idempotency_and_conflicts_are_visible(self):
    rows = load()["candidates"]
    self.assertTrue(any(r["action"] == "existing_event_programme_noop" for r in rows))
    self.assertTrue(any(r["status"] == "event_programme_conflict_review" for r in rows))


  def test_same_work_is_not_deduplicated_globally(self):
    sql = (OUT / "auditorio-event-programme-final-production-apply.sql").read_text(encoding="utf-8")
    self.assertIn('ON CONFLICT (event_id,"order") DO NOTHING', sql)
    self.assertNotIn("DISTINCT event_id, work_id", sql)


  def test_sql_guards_and_forbidden_mutations(self):
    sql = (OUT / "auditorio-event-programme-final-production-apply.sql").read_text(encoding="utf-8").upper()
    self.assertTrue(sql.startswith("--") and "BEGIN;" in sql and "COMMIT;" in sql)
    self.assertIn("RAISE EXCEPTION", sql)
    self.assertIn("MISSING EVENT", sql)
    self.assertIn("MISSING WORK", sql)
    self.assertIn("CONFLICT", sql)
    self.assertNotIn("CREATE COMPOSER", sql)
    self.assertNotIn("UPDATE PUBLIC.COMPOSERS", sql)
    self.assertNotIn("UPDATE PUBLIC.WORKS", sql)
    self.assertNotIn("DELETE", sql)
    self.assertNotIn("TRUNCATE", sql)
    self.assertNotIn("ALTER TABLE", sql)
    self.assertNotIn("EVENT_CREDITS", sql)

  def test_sql_batches_are_explicitly_typed(self):
    uuid_literal = r"[0-9a-f-]{36}"
    typed_row = re.compile(
        rf"\('{uuid_literal}'::uuid, '{uuid_literal}'::uuid, \d+::integer, '[^']+'::text\)"
    )
    untyped_uuid_row = re.compile(
        rf"\('{uuid_literal}', '{uuid_literal}', '[^']+', '[^']+'\)"
    )
    apply_sql = (OUT / "auditorio-event-programme-final-production-apply.sql").read_text(encoding="utf-8")
    validation_sql = (OUT / "auditorio-event-programme-final-production-validation.sql").read_text(encoding="utf-8")
    self.assertEqual(len(typed_row.findall(apply_sql)), 65)
    self.assertEqual(len(typed_row.findall(validation_sql)), 91)
    self.assertFalse(untyped_uuid_row.search(apply_sql))
    self.assertFalse(untyped_uuid_row.search(validation_sql))
    self.assertIn("SELECT event_id, work_id, programme_order FROM (VALUES (", apply_sql)

  def test_not_a_work_does_not_consume_programme_order(self):
    rows = [r for r in load()["candidates"] if r["source_occurrence_id"].endswith("performance:6")]
    assert next(r for r in rows if r["raw_title"].startswith("Joven Orquesta"))["stable_programme_order"] is None
    assert next(r for r in rows if r["raw_title"].startswith("Piano:"))["stable_programme_order"] is None
    assert next(r for r in rows if r["raw_title"].startswith("Campanas"))["stable_programme_order"] == 1

  def test_duplicate_raw_source_order_does_not_increment_order(self):
    rows = [r for r in load()["candidates"] if "Llamarme Guanche" in r["raw_title"]]
    self.assertEqual({r["stable_programme_order"] for r in rows}, {8})
    self.assertEqual(sum(r["action"] is None for r in rows), 2)

  def test_existing_same_event_work_is_review_not_insert(self):
    rows = load()["candidates"]
    self.assertGreater(load()["same_event_same_work_reviews"], 0)
    self.assertFalse(any(r["action"] == "insert_event_programme" and r["status"] == "existing_relationship_order_review" for r in rows))

  def test_repeated_work_requires_explicit_source_evidence(self):
    rows = [r for r in load()["candidates"] if r["status"] == "repeated_work_occurrence_review"]
    self.assertTrue(rows)
    self.assertTrue(all(r.get("existing_same_event_work_orders") for r in rows))

  def test_w_byrd_legacy_work_is_semantically_excluded(self):
    rows = [r for r in load()["candidates"] if r["raw_title"] == "W. Byrd"]
    self.assertEqual(len(rows), 3)
    self.assertTrue(all(r["status"] == "not_a_work" and r["action"] is None and r["stable_programme_order"] is None for r in rows))

  def test_voces_existing_relation_is_not_duplicate_insert(self):
    rows = [r for r in load()["candidates"] if "Voces del Meridiano" in r["raw_title"]]
    self.assertTrue(rows)
    self.assertTrue(all(r["action"] != "insert_event_programme" for r in rows))

  def test_mahler_iii_follows_header_without_shift(self):
    rows = [r for r in load()["candidates"] if r["source_occurrence_id"].endswith("performance:15") and "Sinfonía n." in r["raw_title"] and "3" in r["raw_title"]]
    self.assertTrue(rows)
    self.assertEqual(rows[0]["stable_programme_order"], 1)

  def test_unresolved_artistic_item_reserves_position(self):
    rows = [r for r in load()["candidates"] if r["raw_title"] == "Suite in E Major"]
    self.assertTrue(rows)
    self.assertTrue(all(r["status"] == "unresolved_work" for r in rows))
    self.assertTrue(all(r["stable_programme_order"] is not None for r in rows))
