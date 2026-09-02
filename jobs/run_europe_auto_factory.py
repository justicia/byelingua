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


def _isolated_failure_result(target: dict, output_root: Path, exc: Exception) -> dict:
    """Turn an unexpected venue exception into one isolated batch blocker."""
    venue_id = str(target["venue_id"])
    output_dir = output_root / venue_id
    summary_path = output_dir / "summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        summary = {}
    if not isinstance(summary, dict):
        summary = {}
    summary.update({
        "venue": venue_id,
        "season": target["season"],
        "source_capability": "FAILED",
        "passed": False,
        "failure_reason": str(exc)[:300],
        "factory_exception": type(exc).__name__,
    })
    if "duplicate safe event credit identity" in str(exc).casefold():
        blocker = "SAFE production graph staging rejected duplicate event credit identity"
        next_fix = "Deduplicate safe event credit identities before payload validation, then rerun this venue"
    else:
        blocker = str(exc)[:300]
        next_fix = "Inspect the isolated factory exception and rerun this venue"
    result = {
        "venue_id": venue_id,
        "season": target["season"],
        "status": "FAILED",
        "production_writes": 0,
        "blocker": blocker,
        "next_technical_fix": next_fix,
        "summary": summary,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "onboarding_status.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _find_hermes_facts(venue_id: str, season: str, output_root: Path) -> Path | None:
    candidates = [
        Path("artifacts") / f"hermes-{venue_id}-source-facts.json",
        Path("artifacts") / "hermes-source-facts" / f"{venue_id}-{season}.json",
        output_root / venue_id / "hermes_source_facts.json",
    ]
    if venue_id == "staatsoper_unter_den_linden":
        candidates.insert(0, Path("artifacts/hermes-berlin-source-facts.json"))
    candidates.extend(Path("artifacts").glob(f"*/{venue_id}/hermes_source_facts.json"))
    return next((path for path in candidates if path.exists()), None)


def run_factory(*, season: str, scope: str, selected: list[str], output_root: Path, state_path: Path, hermes_source_facts_root: Path | None = None) -> dict:
    targets = load_targets(season=season, scope=scope, selected=selected)
    previous = load_source_state(state_path)
    entries = dict(previous)
    results = []
    for target in targets:
        key = state_key(str(target["venue_id"]), season)
        try:
            facts_path = None
            if hermes_source_facts_root is not None:
                candidate = hermes_source_facts_root / f"{target['venue_id']}-{season}.json"
                if candidate.exists():
                    facts_path = candidate
            facts_path = facts_path or _find_hermes_facts(str(target["venue_id"]), season, output_root)
            result = run_target(
                target,
                output_root,
                scope="full-season",
                previous_source_hash=previous.get(key),
                hermes_source_facts_path=facts_path,
            )
        except Exception as exc:
            result = _isolated_failure_result(target, output_root, exc)
        results.append(result)
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
    parser.add_argument("--hermes-source-facts-root", type=Path)
    args = parser.parse_args()
    selected = [value.strip() for value in args.venue_ids.split(",") if value.strip()]
    batch = run_factory(
        season=args.season,
        scope=args.scope,
        selected=selected,
        output_root=args.output_root,
        state_path=args.state_path,
        hermes_source_facts_root=args.hermes_source_facts_root,
    )
    print(json.dumps(batch, ensure_ascii=False))
    return 0 if batch.get("batch_status") != "FAILED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
