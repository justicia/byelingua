import json
from pathlib import Path

from events_pipeline.adapters import extract_fixture
from events_pipeline.model import CanonicalEvent
from events_pipeline.auditorio_enrichment import (
    parse_artists,
    parse_programme,
    split_content,
)


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


def test_auditorio_split_ocne_blocks():
    artists, programme = split_content([
        [],
        ["Orquesta Nacional de España", "David Afkham, Director"],
        ["William Walton", "Concierto para violín"],
    ])
    assert artists == ["Orquesta Nacional de España", "David Afkham, Director"]
    assert programme == ["William Walton", "Concierto para violín"]


def test_auditorio_split_mixed_programme_marker():
    artists, programme = split_content([[
        "Rafael Aguirre, guitarra", "Programa", "J.S. Bach (1685 - 1750)",
        "Preludio, Fuga y Allegro, BWV998",
    ]])
    assert artists == ["Rafael Aguirre, guitarra"]
    assert programme[0].startswith("J.S. Bach")


def test_auditorio_parses_artists_and_composer_work_pairs():
    artists = parse_artists(["London Philharmonic Orchestra", "Edward Gardner, dirección"])
    assert artists == [
        {"artist_name": "London Philharmonic Orchestra", "role": "performer"},
        {"artist_name": "Edward Gardner", "role": "dirección"},
    ]
    works = parse_programme([
        "Gustav Mahler (1860-1911)", "Sinfonía núm. 2", "Mikel Urquiza", "Deseo tomó delicia",
        "Chaikovsky", "Concierto para violín y orquesta",
        "BRAHMS Concierto para violín",
    ])
    assert works == [
        {"composer": "Gustav Mahler", "work_title": "Sinfonía núm. 2"},
        {"composer": "Mikel Urquiza", "work_title": "Deseo tomó delicia"},
        {"composer": "Chaikovsky", "work_title": "Concierto para violín y orquesta"},
        {"composer": "BRAHMS", "work_title": "Concierto para violín"},
    ]
