#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from season_ingestion.adapters import WienerStaatsoperAdapter
from season_ingestion.supabase import apply_events


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually stage or apply a venue season")
    parser.add_argument("--venue", choices=["wiener_staatsoper"], required=True)
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output-dir", type=Path, default=Path("season-ingestion-output"))
    args = parser.parse_args()
    config = json.loads((ROOT / "config/venues.json").read_text(encoding="utf-8"))
    settings = config["venues"][args.venue]
    adapter = WienerStaatsoperAdapter(settings)
    events = adapter.ingest(args.season)
    if not events:
        raise SystemExit("refusing apply: the season returned no valid events")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [event.to_dict() for event in events]
    staging = args.output_dir / f"{args.venue}-{args.season}.jsonl"
    staging.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    applied = apply_events(rows) if args.mode == "apply" else 0
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "venue": args.venue,
        "season": args.season, "mode": args.mode, "valid_events": len(rows),
        "applied_events": applied, "deleted_events": 0, "last_errors": adapter.last_errors,
        "staging_file": str(staging),
    }
    report_path = args.output_dir / f"{args.venue}-{args.season}-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
