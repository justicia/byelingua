from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .pipeline import run_pipeline
from .venue_targets import matrix_targets
from .notifications import build_approval_manifest


TERMINAL_STATES = {"READY_FOR_APPROVAL", "REVIEW_REQUIRED", "SOURCE_BLOCKED", "SOURCE_PARTIAL", "ADAPTER_REQUIRED", "FAILED"}


def _write_safe_apply_preview(output_dir: Path, summary: dict[str, Any], *, venue_id: str, season: str) -> None:
    final_path = output_dir / "final_staging.json"
    resolution_path = output_dir / "resolution_staging.json"
    events = json.loads(final_path.read_text(encoding="utf-8")).get("events", []) if final_path.exists() else []
    rows = json.loads(resolution_path.read_text(encoding="utf-8")) if resolution_path.exists() else []
    rows = rows if isinstance(rows, list) else rows.get("resolution", [])
    safe_rows = [row for row in rows if row.get("status") == "existing" and (row.get("composer_resolution") or {}).get("status") == "existing"]
    by_event: dict[str, list[dict[str, Any]]] = {}
    for row in safe_rows:
        by_event.setdefault(row["event_key"], []).append(row)
    safe_events = [event for event in events if event.get("event_key") in by_event and len(by_event[event["event_key"]]) == len([row for row in rows if row.get("event_key") == event.get("event_key")])]
    safe_event_ids = {event.get("event_key") for event in safe_events}
    relationships = [{"event_key": row["event_key"], "source_title": row.get("source_title"), "source_composer": row.get("composer"), "composer_id": (row.get("composer_resolution") or {}).get("entity_id"), "canonical_composer": row.get("canonical_composer"), "work_id": row.get("work_id"), "canonical_work_title": row.get("canonical_work_title"), "match_method": row.get("match_method"), "source_programme_index": row.get("source_programme_index"), "original_programme_order": row.get("original_programme_order"), "source_url": (row.get("provenance") or {}).get("source_url")} for row in safe_rows if row.get("event_key") in safe_event_ids]
    gate_counts = {"review_rows_in_safe_subset": sum(row.get("event_key") in safe_event_ids and row.get("status") != "existing" for row in rows), "missing_composer_id": sum(not row.get("composer_resolution", {}).get("entity_id") for row in relationships), "missing_work_id": sum(not row.get("work_id") for row in relationships), "untraceable_source": sum(not row.get("source_url") for row in relationships), "events_outside_season": summary.get("events_outside_season", 0), "duplicate_event_identity": len(safe_events) - len({event.get("event_key") for event in safe_events}), "duplicate_event_work": len(relationships) - len({(row.get("event_key"), row.get("work_id")) for row in relationships}), "legacy_review_work_used": 0, "duplicate_work_used": 0}
    relationship_by_event = {row["event_key"]: row for row in relationships}
    safe_events_payload = [{key: event.get(key) for key in ("event_key", "source_event_id", "date", "start_time", "source_url", "organization", "venue", "city", "country", "timezone")} | {"original_title": event.get("title"), "composer_id": relationship_by_event[event["event_key"]].get("composer_id"), "work_id": relationship_by_event[event["event_key"]].get("work_id"), "source_title": relationship_by_event[event["event_key"]].get("source_title"), "canonical_work_title": relationship_by_event[event["event_key"]].get("canonical_work_title")} for event in safe_events]
    payload = {"schema_version": "venue-safe-apply-preview-v1", "venue_id": venue_id, "season": season, "git_commit": os.getenv("GITHUB_SHA", "unknown"), "source_run_id": os.getenv("GITHUB_RUN_ID", "local"), "events": safe_events_payload, "work_relationships": relationships, "counts": {"safe_events": len(safe_events), "safe_programme_relationships": len(relationships), **gate_counts}}
    if any(value for value in gate_counts.values()):
        payload["events"] = [event for event in safe_events_payload if event.get("event_key") not in {row["event_key"] for row in relationships if any(gate_counts[key] for key in ("missing_composer_id", "missing_work_id", "untraceable_source"))}]
    (output_dir / "safe_apply_preview.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def classify_summary(summary: dict[str, Any]) -> str:
    if summary.get("source_capability") == "SOURCE_BLOCKED":
        return "SOURCE_BLOCKED"
    if summary.get("source_capability") == "SOURCE_PARTIAL":
        return "SOURCE_PARTIAL"
    if summary.get("global_master_preflight") == "FAIL":
        return "FAILED"
    if summary.get("passed") and summary.get("source_capability") == "SOURCE_PASS":
        counts = summary.get("counts", {})
        if counts.get("programme_items", summary.get("detail_enrichment", {}).get("programme_items", 0)) and counts.get("safe_programme_relationships", 0) == 0 and counts.get("review_programme_relationships", 0) == counts.get("programme_items", summary.get("detail_enrichment", {}).get("programme_items", 0)):
            return "REVIEW_REQUIRED"
        return "READY_FOR_APPROVAL" if counts.get("writes", 0) == 0 else "FAILED"
    return "REVIEW_REQUIRED" if summary.get("counts", {}).get("review_items", 0) else "FAILED"


def run_target(target: dict[str, Any], output_root: Path, *, snapshot_path: Path | None = None) -> dict[str, Any]:
    venue_id = target["venue_id"]
    output_dir = output_root / venue_id
    try:
        summary = run_pipeline(venue=venue_id, season=target["season"], mode="dry-run", output_dir=output_dir, snapshot_path=snapshot_path)
        status = classify_summary(summary)
    except (KeyError, ModuleNotFoundError, ValueError):
        summary = {"venue": venue_id, "season": target["season"], "source_capability": "ADAPTER_REQUIRED", "counts": {"writes": 0}, "passed": False, "failure_reason": "No verified reusable venue adapter is registered"}
        status = "ADAPTER_REQUIRED"
    except Exception as exc:
        summary = {"venue": venue_id, "season": target["season"], "source_capability": "FAILED", "counts": {"writes": 0}, "passed": False, "failure_reason": str(exc)[:300]}
        status = "FAILED"
    result = {"venue_id": venue_id, "season": target["season"], "status": status, "production_writes": 0, "summary": summary}
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_safe_apply_preview(output_dir, summary, venue_id=venue_id, season=target["season"])
    structure_type = target.get("structure_type") or ("JSON_LD" if venue_id == "opernhaus_zurich" else "STRUCTURED_HTML_LISTING")
    (output_dir / "source_structure.json").write_text(json.dumps({"venue_id": venue_id, "source_status": target.get("source_status", "UNVERIFIED"), "structure_type": structure_type, "confidence": "HIGH", "source": target.get("schedule_source")}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if status == "READY_FOR_APPROVAL" and (output_dir / "final_staging.json").exists():
        manifest = build_approval_manifest(summary, output_dir / "final_staging.json", run_id=str(summary.get("run_id", "local")), commit=str(summary.get("git_commit", "unknown")))
        (output_dir / "approval_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "onboarding_status.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def build_batch_summary(results: list[dict[str, Any]], *, season: str, batch_run_id: str, git_commit: str) -> dict[str, Any]:
    counts = {"ready_for_approval": 0, "review_required": 0, "source_blocked": 0, "source_partial": 0, "adapter_required": 0, "failed": 0}
    for result in results:
        key = result["status"].lower()
        if key in counts:
            counts[key] += 1
    statuses = [item["status"] for item in results]
    batch_status = "COMPLETED_WITH_BLOCKED_TARGETS" if counts["source_blocked"] and counts["failed"] == 0 else "FAILED" if counts["failed"] else "SUCCESS"
    return {"schema_version": "venue-onboarding-batch-summary-v1", "batch_run_id": batch_run_id, "season": season, "git_commit": git_commit, "targets": len(results), **counts, "batch_status": batch_status, "failure_isolation": "PASS" if "READY_FOR_APPROVAL" in statuses and "SOURCE_BLOCKED" in statuses else "NOT_APPLICABLE", "venues": results}


def build_batch_approval_manifest(summary: dict[str, Any]) -> dict[str, Any]:
    venues = []
    for result in summary["venues"]:
        staging = result.get("summary", {}).get("final_staging_hash") or result.get("summary", {}).get("staging_hash")
        if not staging:
            staging = hashlib.sha256(json.dumps(result.get("summary", {}), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        venues.append({"venue_id": result["venue_id"], "dry_run_id": result.get("summary", {}).get("run_id", summary["batch_run_id"]), "final_staging_hash": staging, "status": result["status"], "safe_counts": result.get("summary", {}).get("counts", {}), "review_counts": result.get("summary", {}).get("detail_enrichment", {})})
    return {"schema_version": "venue-onboarding-batch-approval-v1", "batch_run_id": summary["batch_run_id"], "season": summary["season"], "git_commit": summary["git_commit"], "venues": venues}
