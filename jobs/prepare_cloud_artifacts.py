"""Materialize the intentionally small, non-sensitive cloud artifact pack.

The ingestion runner may create raw, normalized, snapshot, and staging files in
the ephemeral runner workspace.  This job is the only directory exposed to
the artifact uploader, and it copies aggregate fields by allow-list rather
than attempting to redact arbitrary source rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _read(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return fallback


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _safe_summary(summary: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    counts = summary.get("counts") or {}
    details = summary.get("detail_enrichment") or {}
    health = summary.get("snapshot_health") or {}
    requests = summary.get("request_counts") or {}
    invariants = summary.get("invariants") or {}
    snapshot_path = output_dir / "snapshot.json"
    snapshot_hash = summary.get("snapshot_hash")
    if not snapshot_hash and snapshot_path.exists():
        snapshot_hash = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    return {
        "schema_version": "cloud-season-ingestion-safe-summary-v1",
        "git_sha": os.getenv("GITHUB_SHA", "unknown"),
        "venue": summary.get("venue"),
        "season": summary.get("season"),
        "source_capability": summary.get("source_capability"),
        "source_strategy": summary.get("source_strategy"),
        "snapshot_loaded": bool(summary.get("snapshot_loaded", health.get("global_master_loaded", False))),
        "snapshot_hash": snapshot_hash,
        "global_master_preflight": summary.get("global_master_preflight"),
        "counts": {
            "events": _int(counts.get("events")),
            "events_discovered": _int(counts.get("events_discovered")),
            "programme_items": _int(details.get("programme_items")),
            "credits_total": _int(details.get("credits_total")),
            "credits_safe": _int(counts.get("credits_safe")),
            "credits_review": _int(counts.get("credits_review")),
            "safe_programme_relationships": _int(counts.get("safe_programme_relationships")),
            "review_programme_relationships": _int(counts.get("review_programme_relationships")),
            "review_items": _int(counts.get("review_items")),
        },
        "request_counts": {key: _int(requests.get(key)) for key in (
            "listing_requested", "listing_succeeded", "listing_failed",
            "detail_requested", "detail_succeeded", "detail_failed",
        )},
        "catalog_status_counts": {key: _int(value) for key, value in (summary.get("catalog_status_counts") or {}).items() if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)},
        "staging_classification_counts": {key: _int(value) for key, value in (summary.get("staging_classification_counts") or {}).items() if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)},
        "event_type_distribution": {key: _int(value) for key, value in (summary.get("event_type_distribution") or {}).items() if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)},
        "invariants": {key: value for key, value in invariants.items() if isinstance(key, str) and isinstance(value, (bool, int))},
        "production_writes": 0,
    }


def _safe_pilot_diagnostics(summary: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "work_id", "work_title", "composer_canonical_name", "wikidata_work_qid_candidates",
        "selected_work_qid", "original_language", "p674_count", "p1441_count",
        "wikipedia_role_row_count", "catalog_status", "blocker_review_reason",
    }
    rows = summary.get("pilot_diagnostics")
    if rows is None:
        rows = summary.get("rows") or []
    safe_rows = []
    if isinstance(rows, list):
        for row in rows[:8]:
            if isinstance(row, dict):
                safe_rows.append({key: row[key] for key in allowed if key in row})
    return {"schema_version": "cloud-season-ingestion-pilot-diagnostics-v1", "venue": summary.get("venue"), "season": summary.get("season"), "rows": safe_rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = _read(args.input_dir / "summary.json", {})
    if not isinstance(summary, dict):
        summary = {}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(_safe_summary(summary, args.input_dir), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "pilot_diagnostics.json").write_text(json.dumps(_safe_pilot_diagnostics(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
