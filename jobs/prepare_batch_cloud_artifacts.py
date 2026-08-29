"""Reduce legacy batch output to non-sensitive aggregate cloud artifacts."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _safe_venue(item: dict[str, Any]) -> dict[str, Any]:
    summary = item.get("summary") or item
    counts = summary.get("counts") or {}
    return {
        "venue": item.get("venue") or summary.get("venue"),
        "season": item.get("season") or summary.get("season"),
        "status": item.get("overall_status") or summary.get("overall_status"),
        "discovery_status": item.get("discovery_status"),
        "detail_enrichment_status": item.get("detail_enrichment_status"),
        "preflight_status": item.get("preflight_status"),
        "source_capability": summary.get("source_capability"),
        "counts": {
            "events": _int(summary.get("events") or summary.get("staging_records")),
            "safe_update": _int(counts.get("safe_update")),
            "safe_insert": _int(counts.get("safe_insert")),
            "manual_review": _int(counts.get("manual_review")),
            "must_reconcile": _int(counts.get("must_reconcile")),
            "source_identity_matches": _int(counts.get("source_identity_matches")),
        },
        "production_writes": 0,
    }


def build_safe_batch(summary: dict[str, Any]) -> dict[str, Any]:
    venues = summary.get("venues") or []
    safe_venues = [_safe_venue(item) for item in venues if isinstance(item, dict)]
    return {
        "schema_version": "cloud-season-ingestion-safe-batch-summary-v1",
        "git_sha": os.getenv("GITHUB_SHA", "unknown"),
        "season": summary.get("season"),
        "targets": len(safe_venues),
        "batch_status": summary.get("batch_status") or summary.get("write_status"),
        "venues": safe_venues,
        "production_writes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    safe = build_safe_batch(_read(args.input_dir / "batch-summary.json"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "pilot_diagnostics.json").write_text(json.dumps({"schema_version": "cloud-season-ingestion-pilot-diagnostics-v1", "rows": []}, indent=2) + "\n", encoding="utf-8")
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        lines = ["# Cloud Season Ingestion Batch", "", f"Season: {safe.get('season')}", f"Batch status: {safe.get('batch_status')}", ""]
        for venue in safe["venues"]:
            lines.append(f"- {venue.get('venue')}: {venue.get('status')} ({venue.get('source_capability')})")
        Path(step_summary).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
