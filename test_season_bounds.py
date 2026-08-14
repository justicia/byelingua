import json
import sys
from urllib.parse import parse_qs, urlparse

import pytest

import jobs.sync_season as sync_season
from season_ingestion.season import resolve_season_bounds
from season_ingestion.supabase import fetch_existing_sources


CONFIG = json.loads((sync_season.ROOT / "config/venues.json").read_text(encoding="utf-8"))


class EmptyResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b"[]"


def test_default_and_operadeparis_season_bounds():
    assert resolve_season_bounds("2026-27") == ("2026-09-01", "2027-08-31")
    assert resolve_season_bounds("2026-27", CONFIG["venues"]["operadeparis"]) == (
        "2026-08-28", "2027-08-31"
    )


@pytest.mark.parametrize(
    "venue", ["philharmonie_paris", "teatro_real", "auditorio_nacional"]
)
def test_venues_without_overrides_use_default_bounds(venue):
    assert resolve_season_bounds("2026-27", CONFIG["venues"][venue]) == (
        "2026-09-01", "2027-08-31"
    )


def test_source_name_does_not_create_an_override():
    assert resolve_season_bounds("2026-27", {"source": "operadeparis"}) == (
        "2026-09-01", "2027-08-31"
    )


@pytest.mark.parametrize(
    "season, config",
    [
        ("2026/27", None),
        ("2026-28", None),
        ("2026-27", {"season_bounds": {"2026-27": {"season_start": "2026-02-30", "season_end": "2027-08-31"}}}),
        ("2026-27", {"season_bounds": {"2026-27": {"season_start": "2026-10-01", "season_end": "2026-09-01"}}}),
        ("2026-27", {"season_bounds": {"2026-27": {"season_start": "2025-09-01", "season_end": "2027-08-31"}}}),
    ],
)
def test_invalid_seasons_and_overrides_fail(season, config):
    with pytest.raises(ValueError):
        resolve_season_bounds(season, config)


@pytest.mark.parametrize(
    "kwargs, expected_start",
    [({}, "2026-09-01"), ({"season_start": "2026-08-28", "season_end": "2027-08-31"}, "2026-08-28")],
)
def test_reader_uses_default_or_explicit_server_side_date_filters(monkeypatch, kwargs, expected_start):
    calls = []
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly")

    def fetcher(request, timeout):
        calls.append(request.full_url)
        return EmptyResponse()

    fetch_existing_sources("operadeparis", fetcher=fetcher, **kwargs)
    query = parse_qs(urlparse(calls[0]).query)
    assert query["events.date"] == [f"gte.{expected_start}", "lte.2027-08-31"]


def test_runtime_operadeparis_boundary_is_accepted_and_shared_with_reader(monkeypatch, tmp_path):
    staging = tmp_path / "events.jsonl"
    staging.write_text(json.dumps({"source": "operadeparis", "source_event_id": "x", "date": "2026-08-28"}) + "\n")
    captured = {}

    def fetch(source, season, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(sync_season, "fetch_existing_sources", fetch)
    monkeypatch.setattr(sys, "argv", [
        "sync_season.py", "--venue", "operadeparis", "--season", "2026-27",
        "--mode", "preflight", "--staging-file", str(staging),
        "--report-file", str(tmp_path / "report.json"),
    ])
    sync_season.main()
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert captured["season_start"] == report["season_start"] == "2026-08-28"
    assert captured["season_end"] == report["season_end"] == "2027-08-31"
    assert report["season_bounds_source"] == "venue_override"


def test_runtime_record_outside_resolved_bounds_fails(monkeypatch, tmp_path):
    staging = tmp_path / "events.jsonl"
    staging.write_text(json.dumps({"date": "2026-08-27"}) + "\n")
    monkeypatch.setattr(sys, "argv", [
        "sync_season.py", "--venue", "operadeparis", "--staging-file", str(staging),
    ])
    with pytest.raises(SystemExit, match="outside season range 2026-08-28 to 2027-08-31"):
        sync_season.main()
