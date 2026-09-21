#!/usr/bin/env python3
"""Run the standardized Hermes -> auto PDF -> human PDF state machine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.acquisition_state_machine import run_acquisition_state_machine
from season_ingestion.pdf_batch import UNRESOLVED_ACQUISITION_STATE_MACHINE_VENUES
from season_ingestion.registry import load_registry


def main() -> int:
    registry = load_registry()
    registry_venues = tuple(registry["venues"])
    parser = argparse.ArgumentParser(description="Standardized three-level venue acquisition")
    parser.add_argument("--venue", action="append", choices=registry_venues)
    parser.add_argument(
        "--group",
        choices=sorted({
            str(config["acceptance_group"])
            for config in registry["venues"].values()
            if isinstance(config, dict) and config.get("acceptance_group")
        }),
        help="run the registry-configured acceptance group",
    )
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/acquisition-state-machine-v1"))
    parser.add_argument("--manual-root", type=Path, default=Path("manual_sources"))
    args = parser.parse_args()
    if args.venue:
        venues = args.venue
    elif args.group:
        venues = [
            venue_id for venue_id, config in registry["venues"].items()
            if isinstance(config, dict) and config.get("acceptance_group") == args.group
        ]
    else:
        venues = list(UNRESOLVED_ACQUISITION_STATE_MACHINE_VENUES)
    reports = []
    for venue_id in venues:
        config = registry["venues"].get(venue_id)
        if not isinstance(config, dict):
            reports.append({"venue": venue_id, "final_status": "BLOCKED", "blocker": "registry entry is missing", "production_writes": 0})
            continue
        try:
            reports.append(run_acquisition_state_machine(
                venue_id=venue_id,
                season=args.season,
                config=config,
                output_dir=args.output_root / venue_id,
                manual_root=args.manual_root,
            ))
        except Exception as exc:
            # A venue-specific acquisition failure must not stop the batch.
            reports.append({
                "venue": venue_id,
                "hermes_status": "BLOCKED",
                "hermes_events": 0,
                "pdf_discovered": "UNKNOWN",
                "pdf_download": "NOT_COMPLETED",
                "pdf_type": "NONE",
                "pdf_events": 0,
                "pdf_programme": 0,
                "pdf_credits": 0,
                "merged_events": 0,
                "merged_programme": 0,
                "merged_credits": 0,
                "global_master": "NOT_RUN",
                "final_status": "BLOCKED",
                "human_action": "NONE",
                "production_writes": 0,
                "blocker": str(exc),
            })
    for report in reports:
        for key in (
            "venue", "hermes_status", "hermes_attempts", "raw_output_saved", "hermes_events",
            "source_discovery", "discovered_mode", "discovered_endpoint",
            "acquisition_mode",
            "source_family", "occurrence_source_family", "enrichment_source_families",
            "acquisition_status", "enrichment_status", "canonical_status",
            "pdf_discovered", "pdf_download", "pdf_type",
            "pdf_events", "pdf_programme", "pdf_credits", "merged_events", "merged_programme",
            "merged_credits", "global_master", "final_status", "human_action", "production_writes",
        ):
            print(f"{key.upper()}={report.get(key, 'NONE')}")
        if report.get("blocker"):
            print(f"BLOCKER={report['blocker']}")
    status_groups = {
        "SOURCE_READY": [],
        "SOURCE_PARTIAL": [],
        "ADAPTER_REQUIRED": [],
        "REVIEW_REQUIRED": [],
        "HUMAN_PDF_REQUIRED": [],
        "NO_OFFICIAL_PDF": [],
        "BLOCKED": [],
    }
    for report in reports:
        status_groups.setdefault(report.get("acquisition_status") or report.get("final_status", "BLOCKED"), []).append(report.get("venue", "UNKNOWN"))
    print(f"VENUES_ATTEMPTED={len(reports)}")
    for status, venue_ids in status_groups.items():
        print(f"{status}={','.join(venue_ids)}")
    print(f"PRODUCTION_WRITES={sum(report.get('production_writes', 0) for report in reports)}")
    return 0 if all(report.get("production_writes", 0) == 0 for report in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
