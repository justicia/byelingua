from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from season_ingestion.factory import build_batch_approval_manifest, build_batch_summary


def render_summary(summary: dict) -> str:
    lines = ["# Venue Onboarding Factory V1", "", f"Season: {summary['season']}", f"Batch status: {summary['batch_status']}", ""]
    for venue in summary["venues"]:
        item = venue["summary"]
        lines.extend([f"## {venue['venue_id']}", f"- Status: {venue['status']}", f"- Source: {item.get('source_capability', 'UNKNOWN')}", f"- Productions discovered: {item.get('productions_discovered', 0)}", f"- Events: {item.get('counts', {}).get('events_discovered', 0)}", f"- Date range: {item.get('date_min')} to {item.get('date_max')}", f"- Events outside season: {item.get('events_outside_season', 0)}", f"- Unique Work candidates: {item.get('detail_enrichment', {}).get('unique_work_candidates', 0)}", f"- Safe programme relationships: {item.get('counts', {}).get('safe_programme_relationships', 0)}", f"- Review programme relationships: {item.get('counts', {}).get('review_programme_relationships', 0)}", f"- Production writes: {venue.get('production_writes', 0)}", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("onboarding-output"))
    parser.add_argument("--season", required=True)
    parser.add_argument("--batch-run-id", default=os.getenv("GITHUB_RUN_ID", "local"))
    parser.add_argument("--commit", default=os.getenv("GITHUB_SHA", "unknown"))
    args = parser.parse_args()
    results = []
    for path in sorted(args.output_root.rglob("onboarding_status.json")):
        results.append(json.loads(path.read_text(encoding="utf-8")))
    summary = build_batch_summary(results, season=args.season, batch_run_id=args.batch_run_id, git_commit=args.commit)
    (args.output_root / "venue-onboarding-batch-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    safe = {key: value for key, value in summary.items() if key != "venues"}
    safe["venues"] = [{"venue_id": item["venue_id"], "status": item["status"], "production_writes": item.get("production_writes", 0), "summary": {key: value for key, value in item.get("summary", {}).items() if key in {"venue", "season", "source_capability", "productions_discovered", "detail_pages_out_of_season_skipped", "date_min", "date_max", "events_outside_season", "counts", "detail_enrichment", "global_master_preflight"}}} for item in summary["venues"]]
    (args.output_root / "summary.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_root / "pilot_diagnostics.json").write_text("[]\n", encoding="utf-8")
    (args.output_root / "batch_approval_manifest.json").write_text(json.dumps(build_batch_approval_manifest(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target = os.getenv("GITHUB_STEP_SUMMARY")
    if target:
        Path(target).write_text(render_summary(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["batch_status"] != "FAILED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
