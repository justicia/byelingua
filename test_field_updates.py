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
    assert report["field_stats"]["protected_from_null_overwrite"] >= 4
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
    assert report["field_stats"]["protected_from_quality_downgrade"] >= 1
    assert report["field_stats"]["blocked_field_conflicts"] >= 1
    assert report["collision_guard_blocked"] is True


def test_unchanged_event_produces_no_update_plan():
    existing = record()
    assert build_event_updates([staging()], [existing]) == []
