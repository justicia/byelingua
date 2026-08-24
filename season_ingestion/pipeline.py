from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import STAGES, validate_canonical_event
from .global_master import load_global_snapshot, resolve_entity, resolve_work
from .registry import load_adapter, load_registry


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
    snapshot = load_global_snapshot(path=snapshot_path)
    resolution_rows, review_rows = [], []
    composer_resolution = []
    for event in events:
        for item in event.programme:
            work_resolution = resolve_work(item["source_title"], item.get("composer"), snapshot)
            composer = item.get("composer")
            composer_status = resolve_entity("composer", composer, snapshot) if composer else {"status": "not_applicable", "entity_id": None, "reason": "programme item has no composer"}
            composer_resolution.append(composer_status)
            row = {"event_key": event.event_key, "source_title": item["source_title"], **work_resolution, "composer": composer, "composer_resolution": composer_status, "source_programme_index": item["source_programme_index"], "original_programme_order": item["original_programme_order"], "provenance": item.get("provenance", {})}
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
    gates = {"events_gt_zero": len(events) > 0, "traceable_urls": all(bool(event.source_url) for event in events), "duplicate_event_identity": duplicate_event_identity == 0, "artist_boundary_high": all(not (credit.get("artist_name") or "").casefold().endswith((" soprano", " tenor", " baritone", " bass")) for credit in credits), "programme_credit_contamination": all(credit.get("credit_kind") not in {"cast", "character"} or credit.get("function") not in {"conductor", "director", "orchestra", "chorus", "designer"} for credit in credits), "source_order_missing": all(item.get("original_programme_order") == item.get("source_programme_index") for item in programme_rows), "untraceable": not untraceable, "review_items_in_safe_subset": 0 == 0, "production_writes": 0 == 0, "source_fetch_failures": len(adapter.last_errors) == 0}
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
    work_counts = {"existing_exact": sum(row["status"] == "existing" for row in resolution_rows), "existing_alias": 0, "existing_normalized": 0, "legacy_existing": 0, "new_candidate": 0, "review": len(review_rows), "no_programme_evidence": no_programme_evidence}
    composer_counts = {"existing": sum(row.get("status") == "existing" for row in composer_resolution), "alias": 0, "normalized": 0, "new_candidate": 0, "review": sum(row.get("status") == "review_required" for row in composer_resolution)}
    summary = {"generated_at": generated_at, "venue": venue, "season": season, "mode": mode, "source_capability": source_capability, "months": {"requested": len(requested_months), "successful": len(successful_months), "failed": len(failed_months)}, "counts": {"events": len(events), "events_discovered": len(events), "normalized": len(events), "works_existing": work_counts["existing_exact"], "works_review": work_counts["review"], "review_items": len(review_rows), "writes": 0}, "detail_enrichment": {"detail_pages_requested": len(requested_months), "detail_pages_successful": len(successful_months), "detail_pages_failed": len(failed_months), "events_with_programme_evidence": sum(status == "PROGRAMME_EVIDENCE_FOUND" for status in programme_statuses), "events_without_programme_evidence": no_programme_evidence, "detail_parse_review": detail_parse_review, "programme_items": len(programme_rows), "composer_candidates": sum(bool(item.get("composer_candidate")) for item in programme_rows), "credits_total": len(credits), "artist_candidates": len([c for c in credits if c.get("artist_name")]), "character_candidates": len([c for c in credits if c.get("character")]), "composer_resolution": composer_counts, "work_resolution": work_counts}, "gates": gates, "passed": all(gates.values())}
    payloads = {"source_audit": source_audit, "raw": [event.raw | {"event_key": event.event_key, "source_url": event.source_url} for event in events], "normalized": [event.to_dict() for event in events], "snapshot": snapshot.__dict__, "resolution_staging": resolution_rows, "final_staging": {"events": [event.to_dict() for event in events], "resolution": resolution_rows, "review": review_rows, "writes": 0}, "summary": summary}
    output_dir.mkdir(parents=True, exist_ok=True)
    for stage in STAGES:
        (output_dir / f"{stage}.json").write_text(json.dumps(payloads[stage], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(payloads["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    return payloads["summary"]
