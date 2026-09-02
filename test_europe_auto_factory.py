from __future__ import annotations

import json
from pathlib import Path

from season_ingestion.incremental import (
    SOURCE_STATE_SCHEMA_VERSION,
    compare_source_fingerprint,
    load_source_state,
    save_source_state,
    source_fingerprint,
    state_key,
)
from season_ingestion.schema import CanonicalEvent
from season_ingestion.venue_targets import load_targets
from season_ingestion.factory import build_batch_summary
from jobs.render_europe_wave1_report import build_report
from season_ingestion.adapters.europe_venue import _generic_event_title
from jobs import run_europe_auto_factory


def _event(*, start_time: str = "20:00", artist: str = "Artist") -> CanonicalEvent:
    return CanonicalEvent(
        source="opera_roma",
        source_event_id="work-2027-06-22-2000",
        source_url="https://official.example/work/occurrence",
        organization="Teatro dell'Opera di Roma",
        venue="Teatro Costanzi",
        city="Rome",
        country="Italy",
        timezone="Europe/Rome",
        title="Il trovatore",
        date="2027-06-22",
        start_time=start_time,
        end_time=None,
        room=None,
        event_type="performance",
        programme=[{
            "source_title": "Il trovatore",
            "composer": "Giuseppe Verdi",
            "source_programme_index": 1,
            "original_programme_order": 1,
            "provenance": {"source_url": "https://official.example/work/occurrence", "raw": "not hashed"},
        }],
        credits=[{
            "artist_name": artist,
            "character": "Manrico",
            "function": "performer",
            "credit_kind": "cast",
            "source_field": "official.cast",
            "provenance": {"source_url": "https://official.example/work/occurrence", "raw": "not hashed"},
        }],
    )


def test_source_fingerprint_is_stable_and_tracks_source_facts_only():
    first = source_fingerprint([_event()])
    same = source_fingerprint([_event()])
    changed = source_fingerprint([_event(artist="Different Artist")])
    assert first == same
    assert first != changed
    assert "not hashed" not in first


def test_source_state_is_hash_only_and_round_trips(tmp_path):
    path = tmp_path / "state" / "source-hashes.json"
    key = state_key("opera_roma", "2026-27")
    save_source_state(path, {key: "abc123"})
    assert load_source_state(path) == {key: "abc123"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SOURCE_STATE_SCHEMA_VERSION
    assert set(payload) == {"schema_version", "entries"}


def test_incremental_comparison_processes_first_run_and_noops_unchanged():
    assert compare_source_fingerprint(None, "new") ["action"] == "PROCESS"
    assert compare_source_fingerprint("old", "new")["source_changed"] is True
    assert compare_source_fingerprint("same", "same") == {
        "source_changed": False,
        "previous_source_hash": "same",
        "current_source_hash": "same",
        "action": "NOOP",
    }


def test_full_season_is_the_factory_mode_and_existing_scope_is_not_selected():
    targets = load_targets(season="2026-27", scope="selected", selected=["opera_roma"])
    assert len(targets) == 1
    assert targets[0]["venue_id"] == "opera_roma"
    assert targets[0]["enabled"] is True


def test_factory_workflow_has_schedule_and_safe_upload_only():
    workflow = Path(".github/workflows/europe-auto-ingestion-factory.yml").read_text(encoding="utf-8")
    assert "schedule:" in workflow
    assert "full-season" in workflow
    assert "SUPABASE_SECRET_KEY" not in workflow
    assert "path: onboarding-output/" not in workflow
    assert "cloud-artifacts/**/summary.json" in workflow
    assert "cloud-artifacts/**/pilot_diagnostics.json" in workflow


def test_factory_reuses_berlin_hermes_facts_path(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(run_europe_auto_factory, "load_targets", lambda **kwargs: [{"venue_id": "staatsoper_unter_den_linden", "season": "2026-27", "enabled": True}])
    monkeypatch.setattr(run_europe_auto_factory, "_find_hermes_facts", lambda *args: Path("artifacts/hermes-berlin-source-facts.json"))
    monkeypatch.setattr(run_europe_auto_factory, "_run_venue_child", lambda target, output_root, facts_path, timeout: calls.append(facts_path) or {"venue_id": target["venue_id"], "season": target["season"], "status": "FAILED", "production_writes": 0, "summary": {}})
    run_europe_auto_factory.run_factory(season="2026-27", scope="selected", selected=["staatsoper_unter_den_linden"], output_root=tmp_path / "out", state_path=tmp_path / "state.json")
    assert calls[0] == Path("artifacts/hermes-berlin-source-facts.json")


def test_factory_runner_uses_full_season_and_persists_only_successful_source_hash(tmp_path, monkeypatch):
    calls = []

    def fake_run_child(target, output_root, facts_path, timeout):
        kwargs = {"scope": "full-season", "previous_source_hash": "old-hash"}
        calls.append((target["venue_id"], kwargs))
        return {
            "venue_id": target["venue_id"],
            "season": target["season"],
            "status": "READY_FOR_APPROVAL",
            "production_writes": 0,
            "summary": {
                "source_capability": "SOURCE_PASS",
                "source_fingerprint": "rome-hash",
                "counts": {"review_items": 0},
            },
        }

    monkeypatch.setattr(run_europe_auto_factory, "_run_venue_child", fake_run_child)
    state_path = tmp_path / "state.json"
    save_source_state(state_path, {state_key("opera_roma", "2026-27"): "old-hash"})
    batch = run_europe_auto_factory.run_factory(
        season="2026-27",
        scope="selected",
        selected=["opera_roma"],
        output_root=tmp_path / "output",
        state_path=state_path,
    )
    assert batch["operating_mode"] == "FULL_SEASON"
    assert calls[0][1]["scope"] == "full-season"
    assert calls[0][1]["previous_source_hash"] == "old-hash"
    assert load_source_state(state_path)[state_key("opera_roma", "2026-27")] == "rome-hash"
    assert batch["production_writes"] == 0


def test_factory_isolates_unexpected_venue_exception_and_continues(tmp_path, monkeypatch):
    targets = [
        {"venue_id": "good_venue", "season": "2026-27", "enabled": True},
        {"venue_id": "broken_venue", "season": "2026-27", "enabled": True},
    ]

    def fake_run_child(target, output_root, facts_path, timeout):
        if target["venue_id"] == "broken_venue":
            raise ValueError("duplicate safe event credit identity")
        return {
            "venue_id": target["venue_id"],
            "season": target["season"],
            "status": "READY_FOR_APPROVAL",
            "production_writes": 0,
            "summary": {"source_capability": "SOURCE_PASS", "source_fingerprint": "good-hash", "counts": {"events": 1}},
        }

    monkeypatch.setattr(run_europe_auto_factory, "load_targets", lambda **kwargs: targets)
    monkeypatch.setattr(run_europe_auto_factory, "_run_venue_child", fake_run_child)
    batch = run_europe_auto_factory.run_factory(
        season="2026-27",
        scope="all-enabled",
        selected=[],
        output_root=tmp_path / "output",
        state_path=tmp_path / "state.json",
    )

    assert [venue["venue_id"] for venue in batch["venues"]] == ["good_venue", "broken_venue"]
    assert batch["venues_production_ready"] == 1
    assert batch["venues_blocked"] == 1
    broken = batch["venues"][1]
    assert broken["blocker"] == "SAFE production graph staging rejected duplicate event credit identity"
    assert (tmp_path / "output" / "broken_venue" / "summary.json").exists()


def test_factory_resume_skips_valid_completed_and_checkpoints_each_venue(tmp_path, monkeypatch):
    targets = [
        {"venue_id": "completed", "season": "2026-27", "enabled": True},
        {"venue_id": "pending", "season": "2026-27", "enabled": True},
    ]
    resume_root = tmp_path / "resume"
    completed_dir = resume_root / "completed"
    completed_dir.mkdir(parents=True)
    (completed_dir / "normalized.json").write_text(json.dumps([{"source_url": "https://official.example/event/1", "title": "A real event", "date": "2026-10-01", "start_time": "20:00", "programme": []}]), encoding="utf-8")
    (completed_dir / "summary.json").write_text(json.dumps({"source_capability": "SOURCE_PASS", "counts": {"events": 1}, "months": {"successful": 1}, "duplicate_performance_slot": 0}), encoding="utf-8")
    for name in ("source_audit", "raw", "snapshot", "resolution_staging", "final_staging"):
        (completed_dir / f"{name}.json").write_text("{}", encoding="utf-8")
    (completed_dir / "onboarding_status.json").write_text(json.dumps({"venue_id": "completed", "status": "REVIEW_REQUIRED", "production_writes": 0, "summary": {"source_capability": "SOURCE_PASS", "counts": {"events": 1}}}), encoding="utf-8")
    calls = []
    monkeypatch.setattr(run_europe_auto_factory, "load_targets", lambda **kwargs: targets)
    monkeypatch.setattr(run_europe_auto_factory, "_run_venue_child", lambda target, output_root, facts_path, timeout: calls.append(target["venue_id"]) or {"venue_id": target["venue_id"], "season": target["season"], "status": "FAILED", "production_writes": 0, "summary": {"source_capability": "FAILED", "counts": {"events": 0}}})
    batch = run_europe_auto_factory.run_factory(season="2026-27", scope="selected", selected=["completed", "pending"], output_root=tmp_path / "output", state_path=tmp_path / "state.json", resume_root=resume_root)
    assert calls == ["pending"]
    assert batch["venues_reused"] == 1
    assert json.loads((tmp_path / "output" / "factory_progress.json").read_text(encoding="utf-8"))["completed_venues"] == ["completed", "pending"]
    assert not (tmp_path / "output" / "factory_summary.partial.json").exists()
    assert (tmp_path / "output" / "europe-wave1-report.json").exists()


def test_review_result_is_reused_only_when_occurrence_quality_passes(tmp_path):
    source_dir = tmp_path / "resume" / "venue"
    source_dir.mkdir(parents=True)
    event = {"source_url": "https://official.example/category", "title": "What's on – Classical music | Venue", "date": "2026-10-01", "start_time": "20:00", "programme": [{"provenance": {"source_field": "jsonld.name"}}]}
    for name, payload in {
        "source_audit": {}, "raw": [], "normalized": [event], "snapshot": {}, "resolution_staging": [], "final_staging": {},
        "summary": {"source_capability": "SOURCE_PASS", "counts": {"events": 1}, "months": {"successful": 1}, "duplicate_performance_slot": 0},
    }.items():
        (source_dir / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    status = {"venue_id": "venue", "status": "REVIEW_REQUIRED", "production_writes": 0}
    (source_dir / "onboarding_status.json").write_text(json.dumps(status), encoding="utf-8")
    assert run_europe_auto_factory._reusable_result(tmp_path / "resume", "venue", tmp_path / "out") is None


def test_generic_page_title_is_rejected_as_event():
    assert _generic_event_title("What's on – Classical music | Barbican") is True
    assert _generic_event_title("Season 2026-27") is True
    assert _generic_event_title("La Traviata") is False


def test_factory_and_report_classifications_are_mutually_exclusive():
    results = [{"venue_id": "ready", "status": "READY_FOR_APPROVAL", "summary": {"source_capability": "SOURCE_PASS", "counts": {"events": 1}}}, {"venue_id": "review", "status": "SOURCE_PARTIAL", "summary": {"source_capability": "SOURCE_PARTIAL", "counts": {"events": 2}}}, {"venue_id": "blocked", "status": "FAILED", "summary": {"source_capability": "FAILED", "counts": {"events": 0}}}]
    batch = build_batch_summary(results, season="2026-27", batch_run_id="test", git_commit="test")
    report = build_report({"venues": results})
    assert (batch["venues_production_ready"], batch["venues_review_required"], batch["venues_blocked"]) == (report["VENUES_PRODUCTION_READY"], report["VENUES_REVIEW_REQUIRED"], report["VENUES_BLOCKED"])
    assert sum((report["VENUES_PRODUCTION_READY"], report["VENUES_REVIEW_REQUIRED"], report["VENUES_BLOCKED"])) == report["VENUES_ATTEMPTED"]
    assert batch["production_writes"] == 0
