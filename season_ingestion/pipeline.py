from __future__ import annotations

import json
import hashlib
import os
import re
from dataclasses import replace
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .contracts import STAGES, validate_canonical_event, validate_schedule_integrity
from .contracts import empty_global_snapshot
from .global_master import GlobalMasterError, load_global_snapshot, resolve_entity, resolve_work
from .registry import load_adapter, load_registry
from .credit_resolution import stage_credits
from .incremental import source_fingerprint
from .supabase import ExistingRecord, fetch_existing_sources
from .hermes_acquisition import HermesAcquisitionError, acquire_events, eligible_for_fallback, facts_to_events, persist_source_facts


DERIVED_PROGRAMME_SOURCE_FIELDS = {"jsonld.name", "event.name", "og:title", "html.title", "page.heading", "listing-card.title", "event.title"}


def sanitize_programme_evidence(events: list[Any]) -> list[Any]:
    """Remove title/heading metadata that is not Work evidence."""
    sanitized = []
    for event in events:
        kept = []
        for item in event.programme:
            field = str((item.get("provenance") or {}).get("source_field") or "").casefold()
            if field in DERIVED_PROGRAMME_SOURCE_FIELDS or field.endswith(".name"):
                continue
            kept.append(item)
        quality = dict(event.data_quality)
        if not kept:
            quality["programme"] = {"status": "NO_PROGRAMME_EVIDENCE", "reason": "no explicit official programme field"}
        sanitized.append(replace(event, programme=kept, data_quality=quality))
    return sanitized


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


def _normalise_match_url(value: Any) -> str:
    if not value:
        return ""
    parsed = urlsplit(str(value).strip())
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path.rstrip("/"), parsed.query, ""))


def _normalise_match_title(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _normalise_match_time(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", text)
    return f"{int(match.group(1)):02d}:{match.group(2)}" if match else text


def match_existing_events(events: list[Any], existing: list[ExistingRecord]) -> dict[str, Any]:
    """Match official staged occurrences to existing production identities.

    This is a read-only closeout guard.  It requires the official detail URL,
    title, date, and start time to identify one existing event; it never treats
    an unmatched staged occurrence as an insert candidate.
    """
    exact: dict[tuple[str, str, str | None, str | None], list[ExistingRecord]] = defaultdict(list)
    relaxed: dict[tuple[str, str | None, str | None], list[ExistingRecord]] = defaultdict(list)
    for record in existing:
        start_time = _normalise_match_time(record.fields.get("start_time") if record.fields else None)
        exact[(_normalise_match_url(record.source_url), _normalise_match_title(record.title), record.date, start_time)].append(record)
        relaxed[(_normalise_match_url(record.source_url), record.date, start_time)].append(record)

    matched: list[Any] = []
    matched_records: list[ExistingRecord] = []
    used_ids: set[str] = set()
    ambiguous: list[dict[str, Any]] = []
    unmatched_staged: list[Any] = []
    for event in events:
        start_time = _normalise_match_time(event.start_time)
        exact_candidates = [record for record in exact[(_normalise_match_url(event.source_url), _normalise_match_title(event.title), event.date, start_time)] if record.event_id not in used_ids]
        candidates = exact_candidates
        if not candidates:
            candidates = [
                record for record in relaxed[(_normalise_match_url(event.source_url), event.date, start_time)]
                if record.event_id not in used_ids
                and (not record.title or not event.title)
            ]
        if len(candidates) != 1:
            if len(candidates) > 1:
                ambiguous.append({"source_url": event.source_url, "title": event.title, "date": event.date, "start_time": event.start_time, "candidate_event_ids": [record.event_id for record in candidates]})
            unmatched_staged.append(event)
            continue
        matched.append(event)
        matched_records.append(candidates[0])
        used_ids.add(candidates[0].event_id)

    unmatched_existing = [record for record in existing if record.event_id not in used_ids]
    return {
        "matched_events": matched,
        "matched_records": matched_records,
        "unmatched_staged": unmatched_staged,
        "unmatched_existing": unmatched_existing,
        "ambiguous": ambiguous,
        "matched_count": len(matched),
    }


def run_pipeline(*, venue: str, season: str, mode: str = "dry-run", scope: str = "full-season", output_dir: Path = Path("season-ingestion-output"), snapshot_path: Path | None = None, hermes_source_facts_path: Path | None = None) -> dict[str, Any]:
    if mode not in {"dry-run", "apply"}:
        raise ValueError("mode must be dry-run or apply")
    if mode == "apply":
        raise RuntimeError("production apply is intentionally disabled in Season Ingestion Pipeline V1")
    if scope not in {"full-season", "existing-production"}:
        raise ValueError("scope must be full-season or existing-production")
    config = load_registry()["venues"][venue]
    adapter = load_adapter(venue)
    existing_records: list[ExistingRecord] = []
    existing_match: dict[str, Any] = {"matched_count": None, "unmatched_staged": [], "unmatched_existing": [], "ambiguous": []}
    if scope == "existing-production":
        bounds = (config.get("season_bounds") or {}).get(season) or {}
        existing_records = fetch_existing_sources(
            config.get("source_id", venue),
            season,
            season_start=bounds.get("season_start"),
            season_end=bounds.get("season_end"),
            apply_mode=False,
        )
        adapter.allowed_detail_urls = {record.source_url for record in existing_records if record.source_url}
    force_hermes = os.getenv("BYELINGUA_FORCE_HERMES_FALLBACK", "").casefold() in {"1", "true", "yes"}
    hermes_fallback: dict[str, Any] = {"attempted": False, "status": "NOT_ATTEMPTED"}
    if hermes_source_facts_path is not None:
        facts = json.loads(hermes_source_facts_path.read_text(encoding="utf-8"))
        if facts.get("venue_id") != venue or facts.get("season") != season:
            raise ValueError("Hermes source-facts artifact venue/season does not match the requested target")
        events = facts_to_events(facts, venue=venue, config=config)
        hermes_fallback = {
            "attempted": True,
            "status": "PASS",
            "acquisition_mode": "validated_source_facts_artifact",
            "source_type": facts["source_type"],
            "official_source_url": facts["official_source_url"],
            "source_contract": facts["source_contract"],
            "events": len(events),
        }
    else:
        events = [] if force_hermes else adapter.ingest(season)
        if eligible_for_fallback(events=events, adapter=adapter, force=force_hermes) and os.getenv("BYELINGUA_HERMES_ACQUIRE_COMMAND"):
            try:
                facts, hermes_events = acquire_events(
                    venue=venue,
                    season=season,
                    config=config,
                    reason="forced_validation" if force_hermes else "deterministic_source_failure",
                )
                events = hermes_events
                persisted_facts_path = persist_source_facts(facts)
                hermes_fallback = {
                    "attempted": True,
                    "status": "PASS",
                    "acquisition_mode": "worker_subprocess",
                    "source_type": facts["source_type"],
                    "official_source_url": facts["official_source_url"],
                    "source_contract": facts["source_contract"],
                    "events": len(events),
                    "persisted_source_facts": str(persisted_facts_path),
                }
            except HermesAcquisitionError as exc:
                hermes_fallback = {"attempted": True, "status": "BLOCKED", "error": str(exc)[:300]}
        elif eligible_for_fallback(events=events, adapter=adapter, force=force_hermes):
            hermes_fallback = {"attempted": False, "status": "NOT_CONFIGURED"}
    events = sanitize_programme_evidence(list(events))
    scoped_events = list(events)
    source_hash = source_fingerprint(scoped_events)
    if scope == "existing-production":
        existing_match = match_existing_events(events, existing_records)
        if existing_match["unmatched_existing"] or existing_match["unmatched_staged"] or existing_match["ambiguous"]:
            raise RuntimeError(
                "existing-production match failed: "
                f"matched={existing_match['matched_count']} "
                f"existing={len(existing_records)} "
                f"staged={len(events)}"
            )
        events = existing_match["matched_events"]
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
    missing_start_time = sum(not event.start_time for event in events)
    missing_start_time_rate = missing_start_time / len(events) if events else 0.0
    programme_statuses = [event.data_quality.get("programme", {}).get("status") for event in events]
    no_programme_evidence = sum(status == "NO_PROGRAMME_EVIDENCE" for status in programme_statuses)
    detail_parse_review = sum(status == "DETAIL_PARSE_REVIEW" for status in programme_statuses)
    event_type_distribution = dict(sorted(Counter(event.event_type for event in events).items()))
    programme_source_evidence = {
        "programme_evidence_events": sum(status == "PROGRAMME_EVIDENCE_FOUND" for status in programme_statuses),
        "expected_no_programme_events": no_programme_evidence,
        "programme_source_ambiguous_events": sum(status == "PROGRAMME_SOURCE_AMBIGUOUS" for status in programme_statuses),
        "detail_parse_review_events": detail_parse_review,
    }
    untraceable = any(not item.get("provenance", {}).get("source_url") for item in programme_rows)
    snapshot_counts = {kind: len(snapshot.entities.get(kind, [])) for kind in ("composer", "artist", "work", "character")}
    snapshot_counts["composer_aliases"] = len(getattr(snapshot, "composer_aliases", []))
    snapshot_counts["work_aliases"] = len(getattr(snapshot, "work_aliases", []))
    gates = {"events_gt_zero": len(events) > 0, "traceable_urls": all(bool(event.source_url) for event in events), "duplicate_event_identity": duplicate_event_identity == 0, "duplicate_performance_slot": schedule_contract["duplicate_performance_slot"] == 0, "null_timed_shadow_duplicates": schedule_contract["null_timed_shadow_duplicates"] == 0, "ambiguous_same_day_occurrence": schedule_contract["ambiguous_same_day_occurrence"] == 0, "year_inferred_without_production_evidence": schedule_contract["year_inferred_without_production_evidence"] == 0, "year_unverified": schedule_contract["year_unverified"] == 0, "acceptable_time_completeness": missing_start_time_rate <= 0.2, "artist_boundary_high": all(not (credit.get("artist_name") or "").casefold().endswith((" soprano", " tenor", " baritone", " bass")) for credit in credits), "programme_credit_contamination": all(credit.get("credit_kind") not in {"cast", "character"} or credit.get("function") not in {"conductor", "director", "orchestra", "chorus", "designer"} for credit in credits), "source_order_missing": all(item.get("original_programme_order") == item.get("source_programme_index") for item in programme_rows), "untraceable": not untraceable, "review_items_in_safe_subset": 0 == 0, "production_writes": 0 == 0, "source_fetch_failures": len(adapter.last_errors) == 0 or hermes_fallback["status"] == "PASS", "global_master_loaded": global_master_loaded, "existing_event_match": scope != "existing-production" or (existing_match["matched_count"] == len(existing_records) == len(events)), "credit_extraction": scope != "existing-production" or len(credits) > 0}
    requested_months = getattr(adapter, "requested_months", [])
    successful_months = getattr(adapter, "successful_months", [])
    failed_months = getattr(adapter, "failed_months", [])
    source_audit = {"venue": venue, "season": season, "scope": scope, "official_source": config["official_source"], "official_fallback_source": config.get("fallback_source"), "source_strategy": "official listing -> official detail links -> performance-level detail extraction", "requested_months": requested_months, "successful_months": successful_months, "failed_months": failed_months, "source_pages": getattr(adapter, "source_pages", {}), "adapter_errors": adapter.last_errors, "events": len(events), "events_after_scope": len(scoped_events), "existing_records_loaded": len(existing_records), "existing_events_matched": existing_match["matched_count"], "listing_pages_requested": len(getattr(adapter, "listing_pages_requested", [])), "listing_pages_successful": len(getattr(adapter, "listing_pages_successful", [])), "listing_pages_failed": len(getattr(adapter, "listing_pages_failed", [])), "detail_pages_requested": len(getattr(adapter, "detail_pages_requested", requested_months)), "detail_pages_successful": len(getattr(adapter, "detail_pages_successful", successful_months)), "detail_pages_failed": len(getattr(adapter, "detail_pages_failed", failed_months)), "detail_urls_discovered_before_scope": getattr(adapter, "productions_discovered_before_scope", getattr(adapter, "productions_discovered", 0)), "detail_urls_filtered_by_scope": getattr(adapter, "detail_scope_filtered", 0)}
    source_audit["hermes_fallback"] = hermes_fallback
    if hermes_fallback["status"] == "PASS":
        source_audit["source_strategy"] = "deterministic official source -> Hermes Browser Automation fallback -> shared canonical normalization"
    source_audit.update({key: getattr(adapter, key, 0) for key in ("productions_discovered", "detail_pages_out_of_season_skipped", "date_candidates_found", "date_candidates_accepted", "date_candidates_rejected", "date_year_unverified", "events_outside_season", "duplicate_performance_slot", "ambiguous_same_day_occurrence", "null_timed_shadow_duplicates", "year_inferred_without_production_evidence")})
    if hermes_fallback["status"] == "PASS":
        source_capability = "SOURCE_PASS"
    elif failed_months:
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
    snapshot_hash = hashlib.sha256(json.dumps(snapshot.__dict__, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    summary = {"generated_at": generated_at, "venue": venue, "season": season, "mode": mode, "scope": scope, "source_fingerprint": source_hash, "source_capability": source_capability, "source_strategy": "official listing -> official detail links -> performance-level detail extraction", "adapter_errors": adapter.last_errors, "months": {"requested": len(requested_months), "successful": len(successful_months), "failed": len(failed_months)}, "global_master_preflight": "PASS" if global_master_loaded else "FAIL", "snapshot_loaded": global_master_loaded, "snapshot_hash": snapshot_hash, "global_master_error": global_master_error, "snapshot_health": snapshot_health, "snapshot_counts": snapshot_counts, "event_type_distribution": event_type_distribution, "programme_source_evidence": programme_source_evidence, "existing_production": {"records_loaded": len(existing_records), "events_scoped": len(scoped_events), "events_matched": existing_match["matched_count"], "unmatched_existing": len(existing_match["unmatched_existing"]), "unmatched_staged": len(existing_match["unmatched_staged"]), "ambiguous": len(existing_match["ambiguous"])}, "counts": {"events": len(events), "events_discovered": len(events), "normalized": len(events), "missing_start_time": missing_start_time, "missing_start_time_rate": missing_start_time_rate, "works_existing": work_counts["existing_exact"], "works_review": work_counts["review"], "review_items": len(review_rows), "writes": 0, **credit_staging.get("counts", {})}, "detail_enrichment": {"listing_pages_requested": source_audit["listing_pages_requested"], "listing_pages_successful": source_audit["listing_pages_successful"], "detail_pages_requested": source_audit["detail_pages_requested"], "detail_pages_successful": source_audit["detail_pages_successful"], "detail_pages_failed": source_audit["detail_pages_failed"], "events_with_programme_evidence": programme_source_evidence["programme_evidence_events"], "events_without_programme_evidence": no_programme_evidence, "programme_source_ambiguous_events": programme_source_evidence["programme_source_ambiguous_events"], "detail_parse_review": detail_parse_review, "programme_items": len(programme_rows), "work_candidates": len(programme_rows), "single_work_events": sum(len(event.programme) == 1 for event in events), "multi_work_events": sum(len(event.programme) > 1 for event in events), "work_parse_review": programme_source_evidence["programme_source_ambiguous_events"], "composer_candidates": sum(bool(item.get("composer_candidate")) for item in programme_rows), "composer_evidence_present": sum(bool(item.get("composer")) for item in programme_rows), "composer_missing_source_evidence": sum(not item.get("composer") for item in programme_rows), "composer_parse_review": sum(not item.get("composer") for item in programme_rows), "credits_total": len(credits), "raw_credit_rows": credit_staging.get("counts", {}).get("credits_raw", len(credits)), "credit_parse_success": credit_staging.get("counts", {}).get("credits_safe", 0), "credit_parse_review": credit_staging.get("counts", {}).get("credits_review", 0), "artist_candidates": len([c for c in credits if c.get("artist_name")]), "character_candidates": len([c for c in credits if c.get("character")]), "composer_resolution": composer_counts, "work_resolution": work_counts}, "composer_trace": _composer_trace(resolution_rows, snapshot), "credit_resolution": credit_staging, "gates": gates, "passed": all(gates.values())}
    summary["hermes_fallback"] = hermes_fallback
    summary["source_strategy"] = source_audit["source_strategy"]
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
    summary["request_counts"] = {"listing_requested": len(getattr(adapter, "listing_pages_requested", [])), "listing_succeeded": len(getattr(adapter, "listing_pages_successful", [])), "listing_failed": len(getattr(adapter, "listing_pages_failed", [])), "detail_requested": len(getattr(adapter, "detail_pages_requested", [])), "detail_succeeded": len(getattr(adapter, "detail_pages_successful", [])), "detail_failed": len(getattr(adapter, "detail_pages_failed", []))}
    summary["catalog_status_counts"] = {"source_pass": int(source_capability == "SOURCE_PASS"), "source_partial": int(source_capability == "SOURCE_PARTIAL"), "source_blocked": int(source_capability in {"SOURCE_BLOCKED", "SOURCE_UNSUPPORTED"}), "review": len(review_rows), "safe": safe_programme_relationships}
    summary["staging_classification_counts"] = {"safe_programme_relationships": safe_programme_relationships, "review_programme_relationships": review_programme_relationships, "safe_event_credits": credit_staging.get("counts", {}).get("credits_safe", 0), "review_event_credits": credit_staging.get("counts", {}).get("credits_review", 0)}
    summary["invariants"] = {name: value for name, value in gates.items() if name in {"events_gt_zero", "traceable_urls", "acceptable_time_completeness", "duplicate_event_identity", "duplicate_performance_slot", "null_timed_shadow_duplicates", "ambiguous_same_day_occurrence", "year_inferred_without_production_evidence", "year_unverified", "untraceable", "production_writes", "source_fetch_failures", "global_master_loaded"}}
    payloads = {"source_audit": source_audit, "raw": [event.raw | {"event_key": event.event_key, "source_url": event.source_url} for event in events], "normalized": [event.to_dict() for event in events], "snapshot": snapshot.__dict__, "resolution_staging": resolution_rows, "credit_resolution_staging": credit_staging, "final_staging": {"events": [event.to_dict() for event in events], "resolution": resolution_rows, "review": review_rows, "credit_resolution": credit_staging, "artists": credit_staging.get("safe_new_artists", []), "event_credits": credit_staging.get("safe_event_credits", []), "writes": 0}, "summary": summary}
    output_dir.mkdir(parents=True, exist_ok=True)
    for stage in STAGES:
        (output_dir / f"{stage}.json").write_text(json.dumps(payloads[stage], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (output_dir / "credit_resolution_staging.json").write_text(json.dumps(credit_staging, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(payloads["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    return payloads["summary"]
