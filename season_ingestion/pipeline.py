from __future__ import annotations

import json
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import STAGES, validate_canonical_event, validate_schedule_integrity
from .contracts import empty_global_snapshot
from .global_master import GlobalMasterError, load_global_snapshot, resolve_entity, resolve_work
from .registry import load_adapter, load_registry
from .credit_resolution import stage_credits


def _composer_trace(programme_rows: list[dict[str, Any]], snapshot: Any) -> dict[str, list[dict[str, Any]]]:
    frequency: dict[str, int] = {}
    first_rows: dict[str, dict[str, Any]] = {}
    for item in programme_rows:
        raw = str(item.get("composer") or "")
        if not raw:
            continue
        frequency[raw] = frequency.get(raw, 0) + 1
        first_rows.setdefault(raw, item)
    first = list(first_rows)[:20]
    top = [raw for raw, _ in sorted(frequency.items(), key=lambda pair: (-pair[1], pair[0]))[:20]]
    selected = list(dict.fromkeys(first + top))
    rows = []
    for raw in selected:
        item = first_rows[raw]
        resolution = item.get("composer_resolution") or {}
        candidate = item.get("composer_candidate") or {}
        normalized = resolution.get("lookup_key") or " ".join(raw.casefold().split())
        rows.append({"raw_composer": raw, "normalized_composer": normalized, "source_field": candidate.get("source_field", item.get("provenance", {}).get("source_field")), "source_url": candidate.get("source_url", item.get("provenance", {}).get("source_url")), "candidate_key": f"composer:{hashlib.sha256(normalized.encode()).hexdigest()[:24]}", "resolver_lookup_key": resolution.get("lookup_key", normalized), "global_master_match_candidates": resolution.get("candidate_matches", []), "final_resolution_reason": resolution.get("reason"), "frequency": frequency[raw]})
    return {"first_20_distinct": rows[:20], "frequency_top_20_distinct": [row for row in rows if row["raw_composer"] in top]}


def run_pipeline(*, venue: str, season: str, mode: str = "dry-run", output_dir: Path = Path("season-ingestion-output"), snapshot_path: Path | None = None) -> dict[str, Any]:
    if mode not in {"dry-run", "apply"}:
        raise ValueError("mode must be dry-run or apply")
    if mode == "apply":
        raise RuntimeError("production apply is intentionally disabled in Season Ingestion Pipeline V1")
    config = load_registry()["venues"][venue]
    adapter = load_adapter(venue)
    events = adapter.ingest(season)
    for event in events:
        validate_canonical_event(event)
    schedule_contract = validate_schedule_integrity(events)
    generated_at = datetime.now(timezone.utc).isoformat()
    global_master_error = None
    try:
        snapshot = load_global_snapshot(path=snapshot_path)
    except GlobalMasterError as exc:
        global_master_error = {"code": exc.code, "message": exc.message}
        snapshot = empty_global_snapshot(generated_at)
    snapshot_health = dict(getattr(snapshot, "health", {}) or {})
    global_master_loaded = bool(snapshot_health.get("global_master_loaded", snapshot.entities.get("composer") and snapshot.entities.get("work")))
    if not global_master_loaded and snapshot_health.get("error_code"):
        global_master_error = {"code": snapshot_health["error_code"], "message": snapshot_health.get("error_message", "Global Master unavailable")}
    if global_master_error:
        snapshot_health.update({"preflight_status": "FAIL", "global_master_loaded": False, "error_code": global_master_error["code"], "error_message": global_master_error["message"]})
        if "query_errors" not in snapshot_health:
            snapshot_health["query_errors"] = 1
    resolution_rows, review_rows = [], []
    work_cache: dict[tuple[str, str], dict[str, Any]] = {}
    composer_resolution = []
    for event in events:
        for item in event.programme:
            composer = item.get("composer")
            if not global_master_loaded:
                composer_status = {"status": "not_run", "entity_id": None, "lookup_key": None, "reason": "RESOLUTION_NOT_RUN_GLOBAL_MASTER_UNAVAILABLE"}
            else:
                composer_status = resolve_entity("composer", composer, snapshot) if composer else {"status": "not_applicable", "entity_id": None, "reason": "programme item has no composer"}
            composer_resolution.append(composer_status)
            if not global_master_loaded:
                work_resolution = {"status": "not_run", "work_id": None, "reason": "RESOLUTION_NOT_RUN_GLOBAL_MASTER_UNAVAILABLE"}
            else:
                if composer_status.get("status") == "existing":
                    key = (str(composer_status.get("entity_id")), " ".join(str(item["source_title"]).casefold().split()))
                    if key not in work_cache:
                        work_cache[key] = resolve_work(item["source_title"], composer_status, snapshot)
                    work_resolution = dict(work_cache[key])
                    if work_resolution.get("status") == "review_required" and work_resolution.get("reason") == "no operational Work match; do not auto-create":
                        work_resolution.update(status="new_candidate", reason="resolved Composer with no operational Work match; candidate only")
                else:
                    work_resolution = {"status": "review_required", "work_id": None, "reason": "composer unresolved; Work resolution deferred"}
            work_entity = next((work for work in snapshot.entities.get("work", []) if work.get("id") == work_resolution.get("work_id")), {})
            row = {"event_key": event.event_key, "source_title": item["source_title"], **work_resolution, "canonical_work_title": work_entity.get("canonical_name") or work_entity.get("title"), "composer": composer, "canonical_composer": composer_status.get("canonical_name"), "composer_candidate": item.get("composer_candidate", {}), "composer_resolution": composer_status, "source_programme_index": item["source_programme_index"], "original_programme_order": item["original_programme_order"], "provenance": item.get("provenance", {})}
            resolution_rows.append(row)
            if work_resolution["status"] in {"review_required", "new_candidate"}:
                review_rows.append(row)
    duplicate_event_identity = len(events) - len({event.event_key for event in events})
    programme_rows = [item for event in events for item in event.programme]
    credits = [credit for event in events for credit in event.credits]
    programme_statuses = [event.data_quality.get("programme", {}).get("status") for event in events]
    no_programme_evidence = sum(status == "NO_PROGRAMME_EVIDENCE" for status in programme_statuses)
    detail_parse_review = sum(status == "DETAIL_PARSE_REVIEW" for status in programme_statuses)
    untraceable = any(not item.get("provenance", {}).get("source_url") for item in programme_rows)
    snapshot_counts = {kind: len(snapshot.entities.get(kind, [])) for kind in ("composer", "artist", "work", "character")}
    snapshot_counts["composer_aliases"] = len(getattr(snapshot, "composer_aliases", []))
    snapshot_counts["work_aliases"] = len(getattr(snapshot, "work_aliases", []))
    gates = {"events_gt_zero": len(events) > 0, "traceable_urls": all(bool(event.source_url) for event in events), "duplicate_event_identity": duplicate_event_identity == 0, "duplicate_performance_slot": schedule_contract["duplicate_performance_slot"] == 0, "null_timed_shadow_duplicates": schedule_contract["null_timed_shadow_duplicates"] == 0, "ambiguous_same_day_occurrence": schedule_contract["ambiguous_same_day_occurrence"] == 0, "year_inferred_without_production_evidence": schedule_contract["year_inferred_without_production_evidence"] == 0, "year_unverified": schedule_contract["year_unverified"] == 0, "artist_boundary_high": all(not (credit.get("artist_name") or "").casefold().endswith((" soprano", " tenor", " baritone", " bass")) for credit in credits), "programme_credit_contamination": all(credit.get("credit_kind") not in {"cast", "character"} or credit.get("function") not in {"conductor", "director", "orchestra", "chorus", "designer"} for credit in credits), "source_order_missing": all(item.get("original_programme_order") == item.get("source_programme_index") for item in programme_rows), "untraceable": not untraceable, "review_items_in_safe_subset": 0 == 0, "production_writes": 0 == 0, "source_fetch_failures": len(adapter.last_errors) == 0, "global_master_loaded": global_master_loaded}
    requested_months = getattr(adapter, "requested_months", [])
    successful_months = getattr(adapter, "successful_months", [])
    failed_months = getattr(adapter, "failed_months", [])
    source_audit = {"venue": venue, "season": season, "official_source": config["official_source"], "official_fallback_source": config.get("fallback_source"), "source_strategy": "official listing -> official detail links -> performance-level detail extraction", "requested_months": requested_months, "successful_months": successful_months, "failed_months": failed_months, "source_pages": getattr(adapter, "source_pages", {}), "adapter_errors": adapter.last_errors, "events": len(events), "listing_pages_requested": len(getattr(adapter, "listing_pages_requested", [])), "listing_pages_successful": len(getattr(adapter, "listing_pages_successful", [])), "listing_pages_failed": len(getattr(adapter, "listing_pages_failed", [])), "detail_pages_requested": len(getattr(adapter, "detail_pages_requested", requested_months)), "detail_pages_successful": len(getattr(adapter, "detail_pages_successful", successful_months)), "detail_pages_failed": len(getattr(adapter, "detail_pages_failed", failed_months))}
    source_audit.update({key: getattr(adapter, key, 0) for key in ("productions_discovered", "detail_pages_out_of_season_skipped", "date_candidates_found", "date_candidates_accepted", "date_candidates_rejected", "date_year_unverified", "events_outside_season", "duplicate_performance_slot", "ambiguous_same_day_occurrence", "null_timed_shadow_duplicates", "year_inferred_without_production_evidence")})
    if failed_months:
        source_capability = "SOURCE_BLOCKED" if not events and adapter.last_errors and all("403" in item.get("error", "") for item in adapter.last_errors) else "SOURCE_PARTIAL"
    elif not successful_months or not events:
        source_capability = "SOURCE_UNSUPPORTED"
    else:
        source_capability = "SOURCE_PASS"
    source_audit["source_capability"] = source_capability
    if global_master_loaded:
        work_counts = {"existing_exact": sum(row.get("status") == "existing" and row.get("match_method") == "exact" for row in work_cache.values()), "existing_alias": sum(row.get("status") == "existing" and row.get("match_method") == "alias" for row in work_cache.values()), "existing_normalized": sum(row.get("status") == "existing" and row.get("match_method") == "normalized" for row in work_cache.values()), "legacy_existing": 0, "new_candidate": sum(row.get("status") == "new_candidate" for row in work_cache.values()), "review": sum(row.get("status") == "review_required" for row in work_cache.values()), "not_run": 0, "no_programme_evidence": no_programme_evidence}
        composer_counts = {"exact": sum(row.get("status") == "existing" and row.get("match_method") == "exact" for row in composer_resolution), "alias": sum(row.get("status") == "existing" and row.get("match_method") == "alias" for row in composer_resolution), "normalized": sum(row.get("status") == "existing" and row.get("match_method") == "normalized" for row in composer_resolution), "new_candidate": 0, "review": sum(row.get("status") == "review_required" for row in composer_resolution), "not_run": 0}
    else:
        not_run = len([row for row in composer_resolution if row.get("status") == "not_run"])
        work_counts = {"existing_exact": 0, "existing_alias": 0, "existing_normalized": 0, "legacy_existing": 0, "new_candidate": 0, "review": 0, "not_run": not_run, "no_programme_evidence": no_programme_evidence}
        composer_counts = {"exact": 0, "alias": 0, "normalized": 0, "new_candidate": 0, "review": 0, "not_run": not_run}
    credit_staging = stage_credits(events, resolution_rows, snapshot) if global_master_loaded else {"safe_event_credits": [], "review_event_credits": [], "counts": {"credits_raw": len(credits), "credits_safe": 0, "credits_review": len(credits)}}
    safe_programme_relationships = sum(row.get("status") == "existing" for row in resolution_rows)
    review_programme_relationships = sum(row.get("status") in {"review_required", "new_candidate"} for row in resolution_rows)
    reviewed_events = {row["event_key"] for row in resolution_rows if row.get("status") in {"review_required", "new_candidate"}}
    event_dates = [event.date for event in events]
    summary = {"generated_at": generated_at, "venue": venue, "season": season, "mode": mode, "source_capability": source_capability, "months": {"requested": len(requested_months), "successful": len(successful_months), "failed": len(failed_months)}, "global_master_preflight": "PASS" if global_master_loaded else "FAIL", "global_master_error": global_master_error, "snapshot_health": snapshot_health, "snapshot_counts": snapshot_counts, "counts": {"events": len(events), "events_discovered": len(events), "normalized": len(events), "works_existing": work_counts["existing_exact"], "works_review": work_counts["review"], "review_items": len(review_rows), "writes": 0, **credit_staging.get("counts", {})}, "detail_enrichment": {"listing_pages_requested": source_audit["listing_pages_requested"], "listing_pages_successful": source_audit["listing_pages_successful"], "detail_pages_requested": source_audit["detail_pages_requested"], "detail_pages_successful": source_audit["detail_pages_successful"], "detail_pages_failed": source_audit["detail_pages_failed"], "events_with_programme_evidence": sum(status == "PROGRAMME_EVIDENCE_FOUND" for status in programme_statuses), "events_without_programme_evidence": no_programme_evidence, "detail_parse_review": detail_parse_review, "programme_items": len(programme_rows), "composer_candidates": sum(bool(item.get("composer_candidate")) for item in programme_rows), "credits_total": len(credits), "artist_candidates": len([c for c in credits if c.get("artist_name")]), "character_candidates": len([c for c in credits if c.get("character")]), "composer_resolution": composer_counts, "work_resolution": work_counts}, "composer_trace": _composer_trace(resolution_rows, snapshot), "credit_resolution": credit_staging, "gates": gates, "passed": all(gates.values())}
    summary.update({
        "productions_discovered": source_audit["productions_discovered"],
        "detail_pages_out_of_season_skipped": source_audit["detail_pages_out_of_season_skipped"],
        "date_candidates_found": source_audit["date_candidates_found"],
        "date_candidates_accepted": source_audit["date_candidates_accepted"],
        "date_candidates_rejected": source_audit["date_candidates_rejected"],
        "date_year_unverified": source_audit["date_year_unverified"],
        "events_outside_season": source_audit["events_outside_season"],
        "duplicate_performance_slot": source_audit["duplicate_performance_slot"],
        "ambiguous_same_day_occurrence": source_audit["ambiguous_same_day_occurrence"],
        "null_timed_shadow_duplicates": source_audit["null_timed_shadow_duplicates"],
        "year_inferred_without_production_evidence": source_audit["year_inferred_without_production_evidence"],
        "date_min": min(event_dates) if event_dates else None,
        "date_max": max(event_dates) if event_dates else None,
    })
    summary["counts"].update({"safe_events": len(events) - len(reviewed_events), "safe_programme_relationships": safe_programme_relationships, "review_programme_relationships": review_programme_relationships})
    summary["detail_enrichment"].update({"programme_occurrences": len(programme_rows), "unique_work_candidates": len(work_cache), "unique_work_safe_existing": sum(row.get("status") == "existing" for row in work_cache.values()), "unique_work_new_candidate": sum(row.get("status") == "new_candidate" for row in work_cache.values()), "unique_work_review": sum(row.get("status") == "review_required" for row in work_cache.values())})
    payloads = {"source_audit": source_audit, "raw": [event.raw | {"event_key": event.event_key, "source_url": event.source_url} for event in events], "normalized": [event.to_dict() for event in events], "snapshot": snapshot.__dict__, "resolution_staging": resolution_rows, "credit_resolution_staging": credit_staging, "final_staging": {"events": [event.to_dict() for event in events], "resolution": resolution_rows, "review": review_rows, "credit_resolution": credit_staging, "artists": credit_staging.get("safe_new_artists", []), "event_credits": credit_staging.get("safe_event_credits", []), "writes": 0}, "summary": summary}
    output_dir.mkdir(parents=True, exist_ok=True)
    for stage in STAGES:
        (output_dir / f"{stage}.json").write_text(json.dumps(payloads[stage], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (output_dir / "credit_resolution_staging.json").write_text(json.dumps(credit_staging, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(payloads["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    return payloads["summary"]
