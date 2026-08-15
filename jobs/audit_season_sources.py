#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.audit import PRODUCTION_SOURCES, audit_season_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only audit of production season sources")
    parser.add_argument("--season", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", action="append", choices=PRODUCTION_SOURCES, dest="sources")
    args = parser.parse_args(argv)

    config_path = Path(__file__).resolve().parents[1] / "config" / "venues.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    report = audit_season_sources(args.season, config, args.sources or PRODUCTION_SOURCES)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
