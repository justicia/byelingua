#!/usr/bin/env python3
"""Audit existing venue artifacts for safe release; never runs acquisition."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.release_readiness import (
    REJECT_RELEASE_CANDIDATE,
    REVIEW_RELEASE_CANDIDATE,
    SAFE_RELEASE_CANDIDATE,
    audit_artifact_directory,
)


BLIND_RELEASE_VENUES = (
    "wiener_musikverein",
    "wiener_konzerthaus",
    "theater_an_der_wien",
    "maison_radio_france",
    "teatro_de_la_zarzuela",
    "hamburgische_staatsoper",
    "gran_teatre_del_liceu",
    "palau_de_la_musica_catalana",
    "concertgebouw",
    "royal_opera_house",
    "bozar",
)


def _find_artifact_root(root: Path, venue: str) -> Path:
    candidates = []
    for batch in root.glob("generic-v1-blind-test*"):
        candidate = batch / venue
        if (candidate / "deterministic" / "summary.json").exists():
            candidates.append(candidate)
    if not candidates:
        raise FileNotFoundError(f"no existing deterministic artifact for {venue}")
    return max(candidates, key=lambda path: (path.stat().st_mtime, str(path)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only release admission audit")
    parser.add_argument("--artifacts-root", type=Path, default=Path("artifacts"))
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--output", type=Path, default=Path("artifacts/generic-v1-release-readiness/report.json"))
    args = parser.parse_args()

    reports = []
    for venue in BLIND_RELEASE_VENUES:
        artifact_dir = _find_artifact_root(args.artifacts_root, venue)
        report = audit_artifact_directory(venue_id=venue, season=args.season, artifact_dir=artifact_dir)
        report["artifact_dir"] = str(artifact_dir)
        reports.append(report)

    cohorts = {
        SAFE_RELEASE_CANDIDATE: [r["venue"] for r in reports if r["release_status"] == SAFE_RELEASE_CANDIDATE],
        REVIEW_RELEASE_CANDIDATE: [r["venue"] for r in reports if r["release_status"] == REVIEW_RELEASE_CANDIDATE],
        REJECT_RELEASE_CANDIDATE: [r["venue"] for r in reports if r["release_status"] == REJECT_RELEASE_CANDIDATE],
    }
    result = {
        "season": args.season,
        "venues_audited": len(reports),
        "safe_release_candidates": len(cohorts[SAFE_RELEASE_CANDIDATE]),
        "review_release_candidates": len(cohorts[REVIEW_RELEASE_CANDIDATE]),
        "reject_release_candidates": len(cohorts[REJECT_RELEASE_CANDIDATE]),
        "safe_events_total": sum(r["events_release_safe"] for r in reports),
        "review_events_total": sum(r["events_release_review"] for r in reports),
        "rejected_events_total": sum(r["events_rejected"] for r in reports),
        "safe_release_venues": cohorts[SAFE_RELEASE_CANDIDATE],
        "review_release_venues": cohorts[REVIEW_RELEASE_CANDIDATE],
        "reject_release_venues": cohorts[REJECT_RELEASE_CANDIDATE],
        "reports": reports,
        "production_writes": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    for report in reports:
        for key in (
            "venue", "acquisition_status", "events_discovered", "events_release_safe",
            "events_release_review", "events_rejected", "season_gate", "duplicate_gate",
            "slot_gate", "coverage_gate", "traceability_gate", "programme", "credits",
            "global_master", "release_status", "release_blocker",
        ):
            print(f"{key.upper()}={report.get(key)}")
    print(f"VENUES_AUDITED={result['venues_audited']}")
    print(f"SAFE_RELEASE_CANDIDATES={result['safe_release_candidates']}")
    print(f"REVIEW_RELEASE_CANDIDATES={result['review_release_candidates']}")
    print(f"REJECT_RELEASE_CANDIDATES={result['reject_release_candidates']}")
    print(f"SAFE_EVENTS_TOTAL={result['safe_events_total']}")
    print(f"REVIEW_EVENTS_TOTAL={result['review_events_total']}")
    print(f"REJECTED_EVENTS_TOTAL={result['rejected_events_total']}")
    print(f"SAFE_RELEASE_VENUES={','.join(result['safe_release_venues'])}")
    print(f"REVIEW_RELEASE_VENUES={','.join(result['review_release_venues'])}")
    print(f"REJECT_RELEASE_VENUES={','.join(result['reject_release_venues'])}")
    print("PRODUCTION_WRITES=0")
    print(f"SAFE_RELEASE_PREPARATION={'PASS' if result['safe_release_candidates'] else 'FAIL'}")
    return 0 if result["safe_release_candidates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
