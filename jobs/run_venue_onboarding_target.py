from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.factory import run_target
from season_ingestion.venue_targets import load_targets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--venue-id", required=True)
    parser.add_argument("--season", required=True)
    parser.add_argument("--output-root", type=Path, default=Path("onboarding-output"))
    parser.add_argument("--hermes-source-facts", type=Path)
    args = parser.parse_args()
    targets = load_targets(season=args.season, scope="selected", selected=[args.venue_id])
    if len(targets) != 1:
        raise SystemExit(f"target not found or disabled: {args.venue_id}")
    if args.hermes_source_facts is not None and not args.hermes_source_facts.is_file():
        raise SystemExit(f"Hermes source-facts artifact not found: {args.hermes_source_facts}")
    result = run_target(targets[0], args.output_root, hermes_source_facts_path=args.hermes_source_facts)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
