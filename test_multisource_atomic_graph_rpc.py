from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parent
    / "supabase"
    / "migrations"
    / "202608280001_add_multisource_event_sources_to_shared_graph.sql"
)


def sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_rpc_v2_keeps_legacy_payload_path():
    text = sql()
    assert "jsonb_array_elements(p_payload->'events')" in text
    assert "else\n    for v_key,v_source_event" in text
    assert "p_payload->>'source'" in text
    assert "x->>'source_url'" in text


def test_rpc_v2_uses_top_level_sources_as_authoritative_input():
    text = sql()
    assert "jsonb_array_elements(p_payload->'event_sources')" in text
    assert "if jsonb_typeof(p_payload->'event_sources') = 'array'" in text
    assert "and jsonb_array_length(p_payload->'event_sources') > 0" in text
    assert "values(v_event_id,v_source,v_source_event,v_source_url)" in text


def test_rpc_v2_resolves_every_source_event_and_fails_closed():
    text = sql()
    assert "from _graph_events where staging_key=v_key" in text
    assert "raise exception 'event source event identity unresolved %',v_key" in text
    assert "raise exception 'event source row incomplete %',v_key" in text


def test_rpc_v2_source_idempotency_is_source_scoped():
    text = sql()
    assert "where source=v_source and source_event_id=v_source_event" in text
    assert "where source=p_payload->>'source' and source_event_id=v_source_event" in text
    assert "unique(event_id)" not in text.lower()


def test_rpc_v2_does_not_change_table_schema_or_other_graph_sections():
    text = sql().lower()
    assert "alter table" not in text
    assert "create table" not in text
    assert "drop table" not in text
    for marker in ("organizations", "venues", "events", "event_programme", "composers", "works", "artists", "event_credits"):
        assert marker in text


def test_v2_contract_cases_are_explicitly_represented_in_migration():
    text = sql()
    # Legacy and V2 single/multi-source paths are represented by the two branches;
    # the source identity check makes reruns no-ops, while the resolver guard covers invalid references.
    assert text.count("insert into event_sources") == 2
    assert "if not exists(select 1 from event_sources" in text
    assert "event source event identity unresolved" in text
