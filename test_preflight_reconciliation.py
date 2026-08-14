import pytest

from jobs.sync_season import apply_if_clear
from season_ingestion.preflight import ExistingSource, reconcile


def event(**overrides):
    row = {"source": "operadeparis", "source_event_id": "p-1", "event_key": "operadeparis:key-1", "title": "La Traviata", "date": "2027-03-01", "start_time": "19:30", "end_time": None, "room": "Bastille"}
    row.update(overrides)
    return row


def existing(**overrides):
    row = {"event_id": "e-1", "event_key": "operadeparis:key-1", "source": "operadeparis", "source_event_id": "p-1", "source_url": "https://example.test/program", "title": "La Traviata", "date": "2027-03-01"}
    row.update(overrides)
    return ExistingSource(**row)


def test_identity_precedes_event_key_and_url_is_not_identity():
    result = reconcile("operadeparis", [event(source_url="https://other.test")], [existing(source_url="https://different.test")])
    assert result["counts"] == {"inserted": 0, "updated": 0, "unchanged": 1, "quarantined": 0, "ambiguous": 0}


def test_ambiguous_identity_blocks_apply_and_reports_fields():
    result = reconcile("operadeparis", [event()], [existing(event_id="e-1"), existing(event_id="e-2")])
    assert result["apply_blocked"] is True
    assert result["counts"]["ambiguous"] == 1
    assert result["events"][0]["source_event_id"] == "p-1"
    assert "multiple" in result["events"][0]["reason"]


def test_auditorio_is_risk_only_and_wiener_review_is_not_deleted():
    auditorio = reconcile("auditorio_nacional", [event(source="auditorio_nacional", source_event_id="a-1")], [])
    assert auditorio["counts"]["quarantined"] == 1
    wiener = reconcile("wiener_staatsoper", [event(source="wiener_staatsoper", source_event_id="w-1", title="Die Zauberflöte", date="2027-02-05")], [])
    assert wiener["events"][0]["reason"] == "review_required_wiener_2027_02_05_do_not_delete"


def test_duplicate_event_key_with_multiple_identities_is_audit_anomaly():
    result = reconcile("operadeparis", [event(source_event_id="p-1"), event(source_event_id="p-2")], [])
    assert result["apply_blocked"] is True
    assert any(item["type"] == "event_key_has_multiple_source_identities" for item in result["duplicate_anomalies"])


def test_apply_never_calls_a_writer_when_preflight_has_anomaly(monkeypatch):
    calls = []
    monkeypatch.setattr("season_ingestion.supabase.apply_events", lambda rows: calls.append(rows))
    report = reconcile("operadeparis", [event()], [existing(event_id="e-1"), existing(event_id="e-2")])
    with pytest.raises(RuntimeError, match="apply blocked by preflight"):
        apply_if_clear([event()], report)
    assert calls == []


def test_apply_is_explicitly_disabled_even_when_preflight_is_clear():
    report = reconcile("operadeparis", [event()], [existing()])
    with pytest.raises(RuntimeError, match="production writer not implemented"):
        apply_if_clear([event()], report)
