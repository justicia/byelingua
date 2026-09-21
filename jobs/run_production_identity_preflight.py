"""Run the fixed-production, read-only Supabase identity preflight."""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.production_identity import production_identity_preflight


def main() -> int:
    report = production_identity_preflight()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["production_preflight"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
