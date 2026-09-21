#!/usr/bin/env python3
"""Run the official-PDF acquisition batch independently per venue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.pdf_batch import BATCH_SEASON, BATCH_VENUES, run_pdf_batch_venue
from season_ingestion.registry import load_registry


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(*, output_root: Path, season: str = BATCH_SEASON, download_timeout_seconds: int = 60) -> dict[str, Any]:
    registry = load_registry()
    results: list[dict[str, Any]] = []
    for venue_id in BATCH_VENUES:
        config = registry["venues"].get(venue_id)
        if not isinstance(config, dict):
            result = {
                "venue": venue_id,
                "status": "BLOCKED",
                "blocker": "registry entry is missing",
                "pdf_download": "FAIL",
                "production_writes": 0,
            }
        else:
            try:
                result = run_pdf_batch_venue(
                    venue_id=venue_id,
                    config=config,
                    season=season,
                    output_dir=output_root / venue_id,
                    download_timeout_seconds=download_timeout_seconds,
                )
            except Exception as exc:
                result = {
                    "venue": venue_id,
                    "status": "BLOCKED",
                    "blocker": f"{type(exc).__name__}: {exc}",
                    "pdf_download": "FAIL",
                    "production_writes": 0,
                }
        results.append(result)

    ready = [row for row in results if row.get("status") == "SOURCE_READY"]
    review_only = [row for row in results if row.get("status") == "REVIEW_ONLY"]
    blocked = [row for row in results if row.get("status") == "BLOCKED"]
    summary = {
        "venues_attempted": len(BATCH_VENUES),
        "pdf_source_ready": [row["venue"] for row in ready],
        "review_only": [row["venue"] for row in review_only],
        "blocked": [row["venue"] for row in blocked],
        "total_events": sum(int(row.get("events", 0) or 0) for row in results),
        "total_programme": sum(int(row.get("programme", 0) or 0) for row in results),
        "total_credits": sum(int(row.get("credits", 0) or 0) for row in results),
        "production_writes": sum(int(row.get("production_writes", 0) or 0) for row in results),
        "venues": results,
    }
    _write_json(output_root / "batch-summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic official-PDF batch acquisition")
    parser.add_argument("--season", default=BATCH_SEASON)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/official-pdf-batch-v1"))
    parser.add_argument("--download-timeout", type=int, default=60)
    args = parser.parse_args()
    if args.season != BATCH_SEASON:
        raise SystemExit("This batch is intentionally limited to season 2026-27")
    summary = run(
        output_root=args.output_root,
        season=args.season,
        download_timeout_seconds=args.download_timeout,
    )
    for row in summary["venues"]:
        print(f"VENUE={row.get('venue')}")
        for key in ("pdf_download", "pdf_pages", "text_pages", "pdf_event_blocks", "deterministic_parsed", "review_blocks", "events", "programme", "credits", "source_type", "global_master", "production_writes", "status"):
            print(f"{key.upper()}={row.get(key, 0)}")
        if row.get("blocker"):
            print(f"BLOCKER={row['blocker']}")
    print(f"VENUES_ATTEMPTED={summary['venues_attempted']}")
    print(f"PDF_SOURCE_READY={','.join(summary['pdf_source_ready']) or 'NONE'}")
    print(f"REVIEW_ONLY={','.join(summary['review_only']) or 'NONE'}")
    print(f"BLOCKED={','.join(summary['blocked']) or 'NONE'}")
    print(f"TOTAL_EVENTS={summary['total_events']}")
    print(f"TOTAL_PROGRAMME={summary['total_programme']}")
    print(f"TOTAL_CREDITS={summary['total_credits']}")
    print(f"PRODUCTION_WRITES={summary['production_writes']}")
    return 0 if summary["production_writes"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
