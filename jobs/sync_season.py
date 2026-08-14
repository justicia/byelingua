#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from season_ingestion.adapters import WienerStaatsoperAdapter
from season_ingestion.reconciliation import VENUE_SOURCES, reconcile
from season_ingestion.season import resolve_season_bounds
from season_ingestion.supabase import PreflightConfigurationError, apply_events, fetch_existing_sources


def load_rows(args: argparse.Namespace, venue_config: dict) -> tuple[list[dict], WienerStaatsoperAdapter | None]:
    if args.staging_file:
        return [json.loads(line) for line in args.staging_file.read_text(encoding="utf-8").splitlines() if line.strip()], None
    if args.venue != "wiener_staatsoper":
        raise SystemExit(f"no staging input or adapter is available for {args.venue}")
    adapter = WienerStaatsoperAdapter(venue_config)
    return [event.to_dict() for event in adapter.ingest(args.season)], adapter


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage or read-only preflight a venue season")
    parser.add_argument("--venue", required=True)
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--mode", choices=["dry-run", "preflight", "apply"], default="dry-run")
    parser.add_argument("--output-dir", type=Path, default=Path("season-ingestion-output"))
    parser.add_argument("--staging-file", type=Path)
    parser.add_argument("--report-file", type=Path)
    args = parser.parse_args()
    config = json.loads((ROOT / "config/venues.json").read_text(encoding="utf-8"))
    try:
        venue_config = config["venues"][args.venue]
    except KeyError:
        raise SystemExit(f"venue is not configured: {args.venue}") from None
    if args.venue not in VENUE_SOURCES:
        raise SystemExit(f"venue has no production source mapping: {args.venue}")
    season_start, season_end = resolve_season_bounds(args.season, venue_config)
    bounds_source = (
        "venue_override"
        if args.season in venue_config.get("season_bounds", {})
        else "default"
    )
    rows, adapter = load_rows(args, venue_config)
    if not rows:
        raise SystemExit("refusing to continue: the season returned no valid events")
    start_date, end_date = date.fromisoformat(season_start), date.fromisoformat(season_end)
    for index, row in enumerate(rows, start=1):
        row_date = row.get("date")
        try:
            parsed_date = date.fromisoformat(row_date) if isinstance(row_date, str) else None
        except ValueError:
            parsed_date = None
        if parsed_date is None or not start_date <= parsed_date <= end_date:
            raise SystemExit(
                f"staging record {index} date {row_date!r} is outside season range "
                f"{season_start} to {season_end}"
            )

    bounds_report = {
        "season_start": season_start,
        "season_end": season_end,
        "season_bounds_source": bounds_source,
    }

    if args.mode in {"preflight", "apply"}:
        try:
            existing = fetch_existing_sources(
                VENUE_SOURCES[args.venue], args.season,
                season_start=season_start, season_end=season_end,
                apply_mode=args.mode == "apply",
            )
        except PreflightConfigurationError as exc:
            report = {
                "venue": args.venue, "source": VENUE_SOURCES[args.venue], "season": args.season,
                "mode": args.mode, "staging_records": len(rows), "collision_guard_blocked": True,
                "preflight_configuration_error": {
                    "type": "preflight_configuration_error",
                    "missing_fields": sorted(set(exc.missing_fields)),
                    "affected_records": len(rows),
                },
            }
            report.update(bounds_report)
            path = args.report_file or Path("reconciliation-report.json")
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if args.mode == "apply":
                raise SystemExit("apply blocked by preflight configuration error")
            print(json.dumps(report, ensure_ascii=False))
            return
        report = reconcile(rows, existing, args.venue)
        report.update(bounds_report)
        if args.mode == "preflight":
            report.update({"season": args.season, "mode": "preflight"})
            path = args.report_file or Path("reconciliation-report.json")
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False))
            return
        if report["collision_guard_blocked"]:
            raise SystemExit("apply blocked by reconciliation collision guard")
        from season_ingestion.supabase import apply_events
        apply_events(rows, existing)
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    staging = args.output_dir / f"{args.venue}-{args.season}.jsonl"
    staging.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    missing_time = Counter(row["event_type"] for row in rows if row.get("start_time") is None)
    review_required = sum(any(item.get("normalization_status") == "review_required" for item in row.get("programme", [])) for row in rows)
    errors = adapter.last_errors if adapter else []
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "venue": args.venue, "season": args.season, "mode": "dry-run",
        "valid_events": len(rows), "date_range": {"start": min(row["date"] for row in rows), "end": max(row["date"] for row in rows)},
        "applied_events": 0, "deleted_events": 0, "last_errors": errors,
        "start_time_count": sum(row.get("start_time") is not None for row in rows),
        "start_time_coverage_percent": round(100 * sum(row.get("start_time") is not None for row in rows) / len(rows), 2),
        "missing_start_time_by_event_type": dict(sorted(missing_time.items())), "review_required_events": review_required,
        "zero_credits_events": sum(not row.get("credits") for row in rows), "not_found_month_errors": sum("404" in e.get("error", "") for e in errors),
        "staging_file": str(staging),
    }
    report.update(bounds_report)
    (args.output_dir / f"{args.venue}-{args.season}-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
