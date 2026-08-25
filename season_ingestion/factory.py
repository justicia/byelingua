from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .pipeline import run_pipeline
from .venue_targets import matrix_targets
from .notifications import build_approval_manifest


TERMINAL_STATES = {"READY_FOR_APPROVAL", "REVIEW_REQUIRED", "SOURCE_BLOCKED", "SOURCE_PARTIAL", "ADAPTER_REQUIRED", "FAILED"}


def classify_summary(summary: dict[str, Any]) -> str:
    if summary.get("source_capability") == "SOURCE_BLOCKED":
        return "SOURCE_BLOCKED"
    if summary.get("source_capability") == "SOURCE_PARTIAL":
        return "SOURCE_PARTIAL"
    if summary.get("global_master_preflight") == "FAIL":
        return "FAILED"
    if summary.get("passed") and summary.get("source_capability") == "SOURCE_PASS":
        return "READY_FOR_APPROVAL" if summary.get("counts", {}).get("writes", 0) == 0 else "FAILED"
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
