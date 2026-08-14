import json
from pathlib import Path

from venue_ingestion_batch import inspect_html


def test_inspection_extracts_iso_dates_and_heading_titles():
    raw = b'<h3>Beethoven: Symphony No. 5</h3><span>2026-10-03T19:30:00</span>'
    result = inspect_html(raw)
    assert result["iso_datetime_tokens"] == 1
    assert result["title_samples"] == ["Beethoven: Symphony No. 5"]


def test_batch_report_is_staging_only_and_covers_all_venues():
    report = json.loads(Path("venue-ingestion-batch/venue_ingestion_batch_report.json").read_text())
    assert report["production_database_modified"] is False
    assert report["venues_attempted"] == 16
    assert len(report["venues"]) == 16
    assert set(report["ready_for_import"]) == set()
