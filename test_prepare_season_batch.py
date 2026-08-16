import json

import jobs.prepare_season_batch as batch
from season_ingestion.schema import CanonicalEvent


def event(source="teatro_real"):
    return CanonicalEvent(source, "id-1", "https://example.test/event", "Org", "Venue", "City",
                          "Country", "Europe/Madrid", "Title", "2026-10-01", "20:00", None,
                          None, "opera")


def test_missing_contract_has_reports_but_never_staging(tmp_path):
    result = batch.prepare_venue("operadeparis", "2026-27", {"adapter": None}, tmp_path)
    assert result["overall_status"] == "source_contract_missing"
    assert result["write_status"] == "write_not_approved"
    assert not (tmp_path / "operadeparis" / "staging.jsonl").exists()
    assert (tmp_path / "operadeparis" / "report.json").exists()
    assert (tmp_path / "operadeparis" / "status.json").exists()


def test_venue_failure_is_captured_and_does_not_raise(monkeypatch, tmp_path):
    monkeypatch.setattr(batch.TeatroRealAdapter, "ingest", lambda self, season: [])
    result = batch.prepare_venue("teatro_real", "2026-27", {
        "adapter": "teatro_real", "season_bounds": {"2026-27": {
            "season_start": "2026-09-01", "season_end": "2027-08-31"}},
    }, tmp_path)
    assert result["overall_status"] == "not_ready"
    assert "no valid events" in result["failure_reason"]


def test_readonly_preflight_produces_canonical_staging(monkeypatch, tmp_path):
    monkeypatch.setattr(batch.TeatroRealAdapter, "ingest", lambda self, season: [event()])
    monkeypatch.setattr(batch, "fetch_existing_sources", lambda *args, **kwargs: [])
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly")
    settings = {"adapter": "teatro_real", "season_bounds": {"2026-27": {
        "season_start": "2026-09-01", "season_end": "2027-08-31"}}}
    result = batch.prepare_venue("teatro_real", "2026-27", settings, tmp_path)
    assert result["discovery_status"] == "discovery_ready"
    assert result["preflight_status"] == "preflight_ready"
    assert result["overall_status"] == "preflight_ready"
    assert json.loads((tmp_path / "teatro_real" / "staging.jsonl").read_text())['event_key']


def test_select_all_preserves_configured_order():
    assert batch._select("all", ["a", "b"]) == ["a", "b"]
