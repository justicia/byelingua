import io
import pytest
from pathlib import Path
from urllib.error import HTTPError
from season_ingestion.production_graph import (
    ProductionGraphRPCError,
    add_original_title,
    apply_graph,
    build_payload,
    normalize_graph_staging,
    validate_production_graph_contract,
)

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


def test_existing_work_uuid_uses_work_id_without_candidate_payload():
    staging = {
        "composer": {"safe": []},
        "work": {"safe": [{"id": "existing-work", "title": "Existing"}]},
        "relationships": {"safe_existing": [{"event_key": "e", "work_id": "existing-work", "order": 1}], "safe_new": []},
    }
    payload = build_payload([_event()], staging, organization={"name": "O", "slug": "o"}, venue={"name": "V", "city": "C", "country_code": "CH"})
    assert payload["works"] == []
    assert payload["relationships"] == [{"event_key": "e", "work_id": "existing-work", "order": 1}]


def test_valid_new_work_candidate_is_preserved():
    staging = {
        "composer": {"safe": []},
        "work": {"safe": [{"candidate_key": "work:new", "normalized_source_title": "new-work", "proposed_canonical_title": "New Work"}]},
        "relationships": {"safe_existing": [], "safe_new": [{"event_key": "e", "candidate_key": "work:new", "order": 1}]},
    }
    payload = build_payload([_event()], staging, organization={"name": "O", "slug": "o"}, venue={"name": "V", "city": "C", "country_code": "CH"})
    assert payload["works"][0]["candidate_key"] == "work:new"
    assert payload["relationships"][0]["candidate_key"] == "work:new"


def test_malformed_work_and_unresolved_relationship_are_excluded_from_safe_graph():
    works, relationships, diagnostics = normalize_graph_staging({
        "work": {"safe": [{"candidate_key": None, "normalized_source_title": "", "proposed_canonical_title": ""}]},
        "relationships": {"safe_existing": [{"event_key": "e", "candidate_key": "missing"}], "safe_new": []},
    })
    assert works == []
    assert relationships == []
    assert diagnostics["null_work_candidate_key"] == 1
    assert diagnostics["excluded_unresolved_relationships"] == 1


def test_malformed_programme_does_not_block_unrelated_event_or_credit():
    malformed = {"candidate_key": None, "normalized_source_title": "", "proposed_canonical_title": ""}
    payload = build_payload(
        [_event()],
        {
            "composer": {"safe": []},
            "work": {"safe": [malformed]},
            "relationships": {"safe_existing": [{"event_key": "e", "candidate_key": "missing", "order": 1}], "safe_new": []},
            "credit_resolution": {"safe_event_credits": [_credit("e", "Artist A", "conductor")]},
        },
        organization={"name": "O", "slug": "o"},
        venue={"name": "V", "city": "C", "country_code": "CH"},
    )
    assert len(payload["events"]) == 1
    assert payload["works"] == []
    assert payload["relationships"] == []
    assert len(payload["event_credits"]) == 1


def test_graph_validator_rejects_null_candidate_before_rpc():
    with pytest.raises(ValueError, match="NULL_WORK_CANDIDATE_KEY"):
        validate_production_graph_contract({"works": [{"candidate_key": None, "normalized_source_title": "x", "proposed_canonical_title": "X"}], "relationships": []})


def test_graph_validator_rejects_relationship_without_resolution_path():
    with pytest.raises(ValueError, match="UNRESOLVED_RELATIONSHIP_WORK_IDENTITY"):
        validate_production_graph_contract({"works": [], "relationships": [{"event_key": "e", "order": 1}]})


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


def test_null_character_duplicate_identity_is_deduplicated_before_apply():
    rows = [_credit("e", "Artist A", "conductor"), _credit("e", "Artist A", "conductor")]
    payload = build_payload([_event()], _staging(rows), organization={"name": "O", "slug": "o"}, venue={"name": "V", "city": "C", "country_code": "CH"})
    assert len(payload["event_credits"]) == 1


def test_rpc_error_preserves_bounded_response_body_without_request_headers(monkeypatch):
    class Response:
        status = 500

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"code":"PGRST500","message":"database function failed"}'

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "unit-test-secret")
    with pytest.raises(ProductionGraphRPCError) as raised:
        apply_graph({"events": [], "product_contract_version": 1, "product_contract_id": "BYELINGUA_PRODUCT_CONTRACT_VERSION=1"}, sender=lambda request, timeout=0: Response())
    assert raised.value.http_status == 500
    assert "database function failed" in raised.value.response_body
    assert "Authorization" not in str(raised.value)


def test_http_error_response_body_is_structured_and_secret_redacted(monkeypatch):
    body = b'{"code":"23505","message":"duplicate key","details":"secret-token","hint":"retry"}'
    error = HTTPError("https://example.supabase.co", 400, "Bad Request", {}, io.BytesIO(body))
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret-token")

    with pytest.raises(ProductionGraphRPCError) as raised:
        apply_graph({"events": [], "product_contract_version": 1, "product_contract_id": "BYELINGUA_PRODUCT_CONTRACT_VERSION=1"}, sender=lambda request, timeout=0: (_ for _ in ()).throw(error))

    failure = raised.value.as_dict()
    assert failure["http_status"] == 400
    assert failure["error_code"] == "23505"
    assert failure["message"] == "duplicate key"
    assert failure["details"] == "[REDACTED]"
    assert failure["hint"] == "retry"
    assert "secret-token" not in str(failure)


def test_shared_graph_credit_guard_matches_character_text_unique_identity():
    migration = Path(__file__).parent / "supabase" / "migrations" / "202609160001_align_credit_idempotency_guard.sql"
    sql = migration.read_text(encoding="utf-8")
    assert "ec.character is not distinct from v_character" in sql
    assert "ec.character_id is not distinct from v_character_id" not in sql

