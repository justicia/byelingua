from __future__ import annotations

import json
from pathlib import Path

from jobs.prepare_cloud_artifacts import _safe_pilot_diagnostics, _safe_summary
from jobs.probe_official_source import _candidate_links
from jobs.aggregate_cloud_summaries import build_safe_batch


def test_cloud_summary_is_aggregate_only(tmp_path, monkeypatch):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({"entities": [{"artist_name": "must not appear"}]}), encoding="utf-8")
    summary = {
        "venue": "teatro_real",
        "season": "2026-27",
        "source_capability": "SOURCE_PASS",
        "snapshot_loaded": True,
        "snapshot_health": {"global_master_loaded": True},
        "counts": {"events": 2, "events_discovered": 2, "credits_safe": 3, "credits_review": 1, "review_items": 1},
        "detail_enrichment": {"programme_items": 2, "credits_total": 4},
        "request_counts": {"listing_requested": 1, "listing_succeeded": 1, "detail_requested": 1, "detail_succeeded": 1},
        "invariants": {"duplicate_event_identity": True, "production_writes": True},
        "pilot_diagnostics": [{"work_id": "w1", "artist_name": "must not appear", "work_title": "Example"}],
    }
    monkeypatch.setenv("GITHUB_SHA", "test-sha")
    output = _safe_summary(summary, tmp_path)
    serialized = json.dumps(output, ensure_ascii=False)
    assert output["git_sha"] == "test-sha"
    assert output["production_writes"] == 0
    assert "artist_name" not in serialized
    assert "must not appear" not in serialized
    assert "entities" not in serialized


def test_pilot_diagnostics_has_an_explicit_allow_list():
    output = _safe_pilot_diagnostics({
        "venue": "teatro_real",
        "season": "2026-27",
        "pilot_diagnostics": [{
            "work_id": "w1",
            "work_title": "Example",
            "composer_canonical_name": "Composer",
            "selected_work_qid": "Q1",
            "artist_name": "must not appear",
            "raw_supabase_row": {"secret": "must not appear"},
        }],
    })
    row = output["rows"][0]
    assert row == {"work_id": "w1", "work_title": "Example", "composer_canonical_name": "Composer", "selected_work_qid": "Q1"}
    assert "artist_name" not in json.dumps(output)
    assert "raw_supabase_row" not in json.dumps(output)


def test_cloud_workflows_have_no_manual_staging_or_write_credentials():
    root = Path(__file__).resolve().parent
    for filename in (
        "cloud-season-ingestion.yml",
        "season-ingestion.yml",
        "venue-onboarding-factory.yml",
        "prepare-season-batch.yml",
    ):
        workflow = (root / ".github" / "workflows" / filename).read_text(encoding="utf-8")
        assert "staging_file" not in workflow
        assert "SUPABASE_SECRET_KEY" not in workflow
        assert "--staging-file" not in workflow
        assert "path: season-ingestion-output/" not in workflow
        assert "cloud-artifacts" in workflow


def test_source_probe_uses_registry_patterns_without_venue_data():
    html = """
    <a href='/en/season/2026-2027/work-a'>Work A</a>
    <a data-href='/en/season/2026-2027/work-b'>Work B</a>
    <a href='https://external.example/work-c'>External</a>
    """
    links = _candidate_links(
        html,
        base_url="https://official.example/calendar",
        config={"detail_path_prefixes": ["/en/season/2026-2027/"]},
    )
    assert links == [
        "https://official.example/en/season/2026-2027/work-a",
        "https://official.example/en/season/2026-2027/work-b",
    ]


def test_batch_aggregate_keeps_only_safe_summaries_and_eight_diagnostics(tmp_path):
    venue = tmp_path / "work-character-catalog-summary-teatro-real"
    venue.mkdir()
    (venue / "summary.json").write_text(json.dumps({
        "schema_version": "cloud-season-ingestion-safe-summary-v1",
        "venue": "teatro_real", "season": "2026-27", "source_capability": "SOURCE_PASS",
        "snapshot_loaded": True, "counts": {"events": 1, "review_items": 0},
        "request_counts": {"detail_succeeded": 1}, "invariants": {"production_writes": True},
    }), encoding="utf-8")
    (venue / "pilot_diagnostics.json").write_text(json.dumps({
        "rows": [{"work_id": str(index), "artist_name": "must not appear"} for index in range(10)]
    }), encoding="utf-8")
    summary, diagnostics = build_safe_batch(tmp_path)
    assert summary["production_writes"] == 0
    assert summary["targets"] == 1
    assert len(diagnostics["rows"]) == 8
    assert "artist_name" not in json.dumps(diagnostics)
