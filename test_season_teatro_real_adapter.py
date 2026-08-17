import json
import sys
from pathlib import Path

import pytest

import jobs.sync_season as sync_season
from ingestion.schema import stable_event_identity
from season_ingestion.adapters.teatro_real import TeatroRealAdapter, parse_calendar


SETTINGS = {
    "organization": "Teatro Real", "venue": "Teatro Real", "city": "Madrid",
    "country": "Spain", "timezone": "Europe/Madrid",
    "calendar_url": "https://www.teatroreal.es/en/calendario",
    "season_bounds": {"2026-27": {"season_start": "2026-09-01", "season_end": "2027-07-31"}},
}

HTML = """
<div class="calendario-mensual-sidebar">
  <div class="item-box" id="box09-2026-23"><div class="contentbox">
    <div class="item-box--premiere__text--title"><span>Ópera</span><h3><a href="/es/espectaculo/manon-lescaut">Manon Lescaut</a></h3></div>
    <div class="item-box--premiere__text--btn"><a>19:30</a></div>
  </div></div>
</div>
"""


def test_teatro_real_remains_disabled_and_workflow_uses_safe_modes():
    root = Path(__file__).parent
    config = json.loads((root / "config/venues.json").read_text())
    workflow = (root / ".github/workflows/season-ingestion.yml").read_text()

    assert config["venues"]["teatro_real"]["enabled"] is False

    assert "default: dry-run" in workflow
    assert "- dry-run" in workflow
    assert "- write" in workflow

    assert "INGEST_VENUE: ${{ inputs.venue }}" in workflow
    assert "INGEST_SEASON: ${{ inputs.season }}" in workflow
    assert '--venue "$INGEST_VENUE"' in workflow
    assert '--season "$INGEST_SEASON"' in workflow

    assert "Upload dry-run artifact" in workflow
    assert "path: season-ingestion-output/" in workflow

    assert "inputs.mode == 'write'" in workflow
    assert "--mode apply" in workflow
    assert "SUPABASE_SECRET_KEY: ${{ secrets.SUPABASE_SECRET_KEY }}" in workflow

def test_calendar_uses_existing_source_event_id_algorithm():
    event = parse_calendar(
        HTML, SETTINGS["calendar_url"], SETTINGS,
        season_start="2026-09-01", season_end="2027-07-31",
    )[0]
    expected = stable_event_identity({
        "source": "teatro_real", "source_url": event.source_url,
        "organization": "Teatro Real", "venue": "Teatro Real", "room": None,
        "date": "2026-09-23", "start_time": "19:30",
    })
    assert event.source_event_id == expected
    assert event.date == "2026-09-23" and event.event_type == "opera"
    assert event.programme[0]["normalization_status"] == "review_required"


def test_adapter_fetches_the_audited_calendar_once():
    calls = []
    adapter = TeatroRealAdapter(SETTINGS, fetch=lambda url: calls.append(url) or HTML)
    assert len(adapter.ingest("2026-27")) == 1
    assert calls == ["https://www.teatroreal.es/en/calendario"]


def test_teatro_real_apply_is_always_blocked_before_adapter_or_writer(monkeypatch):
    monkeypatch.setattr(sync_season.TeatroRealAdapter, "ingest", lambda *args: pytest.fail("adapter attempted"))
    monkeypatch.setattr(sync_season, "apply_events", lambda *args: pytest.fail("Supabase write attempted"))
    monkeypatch.setattr(sys, "argv", ["sync_season.py", "--venue", "teatro_real", "--mode", "apply"])
    with pytest.raises(SystemExit, match="forbids apply"):
        sync_season.main()


def test_teatro_real_preflight_reads_2026_27_with_readonly_path(monkeypatch, tmp_path):
    events = TeatroRealAdapter(SETTINGS, fetch=lambda _: HTML).ingest("2026-27")
    calls = []
    monkeypatch.setattr(sync_season.TeatroRealAdapter, "ingest", lambda self, season: events)
    monkeypatch.setattr(sync_season, "fetch_existing_sources", lambda *args, **kwargs: calls.append((args, kwargs)) or [])
    monkeypatch.setattr(sync_season, "apply_events", lambda *args: pytest.fail("Supabase write attempted"))
    report_path = tmp_path / "reconciliation-report.json"
    monkeypatch.setattr(sys, "argv", [
        "sync_season.py", "--venue", "teatro_real", "--season", "2026-27",
        "--mode", "preflight", "--report-file", str(report_path),
    ])
    sync_season.main()
    assert calls == [(('teatro_real', '2026-27'), {
        "season_start": "2026-09-01", "season_end": "2027-08-31", "apply_mode": False,
    })]
    assert json.loads(report_path.read_text())["mode"] == "preflight"


def test_teatro_real_rejected_preflight_still_writes_report(monkeypatch, tmp_path):
    report_path = tmp_path / "reconciliation-report.json"
    monkeypatch.setattr(sync_season, "fetch_existing_sources", lambda *args, **kwargs: pytest.fail("read attempted"))
    monkeypatch.setattr(sys, "argv", [
        "sync_season.py", "--venue", "teatro_real", "--season", "2027-28",
        "--mode", "preflight", "--report-file", str(report_path),
    ])
    with pytest.raises(SystemExit, match="limited to 2026-27"):
        sync_season.main()
    report = json.loads(report_path.read_text())
    assert report["collision_guard_blocked"] is True
    assert report["safety_gate_error"]["type"] == "safety_gate_error"


def test_teatro_real_read_failure_still_writes_report(monkeypatch, tmp_path):
    events = TeatroRealAdapter(SETTINGS, fetch=lambda _: HTML).ingest("2026-27")
    monkeypatch.setattr(sync_season.TeatroRealAdapter, "ingest", lambda self, season: events)
    monkeypatch.setattr(sync_season, "fetch_existing_sources", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")))
    report_path = tmp_path / "reconciliation-report.json"
    monkeypatch.setattr(sys, "argv", [
        "sync_season.py", "--venue", "teatro_real", "--season", "2026-27",
        "--mode", "preflight", "--report-file", str(report_path),
    ])
    sync_season.main()
    report = json.loads(report_path.read_text())
    assert report["collision_guard_blocked"] is True
    assert report["preflight_read_error"] == {
        "type": "preflight_read_error", "error_type": "OSError", "message": "offline",
    }


def test_dry_run_writes_staging_without_supabase(monkeypatch, tmp_path):
    events = TeatroRealAdapter(SETTINGS, fetch=lambda _: HTML).ingest("2026-27")
    monkeypatch.setattr(sync_season.TeatroRealAdapter, "ingest", lambda self, season: events)
    monkeypatch.setattr(sync_season, "fetch_existing_sources", lambda *args, **kwargs: pytest.fail("Supabase read attempted"))
    monkeypatch.setattr(sync_season, "apply_events", lambda *args, **kwargs: pytest.fail("Supabase write attempted"))
    monkeypatch.setattr(sys, "argv", [
        "sync_season.py", "--venue", "teatro_real", "--season", "2026-27",
        "--mode", "dry-run", "--output-dir", str(tmp_path),
    ])
    sync_season.main()
    report = json.loads((tmp_path / "teatro_real-2026-27-report.json").read_text())
    assert report["mode"] == "dry-run"
    assert report["database_accessed"] is False
    assert report["reconciliation_executed"] is False
    assert report["applied_events"] == report["deleted_events"] == 0
    assert (tmp_path / "teatro_real-2026-27.jsonl").exists()
