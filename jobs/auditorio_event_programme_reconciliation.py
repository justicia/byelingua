"""Final read-only Auditorio event_programme relationship reconciliation."""
from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "global-entities"
AUD = ROOT / "artifacts" / "auditorio-nacional"
GIT = r"C:\Users\cheng\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"
WORK_REF = "1cf4ae1:artifacts/global-entities/auditorio-work-final-consolidation-review.json"
REVIEW_STATUSES = {"ambiguous_work", "unresolved_work", "parent_work_excerpt_review", "source_attribution_review", "parser_issue", "not_a_work", "event_identity_review", "event_programme_conflict_review"}
NON_PROGRAMME = {"not_a_work", "parser_issue"}
DEBRIS_PATTERNS = [
    (re.compile(r"^(director|director musical|director orquesta|piano|viol[ií]n|voz|soprano|tenor|bar[ií]tono|mezzosoprano)\s*:", re.I), "artist_or_role_credit"),
    (re.compile(r"^(director|piano|viol[ií]n|voz|soprano|tenor|bar[ií]tono|mezzosoprano)\b", re.I), "artist_or_role_credit"),
    (re.compile(r"^(arr\.?|arreglo|arrangement)\b", re.I), "arrangement_annotation"),
]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value):
    value = unicodedata.normalize("NFKD", value or "").casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def q(value):
    return "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"


def work_review():
    return json.loads(subprocess.check_output([GIT, "-c", f"safe.directory={ROOT}", "show", WORK_REF], cwd=ROOT, text=True, encoding="utf-8"))["rows"]


def current_work_match(row, works, aliases):
    title_key = norm(row.get("raw_work_title") or row.get("raw_full_programme_line"))
    composer_id = row.get("resolved_composer_id")
    candidates = set()
    for work in works:
        if norm(work.get("title")) == title_key or False:
            if composer_id is None or work.get("composer_id") == composer_id:
                candidates.add(work["id"])
    for alias in aliases:
        if norm(alias.get("alias")) == title_key:
            work = next((w for w in works if w["id"] == alias["work_id"]), None)
            if work and (composer_id is None or work.get("composer_id") == composer_id):
                candidates.add(work["id"])
    if len(candidates) == 1:
        work_id = next(iter(candidates))
        return next(w for w in works if w["id"] == work_id), "current_master_exact_or_alias"
    # A unique title/alias in the closed master is safe even when the source
    # composer fragment is malformed or an attribution review is stale.
    unscoped = set()
    for work in works:
        if norm(work.get("title")) == title_key:
            unscoped.add(work["id"])
    for alias in aliases:
        if norm(alias.get("alias")) == title_key:
            unscoped.add(alias["work_id"])
    if len(unscoped) == 1:
        work_id = next(iter(unscoped))
        return next(w for w in works if w["id"] == work_id), "current_master_unique_title_or_alias"
    # Catalogue identifiers survive translation and source punctuation noise.
    tokens = re.findall(r"(?:bwv|rv|g|d|op)\s*\.?\s*\d+", (row.get("raw_work_title") or "").casefold())
    token_candidates = set()
    for token in tokens:
        token_key = norm(token)
        for work in works:
            if token_key in norm(work.get("title")) and (composer_id is None or work.get("composer_id") == composer_id):
                token_candidates.add(work["id"])
        for alias in aliases:
            if token_key in norm(alias.get("alias")):
                work = next((w for w in works if w["id"] == alias["work_id"]), None)
                if work and (composer_id is None or work.get("composer_id") == composer_id):
                    token_candidates.add(work["id"])
    if len(token_candidates) == 1:
        work_id = next(iter(token_candidates))
        return next(w for w in works if w["id"] == work_id), "current_master_catalogue_match"
    if len(candidates) > 1 or len(unscoped) > 1 or len(token_candidates) > 1:
        return None, "current_master_ambiguous"
    return None, "current_master_unresolved"


def debris_reason(title):
    for pattern, reason in DEBRIS_PATTERNS:
        if pattern.search(title or ""):
            return reason
    return None


def semantic_not_work(row):
    """Reject obvious source fragments before any Work lookup."""
    title = (row.get("raw_work_title") or row.get("raw_full_programme_line") or "").strip()
    folded = norm(title)
    if folded in {"w byrd", "joven orquesta de canarias jocan"}:
        return "composer_or_ensemble_header"
    if re.match(r"^(piano|director|director musical|director orquesta|voz|soprano|tenor|bar[ií]tono|mezzosoprano)\s*:", title, re.I):
        return "artist_or_role_credit"
    if "," in title and re.search(r"\b(director|directora|soprano|tenor|bar[ií]tono|mezzosoprano|solista|voz)\b", title, re.I):
        return "artist_or_role_credit"
    if re.match(r"^[A-ZÁÉÍÓÚÑ]\.\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+$", title):
        return "person_or_composer_header"
    if re.match(r"^(arr\.?|arreglo|arrangement)\b", title, re.I):
        return "arrangement_annotation"
    return None


def same_work(old, new, by_id):
    if not old or not new:
        return False
    if old == new:
        return True
    a, b = by_id.get(old), by_id.get(new)
    if not a or not b:
        return False
    return (a.get("identity_key") and a.get("identity_key") == b.get("identity_key")) or (norm(a.get("title")) == norm(b.get("title")) and a.get("composer_id") == b.get("composer_id"))


def build():
    parser = read(AUD / "auditorio-parser-dry-run.json")["occurrences"]
    event_rows = read(AUD / "auditorio-live-readonly-event-source-refresh.json")["rows"]
    programme_rows = read(AUD / "auditorio-live-readonly-event-programme-refresh.json")["rows"]
    master = read(AUD / "auditorio-live-readonly-work-master-refresh.json")["rows"]
    works, aliases = master["works"], master["aliases"]
    by_id = {w["id"]: w for w in works}
    existing = {(r["event_id"], int(r["order"])): r["work_id"] for r in programme_rows}
    review = work_review()
    by_url = defaultdict(list)
    for row in review:
        by_url[row["source_url"]].append(row)
    stable = {}
    primary = {}
    for url, rows in by_url.items():
        rows.sort(key=lambda r: tuple(r.get("programme_order") or (10**9, 10**9)))
        positions = {}
        next_position = 1
        for row in rows:
            raw_position = tuple(row.get("programme_order") or (10**9, 10**9))
            if semantic_not_work(row):
                stable[id(row)] = None
                primary[id(row)] = False
                continue
            if raw_position not in positions:
                positions[raw_position] = next_position
                next_position += 1
                primary[id(row)] = True
            else:
                primary[id(row)] = False
            stable[id(row)] = positions[raw_position]
    event_index = defaultdict(list)
    for event in event_rows:
        event_index[(event.get("source_url"), event.get("date"), event.get("start_time"), event.get("title"), event.get("room"))].append(event)
    candidates = []
    occurrence_event = {}
    for occurrence in parser:
        dt = datetime.fromisoformat(occurrence["raw_datetime"])
        key = (occurrence.get("source_url"), dt.date().isoformat(), dt.strftime("%H:%M:%S"), occurrence.get("raw_title"), occurrence.get("raw_venue"))
        matches = {e["event_id"]: e for e in event_index.get(key, [])}
        source_occurrence_id = f"auditorio_nacional:performance:{occurrence['discovery_order'] + 1}"
        event = next(iter(matches.values())) if len(matches) == 1 else None
        if event:
            occurrence_event[source_occurrence_id] = event["event_id"]
        for row in by_url.get(occurrence["source_url"], []):
            raw_status = row.get("final_status")
            stable_order = stable[id(row)]
            semantic_reason = semantic_not_work(row)
            matched, method = (None, semantic_reason) if semantic_reason or raw_status in NON_PROGRAMME or raw_status == "parent_work_excerpt_review" or raw_status == "source_attribution_review" else current_work_match(row, works, aliases)
            # Revalidate previously accepted/repaired UUIDs against the CLOSED
            # current master only as a lookup fallback. This is not adopting
            # the stale classification or mutating the Work master.
            if matched is None and raw_status in {"existing_work_needs_identity_key", "existing_work_needs_composer_link", "confirmed_new_global_work"}:
                prior_id = row.get("existing_work_id")
                if prior_id in by_id:
                    matched, method = by_id[prior_id], "current_master_existing_uuid_revalidated"
                else:
                    prior_identity = (row.get("proposed_repairs") or {}).get("identity_key")
                    if prior_identity:
                        identity_matches = [w for w in works if w.get("identity_key") == prior_identity]
                        if len(identity_matches) == 1:
                            matched, method = identity_matches[0], "current_master_identity_key_revalidated"
            if semantic_reason:
                resolved_id = canonical = None
                status = "not_a_work"
                match_method = f"semantic_not_work_gate:{semantic_reason}"
            elif matched:
                status = "resolved_executable" if event else "event_identity_review"
                resolved_id, canonical, match_method = matched["id"], matched["title"], method
            else:
                resolved_id = canonical = None
                match_method = method
                if event is None:
                    status = "event_identity_review"
                elif raw_status in NON_PROGRAMME:
                    status = raw_status
                elif raw_status == "parent_work_excerpt_review":
                    status = raw_status
                elif raw_status == "source_attribution_review":
                    status = raw_status
                elif method == "current_master_ambiguous":
                    status = "ambiguous_work"
                else:
                    status = "unresolved_work"
            item = {
                "source_occurrence_id": source_occurrence_id, "source_url": occurrence.get("source_url"),
                "event_id": event["event_id"] if event else None, "raw_source_order": row.get("programme_order"),
                "stable_programme_order": stable_order, "raw_title": row.get("raw_work_title") or row.get("raw_full_programme_line"),
                "raw_composer_fragment": row.get("raw_composer_fragment"), "resolved_work_id": resolved_id,
                "canonical_work_title": canonical, "match_method": match_method, "status": status, "action": None,
                "matcher_final_status_before_refresh": raw_status, "matcher_occurrence_id": row.get("occurrence_id"),
            }
            if resolved_id and event and stable_order is not None and primary[id(row)]:
                prior = existing.get((event["event_id"], stable_order))
                if prior is None:
                    item["action"] = "insert_event_programme"
                elif same_work(prior, resolved_id, by_id):
                    item["action"] = "existing_event_programme_noop"
                    item["existing_work_id_at_slot"] = prior
                else:
                    reason = debris_reason(by_id.get(prior, {}).get("title"))
                    if reason:
                        item["status"], item["action"] = "legacy_order_contamination_review", "legacy_order_contamination_review"
                        item["conflict_taxonomy"] = "legacy_order_contamination"
                    else:
                        item["status"], item["action"] = "event_programme_conflict_review", "event_programme_conflict_review"
                        item["conflict_taxonomy"] = "genuine_work_conflict"
                    item["existing_work_id_at_slot"] = prior
            elif not event and not semantic_reason:
                item["status"] = "event_identity_review"
            if not primary[id(row)] and stable_order is not None:
                item["status"] = "duplicate_source_position_review"
                item["action"] = None
                item["duplicate_source_position"] = True
            candidates.append(item)
    source_work_positions = defaultdict(set)
    for item in candidates:
        if item.get("resolved_work_id") and item.get("stable_programme_order") is not None:
            source_work_positions[(item["source_url"], item["resolved_work_id"])].add(tuple(item.get("raw_source_order") or ()))
    for item in candidates:
        if item.get("resolved_work_id") and item.get("event_id") and item.get("stable_programme_order") is not None and item.get("status") in {"event_programme_conflict_review", "legacy_order_contamination_review"}:
            same_orders = [order for (event_id, order), work_id in existing.items() if event_id == item["event_id"] and work_id == item["resolved_work_id"] and order != item["stable_programme_order"]]
            if same_orders:
                item["action"] = "existing_relationship_order_review"
                item["status"] = "existing_relationship_order_review"
                item["existing_same_event_work_orders"] = sorted(same_orders)
            elif len(source_work_positions[(item["source_url"], item["resolved_work_id"])]) > 1:
                item["action"] = "repeated_work_occurrence_review"
                item["status"] = "repeated_work_occurrence_review"
        if item.get("action") != "insert_event_programme":
            continue
        existing_orders = [order for (event_id, order), work_id in existing.items() if event_id == item["event_id"] and work_id == item["resolved_work_id"] and order != item["stable_programme_order"]]
        if existing_orders:
            if len(source_work_positions[(item["source_url"], item["resolved_work_id"])]) > 1:
                item["action"] = "repeated_work_occurrence_review"
                item["status"] = "repeated_work_occurrence_review"
            else:
                item["action"] = "existing_relationship_order_review"
                item["status"] = "existing_relationship_order_review"
            item["existing_same_event_work_orders"] = sorted(existing_orders)
    return candidates, parser, event_rows, programme_rows, works, occurrence_event, review, existing, by_id


def values(rows, only_inserts=True):
    chosen = [r for r in rows if (r.get("action") == "insert_event_programme" if only_inserts else r.get("action") in {"insert_event_programme", "existing_event_programme_noop"})]
    return ",\n".join("(" + ", ".join(q(r[k]) for k in ("event_id", "resolved_work_id", "stable_programme_order", "source_occurrence_id")) + ")" for r in chosen) or "(NULL, NULL, NULL, NULL)"


def sql_apply(candidates, event_count, programme_count, insert_count):
    v = values(candidates)
    return f"""-- FINAL Auditorio relationship reconciliation. DO NOT EXECUTE in this phase.
-- database_writes = 0; generated {datetime.now().astimezone().isoformat()}
BEGIN;
DO $$ DECLARE events_now integer; programme_now integer;
BEGIN
  SELECT count(*) INTO events_now FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
  SELECT count(*) INTO programme_now FROM public.event_programme ep JOIN public.events e ON e.id=ep.event_id JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
  IF events_now <> {event_count} THEN RAISE EXCEPTION 'Auditorio event baseline changed: expected {event_count}, got %', events_now; END IF;
  IF programme_now <> {programme_count} THEN RAISE EXCEPTION 'Auditorio event_programme baseline changed: expected {programme_count}, got %', programme_now; END IF;
END $$;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM (VALUES {v}) b(event_id,work_id,programme_order,source_occurrence_id) WHERE b.event_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.events e WHERE e.id=b.event_id)) THEN RAISE EXCEPTION 'Missing event target'; END IF;
  IF EXISTS (SELECT 1 FROM (VALUES {v}) b(event_id,work_id,programme_order,source_occurrence_id) WHERE b.work_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.works w WHERE w.id=b.work_id)) THEN RAISE EXCEPTION 'Missing Work target'; END IF;
  IF EXISTS (SELECT 1 FROM (VALUES {v}) b(event_id,work_id,programme_order,source_occurrence_id) JOIN public.event_programme ep ON ep.event_id=b.event_id AND ep."order"=b.programme_order WHERE ep.work_id<>b.work_id) THEN RAISE EXCEPTION 'Stable programme slot conflict'; END IF;
  IF EXISTS (SELECT 1 FROM (VALUES {v}) b(event_id,work_id,programme_order,source_occurrence_id) JOIN public.event_programme ep ON ep.event_id=b.event_id AND ep.work_id=b.work_id AND ep."order"<>b.programme_order) THEN RAISE EXCEPTION 'Same Event+Work already exists at another order'; END IF;
END $$;
INSERT INTO public.event_programme(event_id, work_id, "order")
SELECT event_id, work_id, programme_order FROM (VALUES {v}) b(event_id,work_id,programme_order,source_occurrence_id)
ON CONFLICT (event_id,"order") DO NOTHING;
-- expected_event_programme_before={programme_count}; expected_safe_insert_count={insert_count}; expected_after={programme_count + insert_count}
COMMIT;
"""


def sql_validation(candidates, event_count, programme_count, insert_count, taxonomy, debris_count):
    v = values(candidates)
    tax = ", ".join(f"({q(k)},{n})" for k, n in sorted(taxonomy.items())) or "(NULL,0)"
    return f"""-- FINAL Auditorio relationship reconciliation validation. Read-only; do not execute as part of apply.
WITH batch(event_id,work_id,programme_order,source_occurrence_id) AS (VALUES {v})
SELECT 'auditorio_event_programme_after' AS check_name,count(*)::text AS value FROM public.event_programme ep JOIN public.events e ON e.id=ep.event_id JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
SELECT 'expected_auditorio_events' AS check_name,{event_count}::text AS value UNION ALL SELECT 'expected_before',{programme_count}::text UNION ALL SELECT 'expected_after',{programme_count + insert_count}::text;
WITH batch(event_id,work_id,programme_order,source_occurrence_id) AS (VALUES {v}) SELECT 'inserted_relations_exist',count(*)::text FROM batch b JOIN public.event_programme ep ON ep.event_id=b.event_id AND ep.work_id=b.work_id AND ep."order"=b.programme_order;
WITH batch(event_id,work_id,programme_order,source_occurrence_id) AS (VALUES {v}) SELECT 'missing_event_targets',count(*)::text FROM batch b LEFT JOIN public.events e ON e.id=b.event_id WHERE e.id IS NULL;
WITH batch(event_id,work_id,programme_order,source_occurrence_id) AS (VALUES {v}) SELECT 'missing_work_targets',count(*)::text FROM batch b LEFT JOIN public.works w ON w.id=b.work_id WHERE w.id IS NULL;
WITH batch(event_id,work_id,programme_order,source_occurrence_id) AS (VALUES {v}) SELECT 'batch_slot_conflicts',count(*)::text FROM batch b JOIN public.event_programme ep ON ep.event_id=b.event_id AND ep."order"=b.programme_order WHERE ep.work_id<>b.work_id;
WITH batch(event_id,work_id,programme_order,source_occurrence_id) AS (VALUES {v}) SELECT 'same_event_same_work_duplicate_introduced',count(*)::text FROM batch b JOIN public.event_programme ep ON ep.event_id=b.event_id AND ep.work_id=b.work_id AND ep."order"<>b.programme_order;
WITH batch(event_id,work_id,programme_order,source_occurrence_id) AS (VALUES {v}) SELECT 'stable_programme_order_nulls',count(*)::text FROM batch WHERE programme_order IS NULL;
SELECT 'legacy_parser_debris_event_programme_rows' AS check_name,{debris_count}::text AS value;
SELECT taxonomy,count FROM (VALUES {tax}) AS x(taxonomy,count) ORDER BY taxonomy;
"""


def main():
    candidates, parser, event_rows, programme_rows, works, occurrence_event, review, existing, by_id = build()
    taxonomy = Counter({"existing_relationship_order_review": 0, "legacy_order_contamination_review": 0, "genuine_work_conflict": 0, "repeated_work_occurrence_review": 0})
    for row in candidates:
        if row.get("status") in taxonomy:
            taxonomy[row["status"]] += 1
        elif row.get("conflict_taxonomy") == "genuine_work_conflict":
            taxonomy["genuine_work_conflict"] += 1
    debris = []
    for (event_id, order), work_id in existing.items():
        reason = debris_reason(by_id.get(work_id, {}).get("title", ""))
        if reason:
            debris.append({"event_id": event_id, "order": order, "current_work_id": work_id, "current_work_title": by_id.get(work_id, {}).get("title"), "reason": reason})
    counts = Counter(r["status"] for r in candidates)
    executable = [r for r in candidates if r.get("action") in {"insert_event_programme", "existing_event_programme_noop"}]
    inserts = [r for r in candidates if r.get("action") == "insert_event_programme"]
    reused = Counter(o.get("source_url") for o in parser)
    shared = [o for o in parser if "film-symphony-orchestra-odisea" in (o.get("source_url") or "") and o.get("raw_datetime", "").startswith("2026-10-02")]
    shared_ids = sorted({occurrence_event.get(f"auditorio_nacional:performance:{o['discovery_order'] + 1}") for o in shared if occurrence_event.get(f"auditorio_nacional:performance:{o['discovery_order'] + 1}")})
    report = {
        "source": "auditorio_nacional", "phase": "FINAL_RELATIONSHIP_RECONCILIATION", "review_only": True, "database_writes": 0,
        "current_production_baseline": {"auditorio_events": 583, "auditorio_event_programme_rows": 2909, "works": len(works), "work_aliases": len(read(AUD / "auditorio-live-readonly-work-master-refresh.json")["rows"]["aliases"])},
        "event_baseline_delta_explanation": {"previous_source_linked_event_identity_count": 582, "current_event_count": 583, "unlinked_event": "ab000640-fb8e-43ba-850b-c3da076f00b9", "reason": "current production event has no public.event_sources row"},
        "source_performance_occurrences": len(parser), "mapped_performance_occurrences": len(occurrence_event), "event_identity_reviews": len(parser) - len(occurrence_event),
        "programme_candidates": len(candidates), "resolved_work_candidates_after_post_apply_refresh": sum(bool(r.get("resolved_work_id")) for r in candidates),
        "safe_noops": sum(r.get("action") == "existing_event_programme_noop" for r in candidates), "safe_inserts": len(inserts),
        "same_event_same_work_reviews": taxonomy["existing_relationship_order_review"], "repeated_work_occurrence_reviews": taxonomy["repeated_work_occurrence_review"],
        "legacy_order_contamination_reviews": taxonomy["legacy_order_contamination_review"], "genuine_work_conflicts": taxonomy["genuine_work_conflict"],
        "relationship_review_taxonomy": dict(sorted(taxonomy.items())), "current_stable_slot_conflicts": sum(r.get("status") in {"event_programme_conflict_review", "legacy_order_contamination_review", "existing_relationship_order_review", "repeated_work_occurrence_review"} for r in candidates),
        "legacy_parser_debris_event_programme_row_count": len(debris), "review_only_work_classification_counts": dict(sorted(counts.items())),
        "reused_detail_url_regression": {"reused_detail_urls": sum(n > 1 for n in reused.values()), "performance_occurrences_covered": sum(n for n in reused.values() if n > 1), "film_symphony_odisea_event_ids": shared_ids, "two_independent_event_uuids": len(shared_ids) == 2},
        "expected_event_programme_before": 2909, "expected_event_programme_after": 2909 + len(inserts), "no_sql_executed": True,
    }
    OUT.mkdir(exist_ok=True, parents=True)
    (OUT / "auditorio-event-programme-final-production-staging.json").write_text(json.dumps({**report, "candidates": candidates, "legacy_parser_debris_evidence": debris}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "auditorio-event-programme-final-production-apply.sql").write_text(sql_apply(candidates, 583, 2909, len(inserts)), encoding="utf-8")
    (OUT / "auditorio-event-programme-final-production-validation.sql").write_text(sql_validation(candidates, 583, 2909, len(inserts), taxonomy, len(debris)), encoding="utf-8")
    (OUT / "auditorio-event-programme-final-production-summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (AUD / "auditorio-event-programme-legacy-parser-debris-review.json").write_text(json.dumps({"database_writes": 0, "rows": debris}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
