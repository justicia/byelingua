import json
from pathlib import Path

from events_pipeline.adapters import extract_fixture
from events_pipeline.model import CanonicalEvent


def test_invalid_event_is_quarantined():
    manifest = {"source": "https://example.test/calendar", "venue": "Test Hall", "city": "Vienna", "country": "Austria"}
    path = Path("/tmp/pipeline-fixture.html")
    path.write_text('<script type="application/ld+json">{"@type":"Event","name":"Bad","startDate":"2026-01-01"}</script>')
    events, quarantine = extract_fixture(manifest, path)
    assert events == []
    assert quarantine


def test_event_validation_requires_source_url_and_identity():
    event = CanonicalEvent("", "", "not-a-url", "Hall", "Vienna", "Austria", "Title", "2026-01-01")
    assert "missing source identity" in event.validate()
    assert "missing source URL" in event.validate()
