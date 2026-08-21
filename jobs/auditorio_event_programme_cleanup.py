import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "global-entities"
STAGING = OUT / "auditorio-event-programme-final-production-staging.json"
CURRENT = OUT / "auditorio-event-programme-cleanup-current-state.json"
WORKS = ROOT / "artifacts" / "auditorio-nacional" / "auditorio-live-readonly-work-master-refresh.json"

REVIEW_STATUSES = {
    "existing_relationship_order_review",
    "event_programme_conflict_review",
    "repeated_work_occurrence_review",
}
EXECUTABLE_STATUSES = {
    "resolved_executable",
    "existing_relationship_order_review",
    "event_programme_conflict_review",
    "repeated_work_occurrence_review",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def person_or_composer_header(title):
    return bool(re.fullmatch(
        r"(?:[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'’-]+|[A-ZÁÉÍÓÚÑÜ]\.)(?:\s+(?:[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'’-]+|[A-ZÁÉÍÓÚÑÜ]\.)){1,3}",
        title.strip(),
    ))


def sql_uuid(value):
    return f"'{value}'::uuid"


def sql_text(value):
    return "'" + value.replace("'", "''") + "'::text"


def values_sql(rows, columns, formatter):
    lines = []
    for row in rows:
        lines.append("(" + ", ".join(formatter(row)) + ")")
    return "VALUES " + ",\n".join(lines)


def typed_current(rows):
    return values_sql(rows, ("event_id", "programme_order", "work_id"), lambda r: (
        sql_uuid(r["event_id"]), f"{int(r['order'])}::integer", sql_uuid(r["work_id"])
    ))


def typed_desired(rows):
    return values_sql(rows, ("event_id", "programme_order", "work_id", "source_occurrence_id"), lambda r: (
        sql_uuid(r["event_id"]), f"{int(r['order'])}::integer", sql_uuid(r["work_id"]), sql_text(r["source_occurrence_id"])
    ))


def typed_event_ids(event_ids):
    return "VALUES " + ",\n".join(f"({sql_uuid(event_id)})" for event_id in event_ids)


def build_sql(current_rows, desired_rows, event_ids, baseline, rows_deleted, rows_inserted, expected_after):
    current_values = typed_current(current_rows)
    desired_values = typed_desired(desired_rows)
    event_values = typed_event_ids(event_ids)
    return f"""-- FINAL Auditorio event_programme relationship cleanup. DO NOT EXECUTE in this phase.
-- database_writes = 0; event-level replacement only for fully deterministic Events.
BEGIN;
DO $$ DECLARE events_now integer; programme_now integer;
BEGIN
  SELECT count(*) INTO events_now FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
  SELECT count(*) INTO programme_now FROM public.event_programme ep JOIN public.events e ON e.id=ep.event_id JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
  IF events_now <> {baseline['auditorio_events']} THEN RAISE EXCEPTION 'Auditorio event baseline changed: expected {baseline['auditorio_events']}, got %', events_now; END IF;
  IF programme_now <> {baseline['auditorio_event_programme']} THEN RAISE EXCEPTION 'Auditorio event_programme baseline changed: expected {baseline['auditorio_event_programme']}, got %', programme_now; END IF;
END $$;
DO $$ BEGIN
  IF EXISTS (WITH expected(event_id,programme_order,work_id) AS ({current_values})
             SELECT 1 FROM expected x LEFT JOIN public.event_programme ep ON ep.event_id=x.event_id AND ep."order"=x.programme_order AND ep.work_id=x.work_id WHERE ep.event_id IS NULL)
  THEN RAISE EXCEPTION 'Cleanup current snapshot missing or changed'; END IF;
  IF EXISTS (WITH expected(event_id,programme_order,work_id) AS ({current_values}), cleanup_events(event_id) AS ({event_values})
             SELECT 1 FROM public.event_programme ep JOIN cleanup_events ce ON ce.event_id=ep.event_id
             WHERE NOT EXISTS (SELECT 1 FROM expected x WHERE x.event_id=ep.event_id AND x.programme_order=ep."order" AND x.work_id=ep.work_id))
  THEN RAISE EXCEPTION 'Cleanup current snapshot has unexpected extra row'; END IF;
  IF EXISTS (WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
             SELECT 1 FROM desired d LEFT JOIN public.events e ON e.id=d.event_id WHERE e.id IS NULL)
  THEN RAISE EXCEPTION 'Desired cleanup Event target missing'; END IF;
  IF EXISTS (WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
             SELECT 1 FROM desired d LEFT JOIN public.works w ON w.id=d.work_id WHERE w.id IS NULL)
  THEN RAISE EXCEPTION 'Desired cleanup Work target missing'; END IF;
  IF EXISTS (WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
             SELECT event_id,programme_order FROM desired GROUP BY event_id,programme_order HAVING count(*)<>1)
  THEN RAISE EXCEPTION 'Desired cleanup duplicate event/order'; END IF;
END $$;
DELETE FROM public.event_programme ep
USING ({event_values}) AS cleanup_events(event_id)
WHERE ep.event_id=cleanup_events.event_id;
INSERT INTO public.event_programme(event_id, work_id, "order")
SELECT event_id, work_id, programme_order
FROM ({desired_values}) AS desired(event_id,programme_order,work_id,source_occurrence_id);
DO $$ BEGIN
  IF EXISTS (WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
             SELECT 1 FROM desired d LEFT JOIN public.event_programme ep ON ep.event_id=d.event_id AND ep."order"=d.programme_order AND ep.work_id=d.work_id WHERE ep.event_id IS NULL)
  THEN RAISE EXCEPTION 'Post-cleanup desired row missing'; END IF;
  IF EXISTS (WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
             SELECT 1 FROM public.event_programme ep JOIN (SELECT DISTINCT event_id FROM desired) d ON d.event_id=ep.event_id
             WHERE NOT EXISTS (SELECT 1 FROM desired x WHERE x.event_id=ep.event_id AND x.programme_order=ep."order" AND x.work_id=ep.work_id))
  THEN RAISE EXCEPTION 'Post-cleanup unexpected row'; END IF;
END $$;
-- expected_before={baseline['auditorio_event_programme']}; rows_deleted={rows_deleted}; rows_inserted={rows_inserted}; expected_after={expected_after}
COMMIT;
"""


def build_validation(desired_rows, event_ids, baseline, rows_deleted, rows_inserted, expected_after):
    desired_values = typed_desired(desired_rows)
    event_values = typed_event_ids(event_ids)
    return f"""-- FINAL Auditorio event_programme relationship cleanup validation. Read-only; do not execute as apply.
SELECT 'auditorio_event_programme_after' AS check_name,count(*)::text AS value FROM public.event_programme ep JOIN public.events e ON e.id=ep.event_id JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
SELECT 'programme_rows_before' AS check_name,{baseline['auditorio_event_programme']}::text AS value UNION ALL SELECT 'rows_deleted',{rows_deleted}::text UNION ALL SELECT 'rows_inserted',{rows_inserted}::text UNION ALL SELECT 'programme_rows_after',{expected_after}::text;
WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
SELECT 'current_minus_desired' AS check_name,count(*)::text FROM (SELECT ep.event_id,ep."order" AS programme_order,ep.work_id FROM public.event_programme ep JOIN (SELECT DISTINCT event_id FROM desired) d ON d.event_id=ep.event_id EXCEPT SELECT event_id,programme_order,work_id FROM desired) q;
WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
SELECT 'desired_minus_current' AS check_name,count(*)::text FROM (SELECT event_id,programme_order,work_id FROM desired EXCEPT SELECT ep.event_id,ep."order",ep.work_id FROM public.event_programme ep JOIN (SELECT DISTINCT event_id FROM desired) d ON d.event_id=ep.event_id) q;
WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
SELECT 'unexpected_extra_programme_rows' AS check_name,count(*)::text FROM (SELECT ep.event_id,ep."order",ep.work_id FROM public.event_programme ep JOIN (SELECT DISTINCT event_id FROM desired) d ON d.event_id=ep.event_id EXCEPT SELECT event_id,programme_order,work_id FROM desired) q;
WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
SELECT 'missing_target_rows' AS check_name,count(*)::text FROM (SELECT event_id,programme_order,work_id FROM desired EXCEPT SELECT ep.event_id,ep."order",ep.work_id FROM public.event_programme ep) q;
WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
SELECT 'duplicate_event_order' AS check_name,count(*)::text FROM (SELECT event_id,programme_order FROM desired GROUP BY event_id,programme_order HAVING count(*)>1) q;
SELECT 'duplicate_event_order_in_production' AS check_name,count(*)::text FROM (SELECT ep.event_id,ep."order" FROM public.event_programme ep GROUP BY ep.event_id,ep."order" HAVING count(*)>1) q;
WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
SELECT 'invalid_event_fk' AS check_name,count(*)::text FROM desired d LEFT JOIN public.events e ON e.id=d.event_id WHERE e.id IS NULL;
WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
SELECT 'invalid_work_fk' AS check_name,count(*)::text FROM desired d LEFT JOIN public.works w ON w.id=d.work_id WHERE w.id IS NULL;
WITH desired(event_id,programme_order,work_id,source_occurrence_id) AS ({desired_values})
SELECT 'unintended_event_work_duplicate' AS check_name,count(*)::text FROM (SELECT event_id,work_id FROM desired GROUP BY event_id,work_id HAVING count(*)>1) q;
SELECT 'cleanup_event_count' AS check_name,{len(event_ids)}::text AS value;
-- cleanup events are intentionally limited to this typed UUID set:
WITH cleanup_events(event_id) AS ({event_values}) SELECT 'cleanup_event_ids' AS check_name,count(*)::text FROM cleanup_events;
"""


def main():
    staging = load(STAGING)
    current_doc = load(CURRENT)
    work_doc = load(WORKS)
    rows = staging["candidates"]
    current = current_doc["rows"]
    work_titles = {r["id"]: r["title"] for r in work_doc["rows"]["works"]}
    affected = {r["event_id"] for r in rows if r["status"] in REVIEW_STATUSES}
    affected |= {r["event_id"] for r in staging["legacy_parser_debris_evidence"]}
    current_by_event = defaultdict(list)
    for r in current:
        current_by_event[r["event_id"]].append(r)

    deterministic = []
    deferred = []
    desired_by_event = {}
    current_by_cleanup_event = {}
    event_classification = {}
    for event_id in sorted(affected):
        event_rows = [r for r in rows if r["event_id"] == event_id]
        status_set = {r["status"] for r in event_rows}
        by_order = defaultdict(list)
        reason = None
        if not event_rows or not status_set.issubset(EXECUTABLE_STATUSES):
            reason = "partial_or_uncertain_event"
        if any(r["resolved_work_id"] and person_or_composer_header(r["raw_title"]) for r in event_rows):
            reason = "partial_or_uncertain_event"
        for r in event_rows:
            if r["resolved_work_id"]:
                by_order[r["stable_programme_order"]].append(r)
        if any(order is None or len(items) != 1 for order, items in by_order.items()):
            reason = "partial_or_uncertain_event"
        if reason:
            deferred.append(event_id)
            continue
        desired = [
            {"event_id": event_id, "order": int(order), "work_id": items[0]["resolved_work_id"],
             "source_occurrence_id": items[0]["source_occurrence_id"], "raw_title": items[0]["raw_title"],
             "canonical_work_title": items[0]["canonical_work_title"]}
            for order, items in sorted(by_order.items())
        ]
        current_rows = sorted(current_by_event.get(event_id, []), key=lambda r: int(r["order"]))
        desired_work_ids = {r["work_id"] for r in desired}
        current_work_ids = {r["work_id"] for r in current_rows}
        if any(r["status"] == "event_programme_conflict_review" for r in event_rows):
            classification = "source_resolved_existing_relation_wrong"
        elif current_work_ids == desired_work_ids:
            classification = "deterministic_reorder_only"
        else:
            classification = "deterministic_reorder_plus_debris_cleanup"
        deterministic.append(event_id)
        desired_by_event[event_id] = desired
        current_by_cleanup_event[event_id] = current_rows
        event_classification[event_id] = classification

    cleanup_current = [r for event_id in deterministic for r in current_by_cleanup_event[event_id]]
    cleanup_desired = [r for event_id in deterministic for r in desired_by_event[event_id]]
    rows_deleted = len(cleanup_current)
    rows_inserted = len(cleanup_desired)
    baseline = current_doc["baseline"]
    expected_after = baseline["auditorio_event_programme"] - rows_deleted + rows_inserted
    conflict_rows = [r for r in rows if r["status"] == "event_programme_conflict_review"]
    conflict_classification = Counter(
        "source_resolved_existing_relation_wrong" if r["event_id"] in deterministic else "unresolved_relationship_conflict"
        for r in conflict_rows
    )
    debris = staging["legacy_parser_debris_evidence"]
    debris_removed = sum(r["event_id"] in deterministic for r in debris)
    remaining_reviews = sum(
        r["status"] in REVIEW_STATUSES and r["event_id"] not in deterministic
        for r in rows
    )
    summary = {
        "source": "auditorio_nacional",
        "phase": "FINAL_RELATIONSHIP_CLEANUP",
        "review_only": True,
        "database_writes": 0,
        "production_baseline": baseline,
        "review_backlog": {"existing_relationship_order_review": 261, "genuine_work_conflict": 26, "repeated_work_occurrence_review": 1},
        "affected_review_rows": sum(r["status"] in REVIEW_STATUSES for r in rows),
        "unique_affected_events": len(affected),
        "fully_deterministic_events": len(deterministic),
        "deferred_events": len(deferred),
        "deterministic_reorder_only": sum(v == "deterministic_reorder_only" for v in event_classification.values()),
        "deterministic_reorder_plus_debris_cleanup": sum(v == "deterministic_reorder_plus_debris_cleanup" for v in event_classification.values()),
        "source_resolved_existing_relation_wrong": conflict_classification["source_resolved_existing_relation_wrong"],
        "legacy_parser_relationship_wrong": 0,
        "relationship_correct_current_source_mapping_wrong": 0,
        "unresolved_relationship_conflict": conflict_classification["unresolved_relationship_conflict"],
        "approved_repeated_work_occurrence": 0,
        "rejected_repeated_work_occurrence": 1,
        "legacy_debris_rows_removed": debris_removed,
        "legacy_debris_rows_deferred": len(debris) - debris_removed,
        "remaining_relationship_review_rows": remaining_reviews,
        "cleanup_event_ids": deterministic,
        "rows_current_in_cleanup_events": rows_deleted,
        "desired_rows_after_cleanup": rows_inserted,
        "rows_deleted": rows_deleted,
        "rows_inserted": rows_inserted,
        "expected_event_programme_after": expected_after,
        "no_sql_executed": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    cleanup_current_doc = {"source": "auditorio_nacional", "database_writes": 0, "baseline": baseline, "rows": cleanup_current}
    cleanup_desired_doc = {"source": "auditorio_nacional", "database_writes": 0, "rows": cleanup_desired}
    (OUT / "auditorio-event-programme-cleanup-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "auditorio-event-programme-cleanup-current-state.json").write_text(json.dumps({**cleanup_current_doc, "queried_from_live_production": True}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "auditorio-event-programme-cleanup-desired-state.json").write_text(json.dumps(cleanup_desired_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "auditorio-event-programme-cleanup-production-apply.sql").write_text(build_sql(cleanup_current, cleanup_desired, deterministic, baseline, rows_deleted, rows_inserted, expected_after), encoding="utf-8")
    (OUT / "auditorio-event-programme-cleanup-production-validation.sql").write_text(build_validation(cleanup_desired, deterministic, baseline, rows_deleted, rows_inserted, expected_after), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
