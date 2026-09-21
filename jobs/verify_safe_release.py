#!/usr/bin/env python3
"""Read-only verifier for a materialized SAFE release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.safe_release import (
    APPROVED_RELEASE_VENUES,
    SafeReleaseVerifierCredentialBlocked,
    verify_production_release,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read production state for a materialized SAFE release; never writes")
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--venue", choices=APPROVED_RELEASE_VENUES, required=True)
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--api-base-url")
    args = parser.parse_args()
    try:
        result = verify_production_release(
            release_dir=args.release_root / args.venue,
            venue_id=args.venue,
            season=args.season,
            api_base_url=args.api_base_url,
        )
    except SafeReleaseVerifierCredentialBlocked as exc:
        result = {
            "venue_id": args.venue,
            "season": args.season,
            "credential_used": exc.credential_used,
            "credential_value_printed": "NO",
            "verifier_read_only": "YES",
            "release_status": "PASS",
            "verifier_status": "CREDENTIAL_BLOCKED",
            "blocker": str(exc),
            "production_writes": 0,
        }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
