#!/usr/bin/env python3
"""Materialize the approved SAFE release cohort; never writes production."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.safe_release import DEFAULT_RELEASE_ID, materialize_release


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize approved SAFE release artifacts without production writes")
    parser.add_argument("--release-report", type=Path, default=Path("artifacts/generic-v1-release-readiness-20260915/report.json"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/safe-release-v1-20260915"))
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--approved-run-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--commit", default=os.getenv("GITHUB_SHA", "unknown"))
    parser.add_argument("--created-at", default="2026-09-15T00:00:00+00:00")
    args = parser.parse_args()
    reports = materialize_release(
        release_report_path=args.release_report,
        output_root=args.output_root,
        season=args.season,
        approved_run_id=args.approved_run_id,
        commit=args.commit,
        created_at=args.created_at,
    )
    print(json.dumps({"release_artifact_root": str(args.output_root), "reports": reports, "production_writes": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
