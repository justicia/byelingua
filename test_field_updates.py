import pytest

from season_ingestion.reconciliation import ExistingRecord, reconcile
from season_ingestion.supabase import build_event_updates


def record(**fields):
    base = ExistingRecord("event-1", "wiener_staatsoper", "source-1", "https://example/1", "db-key-1", "Old title", "2027-01-01")
    return ExistingRecord(base.event_id, base.source, base.source_event_id, base.source_url, base.event_key, base.title, base.date, fields)


def staging(**fields):
    base = {"source": "wiener_staatsoper", "source_event_id": "source-1", "source_url": "https://example/1", "event_key": "staging-key", "title": "Old title", "date": "2027-01-01"}
    base.update(fields)
    return base


def test_null_time_empty_collections_and_low_quality_are_protected():
    existing = record(start_time="19:00", credits=[{"name": "Conductor"}], programme=[{"name": "Aria", "normalization_status": "canonical_verified"}], artists=[{"name": "Singer"}], normalization_status="canonical_verified", data_quality={"verification_status": "canonical_verified"})
    row = staging(start_time=None, credits=[], programme=[], artists=[], normalization_status="source_verified", data_quality={"verification_status": "source_verified"})
    with pytest.raises(RuntimeError, match="field-level quality guard|collision guard"):
        build_event_updates([row], [existing])
    report = reconcile([row], [existing], "wiener_staatsoper")
    assert report["field_stats"]["protected_from_null_overwrite"] >= 1
    assert report["non_writable_observations"]["credits:empty_staging"] == 1
    assert report["non_writable_observations"]["programme:empty_staging"] == 1
    assert report["non_writable_observations"]["artists:empty_staging"] == 1
    assert report["field_stats"]["protected_from_quality_downgrade"] >= 1
    assert report["field_stats"]["blocked_field_conflicts"] >= 1
    assert report["collision_guard_blocked"] is True


def test_change_nonempty_is_reported_with_value_summaries():
    existing = record(title="Old title")
    row = staging(title="New title")
    report = reconcile([row], [existing], "wiener_staatsoper")
    assert report["field_stats"]["change_nonempty"] == 1
    assert report["field_changes"] == [{"source": "wiener_staatsoper", "source_event_id": "source-1", "event_id": "event-1", "field": "title", "old_value_summary": "Old title", "new_value_summary": "New title"}]


def test_lower_normalization_status_cannot_replace_canonical_collection():
    existing = record(programme=[{"name": "Aria", "normalization_status": "canonical_verified"}])
    row = staging(programme=[{"name": "Aria", "normalization_status": "source_verified"}])
    report = reconcile([row], [existing], "wiener_staatsoper")
    assert report["non_writable_observations"]["programme:changed_or_quality_review"] == 1
    assert report["field_stats"]["blocked_field_conflicts"] == 0
    assert report["collision_guard_blocked"] is False


def test_unchanged_event_produces_no_update_plan():
    existing = record()
    assert build_event_updates([staging()], [existing]) == []


def test_time_seconds_zero_is_semantically_unchanged():
    existing = record(start_time="19:00:00")
    row = staging(start_time="19:00")
    report = reconcile([row], [existing], "wiener_staatsoper")
    assert report["field_stats"]["unchanged"] == 3
    assert report["field_stats"]["change_nonempty"] == 0
    assert build_event_updates([row], [existing]) == []


def test_title_whitespace_normalization_is_semantically_unchanged():
    existing = record(title="Vienna Comedian Harmonists")
    row = staging(title="Vienna Comedian  Harmonists")
    report = reconcile([row], [existing], "wiener_staatsoper")
    assert report["field_stats"]["unchanged"] == 2
    assert report["field_stats"]["change_nonempty"] == 0
    assert report["field_changes"] == []
    assert build_event_updates([row], [existing]) == []


def test_empty_values_do_not_create_fill_or_patch():
    existing = record(start_time="19:00", credits=[{"name": "C"}], programme=[{"name": "P"}], artists=[{"name": "A"}])
    row = staging(start_time=None, credits=[], programme=[], artists=[], classification={}, room="")
    report = reconcile([row], [existing], "wiener_staatsoper")
    assert report["field_stats"]["fill_missing"] == 0
    assert report["field_stats"]["change_nonempty"] == 0
    assert report["field_stats"]["protected_from_null_overwrite"] == 1
    assert report["non_writable_observations"]["credits:empty_staging"] == 1
    assert report["non_writable_observations"]["programme:empty_staging"] == 1
    assert build_event_updates([row], [existing]) == []


def test_missing_loaded_database_field_blocks_apply():
    existing = ExistingRecord("event-1", "wiener_staatsoper", "source-1", "https://example/1", "db-key-1", "Old title", "2027-01-01", {"title": "Old title"}, frozenset({"event_key", "title", "date"}))
    row = staging(title="New title")
    report = reconcile([row], [existing], "wiener_staatsoper")
    assert report["existing_field_not_loaded"] > 0
    assert report["collision_guard_blocked"] is True
    with pytest.raises(RuntimeError, match="collision guard"):
        build_event_updates([row], [existing])


def test_specific_event_types_are_not_downgraded():
    cases = [("matinee", "other"), ("children_family", "opera"), ("operetta", "opera")]
    for old_type, new_type in cases:
        existing = record(event_type=old_type)
        row = staging(event_type=new_type)
        report = reconcile([row], [existing], "wiener_staatsoper")
        assert report["field_stats"]["protected_from_quality_downgrade"] == 1
        assert report["collision_guard_blocked"] is True
