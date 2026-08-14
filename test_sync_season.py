import json
import sys
import pytest

import jobs.sync_season as sync_season
from season_ingestion.adapters.wiener_staatsoper import parse_calendar
from season_ingestion.schema import PATCHABLE_EVENT_FIELDS
from season_ingestion.supabase import PreflightConfigurationError
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
    assert (tmp_path / "wiener_staatsoper-2026-27.jsonl").exists()


def test_apply_guard_blocks_without_existing_identity(monkeypatch):
    events = parse_calendar(HTML, "https://example/calendar", SETTINGS)
    monkeypatch.setattr(sync_season.WienerStaatsoperAdapter, "ingest", lambda self, season: events)
    monkeypatch.setattr(sync_season, "fetch_existing_sources", lambda source, season, **kwargs: [])
    monkeypatch.setattr(sys, "argv", ["sync_season.py", "--venue", "wiener_staatsoper", "--mode", "apply"])
    with pytest.raises(SystemExit, match="apply blocked by reconciliation collision guard"):
        sync_season.main()


@pytest.mark.parametrize("mode", ["preflight", "apply"])
def test_column_permission_error_writes_report_and_blocks_apply(monkeypatch, tmp_path, mode):
    events = parse_calendar(HTML, "https://example/calendar", SETTINGS)
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(sync_season.WienerStaatsoperAdapter, "ingest", lambda self, season: events)

    def denied(*args, **kwargs):
        raise PreflightConfigurationError(list(PATCHABLE_EVENT_FIELDS), "columns denied")

    monkeypatch.setattr(sync_season, "fetch_existing_sources", denied)
    monkeypatch.setattr(sys, "argv", [
        "sync_season.py", "--venue", "wiener_staatsoper", "--mode", mode,
        "--report-file", str(report_path),
    ])
    if mode == "apply":
        with pytest.raises(SystemExit, match="apply blocked"):
            sync_season.main()
    else:
        sync_season.main()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["collision_guard_blocked"] is True
    assert report["preflight_configuration_error"] == {
        "type": "preflight_configuration_error",
        "missing_fields": sorted(PATCHABLE_EVENT_FIELDS),
        "affected_records": len(events),
    }
