from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Cloud Season Ingestion Pipeline V1")
    parser.add_argument("--venue", required=True)
    parser.add_argument("--season", required=True)
    parser.add_argument("--mode", choices=("dry-run", "apply"), default="dry-run")
    parser.add_argument("--output-dir", type=Path, default=Path("season-ingestion-output"))
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    summary = run_pipeline(venue=args.venue, season=args.season, mode=args.mode, output_dir=args.output_dir, snapshot_path=args.snapshot)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
