#!/usr/bin/env python3
"""Read-only semantic freeze audit for the accepted PDF release.

The audit consumes the already accepted closeout/freeze manifests.  It never
calls the production writer and never mutates Supabase; the duplicate counts
are supplied by the caller from a read-only database query.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_audit(root: Path, *, duplicate_event: int = 0, duplicate_event_work: int = 0, duplicate_credit: int = 0) -> dict[str, Any]:
    report = _read(root / "final-report.json")
    freeze = _read(root / "data-freeze.json")
    frontend = _read(root / "frontend-freeze.json")
    repair = _read(root / "pollution-repair-manifest.json")
    target_venues = list(freeze.get("target_venues") or [])
    repaired = int(repair.get("rows_repaired", 0) or 0)
    duplicate_free = not any((duplicate_event, duplicate_event_work, duplicate_credit))
    return {
        "schema_version": "semantic-freeze-audit-v1",
        "read_only": True,
        "polluted_venues_audited": len(target_venues),
        "target_venues": target_venues,
        "valid_rows_preserved": int(freeze.get("valid_new_rows_preserved", 0) or 0),
        "raw_programme_fragments_removed": repaired,
        "semantic_programme_duplicates_removed": int(report.get("SEMANTIC_PROGRAMME_DUPLICATES_REMOVED", 0) or 0),
        "semantic_credit_duplicates_removed": int(report.get("SEMANTIC_CREDIT_DUPLICATES_REMOVED", 0) or 0),
        "wrong_role_credits_fixed": int(report.get("WRONG_ROLE_CREDITS_FIXED", 0) or 0),
        "wrong_character_links_fixed": int(report.get("WRONG_CHARACTER_LINKS_FIXED", 0) or 0),
        "wrong_event_credits_fixed": int(report.get("WRONG_EVENT_CREDITS_FIXED", 0) or 0),
        "role_bleed_errors_fixed": int(report.get("ROLE_BLEED_ERRORS_FIXED", 0) or 0),
        "soloist_instruments_fixed": int(report.get("SOLOIST_INSTRUMENTS_FIXED", 0) or 0),
        "duplicate_event": duplicate_event,
        "duplicate_event_work": duplicate_event_work,
        "duplicate_credit": duplicate_credit,
        "out_of_scope_mutations": int(freeze.get("out_of_scope_mutations", 0) or 0),
        "audit_basis": {
            "legacy_repair_manifest": repair.get("reason"),
            "legacy_repair_status": repair.get("status"),
            "frontend_freeze": frontend.get("freeze_status"),
            "data_freeze": freeze.get("status"),
            "production_apply": report.get("PRODUCTION_APPLY"),
            "new_frozen_frontend_commit": report.get("NEW_FROZEN_FRONTEND_COMMIT"),
            "frontend_files_changed": report.get("FRONTEND_FILES_CHANGED", 0),
            "live_visual_smoke": report.get("LIVE_VISUAL_SMOKE"),
            "frontend_deployment": report.get("FRONTEND_DEPLOYMENT"),
        },
        "status": "PASS" if duplicate_free and freeze.get("status") == "PASS" and frontend.get("freeze_status") == "PASS" else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only semantic freeze audit")
    parser.add_argument("--root", type=Path, default=Path("artifacts/pdf-bulk-ingestion"))
    args = parser.parse_args()
    print(json.dumps(build_audit(args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
