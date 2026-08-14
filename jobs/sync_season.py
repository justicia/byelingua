#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from season_ingestion.adapters import WienerStaatsoperAdapter
from season_ingestion.preflight import ExistingSource, fetch_existing_sources, reconcile
from season_ingestion.supabase import apply_events  # disabled compatibility symbol; never called

SUPPORTED_APPLY_VENUES = ("wiener_staatsoper",)


def apply_if_clear(rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    if report["apply_blocked"]:
        raise RuntimeError("apply blocked by preflight")
    raise RuntimeError("production writer not implemented")


def load_rows(venue: str, season: str, staging_file: Path | None, config: dict[str, Any]) -> list[dict[str, Any]]:
    if staging_file:
        return [json.loads(line) for line in staging_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if venue != "wiener_staatsoper":
        raise SystemExit("unsupported venue: no adapter or staging input is available")
    adapter = WienerStaatsoperAdapter(config["venues"][venue])
    return [event.to_dict() for event in adapter.ingest(season)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run season ingestion dry-run or read-only preflight")
    parser.add_argument("--venue", choices=SUPPORTED_APPLY_VENUES, required=True)
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--mode", choices=["dry-run", "preflight", "apply"], default="dry-run")
    parser.add_argument("--staging-file", type=Path, help="Existing JSONL input; no staging file is generated")
    parser.add_argument("--existing-file", type=Path, help="Read-only JSONL event_sources fixture for offline tests")
    parser.add_argument("--report-file", type=Path, help="Runtime reconciliation report path")
    parser.add_argument("--output-dir", type=Path, help="Deprecated dry-run report directory")
    args = parser.parse_args()

    config = json.loads((ROOT / "config/venues.json").read_text(encoding="utf-8"))
    rows = load_rows(args.venue, args.season, args.staging_file, config)
    if not rows:
        raise SystemExit("preflight refused: no staging events")
    if args.mode == "dry-run":
        report = {"venue": args.venue, "season": args.season, "mode": args.mode, "valid_events": len(rows), "applied_events": 0, "deleted_events": 0}
    else:
        existing = (
            [ExistingSource(**json.loads(line)) for line in args.existing_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            if args.existing_file else fetch_existing_sources()
        )
        report = reconcile(args.venue, rows, existing)
        report["mode"] = args.mode
        report["applied_events"] = 0
        if args.mode == "apply":
            apply_if_clear(rows, report)

    if args.report_file and args.mode in {"preflight", "apply"}:
        args.report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif args.output_dir and args.mode == "dry-run":
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / f"{args.venue}-{args.season}-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
