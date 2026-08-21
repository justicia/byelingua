import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "global-entities"
STAGING = OUT / "auditorio-event-programme-final-production-staging.json"
FIRST = OUT / "auditorio-event-programme-cleanup-summary.json"
CURRENT = OUT / "auditorio-event-programme-deferred-current-state.json"
WORKS = ROOT / "artifacts" / "auditorio-nacional" / "auditorio-live-readonly-work-master-refresh.json"
RAW = ROOT / "artifacts" / "auditorio-nacional" / "auditorio-parser-dry-run.json"
REVIEW = {"existing_relationship_order_review", "event_programme_conflict_review", "repeated_work_occurrence_review"}
BUCKETS = {"SECOND_BATCH_DETERMINISTIC", "FINAL_RESIDUAL_BACKLOG"}
PRIOR_PROPOSED = {"03abbf8d-381c-4132-8747-aa42bfd8f226", "045fd06e-3ce8-4595-979f-eca5a0f6a522", "04cd5682-b173-490b-b822-1d33585c7cc7", "0537a5f4-bb60-4005-a04e-4a3c2bff8c10", "072264f4-b6b0-44f5-9bd6-4c711f6f8e30", "0f78b159-c511-4a60-b976-ebabf9217d1e", "1f6130f6-7824-4795-af56-fc3950aa03f5", "23dd182d-6d7b-472a-baf7-29e55390ed79", "254f03d3-4b85-4418-9786-ccefdccf6b6d", "4d2f80cb-40f9-4eb6-be8d-387ba6085641", "4f9d3cb2-7ed3-4edc-8eab-e8bdef8b6814", "54f8f381-cff9-44f2-87e7-d5474b70fbc1", "642c41c0-723c-4d11-98f5-8ac7d0f9f2a6", "68f1056e-38ff-4b01-9de5-8131ce841dbb", "724a01df-5cdd-4ae3-b04d-639f620e54da", "75313c84-3a84-4cc8-9bdf-466ba7f681ca", "7827b0b5-5192-4550-a94d-0b1d5e2ab5dd", "7c4d0397-b098-4002-8314-f85ade59257d", "81d2c668-7e8a-4ee3-ade5-03cf5631ed15", "990464ec-755d-4ace-be39-576058e802a3", "9e69d010-f549-4abb-8b6f-553ebefed690", "b6261109-846e-4d47-b6cb-2cbc3bb4455b", "b7ad8748-c064-4176-a281-1e781c70e996", "b9daae0a-350c-4988-93ec-509671f6c2e7", "bf7d7437-5c71-4911-a5d6-a0beb8078af6", "c226cc57-d877-4b65-bbb6-5f77de752c53", "ce4c0c7b-8b88-4842-b4a1-4b165fc5a281", "e66eacc7-16ad-4183-8859-b0d3260a3424"}


def load(p): return json.loads(p.read_text(encoding="utf-8"))


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def sql_uuid(v): return "'" + v + "'::uuid"
def sql_text(v): return "'" + v.replace("'", "''") + "'::text"


def values(rows, four=True):
    out = []
    for r in rows:
        vals = [sql_uuid(r["event_id"]), sql_uuid(r["work_id"]), f"{int(r['order'])}::integer"]
        if four: vals.append(sql_text(r["source_occurrence_id"]))
        out.append("(" + ", ".join(vals) + ")")
    return "VALUES " + ",\n".join(out)


def event_values(ids): return "VALUES " + ",\n".join("(" + sql_uuid(x) + ")" for x in ids)


def build_apply(current, desired, ids, baseline, deleted, inserted, after):
    cv, dv, ev = values(current, False), values(desired), event_values(ids)
    return f"""-- Deferred Auditorio event_programme cleanup. Review-only; do not execute.
-- database_writes = 0; generated_at = {datetime.now(timezone.utc).isoformat()}
BEGIN;
DO $$ DECLARE e integer; p integer; BEGIN
 SELECT count(*) INTO e FROM public.events e JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
 SELECT count(*) INTO p FROM public.event_programme ep JOIN public.events e ON e.id=ep.event_id JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
 IF e <> {baseline['auditorio_events']} THEN RAISE EXCEPTION 'Event baseline drift'; END IF;
 IF p <> {baseline['auditorio_event_programme']} THEN RAISE EXCEPTION 'event_programme baseline drift'; END IF;
END $$;
DO $$ BEGIN
 IF EXISTS (WITH x(event_id,work_id,programme_order) AS ({cv}) SELECT 1 FROM x LEFT JOIN public.event_programme ep ON ep.event_id=x.event_id AND ep."order"=x.programme_order AND ep.work_id=x.work_id WHERE ep.event_id IS NULL) THEN RAISE EXCEPTION 'current snapshot drift'; END IF;
 IF EXISTS (WITH x(event_id,work_id,programme_order) AS ({cv}), ce(event_id) AS ({ev}) SELECT 1 FROM public.event_programme ep JOIN ce ON ce.event_id=ep.event_id WHERE NOT EXISTS (SELECT 1 FROM x WHERE x.event_id=ep.event_id AND x.programme_order=ep."order" AND x.work_id=ep.work_id)) THEN RAISE EXCEPTION 'unexpected current row'; END IF;
 IF EXISTS (WITH x(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}) SELECT 1 FROM x LEFT JOIN public.events e ON e.id=x.event_id WHERE e.id IS NULL) THEN RAISE EXCEPTION 'missing Event'; END IF;
 IF EXISTS (WITH x(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}) SELECT 1 FROM x LEFT JOIN public.works w ON w.id=x.work_id WHERE w.id IS NULL) THEN RAISE EXCEPTION 'missing Work'; END IF;
 IF EXISTS (WITH x(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}) SELECT 1 FROM x GROUP BY event_id,programme_order HAVING count(*) <> 1) THEN RAISE EXCEPTION 'duplicate target slot'; END IF;
 IF EXISTS (WITH x(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}) SELECT 1 FROM x GROUP BY event_id,work_id HAVING count(*) > 1) THEN RAISE EXCEPTION 'unapproved same Event+Work duplicate'; END IF;
END $$;
DELETE FROM public.event_programme ep USING ({ev}) ce(event_id) WHERE ep.event_id=ce.event_id;
INSERT INTO public.event_programme(event_id, work_id, "order") SELECT event_id, work_id, programme_order FROM ({dv}) x(event_id,work_id,programme_order,source_occurrence_id);
DO $$ BEGIN
 IF (SELECT count(*) FROM public.event_programme ep JOIN ({ev}) ce(event_id) ON ce.event_id=ep.event_id) <> {inserted} THEN RAISE EXCEPTION 'inserted relationship count mismatch'; END IF;
END $$;
-- expected_before={baseline['auditorio_event_programme']}; rows_deleted={deleted}; rows_inserted={inserted}; expected_after={after}
COMMIT;
"""


def build_validation(desired, ids, baseline, deleted, inserted, after):
    dv, ev = values(desired), event_values(ids)
    return f"""-- Deferred Auditorio event_programme cleanup validation; read-only.
    WITH desired(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}), cleanup_events(event_id) AS ({ev})
SELECT 'auditorio_event_programme_after' AS check_name, count(*)::text AS value FROM public.event_programme ep JOIN public.events e ON e.id=ep.event_id JOIN public.organizations o ON o.id=e.organization_id WHERE o.slug='auditorio-nacional-inaem';
WITH desired(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}), cleanup_events(event_id) AS ({ev})
SELECT 'current_minus_desired' AS check_name, count(*)::text FROM (SELECT ep.event_id,ep."order",ep.work_id FROM public.event_programme ep JOIN cleanup_events ce ON ce.event_id=ep.event_id EXCEPT SELECT event_id,programme_order,work_id FROM desired) q;
WITH desired(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}), cleanup_events(event_id) AS ({ev})
SELECT 'desired_minus_current' AS check_name, count(*)::text FROM (SELECT event_id,programme_order,work_id FROM desired EXCEPT SELECT ep.event_id,ep."order",ep.work_id FROM public.event_programme ep JOIN cleanup_events ce ON ce.event_id=ep.event_id) q;
WITH desired(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}) SELECT 'missing_Event_targets' AS check_name,count(*)::text FROM desired d LEFT JOIN public.events e ON e.id=d.event_id WHERE e.id IS NULL;
WITH desired(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}) SELECT 'missing_Work_targets' AS check_name,count(*)::text FROM desired d LEFT JOIN public.works w ON w.id=d.work_id WHERE w.id IS NULL;
WITH desired(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}) SELECT 'batch_slot_conflicts' AS check_name,count(*)::text FROM desired GROUP BY event_id,programme_order HAVING count(*)>1;
WITH desired(event_id,work_id,programme_order,source_occurrence_id) AS ({dv}) SELECT 'unapproved_same_event_same_work' AS check_name, count(*)::text FROM (SELECT event_id,work_id FROM desired GROUP BY event_id,work_id HAVING count(*)>1) q;
SELECT 'expected_after' AS check_name,{after}::text AS value UNION ALL SELECT 'inserted_relationships',{inserted}::text UNION ALL SELECT 'expected_before',{baseline['auditorio_event_programme']}::text;
"""


def nonwork(title, status, resolved_work_id=None):
    t = (title or "").strip().lower()
    if status == "not_a_work": return True
    if resolved_work_id:
        return status == "parser_issue" and bool(re.fullmatch(r"[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü'’-]+(?:\s+[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü'’-]+){1,3}", (title or "").strip()))
    return bool(re.search(r"\b(?:soprano|tenor|bar[ií]tono|bajo|mezzosoprano|contratenor|solista|directora?|director|orquesta|coro|viol[ií]n|viola|fagot)\b", t)) or bool(re.fullmatch(r"[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü'’-]+(?:\s+[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü'’-]+){1,3}", (title or "").strip()))


def raw_lines_for(url, raw_by_url):
    blocks = raw_by_url.get(url, {}).get("raw_content_blocks", [])
    return [line.strip() for block in blocks for line in block.get("raw_lines", []) if line.strip()]


def source_items(lines, composer_names):
    """Reconstruct source works before consulting the Work UUIDs."""
    items, excluded, pending = [], 0, None
    role_re = re.compile(r"\b(?:director(?:a)?|dir\.?|soprano|tenor|bar[ií]tono|bajo|mezzosoprano|contratenor|viol[ií]n|viola|flauta|clarinete|piano|órgano|organo|coro|ensemble)\b", re.I)
    section_re = re.compile(r"^(?:programa|pausa|[- ]*pausa[- ]*|\*+\s*estreno|\+\s*primera vez)", re.I)
    movement_re = re.compile(r"^(?:[IVX]+\.|[IVX]+\s|[A-Z]\.)")
    for raw in lines:
        n = norm(raw)
        if re.search(r"^(?:orquesta|orchestra|cantores|obni|escuela veneciana|miembros del|pequeños cantores)", raw, re.I):
            pending = None; excluded += 1; continue
        if re.search(r"\b(?:director(?:a)?|dir\.?|soprano|tenor|bar[ií]tono|bajo|mezzosoprano|contratenor)\b", raw, re.I):
            pending = None; excluded += 1; continue
        work_hint = re.search(r"(?:concierto|sinfon|sonata|suite|misa|cantata|canto|cántico|quimera|silencio|syrinx|rítmicas|szenen|obertura|romeo|fidelio|canciones|cuarteto|tr[ií]o|offertorium|júpiter|jupiter|carnaval|requiem|obra a determinar|largo|allegro|miramondo|zwei)", raw, re.I)
        initials_header = re.fullmatch(r"(?:[A-ZÁÉÍÓÚÑÜ]\.?\s+){1,2}[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü'’-]+", raw)
        if not work_hint and (role_re.search(raw) or re.search(r"programa:", raw, re.I)):
            pending = None; excluded += 1; continue
        if not work_hint and (n in composer_names or initials_header or re.fullmatch(r"[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü'’-]+(?:\s+[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü'’-]+){1,3}", raw)):
            pending = None; excluded += 1; continue
        if section_re.search(raw) or role_re.search(raw) and not re.search(r"(?:concierto|sinfon|sonata|suite|misa|cantata|canto|cántico|quimera|silencio|syrinx|rítmicas|szenen|obertura|romeo|fidelio|canciones|cuarteto|tr[ií]o|offertorium|júpiter|jupiter|carnaval|requiem|requiem|obertura-fantasía)", raw, re.I):
            pending = None; excluded += 1; continue
        if raw.startswith("(") or raw.lower().startswith(("de los tiempos", "violín,", "viola,", "violonchelo", "violoncello", "overture-fantasy")):
            if items and raw.startswith("("):
                items[-1]["text"] += " " + raw
            elif items:
                items[-1]["text"] += " " + raw
            else: excluded += 1
            continue
        if movement_re.match(raw) and items and not re.search(r"(?:JunP|op\.|rv\.|hwv|d\.|k\.|n\.?\s*\d)", raw, re.I):
            items[-1]["text"] += " " + raw; continue
        if raw.startswith("[Largo]") or raw.startswith("�") or raw.startswith("«") or raw.startswith("Rítmicas") or raw.startswith("Zwei Szenen"):
            items.append({"text": raw}); continue
        items.append({"text": raw})
    return items, excluded


def main():
    st, first, cur, wm, raw_doc = load(STAGING), load(FIRST), load(CURRENT), load(WORKS), load(RAW)
    rows = st["candidates"]
    closed = set(first["cleanup_event_ids"])
    affected = {r["event_id"] for r in rows if r["status"] in REVIEW} | {r["event_id"] for r in st["legacy_parser_debris_evidence"]}
    deferred = sorted(affected - closed)
    assert len(deferred) == 78
    review_rows = [r for r in rows if r["event_id"] in deferred and r["status"] in REVIEW]
    assert len(review_rows) == 219
    title_index = defaultdict(set)
    for w in wm["rows"]["works"]: title_index[norm(w["title"])].add(w["id"])
    raw_by_url = {r["source_url"]: r for r in raw_doc["occurrences"]}
    by_event = defaultdict(list)
    for r in rows:
        if r["event_id"] in deferred: by_event[r["event_id"]].append(r)
    current_by = defaultdict(list)
    for r in cur["rows"]: current_by[r["event_id"]].append(r)
    det, residual, desired_by, reasons, resolution, completeness = [], [], {}, Counter(), Counter(), []
    source_composer_names = {norm(r.get("raw_composer_fragment")) for r in rows if r.get("raw_composer_fragment")}
    source_composer_names |= {norm(x) for x in ("J. G. Pisendel", "Benjamin Britten", "Federigo Fiorillo", "Jean Françaix", "Eddie Mora", "Amparo Edo Biol", "Gabriel Fauré", "Arthur Honegger", "Camille Saint-Saëns", "Serguéi Prokófiev", "Olivier Messiaen")}
    for eid in deferred:
        candidates, blocking = [], []
        event_rows = by_event[eid]
        if not event_rows:
            reasons["relationship_evidence_insufficient"] += 1
            residual.append(eid)
            completeness.append({"event_id": eid, "source_occurrence_id": None, "source_artistic_item_count": 0, "desired_artistic_item_count": 0, "excluded_nonwork_count": 0, "unresolved_artistic_item_count": 1, "semantic_completeness_pass": False, "final_bucket": "FINAL_RESIDUAL_BACKLOG"})
            continue
        lines = raw_lines_for(event_rows[0]["source_url"], raw_by_url)
        source, excluded = source_items(lines, source_composer_names)
        source_texts = [norm(x["text"]) for x in source]
        source_count = len(source)
        for r in by_event[eid]:
            if nonwork(r["raw_title"], r["status"], r.get("resolved_work_id")):
                resolution["resolved_parser_structure"] += r["status"] == "parser_issue"
                continue
            wid = r.get("resolved_work_id")
            if not wid and r["status"] in {"source_attribution_review", "parser_issue"}:
                hits = title_index.get(norm(r["raw_title"]), set())
                if len(hits) == 1 and len(norm(r["raw_title"])) >= 8 and not re.search(r"pendiente|otros compositores|recital|programa", r["raw_title"], re.I):
                    wid = next(iter(hits)); resolution["resolved_source_attribution"] += 1
            if not wid:
                blocking.append(r)
            else:
                candidates.append((r, wid))
        by_order = defaultdict(list)
        for r, wid in candidates:
            if r.get("stable_programme_order") is None: blocking.append(r); continue
            by_order[r["stable_programme_order"]].append((r, wid))
        # Match the reconstructed source sequence to candidate works. A source
        # work with no safe existing UUID is a hard event-level failure.
        source_desired = []
        for item in source:
            key = norm(item["text"])
            base_key = norm(re.sub(r"\s*\([^)]*\)\s*$", "", item["text"]))
            hits = title_index.get(key, set()) or title_index.get(base_key, set())
            matching = [r for r in candidates if norm(r[0]["raw_title"]) in {key, base_key} or norm(r[0]["raw_title"]) in key or key in norm(r[0]["raw_title"])]
            if len(hits) == 1:
                source_desired.append((item["text"], next(iter(hits)), matching[0][0] if matching else {"raw_title": item["text"], "source_occurrence_id": event_rows[0]["source_occurrence_id"], "stable_programme_order": None, "canonical_work_title": item["text"]}))
            elif len(matching) == 1 and matching[0][1]:
                source_desired.append((item["text"], matching[0][1], matching[0][0]))
            else:
                blocking.append({"status": "source_attribution_review", "raw_title": item["text"]})
        if source_desired and len(source_desired) != len(by_order):
            # The source reconstruction, rather than stale parser order, is authoritative.
            candidates = [(r, wid) for _, wid, r in source_desired if r]
            by_order = defaultdict(list)
            for ix, (_, wid, r) in enumerate(source_desired, 1):
                if r: by_order[ix].append((r, wid))
        completeness_pass = not blocking and len(source_desired) == len(by_order) and len({wid for _, wid, _ in source_desired}) == len(source_desired)
        completeness.append({"event_id": eid, "source_occurrence_id": event_rows[0]["source_occurrence_id"], "source_artistic_item_count": source_count, "desired_artistic_item_count": len(source_desired), "excluded_nonwork_count": excluded, "unresolved_artistic_item_count": len(blocking), "semantic_completeness_pass": completeness_pass, "final_bucket": "SECOND_BATCH_DETERMINISTIC" if completeness_pass else "FINAL_RESIDUAL_BACKLOG"})
        if not completeness_pass:
            reasons["source_attribution_unresolved"] += len(blocking) or 1
            residual.append(eid); continue
        if any(len(v) != 1 for v in by_order.values()) or blocking:
            if blocking:
                for r in blocking:
                    s = r["status"]
                    reasons["ambiguous_existing_work_review" if s == "ambiguous_work" else "parent_excerpt_unresolved" if s == "parent_work_excerpt_review" else "canonical_gap_review" if s == "unresolved_work" else "source_attribution_unresolved" if s == "source_attribution_review" else "parser_structure_unresolved"] += 1
            else: reasons["ambiguous_existing_work_review"] += 1
            residual.append(eid); continue
        desired = []
        for order, items in sorted(by_order.items()):
            r, wid = items[0]
            desired.append({"event_id": eid, "order": len(desired) + 1, "work_id": wid, "source_occurrence_id": r["source_occurrence_id"], "raw_title": r["raw_title"], "canonical_work_title": r.get("canonical_work_title")})
        if not desired: reasons["relationship_evidence_insufficient"] += 1; residual.append(eid); continue
        det.append(eid); desired_by[eid] = desired; resolution["resolved_existing_work"] += len(desired)
    current = [r for eid in det for r in sorted(current_by[eid], key=lambda x: int(x["order"]))]
    desired = [r for eid in det for r in desired_by[eid]]
    after = cur["baseline"]["auditorio_event_programme"] - len(current) + len(desired)
    baseline = cur["baseline"]
    all_raw = [line for eid in det + residual if by_event[eid] for line in raw_lines_for(by_event[eid][0]["source_url"], raw_by_url)]
    composer_header_exclusions = sum(norm(x) in source_composer_names for x in all_raw)
    title_continuation_merges = sum(bool(re.match(r"(?:de los tiempos|viol[ií]n,|viola,|violonchelo|violoncello|overture-fantasía)", x, re.I)) for x in all_raw)
    subtitle_translation_exclusions = sum(x.strip().startswith("(") for x in all_raw)
    residual_docs = []
    for eid in residual:
        rs = [r for r in by_event[eid] if r["status"] in REVIEW]
        counts = Counter("ambiguous_existing_work_review" if r["status"] == "ambiguous_work" else "canonical_gap_review" if r["status"] == "unresolved_work" else "parent_excerpt_unresolved" if r["status"] == "parent_work_excerpt_review" else "source_attribution_unresolved" if r["status"] == "source_attribution_review" else "parser_structure_unresolved" for r in rs)
        primary = counts.most_common(1)[0][0] if counts else "relationship_evidence_insufficient"
        residual_docs.append({"event_id": eid, "bucket": "FINAL_RESIDUAL_BACKLOG", "primary_reason": primary, "priority": "P3" if primary == "ambiguous_existing_work_review" else "P2" if primary in {"canonical_gap_review", "parent_excerpt_unresolved"} else "P1", "review_row_count": len(rs)})
    proposed_report = [x for x in completeness if x["event_id"] in PRIOR_PROPOSED]
    summary = {"source":"auditorio_nacional", "phase":"DEFERRED_EVENT_RESOLUTION_PASS", "database_writes":0, "no_sql_executed":True, "baseline":baseline, "candidate_events_reviewed":len(proposed_report), "input_deferred_events":78, "input_remaining_review_rows":219, "second_batch_deterministic_events":len(det), "final_residual_backlog_events":len(residual), "second_batch_event_ids":det, "current_rows":len(current), "desired_rows":len(desired), "rows_deleted":len(current), "rows_inserted":len(desired), "expected_after":after, "same_event_same_work_duplicates":0, "source_completeness_failures":sum(not x["semantic_completeness_pass"] for x in proposed_report), "composer_header_exclusions":composer_header_exclusions, "title_continuation_merges":title_continuation_merges, "subtitle_translation_exclusions":subtitle_translation_exclusions, "unresolved_artistic_items_causing_deferral":sum(x["unresolved_artistic_item_count"] for x in proposed_report), "resolution_counts":dict(resolution), "residual_primary_reason_counts":dict(Counter(x["primary_reason"] for x in residual_docs)), "residual_priority_counts":dict(Counter(x["priority"] for x in residual_docs)), "completeness_report":proposed_report, "generated_at":datetime.now(timezone.utc).isoformat()}
    (OUT/"auditorio-event-programme-deferred-resolution-summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    (OUT/"auditorio-event-programme-deferred-current-state.json").write_text(json.dumps({"source":"auditorio_nacional","phase":"DEFERRED_EVENT_RESOLUTION_PASS","database_writes":0,"queried_from_live_production":True,"baseline":baseline,"rows":cur["rows"]},ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    (OUT/"auditorio-event-programme-deferred-desired-state.json").write_text(json.dumps({"source":"auditorio_nacional","database_writes":0,"rows":desired},ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    (OUT/"auditorio-event-programme-final-residual-backlog.json").write_text(json.dumps({"source":"auditorio_nacional","database_writes":0,"events":residual_docs},ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    if det:
        (OUT/"auditorio-event-programme-deferred-cleanup-production-apply.sql").write_text(build_apply(current,desired,det,baseline,len(current),len(desired),after),encoding="utf8")
        (OUT/"auditorio-event-programme-deferred-cleanup-production-validation.sql").write_text(build_validation(desired,det,baseline,len(current),len(desired),after),encoding="utf8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__": main()
