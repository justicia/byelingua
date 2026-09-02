"""Run the enabled venue-season queue in full-season, read-only mode.

The workflow owns the ephemeral output directory.  This entrypoint writes a
small source-hash state file for the next scheduled run, while all raw source,
Global Master, and staging files remain outside the upload path.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.factory import build_batch_summary, run_target
from season_ingestion.incremental import load_source_state, save_source_state, state_key
from season_ingestion.venue_targets import load_targets
from jobs.hermes_acquire_worker import WorkerError, timeout_config_from_env


def _atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        import signal
        os.killpg(process.pid, signal.SIGTERM)


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


_GENERIC_EVENT_MARKERS = ("season 20", "what's on", "classical music", "programme", "calendar", "events")
_DERIVED_PROGRAMME_FIELDS = {"jsonld.name", "event.name", "og:title", "html.title", "page.heading", "listing-card.title", "event.title"}


def _quality_reuse_reasons(source_dir: Path, status: dict) -> list[str]:
    """Return concrete reasons a prior result is not safe to reuse."""
    if status.get("production_writes", 0) != 0:
        return ["production_writes is non-zero"]
    summary = json.loads((source_dir / "summary.json").read_text(encoding="utf-8"))
    events = json.loads((source_dir / "normalized.json").read_text(encoding="utf-8"))
    if not isinstance(events, list) or not events:
        return ["events are empty"]
    reasons: list[str] = []
    if summary.get("passed") is not True:
        reasons.append("summary did not pass all validation gates")
    gates = summary.get("gates") or {}
    if any(value is not True for value in gates.values()):
        reasons.append("summary contains a failed validation gate")
    completeness = summary.get("artifact_completeness") or {}
    if completeness and completeness.get("all_required_present_and_valid") is not True:
        reasons.append("artifact completeness check failed")
    status_summary = status.get("summary") or {}
    if status_summary and status_summary.get("source_capability") != summary.get("source_capability"):
        reasons.append("onboarding status and summary disagree")
    urls = {str(event.get("source_url") or "") for event in events}
    if any(not url for url in urls):
        reasons.append("an event has no traceable source URL")
    if len(events) > 1 and len(urls) == 1:
        reasons.append("multiple events reuse one category URL")
    if any(not event.get("title") or any(marker in str(event.get("title")).casefold() for marker in _GENERIC_EVENT_MARKERS) for event in events):
        reasons.append("generic page title was staged as an event")
    if any(not event.get("date") for event in events):
        reasons.append("an event has no explicit date")
    missing_time = sum(not event.get("start_time") for event in events)
    if missing_time / len(events) > 0.2:
        reasons.append("missing start-time rate exceeds 20 percent")
    if summary.get("duplicate_performance_slot", 0):
        reasons.append("duplicate performance slots are present")
    for event in events:
        for item in event.get("programme") or []:
            field = str((item.get("provenance") or {}).get("source_field") or "").casefold()
            if field in _DERIVED_PROGRAMME_FIELDS or field.endswith(".name"):
                reasons.append("Programme was derived from a title field")
                break
        if reasons and reasons[-1] == "Programme was derived from a title field":
            break
    if not summary.get("months", {}).get("successful") and summary.get("source_capability") != "SOURCE_PASS":
        reasons.append("declared season coverage is not credible")
    return list(dict.fromkeys(reasons))


def _reusable_result(resume_root: Path | None, venue_id: str, output_root: Path) -> dict | None:
    if resume_root is None:
        return None
    source_dir = resume_root / venue_id
    required = ("source_audit", "raw", "normalized", "snapshot", "resolution_staging", "final_staging", "summary", "onboarding_status")
    try:
        status = json.loads((source_dir / "onboarding_status.json").read_text(encoding="utf-8"))
        if status.get("status") not in {"READY_FOR_APPROVAL", "REVIEW_REQUIRED"}:
            return None
        for name in required:
            json.loads((source_dir / f"{name}.json").read_text(encoding="utf-8"))
        if _quality_reuse_reasons(source_dir, status):
            return None
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return None
    destination = output_root / venue_id
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source_dir, destination)
    status["reused"] = True
    _atomic_json_write(destination / "onboarding_status.json", status)
    return status


def _venue_timeout_seconds() -> int:
    try:
        config = timeout_config_from_env()
    except WorkerError as exc:
        raise RuntimeError(str(exc)) from exc
    configured = os.getenv("BYELINGUA_FACTORY_VENUE_TIMEOUT_SECONDS")
    try:
        value = int(configured) if configured else config["total"] + config["margin"] + 60
    except ValueError as exc:
        raise RuntimeError("factory venue timeout must be an integer") from exc
    minimum = config["total"] + config["margin"]
    if value <= minimum:
        raise RuntimeError("factory venue timeout must exceed Hermes total timeout plus process margin")
    return value


def _run_venue_child(target: dict, output_root: Path, facts_path: Path | None, timeout_seconds: int) -> dict:
    command = [sys.executable, str(Path(__file__).with_name("run_venue_onboarding_target.py")), "--venue-id", str(target["venue_id"]), "--season", str(target["season"]), "--output-root", str(output_root)]
    if facts_path is not None:
        command.extend(["--hermes-source-facts", str(facts_path)])
    started = time.monotonic()
    print(f"venue_start={target['venue_id']}", file=sys.stderr, flush=True)
    process = subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", start_new_session=os.name != "nt", creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        _, child_stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        process.communicate()
        result = _isolated_failure_result(target, output_root, RuntimeError("HERMES_ACQUISITION_TIMEOUT"))
        result["blocker"] = "HERMES_ACQUISITION_TIMEOUT"
        result["next_technical_fix"] = "Inspect the official source or Hermes browser acquisition and rerun this venue with a bounded timeout"
    else:
        try:
            result = json.loads((output_root / str(target["venue_id"]) / "onboarding_status.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            result = _isolated_failure_result(target, output_root, RuntimeError("venue child did not write onboarding_status.json"))
        if child_stderr.strip():
            print(f"venue_child_diagnostics={target['venue_id']}", file=sys.stderr, flush=True)
    summary = result.get("summary") or {}
    print(" ".join((f"venue_end={target['venue_id']}", f"elapsed_seconds={time.monotonic() - started:.1f}", f"deterministic_events={(summary.get('source_audit') or {}).get('events', 0)}", f"hermes_attempted={(summary.get('hermes_fallback') or {}).get('attempted', False)}", f"hermes_reused={(summary.get('hermes_fallback') or {}).get('acquisition_mode') == 'validated_source_facts_artifact'}", f"status={result.get('status')}", f"blocker={result.get('blocker') or ''}")), file=sys.stderr, flush=True)
    return result


def run_factory(*, season: str, scope: str, selected: list[str], output_root: Path, state_path: Path, hermes_source_facts_root: Path | None = None, resume_root: Path | None = None) -> dict:
    targets = load_targets(season=season, scope=scope, selected=selected)
    if scope == "selected" and len(targets) != len(selected):
        raise RuntimeError(f"selected venue count mismatch: expected {len(selected)}, loaded {len(targets)}")
    venue_timeout = _venue_timeout_seconds()
    previous = load_source_state(state_path)
    entries = dict(previous)
    results: list[dict] = []
    expected = [str(target["venue_id"]) for target in targets]

    def checkpoint(current: str | None) -> None:
        completed = [item["venue_id"] for item in results]
        failed = [item["venue_id"] for item in results if item.get("status") != "READY_FOR_APPROVAL"]
        progress = {"season": season, "expected_venues": expected, "completed_venues": completed, "failed_venues": failed, "pending_venues": [venue for venue in expected if venue not in completed], "current_venue": current, "updated_at": time.time(), "production_writes": 0}
        partial = build_batch_summary(results, season=season, batch_run_id=os.getenv("GITHUB_RUN_ID", "local"), git_commit=os.getenv("GITHUB_SHA", "unknown"))
        partial.update({"checkpoint_complete": len(completed) == len(expected), "production_writes": 0})
        _atomic_json_write(output_root / "factory_progress.json", progress)
        _atomic_json_write(output_root / "factory_summary.partial.json", partial)
        save_source_state(state_path, entries)

    for target in targets:
        venue_id = str(target["venue_id"])
        checkpoint(venue_id)
        reused = _reusable_result(resume_root, venue_id, output_root)
        if reused is not None:
            print(f"venue_end={venue_id} elapsed_seconds=0 deterministic_events={(reused.get('summary') or {}).get('counts', {}).get('events', 0)} hermes_attempted=False hermes_reused=True status={reused.get('status')} blocker=", file=sys.stderr, flush=True)
            results.append(reused)
            summary = reused.get("summary") or {}
            if summary.get("source_capability") == "SOURCE_PASS" and summary.get("source_fingerprint"):
                entries[state_key(venue_id, season)] = summary["source_fingerprint"]
            checkpoint(None)
            continue
        facts_path = None
        if hermes_source_facts_root is not None:
            candidate = hermes_source_facts_root / f"{venue_id}-{season}.json"
            if candidate.exists():
                facts_path = candidate
        facts_path = facts_path or _find_hermes_facts(venue_id, season, output_root)
        try:
            result = _run_venue_child(target, output_root, facts_path, venue_timeout)
        except Exception as exc:
            result = _isolated_failure_result(target, output_root, exc)
        results.append(result)
        summary = result.get("summary") or {}
        if summary.get("source_capability") == "SOURCE_PASS" and summary.get("source_fingerprint"):
            entries[state_key(venue_id, season)] = summary["source_fingerprint"]
        checkpoint(None)
    batch = build_batch_summary(results, season=season, batch_run_id=os.getenv("GITHUB_RUN_ID", "local"), git_commit=os.getenv("GITHUB_SHA", "unknown"))
    hermes = [(item.get("summary") or {}).get("hermes_fallback", {}) for item in results]
    hermes_attempted = sum(bool(item.get("attempted")) for item in hermes)
    hermes_reused = sum(item.get("acquisition_mode") == "validated_source_facts_artifact" for item in hermes)
    hermes_new = sum(item.get("status") == "PASS" and item.get("acquisition_mode") == "worker_subprocess" for item in hermes)
    hermes_failed = sum(bool(item.get("attempted")) and item.get("status") not in {"PASS", "NOT_ATTEMPTED"} and item.get("acquisition_mode") != "validated_source_facts_artifact" for item in hermes)
    hermes_timed_out = sum("timeout" in str(item.get("error", "")).casefold() for item in hermes)
    batch.update({"operating_mode": "FULL_SEASON", "existing_production_closeout": "DIAGNOSTIC_ONLY", "production_writes": 0, "venues_reused": sum(bool(item.get("reused")) for item in results), "venues_newly_attempted": sum(not bool(item.get("reused")) for item in results), "hermes_attempted": hermes_attempted, "hermes_new_facts_succeeded": hermes_new, "hermes_reused": hermes_reused, "hermes_failed": hermes_failed, "hermes_timed_out": hermes_timed_out})
    _atomic_json_write(output_root / "factory_summary.json", batch)
    from jobs.render_europe_wave1_report import build_report
    _atomic_json_write(output_root / "europe-wave1-report.json", build_report(batch))
    progress = json.loads((output_root / "factory_progress.json").read_text(encoding="utf-8"))
    progress["current_venue"] = None
    progress["updated_at"] = time.time()
    progress["production_writes"] = 0
    _atomic_json_write(output_root / "factory_progress.json", progress)
    partial = output_root / "factory_summary.partial.json"
    if partial.exists():
        partial.unlink()
    return batch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", required=True)
    parser.add_argument("--scope", default="all-enabled", choices=("all-enabled", "pending", "selected"))
    parser.add_argument("--venue-ids", default="")
    parser.add_argument("--output-root", type=Path, default=Path("onboarding-output"))
    parser.add_argument("--state-path", type=Path, default=Path(".factory-state/source-hashes.json"))
    parser.add_argument("--hermes-source-facts-root", type=Path)
    parser.add_argument("--resume-root", type=Path)
    args = parser.parse_args()
    selected = [value.strip() for value in args.venue_ids.split(",") if value.strip()]
    batch = run_factory(
        season=args.season,
        scope=args.scope,
        selected=selected,
        output_root=args.output_root,
        state_path=args.state_path,
        hermes_source_facts_root=args.hermes_source_facts_root,
        resume_root=args.resume_root,
    )
    print(json.dumps(batch, ensure_ascii=False))
    return 0 if batch.get("batch_status") != "FAILED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
