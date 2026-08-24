import pytest

from season_ingestion.production_graph import build_payload
from season_ingestion.unicode_integrity import UnicodeIntegrityError, replacement_character_count, validate_unicode_integrity


@pytest.mark.parametrize("value", ["Opernhaus Zürich", "Zürich", "Théâtre des Champs-Élysées", "Péter Eötvös", "Camille Saint-Saëns", "Franz Lehár"])
def test_unicode_roundtrip(value):
    encoded = value.encode("utf-8")
    assert encoded.decode("utf-8") == value
    validate_unicode_integrity({"value": value})


def test_replacement_character_is_fail_closed():
    with pytest.raises(UnicodeIntegrityError):
        validate_unicode_integrity({"organization": "Opernhaus Z�rich"})
    assert replacement_character_count({"a": "Z�rich", "b": "ok"}) == 1


def test_production_graph_rejects_corrupted_identity():
    event = {"event_key": "e", "source": "s", "source_event_id": "id", "source_url": "https://example.test/e", "title": "Z�rich", "raw": {"source_title": "Z�rich"}}
    with pytest.raises(UnicodeIntegrityError):
        build_payload([event], {"composer": {"safe": []}, "work": {"safe": []}, "relationships": {"safe_existing": [], "safe_new": []}}, organization={"name": "Opernhaus Zürich"}, venue={"name": "Opernhaus Zürich", "city": "Zürich"})
