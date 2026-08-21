"""Build the Auditorio event_programme dry-run artifacts.

This job is deliberately offline after the read-only database snapshots have
been captured. It never calls Supabase and never mutates canonical entities,
events, or event_programme.
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "global-entities"
AUD = ROOT / "artifacts" / "auditorio-nacional"
GIT = r"C:\Users\cheng\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"
PARSER = AUD / "auditorio-parser-dry-run.json"
EVENTS = AUD / "auditorio-live-readonly-event-source-snapshot.json"
EXISTING = AUD / "auditorio-live-readonly-event-programme-snapshot.json"
WORK_REF = "1cf4ae1:artifacts/global-entities/auditorio-work-final-consolidation-review.json"

ACCEPTED = {"existing_work_needs_identity_key", "existing_work_needs_composer_link"}
REVIEW = {
    "unresolved_work", "ambiguous_work", "parent_work_excerpt_review",
    "source_attribution_review", "parser_issue", "not_a_work",
    "event_identity_review", "event_programme_conflict_review",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_work_review():
    raw = subprocess.check_output(
        [GIT, "-c", f"safe.directory={ROOT}", "show", WORK_REF], cwd=ROOT, text=True, encoding="utf-8"
    )
    return json.loads(raw)["rows"]


def iso_parts(value: str):
    dt = datetime.fromisoformat(value)
    return dt.date().isoformat(), dt.strftime("%H:%M:%S")


def sql_quote(value):
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def build_rows():
    parser = load_json(PARSER)["occurrences"]
    event_snapshot = load_json(EVENTS)["rows"]
    existing = {(r["event_id"], int(r["order"])): r["work_id"] for r in load_json(EXISTING)["rows"]}
    work_rows = load_work_review()

    event_index = defaultdict(list)
    for event in event_snapshot:
        event_index[(event.get("source_url"), event.get("date"), event.get("start_time"),
                     event.get("title"), event.get("room"))].append(event)

    by_source = defaultdict(list)
    for row in work_rows:
        by_source[row["source_url"]].append(row)
    for source_rows in by_source.values():
        source_rows.sort(key=lambda r: tuple(r.get("programme_order") or (999999, 999999)))

    output = []
    occurrence_event_ids = {}
    for occurrence in parser:
        source_url = occurrence.get("source_url")
        date, start_time = iso_parts(occurrence["raw_datetime"])
        key = (source_url, date, start_time, occurrence.get("raw_title"), occurrence.get("raw_venue"))
        matches = {e["event_id"]: e for e in event_index.get(key, [])}
        occurrence_id = f"auditorio_nacional:performance:{occurrence['discovery_order'] + 1}"
        if len(matches) == 1:
            event = next(iter(matches.values()))
            occurrence_event_ids[occurrence_id] = event["event_id"]
        else:
            event = None
        source_rows = by_source.get(source_url, [])
        accepted_source_rows = [r for r in source_rows if r.get("final_status") in ACCEPTED and r.get("existing_work_id")]
        order_by_occurrence = {id(r): i for i, r in enumerate(accepted_source_rows, 1)}
        if not source_rows:
            source_rows = []
        for row in source_rows:
            final_status = row.get("final_status")
            resolved = row.get("existing_work_id") if final_status in ACCEPTED else None
            status = "resolved_executable" if resolved else (final_status if final_status in REVIEW else "unresolved_work")
            programme_order = order_by_occurrence.get(id(row))
            item = {
                "source_occurrence_id": occurrence_id,
                "source_url": source_url,
                "event_id": event["event_id"] if event else None,
                "programme_order": programme_order,
                "raw_title": row.get("raw_work_title") or row.get("raw_full_programme_line"),
                "raw_composer_fragment": row.get("raw_composer_fragment"),
                "resolved_work_id": resolved,
                "canonical_work_title": row.get("canonical_work_title") if resolved else None,
                "match_method": row.get("match_method"),
                "status": status,
                "action": None,
                "matcher_final_status": final_status,
                "matcher_occurrence_id": row.get("occurrence_id"),
                "raw_source_order": row.get("programme_order"),
                "performance_datetime": occurrence.get("raw_datetime"),
            }
            if resolved and event and programme_order is not None:
                prior = existing.get((event["event_id"], programme_order))
                if prior == resolved:
                    item["action"] = "existing_event_programme_noop"
                    item["existing_work_id_at_slot"] = prior
                elif prior is not None:
                    item["status"] = "event_programme_conflict_review"
                    item["action"] = None
                    item["existing_work_id_at_slot"] = prior
                else:
                    item["action"] = "insert_event_programme"
            elif not event:
                item["status"] = "event_identity_review"
            output.append(item)

    # Preserve source order and make duplicate exact rows explicit no-ops.
    seen = set()
    for row in output:
        if row["action"] in {"insert_event_programme", "existing_event_programme_noop"}:
            key = (row["event_id"], row["programme_order"], row["resolved_work_id"])
            if key in seen:
                row["action"] = "existing_event_programme_noop"
                row["duplicate_exact_row"] = True
            seen.add(key)
    return output, parser, event_snapshot, existing, occurrence_event_ids


def values(rows, actions=None):
    selected = [r for r in rows if r.get("action") in (actions or {"insert_event_programme"})]
    return ",\n".join(
        "(" + ", ".join(sql_quote(r[k]) for k in ("event_id", "resolved_work_id", "programme_order", "source_occurrence_id")) + ")"
        for r in selected
    ) or "(NULL, NULL, NULL, NULL)"


def build_sql(rows, expected_events, before_count, new_count):
    v = values(rows)
    return f"""-- Auditorio Nacional FINAL event_programme apply dry-run.
-- Generated {datetime.now().astimezone().isoformat()}; DO NOT EXECUTE in this phase.
-- Database writes are intentionally zero.
BEGIN;

DO $$
DECLARE
  expected_event_count integer := {expected_events};
  actual_event_count integer;
BEGIN
  SELECT count(*) INTO actual_event_count FROM public.events e
  JOIN public.organizations o ON o.id=e.organization_id
  WHERE o.slug='auditorio-nacional-inaem';
  IF actual_event_count <> expected_event_count THEN
    RAISE EXCEPTION 'Auditorio event baseline changed: expected %, got %', expected_event_count, actual_event_count;
  END IF;
END $$;

WITH batch(event_id, work_id, programme_order, source_occurrence_id) AS (VALUES
{v}
)
SELECT 1;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM (VALUES
{v}
  ) AS b(event_id, work_id, programme_order, source_occurrence_id)
  WHERE b.event_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.events e WHERE e.id=b.event_id)) THEN
    RAISE EXCEPTION 'Auditorio batch references a missing event';
  END IF;
  IF EXISTS (SELECT 1 FROM (VALUES
{v}
  ) AS b(event_id, work_id, programme_order, source_occurrence_id)
  WHERE b.work_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.works w WHERE w.id=b.work_id)) THEN
    RAISE EXCEPTION 'Auditorio batch references a missing work';
  END IF;
  IF EXISTS (
    SELECT 1 FROM (VALUES
{v}
    ) AS b(event_id, work_id, programme_order, source_occurrence_id)
    JOIN public.event_programme ep ON ep.event_id=b.event_id AND ep."order"=b.programme_order
    WHERE ep.work_id <> b.work_id
  ) THEN
    RAISE EXCEPTION 'Auditorio programme slot conflicts with a different Work';
  END IF;
END $$;

INSERT INTO public.event_programme(event_id, work_id, "order")
SELECT b.event_id, b.work_id, b.programme_order
FROM (VALUES
{v}
) AS b(event_id, work_id, programme_order, source_occurrence_id)
ON CONFLICT (event_id, "order") DO NOTHING;

-- Expected before/after counts are guards for the generated batch, not live writes.
-- expected_event_programme_before={before_count}; expected_event_programme_after={before_count + new_count}
COMMIT;
"""


def build_validation(rows, expected_events, before_count, new_count, counts):
    v = values(rows)
    review_values = ", ".join(f"({sql_quote(k)}, {v})" for k, v in sorted(counts.items())) or "(NULL,0)"
    return f"""-- Auditorio Nacional FINAL event_programme validation (read-only).
-- This file must be run only after an authorized apply; it performs no writes.
WITH batch(event_id, work_id, programme_order, source_occurrence_id) AS (VALUES
{v}
)
SELECT 'auditorio_event_programme_row_count_after' AS check_name, count(*)::text AS value
FROM public.event_programme ep JOIN public.events e ON e.id=ep.event_id
JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
SELECT 'expected_event_programme_before' AS check_name, {before_count}::text AS value
UNION ALL SELECT 'expected_event_programme_after', {before_count + new_count}::text
UNION ALL SELECT 'expected_auditorio_event_count', {expected_events}::text;
WITH batch(event_id, work_id, programme_order, source_occurrence_id) AS (VALUES {v})
SELECT 'all_staged_inserted_relationships_exist' AS check_name, count(*)::text AS value
FROM (SELECT b.* FROM batch b JOIN public.event_programme ep ON ep.event_id=b.event_id AND ep.work_id=b.work_id AND ep."order"=b.programme_order) x;
WITH batch(event_id, work_id, programme_order, source_occurrence_id) AS (VALUES {v})
SELECT 'missing_event_targets' AS check_name, count(*)::text AS value FROM batch b LEFT JOIN public.events e ON e.id=b.event_id WHERE e.id IS NULL;
WITH batch(event_id, work_id, programme_order, source_occurrence_id) AS (VALUES {v})
SELECT 'missing_work_targets' AS check_name, count(*)::text AS value FROM batch b LEFT JOIN public.works w ON w.id=b.work_id WHERE w.id IS NULL;
SELECT 'orphan_event_programme_rows' AS check_name, count(*)::text AS value FROM public.event_programme ep LEFT JOIN public.events e ON e.id=ep.event_id WHERE e.id IS NULL;
WITH batch(event_id, work_id, programme_order, source_occurrence_id) AS (VALUES {v})
SELECT 'batch_slot_conflicts' AS check_name, count(*)::text AS value FROM batch b JOIN public.event_programme ep ON ep.event_id=b.event_id AND ep."order"=b.programme_order WHERE ep.work_id<>b.work_id;
WITH batch(event_id, work_id, programme_order, source_occurrence_id) AS (VALUES {v})
SELECT 'programme_order_preservation' AS check_name, count(*)::text AS value FROM batch WHERE programme_order IS NULL;
WITH batch(event_id, work_id, programme_order, source_occurrence_id) AS (VALUES {v})
SELECT 'executable_null_event_id' AS check_name, count(*)::text AS value FROM batch WHERE event_id IS NULL;
WITH batch(event_id, work_id, programme_order, source_occurrence_id) AS (VALUES {v})
SELECT 'executable_null_work_id' AS check_name, count(*)::text AS value FROM batch WHERE work_id IS NULL;
SELECT status, count(*) FROM (VALUES {review_values}) AS s(status, count) GROUP BY status ORDER BY status;
"""


def main():
    rows, parser, event_snapshot, existing, occurrence_event_ids = build_rows()
    counts = Counter(r["status"] for r in rows)
    inserts = [r for r in rows if r.get("action") == "insert_event_programme"]
    executable = [r for r in rows if r.get("action") in {"insert_event_programme", "existing_event_programme_noop"}]
    event_ids = {r["event_id"] for r in executable}
    work_ids = {r["resolved_work_id"] for r in executable}
    reused = Counter(r.get("source_url") for r in parser)
    reused_urls = {u: n for u, n in reused.items() if n > 1}
    shared_occurrences = [o for o in parser if o.get("raw_datetime", "").startswith("2026-10-02") and "film-symphony-orchestra-odisea" in (o.get("source_url") or "")]
    shared_event_ids = sorted({occurrence_event_ids.get(f"auditorio_nacional:performance:{o['discovery_order'] + 1}") for o in shared_occurrences if occurrence_event_ids.get(f"auditorio_nacional:performance:{o['discovery_order'] + 1}")})
    source_status_counts = Counter(r.get("final_status") for r in load_work_review())
    report = {
        "source": "auditorio_nacional", "phase": "FINAL_EVENT_PROGRAMME_STAGING", "review_only": True,
        "database_writes": 0, "source_performance_occurrences": len(parser),
        "production_events_mapped": len({r["event_id"] for r in rows if r.get("event_id")}),
        "event_identity_review_count": len(parser) - len(occurrence_event_ids),
        "total_programme_candidates": len(rows), "resolved_executable_programme_candidates": len(executable),
        "existing_relationship_noop": sum(r.get("action") == "existing_event_programme_noop" for r in rows),
        "new_insert_event_programme": len(inserts), "review_only_counts": dict(sorted(counts.items())),
        "unique_event_uuids_receiving_programme": len(event_ids), "unique_resolved_work_uuids_used": len(work_ids),
        "matcher_source_status_counts": dict(sorted(source_status_counts.items())),
        "reused_detail_url_regression": {"reused_detail_urls": len(reused_urls),
            "performance_occurrences_covered": sum(reused_urls.values()),
            "programme_relationships_preserved": len(shared_event_ids),
            "film_symphony_odisea_2026_10_02_event_ids": shared_event_ids,
            "shared_url_performance_identity_preserved": len(shared_event_ids) == 2},
        "expected_event_programme_production_count_before": len(existing),
        "expected_event_programme_production_count_after": len(existing) + len(inserts),
        "no_sql_executed": True,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "auditorio-event-programme-final-production-staging.json").write_text(json.dumps({**report, "candidates": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    expected_events = len({e["event_id"] for e in event_snapshot})
    (OUT / "auditorio-event-programme-final-production-apply.sql").write_text(build_sql(rows, expected_events, len(existing), len(inserts)), encoding="utf-8")
    (OUT / "auditorio-event-programme-final-production-validation.sql").write_text(build_validation(rows, expected_events, len(existing), len(inserts), counts), encoding="utf-8")
    (OUT / "auditorio-event-programme-final-production-summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
