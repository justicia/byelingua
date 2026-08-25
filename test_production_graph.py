import pytest
from season_ingestion.production_graph import add_original_title, build_payload

def test_official_event_title_maps_to_original_title_not_work_title():
    e = {"event_key":"e", "title":"Display", "raw":{"source_title":"Official Event"}}
    out = add_original_title(e)
    assert out["original_title"] == "Official Event"
    assert out["raw"]["original_title_source_path"] == "raw.source_title"

def test_event_without_distinct_display_title_uses_source_title():
    out = add_original_title({"event_key":"e", "title":"Official", "raw":{"source_title":"Official"}})
    assert out["title"] == out["original_title"]

def test_build_payload_excludes_review_relationships():
    event = {"event_key":"e","source":"s","source_event_id":"id","source_url":"https://example.test/e","title":"T","raw":{"source_title":"T"}}
    staging={"composer":{"safe":[]},"work":{"safe":[]},"relationships":{"safe_existing":[{"event_key":"e","work_id":"w","order":1}],"safe_new":[]}}
    p=build_payload([event],staging,organization={"name":"O","slug":"o"},venue={"name":"V","city":"C","country_code":"CH"})
    assert len(p["relationships"]) == 1


def _credit(event_key, artist, role, character_id=None):
    return {"event_key": event_key, "credit": {"canonical_role": role, "source_artist_name": artist, "artist_resolution": {"status": "SAFE_NEW_ARTIST", "canonical_name": artist, "lookup_key": artist.casefold()}, "character_resolution": {"character_id": character_id, "character": None}, "source_character": None, "source_url": "https://example.test/e", "source_field": "jsonld.performer"}}


def _staging(rows):
    return {"composer": {"safe": []}, "work": {"safe": []}, "relationships": {"safe_existing": [], "safe_new": []}, "credit_resolution": {"safe_event_credits": rows, "safe_new_artists": [{"canonical_name": r["credit"]["source_artist_name"], "lookup_key": r["credit"]["artist_resolution"]["lookup_key"]} for r in rows]}}


def _event():
    return {"event_key": "e", "source": "s", "source_event_id": "id", "source_url": "https://example.test/e", "title": "T", "raw": {"source_title": "T"}}


def test_one_event_multiple_artists_preserves_each_artist_identity():
    payload = build_payload([_event()], _staging([_credit("e", "Artist A", "conductor"), _credit("e", "Artist B", "stage_director"), _credit("e", "Artist C", "lighting_designer")]), organization={"name": "O", "slug": "o"}, venue={"name": "V", "city": "C", "country_code": "CH"})
    assert len(payload["event_credits"]) == 3
    assert {row["artist_identity_key"] for row in payload["event_credits"]} == {"artist a", "artist b", "artist c"}


def test_same_artist_two_roles_and_same_role_two_artists_are_distinct():
    payload = build_payload([_event()], _staging([_credit("e", "Artist A", "conductor"), _credit("e", "Artist A", "stage_director"), _credit("e", "Artist B", "conductor")]), organization={"name": "O", "slug": "o"}, venue={"name": "V", "city": "C", "country_code": "CH"})
    assert len(payload["event_credits"]) == 3


def test_null_character_duplicate_identity_is_rejected_before_apply():
    rows = [_credit("e", "Artist A", "conductor"), _credit("e", "Artist A", "conductor")]
    with pytest.raises(ValueError, match="duplicate safe event credit identity"):
        build_payload([_event()], _staging(rows), organization={"name": "O", "slug": "o"}, venue={"name": "V", "city": "C", "country_code": "CH"})

