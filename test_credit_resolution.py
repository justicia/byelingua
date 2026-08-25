from types import SimpleNamespace

from season_ingestion.credit_resolution import canonical_role, resolve_credit, stage_credits
from season_ingestion.production_graph import build_payload


def snapshot(artists=None, work_characters=None, character_aliases=None):
    return SimpleNamespace(
        entities={"artist": artists or [], "character": []},
        artist_aliases=[], character_aliases=character_aliases or [],
        work_characters=work_characters or [],
    )


def test_role_taxonomy_and_voice_types():
    assert canonical_role("Musikalische Leitung") == "conductor"
    assert canonical_role("direction musicale") == "conductor"
    assert canonical_role("Inszenierung") == "stage_director"
    assert canonical_role("mise en scène") == "stage_director"
    assert canonical_role("Bühnenbild") == "set_designer"
    assert canonical_role("Lichtgestaltung") == "lighting_designer"
    assert canonical_role("Soprano") == "singer"
    assert canonical_role("Tenor") == "singer"
    assert canonical_role("Baritone") == "singer"


def test_artist_resolution_is_unicode_safe_and_new_artists_are_safe():
    existing = snapshot([{"id": "a1", "artist_name": "Piotr Beczała"}])
    result = resolve_credit({"artist_name": "Piotr Beczala", "source_role": "Soloist"}, work_id=None, snapshot=existing)
    assert result["artist_resolution"]["status"] == "SAFE_EXISTING"
    fresh = resolve_credit({"artist_name": "Jane Doe", "source_role": "Soloist"}, work_id=None, snapshot=existing)
    assert fresh["artist_resolution"]["status"] == "SAFE_NEW_ARTIST"


def test_voice_type_never_becomes_character():
    result = resolve_credit({"artist_name": "Jane Doe", "source_role": "Soprano", "character": "Soprano"}, work_id="w1", snapshot=snapshot())
    assert result["source_character"] is None
    assert result["canonical_role"] == "singer"


def test_work_scoped_character_resolution_and_review():
    s = snapshot(work_characters=[{"work_id": "w1", "canonical_name": "Elisabeth", "character_uid": "c1"}])
    safe = resolve_credit({"artist_name": "Jane Doe", "source_role": "Singer", "character": "Elisabeth"}, work_id="w1", snapshot=s)
    assert safe["character_resolution"]["status"] == "SAFE_CHARACTER"
    review = resolve_credit({"artist_name": "Jane Doe", "source_role": "Singer", "character": "Venus"}, work_id="w1", snapshot=s)
    assert review["resolution_status"] == "REVIEW_CHARACTER_CONFLICT"


def test_review_never_enters_safe_staging_and_duplicates_are_deterministic():
    event = SimpleNamespace(event_key="e1", credits=[{"artist_name": "Jane Doe", "source_role": "Soloist"}, {"artist_name": "Jane Doe", "source_role": "Soloist"}, {"artist_name": "X", "source_role": "Unknown Role"}])
    staged = stage_credits([event], [], snapshot())
    assert len(staged["safe_event_credits"]) == 1
    assert len(staged["review_event_credits"]) == 1
    assert all(not item["credit"]["resolution_status"].startswith("REVIEW") for item in staged["safe_event_credits"])


def test_graph_payload_carries_artists_and_event_credits():
    payload = build_payload(
        [{"event_key": "e1", "source": "s", "source_event_id": "1", "source_url": "https://example.test/e", "title": "Concert", "raw": {"source_title": "Concert"}}],
        {"composer": {"safe": []}, "work": {"safe": []}, "relationships": {"safe_existing": [], "safe_new": []}, "credit_resolution": {"safe_new_artists": [{"canonical_name": "Jane Doe", "lookup_key": "jane doe"}], "safe_event_credits": [{"event_key": "e1", "credit": {"canonical_role": "soloist", "artist_resolution": {"status": "SAFE_NEW_ARTIST", "canonical_name": "Jane Doe"}, "character_resolution": {"character_id": None, "character": None}, "source_artist_name": "Jane Doe"}}]}},
        organization={"slug": "o", "name": "O"}, venue={"name": "V"},
    )
    assert len(payload["artists"]) == 1
    assert payload["expected"]["event_credits"] == 1
