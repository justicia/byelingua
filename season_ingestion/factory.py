from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .pipeline import run_pipeline
from .venue_targets import matrix_targets
from .notifications import build_approval_manifest
from .incremental import compare_source_fingerprint
from .production_graph import build_payload
from .registry import load_registry


TERMINAL_STATES = {"READY_FOR_APPROVAL", "REVIEW_REQUIRED", "SOURCE_BLOCKED", "SOURCE_PARTIAL", "ADAPTER_REQUIRED", "FAILED"}


def _blocker(summary: dict[str, Any], status: str) -> tuple[str | None, str | None]:
    """Return one actionable blocker and the next technical fix."""
    if status == "READY_FOR_APPROVAL":
        return None, None
    errors = summary.get("source_audit", {}).get("adapter_errors") or summary.get("adapter_errors") or []
    if summary.get("source_capability") in {"SOURCE_BLOCKED", "SOURCE_PARTIAL", "SOURCE_UNSUPPORTED"}:
        first = errors[0] if errors else {}
        error_text = str(first.get("error") or "")
        if any(token in error_text.casefold() for token in ("socket", "winerror 10013", "failed to establish a new connection")):
            return "official source HTTPS fetch blocked by the execution environment", "Run this venue in a network-enabled cloud runner and rerun it"
        return str(first.get("error") or summary.get("failure_reason") or summary.get("source_capability")), "Repair the official source discovery/detail contract, then rerun this venue"
    if summary.get("global_master_preflight") == "FAIL":
        return "global master preflight unavailable", "Provide verified read-only Global Master credentials and rerun this venue"
    if summary.get("counts", {}).get("review_items", 0):
        return "canonical programme resolution has review items", "Resolve affected Composer/Work mappings in shared Global Master staging and rerun this venue"
    return str(summary.get("failure_reason") or "venue did not pass the factory gates"), "Inspect the first failing factory gate and rerun only this venue"


def _write_production_graph_staging(output_dir: Path, summary: dict[str, Any], *, venue_id: str) -> None:
    """Freeze the SAFE graph payload consumed by the approved apply job."""
    if summary.get("source_capability") != "SOURCE_PASS" or summary.get("global_master_preflight") != "PASS":
        return
    final_path, snapshot_path = output_dir / "final_staging.json", output_dir / "snapshot.json"
    if not final_path.exists() or not snapshot_path.exists():
        return
    final = json.loads(final_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    resolutions = final.get("resolution") or []
    safe_rows = [row for row in resolutions if row.get("status") == "existing" and row.get("work_id") and (row.get("composer_resolution") or {}).get("status") == "existing"]
    composer_ids = {row["composer_resolution"].get("entity_id") for row in safe_rows}
    work_ids = {row.get("work_id") for row in safe_rows}
    composers = [row for row in snapshot.get("entities", {}).get("composer", []) if row.get("id") in composer_ids]
    works = [row for row in snapshot.get("entities", {}).get("work", []) if row.get("id") in work_ids]
    relationships = [{"event_key": row["event_key"], "work_id": row["work_id"], "order": row.get("original_programme_order") or row.get("source_programme_index") or 1, "source_url": (row.get("provenance") or {}).get("source_url")} for row in safe_rows]
    staging = {"composer": {"safe": composers}, "work": {"safe": works}, "relationships": {"safe_existing": relationships, "safe_new": []}, "credit_resolution": final.get("credit_resolution") or {}}
    config = load_registry()["venues"].get(venue_id) or {}
    payload = build_payload(final.get("events", []), staging, organization={"name": config.get("organization"), "slug": venue_id}, venue={"name": config.get("venue"), "city": config.get("city"), "country_code": config.get("country")})
    payload["release"] = {"venue_id": venue_id, "season": summary.get("season"), "source_fingerprint": summary.get("source_fingerprint"), "final_staging_sha256": hashlib.sha256(final_path.read_bytes()).hexdigest()}
    path = output_dir / "production_graph_staging.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["production_graph_staging_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


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
    gate_counts = {"review_rows_in_safe_subset": sum(row.get("event_key") in safe_event_ids and row.get("status") != "existing" for row in rows), "missing_composer_id": sum(not row.get("composer_id") for row in relationships), "missing_work_id": sum(not row.get("work_id") for row in relationships), "untraceable_source": sum(not row.get("source_url") for row in relationships), "events_outside_season": summary.get("events_outside_season", 0), "duplicate_event_identity": len(safe_events) - len({event.get("event_key") for event in safe_events}), "duplicate_event_work": len(relationships) - len({(row.get("event_key"), row.get("work_id")) for row in relationships}), "duplicate_performance_slot": summary.get("duplicate_performance_slot", 0), "ambiguous_same_day_occurrence": summary.get("ambiguous_same_day_occurrence", 0), "null_timed_shadow_duplicates": summary.get("null_timed_shadow_duplicates", 0), "year_inferred_without_production_evidence": summary.get("year_inferred_without_production_evidence", 0), "legacy_review_work_used": 0, "duplicate_work_used": 0}
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


def run_target(target: dict[str, Any], output_root: Path, *, snapshot_path: Path | None = None, scope: str = "full-season", previous_source_hash: str | None = None, hermes_source_facts_path: Path | None = None) -> dict[str, Any]:
    venue_id = target["venue_id"]
    output_dir = output_root / venue_id
    try:
        summary = run_pipeline(venue=venue_id, season=target["season"], mode="dry-run", scope=scope, output_dir=output_dir, snapshot_path=snapshot_path, hermes_source_facts_path=hermes_source_facts_path)
        summary["incremental"] = compare_source_fingerprint(previous_source_hash, summary.get("source_fingerprint"))
        required_artifacts = ("source_audit", "raw", "normalized", "snapshot", "resolution_staging", "final_staging", "summary")
        artifact_checks = {}
        for artifact_name in required_artifacts:
            artifact_path = output_dir / f"{artifact_name}.json"
            try:
                json.loads(artifact_path.read_text(encoding="utf-8"))
                artifact_checks[artifact_name] = True
            except (FileNotFoundError, OSError, ValueError):
                artifact_checks[artifact_name] = False
        summary["artifact_completeness"] = {
            "files": artifact_checks,
            "all_required_present_and_valid": all(artifact_checks.values()),
        }
        status = classify_summary(summary)
    except (KeyError, ModuleNotFoundError) as exc:
        summary = {"venue": venue_id, "season": target["season"], "source_capability": "ADAPTER_REQUIRED", "counts": {"writes": 0}, "passed": False, "failure_reason": str(exc)[:300], "factory_exception": type(exc).__name__}
        status = "ADAPTER_REQUIRED"
    except ValueError as exc:
        summary = {"venue": venue_id, "season": target["season"], "source_capability": "FAILED", "counts": {"writes": 0}, "passed": False, "failure_reason": str(exc)[:300], "factory_exception": type(exc).__name__}
        status = "FAILED"
    except Exception as exc:
        summary = {"venue": venue_id, "season": target["season"], "source_capability": "FAILED", "counts": {"writes": 0}, "passed": False, "failure_reason": str(exc)[:300]}
        status = "FAILED"
    summary.setdefault("scope", scope)
    summary.setdefault("incremental", compare_source_fingerprint(previous_source_hash, summary.get("source_fingerprint")))
    blocker, next_fix = _blocker(summary, status)
    result = {"venue_id": venue_id, "season": target["season"], "status": status, "production_writes": 0, "blocker": blocker, "next_technical_fix": next_fix, "summary": summary}
    output_dir.mkdir(parents=True, exist_ok=True)
    # The pipeline writes its detailed summary before returning.  Persist the
    # incremental decision in that same runner-local summary without exposing
    # raw source pages or staging in the safe artifact pack.
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_safe_apply_preview(output_dir, summary, venue_id=venue_id, season=target["season"])
    structure_type = target.get("structure_type") or ("JSON_LD" if venue_id == "opernhaus_zurich" else "STRUCTURED_HTML_LISTING")
    (output_dir / "source_structure.json").write_text(json.dumps({"venue_id": venue_id, "source_status": target.get("source_status", "UNVERIFIED"), "structure_type": structure_type, "confidence": "HIGH", "source": target.get("schedule_source")}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if status == "READY_FOR_APPROVAL" and (output_dir / "final_staging.json").exists():
        _write_production_graph_staging(output_dir, summary, venue_id=venue_id)
        manifest = build_approval_manifest(summary, output_dir / "final_staging.json", run_id=str(summary.get("run_id", "local")), commit=str(summary.get("git_commit", "unknown")))
        (output_dir / "approval_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "onboarding_status.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def build_batch_summary(results: list[dict[str, Any]], *, season: str, batch_run_id: str, git_commit: str) -> dict[str, Any]:
    counts = {"ready_for_approval": 0, "review_required": 0, "source_blocked": 0, "source_partial": 0, "adapter_required": 0, "failed": 0}
    for result in results:
        key = result["status"].lower()
        if key in counts:
            counts[key] += 1
    statuses = [item["status"] for item in results]
    blocked = sum(1 for status in statuses if status != "READY_FOR_APPROVAL")
    batch_status = "COMPLETED_WITH_BLOCKED_TARGETS" if blocked else "SUCCESS"
    return {"schema_version": "venue-onboarding-batch-summary-v1", "batch_run_id": batch_run_id, "season": season, "git_commit": git_commit, "targets": len(results), "venues_attempted": len(results), "venues_production_ready": counts["ready_for_approval"], "venues_blocked": blocked, **counts, "batch_status": batch_status, "failure_isolation": "PASS" if blocked < len(results) else "NOT_APPLICABLE", "venues": results}


def build_batch_approval_manifest(summary: dict[str, Any]) -> dict[str, Any]:
    venues = []
    for result in summary["venues"]:
        staging = result.get("summary", {}).get("final_staging_hash") or result.get("summary", {}).get("staging_hash")
        if not staging:
            staging = hashlib.sha256(json.dumps(result.get("summary", {}), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        venues.append({"venue_id": result["venue_id"], "dry_run_id": result.get("summary", {}).get("run_id", summary["batch_run_id"]), "final_staging_hash": staging, "status": result["status"], "safe_counts": result.get("summary", {}).get("counts", {}), "review_counts": result.get("summary", {}).get("detail_enrichment", {})})
    return {"schema_version": "venue-onboarding-batch-approval-v1", "batch_run_id": summary["batch_run_id"], "season": summary["season"], "git_commit": summary["git_commit"], "venues": venues}
