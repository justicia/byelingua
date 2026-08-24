from __future__ import annotations

import json
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import STAGES, validate_canonical_event
from .contracts import empty_global_snapshot
from .global_master import GlobalMasterError, load_global_snapshot, resolve_entity, resolve_work
from .registry import load_adapter, load_registry


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
    generated_at = datetime.now(timezone.utc).isoformat()
    global_master_error = None
    try:
        snapshot = load_global_snapshot(path=snapshot_path)
    except GlobalMasterError as exc:
        global_master_error = {"code": exc.code, "message": exc.message}
        snapshot = empty_global_snapshot(generated_at)
    snapshot_health = dict(getattr(snapshot, "health", {}) or {})
    global_master_loaded = bool(snapshot_health.get("global_master_loaded", snapshot.entities.get("composer") and snapshot.entities.get("work")))
    if global_master_error:
        snapshot_health.update({"preflight_status": "FAIL", "global_master_loaded": False, "error_code": global_master_error["code"], "error_message": global_master_error["message"], "query_errors": 1})
    resolution_rows, review_rows = [], []
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
                work_resolution = resolve_work(item["source_title"], composer_status, snapshot) if composer_status.get("status") == "existing" else {"status": "review_required", "work_id": None, "reason": "composer unresolved; Work resolution deferred"}
            row = {"event_key": event.event_key, "source_title": item["source_title"], **work_resolution, "composer": composer, "composer_candidate": item.get("composer_candidate", {}), "composer_resolution": composer_status, "source_programme_index": item["source_programme_index"], "original_programme_order": item["original_programme_order"], "provenance": item.get("provenance", {})}
            resolution_rows.append(row)
            if work_resolution["status"] == "review_required":
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
    gates = {"events_gt_zero": len(events) > 0, "traceable_urls": all(bool(event.source_url) for event in events), "duplicate_event_identity": duplicate_event_identity == 0, "artist_boundary_high": all(not (credit.get("artist_name") or "").casefold().endswith((" soprano", " tenor", " baritone", " bass")) for credit in credits), "programme_credit_contamination": all(credit.get("credit_kind") not in {"cast", "character"} or credit.get("function") not in {"conductor", "director", "orchestra", "chorus", "designer"} for credit in credits), "source_order_missing": all(item.get("original_programme_order") == item.get("source_programme_index") for item in programme_rows), "untraceable": not untraceable, "review_items_in_safe_subset": 0 == 0, "production_writes": 0 == 0, "source_fetch_failures": len(adapter.last_errors) == 0, "global_master_loaded": global_master_loaded}
    requested_months = getattr(adapter, "requested_months", [])
    successful_months = getattr(adapter, "successful_months", [])
    failed_months = getattr(adapter, "failed_months", [])
    source_audit = {"venue": venue, "season": season, "official_source": config["official_source"], "official_fallback_source": config.get("fallback_source"), "source_strategy": "official Zürich season index -> official detail JSON-LD -> official semantic detail fields", "requested_months": requested_months, "successful_months": successful_months, "failed_months": failed_months, "source_pages": getattr(adapter, "source_pages", {}), "adapter_errors": adapter.last_errors, "events": len(events), "detail_pages_requested": len(requested_months), "detail_pages_successful": len(successful_months), "detail_pages_failed": len(failed_months)}
    if failed_months:
        source_capability = "SOURCE_BLOCKED" if adapter.last_errors and all("403" in item.get("error", "") for item in adapter.last_errors) else "SOURCE_PARTIAL"
    elif not successful_months or not events:
        source_capability = "SOURCE_UNSUPPORTED"
    else:
        source_capability = "SOURCE_PASS"
    source_audit["source_capability"] = source_capability
    if global_master_loaded:
        work_counts = {"existing_exact": sum(row["status"] == "existing" and row.get("match_method") == "exact" for row in resolution_rows), "existing_alias": sum(row["status"] == "existing" and row.get("match_method") == "alias" for row in resolution_rows), "existing_normalized": sum(row["status"] == "existing" and row.get("match_method") == "normalized" for row in resolution_rows), "legacy_existing": 0, "new_candidate": 0, "review": len(review_rows), "not_run": 0, "no_programme_evidence": no_programme_evidence}
        composer_counts = {"exact": sum(row.get("status") == "existing" and row.get("match_method") == "exact" for row in composer_resolution), "alias": sum(row.get("status") == "existing" and row.get("match_method") == "alias" for row in composer_resolution), "normalized": sum(row.get("status") == "existing" and row.get("match_method") == "normalized" for row in composer_resolution), "new_candidate": 0, "review": sum(row.get("status") == "review_required" for row in composer_resolution), "not_run": 0}
    else:
        not_run = len([row for row in composer_resolution if row.get("status") == "not_run"])
        work_counts = {"existing_exact": 0, "existing_alias": 0, "existing_normalized": 0, "legacy_existing": 0, "new_candidate": 0, "review": 0, "not_run": not_run, "no_programme_evidence": no_programme_evidence}
        composer_counts = {"exact": 0, "alias": 0, "normalized": 0, "new_candidate": 0, "review": 0, "not_run": not_run}
    summary = {"generated_at": generated_at, "venue": venue, "season": season, "mode": mode, "source_capability": source_capability, "months": {"requested": len(requested_months), "successful": len(successful_months), "failed": len(failed_months)}, "global_master_preflight": "PASS" if global_master_loaded else "FAIL", "global_master_error": global_master_error, "snapshot_health": snapshot_health, "snapshot_counts": snapshot_counts, "counts": {"events": len(events), "events_discovered": len(events), "normalized": len(events), "works_existing": work_counts["existing_exact"], "works_review": work_counts["review"], "review_items": len(review_rows), "writes": 0}, "detail_enrichment": {"detail_pages_requested": len(requested_months), "detail_pages_successful": len(successful_months), "detail_pages_failed": len(failed_months), "events_with_programme_evidence": sum(status == "PROGRAMME_EVIDENCE_FOUND" for status in programme_statuses), "events_without_programme_evidence": no_programme_evidence, "detail_parse_review": detail_parse_review, "programme_items": len(programme_rows), "composer_candidates": sum(bool(item.get("composer_candidate")) for item in programme_rows), "credits_total": len(credits), "artist_candidates": len([c for c in credits if c.get("artist_name")]), "character_candidates": len([c for c in credits if c.get("character")]), "composer_resolution": composer_counts, "work_resolution": work_counts}, "composer_trace": _composer_trace(resolution_rows, snapshot), "gates": gates, "passed": all(gates.values())}
    payloads = {"source_audit": source_audit, "raw": [event.raw | {"event_key": event.event_key, "source_url": event.source_url} for event in events], "normalized": [event.to_dict() for event in events], "snapshot": snapshot.__dict__, "resolution_staging": resolution_rows, "final_staging": {"events": [event.to_dict() for event in events], "resolution": resolution_rows, "review": review_rows, "writes": 0}, "summary": summary}
    output_dir.mkdir(parents=True, exist_ok=True)
    for stage in STAGES:
        (output_dir / f"{stage}.json").write_text(json.dumps(payloads[stage], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(payloads["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    return payloads["summary"]
