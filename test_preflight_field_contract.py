from pathlib import Path

from season_ingestion.schema import PATCHABLE_EVENT_FIELDS


EXPECTED_FIELDS = (
    "start_time",
    "end_time",
    "room",
    "event_type",
)


def test_patchable_fields_have_one_authoritative_definition():
    assert PATCHABLE_EVENT_FIELDS == EXPECTED_FIELDS
    python_files = list(Path("season_ingestion").glob("*.py"))
    definitions = sum(
        path.read_text(encoding="utf-8").count("PATCHABLE_EVENT_FIELDS =")
        for path in python_files
    )
    assert definitions == 1


def test_reader_comparison_and_writer_import_the_contract():
    supabase_source = Path("season_ingestion/supabase.py").read_text(encoding="utf-8")
    reconciliation_source = Path("season_ingestion/reconciliation.py").read_text(encoding="utf-8")
    assert "from .schema import PATCHABLE_EVENT_FIELDS" in supabase_source
    assert "from .schema import PATCHABLE_EVENT_FIELDS" in reconciliation_source
    assert 'select("*")' not in supabase_source
    assert "INSERT" not in supabase_source
    assert "DELETE" not in supabase_source


def test_staging_only_fields_are_not_selected_from_public_events():
    supabase_source = Path("season_ingestion/supabase.py").read_text(encoding="utf-8")
    for field in (
        "classification", "data_quality", "normalization_status",
        "verification_status",
    ):
        assert field not in supabase_source
