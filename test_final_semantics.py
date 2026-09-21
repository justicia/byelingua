from season_ingestion.auditorio_structure import segment_programme_records
from season_ingestion.credit_resolution import (
    canonical_instrument,
    canonical_voice_type,
    normalize_credit_row,
)
from season_ingestion.hard_freeze import append_only_plan


def test_voice_aliases_normalize_before_identity():
    assert canonical_voice_type("Mezzo Soprano") == "MEZZO_SOPRANO"
    assert canonical_voice_type("Mezzosoprano") == "MEZZO_SOPRANO"
    assert canonical_voice_type("Barítono") == "BARITONE"
    assert normalize_credit_row({"source_role": "Baritono"})["canonical_role"] == "singer"


def test_instrument_aliases_do_not_invent_violin_section():
    assert canonical_instrument("violin") == "VIOLIN"
    assert canonical_instrument("Violin I") == "VIOLIN_I"
    assert canonical_instrument("Violin II") == "VIOLIN_II"
    assert canonical_instrument("violin").endswith("I") is False


def test_programme_segmentation_rejects_composer_only_and_merges_continuation():
    rows = segment_programme_records([
        {"raw_text": "Mikel Urquiza", "classification": "composer_candidate"},
        {"raw_text": "Deseo tomó delicia", "classification": "work_candidate"},
        {"raw_text": "para voz y piano", "classification": "movement_candidate"},
    ])
    assert len(rows) == 1
    assert rows[0]["composer"] == "Mikel Urquiza"
    assert "para voz y piano" in rows[0]["title"]


def test_append_only_plan_surfaces_conflict_without_overwrite():
    plan = append_only_plan(
        [{"event_key": "e", "work_id": "w", "title": "Original"}],
        [{"event_key": "e", "work_id": "w", "title": "Conflicting source title"}],
        kind="programme",
    )
    assert plan["to_add"] == []
    assert plan["already_exists"] == []
    assert len(plan["conflicts"]) == 1
    assert plan["conflicts"][0]["status"] == "CONFLICT"
