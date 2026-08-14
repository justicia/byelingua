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


def test_null_time_is_protected_and_staging_only_fields_are_observations():
    existing = record(start_time="19:00", credits=[{"name": "Conductor"}], programme=[{"name": "Aria", "normalization_status": "canonical_verified"}], artists=[{"name": "Singer"}], normalization_status="canonical_verified", data_quality={"verification_status": "canonical_verified"})
    row = staging(start_time=None, credits=[], programme=[], artists=[], normalization_status="source_verified", data_quality={"verification_status": "source_verified"})
    assert build_event_updates([row], [existing]) == []
    report = reconcile([row], [existing], "wiener_staatsoper")
    assert report["field_stats"]["protected_from_null_overwrite"] >= 1
    assert report["non_writable_observations"]["credits:empty_staging"] == 1
    assert report["non_writable_observations"]["programme:empty_staging"] == 1
    assert report["non_writable_observations"]["artists:empty_staging"] == 1
    assert report["non_writable_observations"]["normalization_status:changed_or_quality_review"] == 1
    assert report["non_writable_observations"]["data_quality:changed_or_quality_review"] == 1
    assert report["field_stats"]["protected_from_quality_downgrade"] == 0
    assert report["field_stats"]["blocked_field_conflicts"] == 0
    assert report["collision_guard_blocked"] is False


def test_change_nonempty_is_reported_with_value_summaries():
    existing = record(room="Old room")
    row = staging(room="New room")
    report = reconcile([row], [existing], "wiener_staatsoper")
    assert report["field_stats"]["change_nonempty"] == 1
    assert report["field_changes"] == [{"source": "wiener_staatsoper", "source_event_id": "source-1", "event_id": "event-1", "field": "room", "old_value_summary": "Old room", "new_value_summary": "New room"}]


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
    assert report["field_stats"]["unchanged"] == 1
    assert report["field_stats"]["change_nonempty"] == 0
    assert build_event_updates([row], [existing]) == []


def test_title_whitespace_normalization_is_semantically_unchanged():
    existing = record(title="Vienna Comedian Harmonists")
    row = staging(title="Vienna Comedian  Harmonists")
    report = reconcile([row], [existing], "wiener_staatsoper")
    assert report["field_stats"]["unchanged"] == 0
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
    assert report["existing_field_not_loaded"] == 0
    assert report["preflight_configuration_error"]["type"] == "preflight_configuration_error"
    assert report["preflight_configuration_error"]["affected_records"] == 1
    assert len(report["blocked_field_conflicts"]) == 0
    assert report["collision_guard_blocked"] is True
    with pytest.raises(RuntimeError, match="collision guard"):
        build_event_updates([row], [existing])


def test_explicit_null_is_loaded_but_an_absent_field_is_configuration_error():
    all_fields = frozenset({
        "start_time", "end_time", "room", "event_type",
    })
    explicit_null = ExistingRecord(
        "event-1", "wiener_staatsoper", "source-1", "https://example/1",
        "db-key-1", "Old title", "2027-01-01", {name: None for name in all_fields}, all_fields,
    )
    loaded_report = reconcile([staging()], [explicit_null], "wiener_staatsoper")
    assert loaded_report["preflight_configuration_error"] is None

    missing_room = ExistingRecord(
        explicit_null.event_id, explicit_null.source, explicit_null.source_event_id,
        explicit_null.source_url, explicit_null.event_key, explicit_null.title,
        explicit_null.date, explicit_null.fields, all_fields - {"room"},
    )
    missing_report = reconcile([staging()], [missing_room], "wiener_staatsoper")
    assert missing_report["preflight_configuration_error"] == {
        "type": "preflight_configuration_error",
        "missing_fields": ["room"],
        "affected_records": 1,
    }


def test_missing_fields_are_aggregated_once_across_records():
    first = ExistingRecord(
        "event-1", "wiener_staatsoper", "source-1", "https://example/1",
        "db-key-1", "Old title", "2027-01-01", {}, frozenset(),
    )
    second = ExistingRecord(
        "event-2", "wiener_staatsoper", "source-2", "https://example/2",
        "db-key-2", "Old title", "2027-01-02", {}, frozenset({"room"}),
    )
    report = reconcile(
        [staging(), staging(source_event_id="source-2", source_url="https://example/2")],
        [first, second],
        "wiener_staatsoper",
    )
    error = report["preflight_configuration_error"]
    assert error["affected_records"] == 2
    assert len(error["missing_fields"]) == len(set(error["missing_fields"])) == 4
    assert report["existing_field_not_loaded"] == 0
    assert report["blocked_field_conflicts"] == []


def test_staging_only_fields_never_require_database_columns_or_block():
    loaded = frozenset({"start_time", "end_time", "room", "event_type"})
    current = ExistingRecord(
        "event-1", "wiener_staatsoper", "source-1", "https://example/1",
        "db-key-1", "Old title", "2027-01-01",
        {name: None for name in loaded}, loaded,
    )
    row = staging(
        classification="opera",
        data_quality={"status": "source_verified"},
        normalization_status="source_verified",
        verification_status="source_verified",
    )
    report = reconcile([row], [current], "wiener_staatsoper")
    assert report["preflight_configuration_error"] is None
    assert report["existing_field_not_loaded"] == 0
    assert report["blocked_field_conflicts"] == []
    assert report["collision_guard_blocked"] is False
    assert report["non_writable_observations"] == {
        "classification:changed_or_quality_review": 1,
        "data_quality:changed_or_quality_review": 1,
        "normalization_status:changed_or_quality_review": 1,
        "verification_status:changed_or_quality_review": 1,
    }
    assert build_event_updates([row], [current]) == []


def test_specific_event_types_are_not_downgraded():
    cases = [("matinee", "other"), ("children_family", "opera"), ("operetta", "opera")]
    for old_type, new_type in cases:
        existing = record(event_type=old_type)
        row = staging(event_type=new_type)
        report = reconcile([row], [existing], "wiener_staatsoper")
        assert report["field_stats"]["protected_from_quality_downgrade"] == 1
        assert report["collision_guard_blocked"] is True
