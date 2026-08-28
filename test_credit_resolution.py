from types import SimpleNamespace

from season_ingestion.credit_resolution import canonical_role, resolve_credit, stage_credits
from season_ingestion.character_linkage import classify_unlinked_character
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


def test_artist_resolution_prefers_official_accent_preserving_exact_match():
    existing = snapshot([
        {"id": "plain", "artist_name": "Etienne Pluss"},
        {"id": "accented", "artist_name": "Étienne Pluss"},
    ])
    result = resolve_credit({"artist_name": "Étienne Pluss", "source_role": "Set Design"}, work_id=None, snapshot=existing)
    assert result["artist_resolution"]["status"] == "SAFE_EXISTING"
    assert result["artist_resolution"]["artist_id"] == "accented"


def test_known_zurich_artists_resolve_existing():
    s = snapshot([{"id": "armiliato", "artist_name": "Marco Armiliato"}, {"id": "beczala", "artist_name": "Piotr Beczała"}])
    assert resolve_credit({"artist_name": "Marco Armiliato", "source_role": "Musical Director"}, work_id=None, snapshot=s)["artist_resolution"]["status"] == "SAFE_EXISTING"
    result = resolve_credit({"artist_name": "Piotr Beczala", "source_role": "Singer"}, work_id=None, snapshot=s)
    assert result["artist_resolution"]["status"] == "SAFE_EXISTING"
    assert result["artist_resolution"]["canonical_name"] == "Piotr Beczała"


def test_voice_type_never_becomes_character():
    result = resolve_credit({"artist_name": "Jane Doe", "source_role": "Soprano", "character": "Soprano"}, work_id="w1", snapshot=snapshot())
    assert result["source_character"] is None
    assert result["canonical_role"] == "singer"


def test_explicit_cast_character_uses_performer_role():
    result = resolve_credit({"artist_name": "Jane Doe", "source_role": "Elisabeth", "credit_kind": "cast", "character": "Elisabeth"}, work_id="w1", snapshot=snapshot())
    assert result["canonical_role"] == "performer"
    assert result["resolution_status"] == "SAFE_UNRESOLVED_CHARACTER"
    assert result["character_resolution"]["status"] == "REVIEW_CHARACTER_CONFLICT"
    assert result["resolution_status"] != "REVIEW_ROLE_UNKNOWN"


def test_work_scoped_character_resolution_and_review():
    s = snapshot(work_characters=[{"id": "wc1", "work_id": "w1", "canonical_name": "Elisabeth", "character_uid": "c1"}])
    safe = resolve_credit({"artist_name": "Jane Doe", "source_role": "Singer", "character": "Elisabeth"}, work_id="w1", snapshot=s)
    assert safe["character_resolution"]["status"] == "SAFE_CHARACTER"
    assert safe["character_resolution"]["character_id"] == "wc1"
    assert safe["character_resolution"]["global_character_id"] == "c1"
    review = resolve_credit({"artist_name": "Jane Doe", "source_role": "Singer", "character": "Venus"}, work_id="w1", snapshot=s)
    assert review["resolution_status"] == "SAFE_UNRESOLVED_CHARACTER"
    assert review["character_resolution"]["status"] == "REVIEW_CHARACTER_CONFLICT"


def test_unlinked_work_character_never_becomes_safe_character():
    s = snapshot(work_characters=[{"id": "wc1", "work_id": "w1", "canonical_name": "Elisabeth", "character_uid": None}])
    result = resolve_credit({"artist_name": "Jane Doe", "source_role": "Singer", "character": "Elisabeth"}, work_id="w1", snapshot=s)
    assert result["resolution_status"] == "SAFE_UNRESOLVED_CHARACTER"
    assert result["character_resolution"]["status"] == "REVIEW_CHARACTER_CONFLICT"


def test_unresolved_character_credit_is_safe_but_identity_stays_in_backlog():
    event = SimpleNamespace(event_key="e1", credits=[
        {"artist_name": "Jane Doe", "source_role": "Elisabeth", "credit_kind": "cast", "character": "Elisabeth"},
    ])
    staged = stage_credits([event], [{"event_key": "e1", "work_id": "w1"}], snapshot())
    assert len(staged["safe_event_credits"]) == 1
    assert len(staged["review_event_credits"]) == 0
    assert len(staged["review_character_conflicts"]) == 1
    assert staged["safe_event_credits"][0]["credit"]["source_character"] == "Elisabeth"


def test_unresolved_dual_roles_for_one_artist_are_not_deduplicated():
    event = SimpleNamespace(event_key="e1", credits=[
        {"artist_name": "Jane Doe", "source_role": "First Lady", "credit_kind": "cast", "character": "First Lady"},
        {"artist_name": "Jane Doe", "source_role": "Second Lady", "credit_kind": "cast", "character": "Second Lady"},
    ])
    staged = stage_credits([event], [{"event_key": "e1", "work_id": "w1"}], snapshot())
    assert len(staged["safe_event_credits"]) == 2


def test_credit_status_precedence_allows_safe_non_character_credits():
    s = snapshot([{"id": "armiliato", "artist_name": "Marco Armiliato"}])
    for role in ("Musikalische Leitung", "Inszenierung", "Singer"):
        result = resolve_credit({"artist_name": "Marco Armiliato", "source_role": role}, work_id="w1", snapshot=s)
        assert result["resolution_status"] == "SAFE_ROLE"
    assert canonical_role("Choreinstudierung") == "chorus_master"
    assert canonical_role("Video") == "video_designer"
    assert canonical_role("Statisten") == "extras"
    assert canonical_role("Background actors") == "extras"
    assert canonical_role("Ausstattung") == "production_designer"
    assert canonical_role("Philharmonia Zürich") == "orchestra"


def test_character_linkage_hard_blocks_jobs_and_allows_linked_characters():
    s = snapshot(work_characters=[], character_aliases=[{"character_id": "c1", "alias": "The Wanderer"}])
    s.entities["character"] = [{"id": "c1", "canonical_name": "Der Wanderer"}]
    assert classify_unlinked_character({"canonical_name": "Stage Director"}, s)["classification"] == "NON_CHARACTER_CONTAMINATION"
    assert classify_unlinked_character({"canonical_name": "The Wanderer"}, s)["classification"] == "SAFE_LINK_EXISTING_CHARACTER"
    assert classify_unlinked_character({"canonical_name": "Elisabeth"}, s, verified_original_names={"Elisabeth"})["classification"] == "SAFE_NEW_GLOBAL_CHARACTER_VERIFIED"
    assert classify_unlinked_character({"canonical_name": "Un Joven Pastor"}, s)["classification"] == "REVIEW_LOCALIZED_NAME"


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

