#!/usr/bin/env python3
"""Prepare every configured season source without performing database writes."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from season_ingestion.adapters import TeatroRealAdapter, WienerStaatsoperAdapter
from season_ingestion.reconciliation import VENUE_SOURCES, reconcile
from season_ingestion.season import resolve_season_bounds
from season_ingestion.supabase import fetch_existing_sources

ADAPTERS = {
    "wiener_staatsoper": WienerStaatsoperAdapter,
    "teatro_real": TeatroRealAdapter,
}
# Capability declarations are deliberately local: an absent contract must never
# turn into a guessed URL or synthetic staging data.
DETAIL_ENRICHMENT = {"wiener_staatsoper": False, "teatro_real": False}


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _select(value: str, configured: list[str]) -> list[str]:
    if value.strip().lower() == "all":
        return configured
    requested = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(requested) - set(configured))
    if unknown:
        raise ValueError(f"unknown venues: {', '.join(unknown)}")
    return requested


def summarize_statuses(results: list[dict]) -> dict[str, int]:
    """Count each readiness milestone from the field that owns it.

    ``overall_status`` describes the furthest completed stage and therefore
    cannot be used to count independent capabilities (for example, a venue
    that reached preflight is still discovery-ready).
    """
    return {
        "source_contract_missing": sum(
            item["overall_status"] == "source_contract_missing" for item in results
        ),
        "not_ready": sum(item["overall_status"] == "not_ready" for item in results),
        "discovery_ready": sum(
            item["discovery_status"] == "discovery_ready" for item in results
        ),
        "detail_enrichment_ready": sum(
            item["detail_enrichment_status"] == "detail_enrichment_ready"
            for item in results
        ),
        "preflight_ready": sum(
            item["preflight_status"] == "preflight_ready" for item in results
        ),
    }


def prepare_venue(venue: str, season: str, settings: dict, output: Path) -> dict:
    venue_dir = output / venue
    base = {
        "venue": venue,
        "season": season,
        "discovery_status": "source_contract_missing",
        "detail_enrichment_status": "source_contract_missing",
        "preflight_status": "source_contract_missing",
        "write_status": "write_not_approved",
        "overall_status": "source_contract_missing",
        "staging_file": None,
        "report_file": f"{venue}/report.json",
        "failure_reason": None,
    }
    adapter_class = ADAPTERS.get(venue)
    if adapter_class is None or not settings.get("adapter"):
        base["failure_reason"] = "No audited source contract or adapter is available"
        _write(venue_dir / "report.json", base)
        _write(venue_dir / "status.json", base)
        return base

    base.update(
        discovery_status="not_ready",
        detail_enrichment_status=("detail_enrichment_ready" if DETAIL_ENRICHMENT[venue] else "not_supported"),
        preflight_status="not_ready",
        overall_status="not_ready",
    )
    try:
        events = adapter_class(settings).ingest(season)
        rows = [event.to_dict() for event in events]
        if not rows:
            raise RuntimeError("official discovery returned no valid events")
        season_start, season_end = resolve_season_bounds(season, settings)
        if any(not season_start <= row["date"] <= season_end for row in rows):
            raise ValueError("canonical staging contains an event outside the season")
        staging = venue_dir / "staging.jsonl"
        staging.parent.mkdir(parents=True, exist_ok=True)
        staging.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        base.update(
            discovery_status="discovery_ready",
            overall_status="discovery_ready",
            staging_file=f"{venue}/staging.jsonl",
            staging_records=len(rows),
        )
        if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_READONLY_KEY"):
            existing = fetch_existing_sources(
                VENUE_SOURCES[venue], season, season_start=season_start, season_end=season_end,
                apply_mode=False,
            )
            base["reconciliation"] = reconcile(rows, existing, venue)
            base["preflight_status"] = "preflight_ready"
            base["overall_status"] = "preflight_ready"
        else:
            base["preflight_status"] = "readonly_credentials_missing"
            base["failure_reason"] = "Read-only preflight was not run because credentials are unavailable"
    except Exception as exc:
        base["failure_reason"] = f"{type(exc).__name__}: {exc}"

    _write(venue_dir / "report.json", base)
    _write(venue_dir / "status.json", base)
    return base


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a read-only batch of season staging artifacts")
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--venues", default="all", help="all or a comma-separated configured venue list")
    parser.add_argument("--output-dir", type=Path, default=Path("season-batch-output"))
    args = parser.parse_args()
    config = json.loads((ROOT / "config/venues.json").read_text(encoding="utf-8"))
    names = _select(args.venues, list(config["venues"]))
    results = []
    for name in names:
        # Each venue is an isolation boundary: failures become data in the report.
        results.append(prepare_venue(name, args.season, config["venues"][name], args.output_dir))
    summary = {
        "season": args.season,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "write_status": "write_not_approved",
        "database_writes_performed": 0,
        "venues": results,
        "counts": summarize_statuses(results),
    }
    _write(args.output_dir / "batch-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
