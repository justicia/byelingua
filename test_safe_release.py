from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from season_ingestion.safe_release import (
    SafeReleaseMaterializationError,
    SafeReleaseVerifierCredentialBlocked,
    materialize_release,
    materialize_venue,
    verify_production_release,
    verify_local_apply_compatibility,
)


VENUE = "theater_an_der_wien"
SEASON = "2026-27"


def _sample_event(index: int) -> dict:
    return {
        "event_key": f"sample-event-{index}",
        "source": VENUE,
        "source_event_id": f"source-{index}",
        "source_url": f"https://official.example/events/{index}",
        "title": f"Official Event {index}",
        "raw": {"source_title": f"Official Event {index}"},
        "date": "2026-10-01",
        "start_time": "19:30:00",
        "organization": "MusikTheater an der Wien",
        "venue": "Theater an der Wien",
        "city": "Vienna",
        "country": "Austria",
        "timezone": "Europe/Vienna",
        "room": None,
        "end_time": None,
        "event_type": "opera",
        "programme": [],
        "credits": [],
        "classification": {},
        "data_quality": {},
    }


def _write_input(tmp_path: Path, *, count: int = 1, venue: str = VENUE, season: str = SEASON, bad_safe_credit: bool = False) -> tuple[Path, dict]:
    directory = tmp_path / "deterministic"
    directory.mkdir()
    events = [_sample_event(index) for index in range(count)]
    for event in events:
        event["source"] = venue
    credit = {
        "safe_existing_artists": [],
        "safe_new_artists": [],
        "safe_cast_assignments": [],
        "safe_artistic_team": [],
        "safe_ensembles": [],
        "review_artist_conflicts": [],
        "review_character_conflicts": [],
        "review_unknown_roles": [],
        "review_source_ambiguous": [],
        "safe_event_credits": [],
        "review_event_credits": [],
        "counts": {"credits_raw": 0, "credits_safe": 0, "credits_review": 0},
    }
    if bad_safe_credit:
        credit["safe_event_credits"] = [{
            "event_key": events[0]["event_key"],
            "credit": {
                "canonical_role": None,
                "artist_resolution": {"status": "REVIEW_ROLE_UNKNOWN"},
                "character_resolution": {"character_id": None, "character": None},
            },
        }]
    final = {"events": events, "resolution": [], "review": [], "credit_resolution": credit, "artists": [], "event_credits": [], "writes": 0}
    summary = {
        "venue": venue,
        "season": season,
        "source_capability": "SOURCE_PASS",
        "global_master_preflight": "PASS",
        "scope": "full-season",
        "source_fingerprint": "fingerprint-sample",
        "counts": {"events": count, "events_discovered": count, "writes": 0, "review_items": 0},
        "detail_enrichment": {"programme_items": 0, "credits_total": 0},
        "gates": {"events_gt_zero": True, "duplicate_event_identity": True, "untraceable": True, "source_order_missing": True, "production_writes": True},
    }
    profile = {"venue_id": venue, "season": season, "occurrence_source": {"url": "https://official.example/calendar"}}
    source_audit = {"coverage_complete": True}
    snapshot = {"entities": {"composer": [], "work": []}}
    for name, payload in {
        "final_staging.json": final,
        "summary.json": summary,
        "source_capability_profile.json": profile,
        "source_audit.json": source_audit,
        "snapshot.json": snapshot,
        "credit_resolution_staging.json": credit,
    }.items():
        (directory / name).write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    approved = {"venue": venue, "season": season, "release_status": "SAFE_RELEASE_CANDIDATE", "events_release_safe": count, "events_release_review": 0, "events_rejected": 0}
    return directory, approved


def test_materialization_exact_event_count_and_event_only_release(tmp_path: Path):
    input_dir, approved = _write_input(tmp_path, count=3)
    report = materialize_venue(input_dir=input_dir, output_root=tmp_path / "release", venue_id=VENUE, season=SEASON, expected_event_count=3, approved_report=approved, approved_run_id="test-release", commit="test", created_at="2026-09-15T00:00:00+00:00")
    assert report["materialized_event_count"] == 3
    assert report["safe_programme_relationships"] == 0
    assert report["safe_credits"] == 0
    assert report["review_rows_included"] == 0
    assert report["production_graph_validation"] == "PASS"


def test_palau_review_credits_are_excluded_from_materialized_graph(tmp_path: Path):
    report_path = Path("artifacts/generic-v1-release-readiness-20260915/report.json")
    reports = materialize_release(release_report_path=report_path, output_root=tmp_path / "release", approved_run_id="test-release", commit="test")
    palau = next(item for item in reports if item["venue_id"] == "palau_de_la_musica_catalana")
    graph = json.loads((tmp_path / "release" / "palau_de_la_musica_catalana" / "production_graph_staging.json").read_text(encoding="utf-8"))
    assert palau["materialized_event_count"] == 434
    assert palau["safe_credits"] == 0
    assert palau["input_review_rows_excluded"] == 407
    assert graph["event_credits"] == []


def test_hashes_and_manifest_graph_consistency_are_deterministic(tmp_path: Path):
    input_dir, approved = _write_input(tmp_path, count=1)
    first = materialize_venue(input_dir=input_dir, output_root=tmp_path / "one", venue_id=VENUE, season=SEASON, expected_event_count=1, approved_report=approved, approved_run_id="test-release", commit="test", created_at="2026-09-15T00:00:00+00:00")
    second = materialize_venue(input_dir=input_dir, output_root=tmp_path / "two", venue_id=VENUE, season=SEASON, expected_event_count=1, approved_report=approved, approved_run_id="test-release", commit="test", created_at="2026-09-15T00:00:00+00:00")
    assert first["input_artifact_sha256"] == second["input_artifact_sha256"]
    assert first["production_graph_staging_sha256"] == second["production_graph_staging_sha256"]
    assert first["approval_manifest_sha256"] == second["approval_manifest_sha256"]
    release_dir = tmp_path / "one" / VENUE
    manifest = json.loads((release_dir / "approval_manifest.json").read_text(encoding="utf-8"))
    assert manifest["final_staging_hash"] == first["final_staging_sha256"]
    assert first["approval_manifest_sha256"] == second["approval_manifest_sha256"]


def test_wrong_venue_season_and_count_are_rejected(tmp_path: Path):
    input_dir, approved = _write_input(tmp_path, count=2)
    with pytest.raises(SafeReleaseMaterializationError, match="venue"):
        materialize_venue(input_dir=input_dir, output_root=tmp_path / "venue", venue_id=VENUE, season=SEASON, expected_event_count=2, approved_report={**approved, "venue": "wrong"})
    with pytest.raises(SafeReleaseMaterializationError, match="season"):
        materialize_venue(input_dir=input_dir, output_root=tmp_path / "season", venue_id=VENUE, season=SEASON, expected_event_count=2, approved_report={**approved, "season": "2027-28"})
    with pytest.raises(SafeReleaseMaterializationError, match="count"):
        materialize_venue(input_dir=input_dir, output_root=tmp_path / "count", venue_id=VENUE, season=SEASON, expected_event_count=3, approved_report={**approved, "events_release_safe": 3})


def test_review_row_cannot_enter_safe_graph(tmp_path: Path):
    input_dir, approved = _write_input(tmp_path, bad_safe_credit=True)
    with pytest.raises(SafeReleaseMaterializationError, match="unsafe credit"):
        materialize_venue(input_dir=input_dir, output_root=tmp_path / "review", venue_id=VENUE, season=SEASON, expected_event_count=1, approved_report=approved)


def test_existing_apply_runner_compatibility_is_verified_without_apply(tmp_path: Path):
    input_dir, approved = _write_input(tmp_path)
    materialize_venue(input_dir=input_dir, output_root=tmp_path / "release", venue_id=VENUE, season=SEASON, expected_event_count=1, approved_report=approved, approved_run_id="test-release")
    result = verify_local_apply_compatibility(tmp_path / "release" / VENUE, venue_id=VENUE, season=SEASON, approved_run_id="test-release")
    assert result["compatible"] is True
    assert result["runtime_scope"]["events"] == 1


def test_verifier_has_no_production_writer_dependency():
    verifier = Path("jobs/verify_safe_release.py").read_text(encoding="utf-8")
    module = Path("season_ingestion/safe_release.py").read_text(encoding="utf-8")
    assert "apply_graph" not in verifier
    assert "apply_events" not in module
    assert "apply_canonical_production_graph" not in module
    assert "SUPABASE_SECRET_KEY" in module


class _ReadResponse:
    def __init__(self, payload: list[dict]):
        self.status = 200
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._payload


def test_verifier_resolves_release_slug_through_production_graph_identity(tmp_path: Path, monkeypatch):
    graph = {
        "source": "release-venue-slug",
        "organization": {"name": "Production Organization", "slug": "production-org-slug"},
        "venue": {"name": "Production Venue", "city": "Paris", "country_code": "France"},
        "events": [
            {"source_event_id": "release-event-1"},
            {"source_event_id": "release-event-2"},
        ],
    }
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    (release_dir / "production_graph_staging.json").write_text(json.dumps(graph), encoding="utf-8")
    requests: list[tuple[str, str, dict[str, list[str]]]] = []

    def fake_fetch(request, timeout=60):
        assert timeout == 60
        method = request.get_method()
        parsed = urlsplit(request.full_url)
        params = parse_qs(parsed.query)
        requests.append((method, parsed.path, params))
        assert method == "GET"
        if parsed.path == "/rest/v1/organizations":
            assert params["slug"] == ["eq.production-org-slug"]
            return _ReadResponse([{"id": "org-1", "name": "Production Organization", "slug": "production-org-slug"}])
        if parsed.path == "/rest/v1/venues":
            assert params["organization_id"] == ["eq.org-1"]
            assert params["name"] == ["eq.Production Venue"]
            return _ReadResponse([{"id": "venue-1", "name": "Production Venue", "city": "Paris", "organization_id": "org-1"}])
        if parsed.path == "/rest/v1/events":
            assert params["organization_id"] == ["eq.org-1"]
            assert params["venue_id"] == ["eq.venue-1"]
            assert set(params["date"]) == {"gte.2026-09-01", "lte.2027-08-31"}
            return _ReadResponse([
                {"id": "event-1", "event_key": "event-key-1", "title": "Event 1", "date": "2026-10-01"},
                {"id": "event-2", "event_key": "event-key-2", "title": "Event 2", "date": "2027-02-01"},
            ])
        if parsed.path == "/rest/v1/event_sources":
            assert "source" not in params
            return _ReadResponse([
                {"event_id": "event-1", "source": "actual-production-source", "source_event_id": "release-event-1", "source_url": "https://official.example/1"},
                {"event_id": "event-2", "source": "actual-production-source", "source_event_id": "release-event-2", "source_url": "https://official.example/2"},
            ])
        if parsed.path in {"/rest/v1/event_programme", "/rest/v1/event_credits"}:
            return _ReadResponse([])
        raise AssertionError(parsed.path)

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret-test-key")
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly-test-key")
    result = verify_production_release(
        release_dir=release_dir,
        venue_id="release-venue-slug",
        season=SEASON,
        fetcher=fake_fetch,
    )

    assert result["production_identity"] == {"organization_id": "org-1", "venue_id": "venue-1"}
    assert result["credential_used"] == "SUPABASE_SECRET_KEY"
    assert result["credential_value_printed"] == "NO"
    assert result["verifier_read_only"] == "YES"
    assert result["verifier_status"] == "PASS"
    assert result["production_events"] == 2
    assert result["event_sources"] == 2
    assert result["programme_relationships"] == 0
    assert result["safe_credits"] == 0
    assert result["production_writes"] == 0
    assert all(method == "GET" for method, _path, _params in requests)


def test_readonly_identity_visibility_is_classified_as_credential_blocked(tmp_path: Path, monkeypatch):
    graph = {
        "source": "release-venue-slug",
        "organization": {"name": "Production Organization", "slug": "production-org-slug"},
        "venue": {"name": "Production Venue", "city": "Paris", "country_code": "France"},
        "events": [{"source_event_id": "release-event-1"}],
    }
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    (release_dir / "production_graph_staging.json").write_text(json.dumps(graph), encoding="utf-8")

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly-test-key")

    def fake_fetch(_request, timeout=60):
        assert timeout == 60
        return _ReadResponse([])

    with pytest.raises(SafeReleaseVerifierCredentialBlocked) as caught:
        verify_production_release(
            release_dir=release_dir,
            venue_id="release-venue-slug",
            season=SEASON,
            fetcher=fake_fetch,
        )
    assert caught.value.credential_used == "SUPABASE_READONLY_KEY"
