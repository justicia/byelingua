"""Aggregate only the safe per-venue cloud summaries."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from jobs.prepare_cloud_artifacts import _safe_pilot_diagnostics


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _safe_venue(summary: dict[str, Any]) -> dict[str, Any]:
    counts = summary.get("counts") or {}
    return {
        "venue": summary.get("venue"),
        "season": summary.get("season"),
        "source_capability": summary.get("source_capability"),
        "snapshot_loaded": bool(summary.get("snapshot_loaded")),
        "counts": {
            key: _int(counts.get(key))
            for key in (
                "events", "events_discovered", "programme_items", "credits_total",
                "credits_safe", "credits_review", "safe_programme_relationships",
                "review_programme_relationships", "review_items",
            )
        },
        "request_counts": {
            key: _int((summary.get("request_counts") or {}).get(key))
            for key in (
                "listing_requested", "listing_succeeded", "listing_failed",
                "detail_requested", "detail_succeeded", "detail_failed",
            )
        },
        "catalog_status_counts": {
            key: _int(value)
            for key, value in (summary.get("catalog_status_counts") or {}).items()
            if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
        },
        "staging_classification_counts": {
            key: _int(value)
            for key, value in (summary.get("staging_classification_counts") or {}).items()
            if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
        },
        "invariants": {
            key: value
            for key, value in (summary.get("invariants") or {}).items()
            if isinstance(key, str) and isinstance(value, (bool, int))
        },
        "production_writes": 0,
    }


def build_safe_batch(input_root: Path, *, season: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    venues: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for path in sorted(input_root.rglob("summary.json")):
        if path.parent.name == "aggregate":
            continue
        summary = _read(path)
        if summary.get("schema_version") != "cloud-season-ingestion-safe-summary-v1":
            continue
        venues.append(_safe_venue(summary))
        diagnostic_path = path.parent / "pilot_diagnostics.json"
        diagnostic = _safe_pilot_diagnostics(_read(diagnostic_path))
        diagnostics.extend(diagnostic.get("rows", []))
    selected_season = season or next((item.get("season") for item in venues if item.get("season")), None)
    batch = {
        "schema_version": "cloud-season-ingestion-safe-batch-summary-v1",
        "git_sha": os.getenv("GITHUB_SHA", "unknown"),
        "season": selected_season,
        "targets": len(venues),
        "venues": venues,
        "production_writes": 0,
    }
    return batch, {
        "schema_version": "cloud-season-ingestion-pilot-diagnostics-v1",
        "season": selected_season,
        "rows": diagnostics[:8],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--season")
    args = parser.parse_args()
    summary, diagnostics = build_safe_batch(args.input_root, season=args.season)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "pilot_diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        lines = ["# Venue Onboarding Factory V1", "", f"Season: {summary.get('season')}", f"Targets: {summary['targets']}", ""]
        for venue in summary["venues"]:
            counts = venue["counts"]
            lines.append(f"- {venue.get('venue')}: {venue.get('source_capability')}; events={counts['events']}; review={counts['review_items']}")
        Path(step_summary).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
