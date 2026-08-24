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
