import json
import sys

import jobs.sync_season as sync_season
from season_ingestion.adapters.wiener_staatsoper import parse_calendar
from test_wiener_staatsoper_adapter import HTML, SETTINGS


def test_dry_run_never_calls_supabase_or_deletes(monkeypatch, tmp_path):
    events = parse_calendar(HTML, "https://example/calendar", SETTINGS)
    monkeypatch.setattr(sync_season.WienerStaatsoperAdapter, "ingest", lambda self, season: events)
    monkeypatch.setattr(sync_season, "apply_events",
                        lambda rows: (_ for _ in ()).throw(AssertionError("Supabase write attempted")))
    monkeypatch.setattr(sys, "argv", ["sync_season.py", "--venue", "wiener_staatsoper",
                                      "--season", "2026-27", "--mode", "dry-run",
                                      "--output-dir", str(tmp_path)])
    sync_season.main()
    report = json.loads((tmp_path / "wiener_staatsoper-2026-27-report.json").read_text())
    assert report["applied_events"] == 0
    assert report["deleted_events"] == 0
