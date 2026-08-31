"""Run the enabled venue-season queue in full-season, read-only mode.

The workflow owns the ephemeral output directory.  This entrypoint writes a
small source-hash state file for the next scheduled run, while all raw source,
Global Master, and staging files remain outside the upload path.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.factory import build_batch_summary, run_target
from season_ingestion.incremental import load_source_state, save_source_state, state_key
from season_ingestion.venue_targets import load_targets


def run_factory(*, season: str, scope: str, selected: list[str], output_root: Path, state_path: Path) -> dict:
    targets = load_targets(season=season, scope=scope, selected=selected)
    previous = load_source_state(state_path)
    entries = dict(previous)
    results = []
    for target in targets:
        key = state_key(str(target["venue_id"]), season)
        results.append(run_target(
            target,
            output_root,
            scope="full-season",
            previous_source_hash=previous.get(key),
        ))
        summary = results[-1].get("summary") or {}
        if summary.get("source_capability") == "SOURCE_PASS" and summary.get("source_fingerprint"):
            entries[key] = summary["source_fingerprint"]
    save_source_state(state_path, entries)
    batch = build_batch_summary(
        results,
        season=season,
        batch_run_id=os.getenv("GITHUB_RUN_ID", "local"),
        git_commit=os.getenv("GITHUB_SHA", "unknown"),
    )
    batch["operating_mode"] = "FULL_SEASON"
    batch["existing_production_closeout"] = "DIAGNOSTIC_ONLY"
    batch["production_writes"] = 0
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "factory_summary.json").write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return batch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", required=True)
    parser.add_argument("--scope", default="all-enabled", choices=("all-enabled", "pending", "selected"))
    parser.add_argument("--venue-ids", default="")
    parser.add_argument("--output-root", type=Path, default=Path("onboarding-output"))
    parser.add_argument("--state-path", type=Path, default=Path(".factory-state/source-hashes.json"))
    args = parser.parse_args()
    selected = [value.strip() for value in args.venue_ids.split(",") if value.strip()]
    batch = run_factory(
        season=args.season,
        scope=args.scope,
        selected=selected,
        output_root=args.output_root,
        state_path=args.state_path,
    )
    print(json.dumps(batch, ensure_ascii=False))
    return 0 if batch.get("batch_status") != "FAILED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
