from season_ingestion.contracts import schedule_integrity_report
from season_ingestion.schema import CanonicalEvent


def event(*, date="2027-06-22", start_time="20:00", title="Il trovatore", schedule=None):
    return CanonicalEvent(
        source="opera_roma", source_event_id=f"{title}-{date}-{start_time}",
        source_url="https://www.operaroma.it/stagione/", organization="Teatro dell'Opera di Roma",
        venue="Teatro Costanzi", city="Rome", country="Italy", timezone="Europe/Rome",
        title=title, date=date, start_time=start_time, end_time=None, room=None,
        event_type="performance", data_quality={"schedule": schedule or {}},
    )


def test_null_timed_shadow_is_not_emitted_by_normalized_adapter_output():
    report = schedule_integrity_report([event(start_time="20:00")])
    assert report["duplicate_performance_slot"] == 0
    assert report["null_timed_shadow_duplicates"] == 0


def test_distinct_same_day_times_are_valid_slots():
    report = schedule_integrity_report([event(start_time="14:00"), event(start_time="20:00")])
    assert report["duplicate_performance_slot"] == 0
    assert report["ambiguous_same_day_occurrence"] == 0


def test_yearless_without_production_evidence_is_reviewed():
    report = schedule_integrity_report([event(schedule={"year_status": "YEAR_UNVERIFIED"})])
    assert report["year_unverified"] == 1

