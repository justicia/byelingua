from __future__ import annotations

from datetime import date, timedelta

from season_ingestion.release_readiness import (
    REVIEW_RELEASE_CANDIDATE,
    SAFE_RELEASE_CANDIDATE,
    assess_release_candidate,
)


def _event(index: int, day: date, *, time: str | None = "19:30") -> dict:
    return {
        "event_key": f"event-{index}",
        "source_event_id": f"source-{index}",
        "organization": "Test Venue",
        "venue": "Main Hall",
        "title": f"Concert {index}",
        "date": day.isoformat(),
        "start_time": time,
        "source_url": "https://official.example/events/" + str(index),
        "programme": [],
        "credits": [],
    }


def _metadata(*, family: str = "STRUCTURED_API", pagination: str = "none", discovered: int = 2):
    events = 2
    return (
        {"global_master_preflight": "PASS", "detail_enrichment": {"programme_items": 0, "credits_total": 0}},
        {"requested_months": ["page"], "successful_months": ["page"], "failed_months": [], "productions_discovered": discovered, "adapter_errors": [], "coverage_complete": True},
        {"occurrence_source_family": family, "occurrence_source": {"family": family, "mode": "API" if family == "STRUCTURED_API" else "HTML", "pagination_mode": pagination, "url": "https://official.example/season-2026-27"}, "source_family": family},
    )


def test_low_count_is_not_automatically_rejected():
    event = _event(1, date(2026, 9, 1))
    summary, audit, profile = _metadata(discovered=1)
    result = assess_release_candidate(venue_id="low", season="2026-27", events=[event], summary=summary, source_audit=audit, capability_profile=profile)
    assert result["release_status"] == SAFE_RELEASE_CANDIDATE
    assert result["events_release_safe"] == 1


def test_high_count_is_not_automatically_rejected():
    events = [_event(i, date(2026, 9, 1) + timedelta(days=i)) for i in range(100)]
    summary, audit, profile = _metadata(discovered=100)
    result = assess_release_candidate(venue_id="high", season="2026-27", events=events, summary=summary, source_audit=audit, capability_profile=profile)
    assert result["release_status"] == SAFE_RELEASE_CANDIDATE
    assert result["events_release_safe"] == 100


def test_incomplete_pagination_is_release_review():
    events = [_event(1, date(2026, 9, 1)), _event(2, date(2027, 3, 1))]
    summary, audit, profile = _metadata(family="PAGINATED_CALENDAR", pagination="bounded", discovered=2)
    audit["requested_months"] = ["m1", "m2", "m3", "m4", "m5", "m6"]
    audit["successful_months"] = audit["requested_months"][:-1]
    audit["failed_months"] = ["m6"]
    result = assess_release_candidate(venue_id="partial", season="2026-27", events=events, summary=summary, source_audit=audit, capability_profile=profile)
    assert result["coverage_gate"] == "FAIL"
    assert result["release_status"] == REVIEW_RELEASE_CANDIDATE


def test_incomplete_month_coverage_is_release_review():
    events = [_event(1, date(2026, 9, 1)), _event(2, date(2026, 9, 2))]
    summary, audit, profile = _metadata(family="PAGINATED_CALENDAR", pagination="bounded", discovered=2)
    audit["requested_months"] = ["m1"]
    audit["successful_months"] = ["m1"]
    result = assess_release_candidate(venue_id="short", season="2026-27", events=events, summary=summary, source_audit=audit, capability_profile=profile)
    assert result["coverage_gate"] == "FAIL"
    assert result["release_status"] == REVIEW_RELEASE_CANDIDATE


def test_completed_api_result_set_passes_coverage():
    events = [_event(1, date(2026, 9, 1)), _event(2, date(2027, 7, 1))]
    summary, audit, profile = _metadata(discovered=2)
    result = assess_release_candidate(venue_id="api", season="2026-27", events=events, summary=summary, source_audit=audit, capability_profile=profile)
    assert result["coverage_gate"] == "PASS"
    assert result["release_status"] == SAFE_RELEASE_CANDIDATE


def test_out_of_season_event_is_rejected():
    events = [_event(1, date(2026, 8, 31)), _event(2, date(2026, 9, 1))]
    summary, audit, profile = _metadata(discovered=2)
    result = assess_release_candidate(venue_id="season", season="2026-27", events=events, summary=summary, source_audit=audit, capability_profile=profile)
    assert result["season_gate"] == "FAIL"
    assert result["events_rejected"] == 1


def test_duplicate_slot_is_rejected():
    first = _event(1, date(2026, 9, 1))
    second = _event(2, date(2026, 9, 1))
    second["event_key"] = "event-2"
    second["title"] = first["title"]
    summary, audit, profile = _metadata(discovered=2)
    result = assess_release_candidate(venue_id="slot", season="2026-27", events=[first, second], summary=summary, source_audit=audit, capability_profile=profile)
    assert result["slot_gate"] == "FAIL"
    assert result["events_rejected"] == 1


def test_null_time_shadow_is_rejected():
    timed = _event(1, date(2026, 9, 1), time="19:30")
    untimed = _event(2, date(2026, 9, 1), time=None)
    untimed["title"] = timed["title"]
    summary, audit, profile = _metadata(discovered=2)
    result = assess_release_candidate(venue_id="shadow", season="2026-27", events=[timed, untimed], summary=summary, source_audit=audit, capability_profile=profile)
    assert result["slot_gate"] == "FAIL"
    assert result["events_rejected"] == 1


def test_missing_programme_credits_and_canonical_review_do_not_block_occurrence():
    events = [_event(1, date(2026, 9, 1)), _event(2, date(2027, 7, 1))]
    summary, audit, profile = _metadata(discovered=2)
    summary["canonical_status"] = "REVIEW_REQUIRED"
    result = assess_release_candidate(venue_id="occurrence", season="2026-27", events=events, summary=summary, source_audit=audit, capability_profile=profile)
    assert result["release_status"] == SAFE_RELEASE_CANDIDATE
    assert result["programme"] == 0
    assert result["credits"] == 0
    assert result["global_master"] == "PASS"


def test_production_writes_are_always_zero():
    events = [_event(1, date(2026, 9, 1)), _event(2, date(2027, 7, 1))]
    summary, audit, profile = _metadata(discovered=2)
    result = assess_release_candidate(venue_id="readonly", season="2026-27", events=events, summary=summary, source_audit=audit, capability_profile=profile)
    assert result.get("production_writes", 0) == 0


def test_production_gap_coverage_requires_verified_existing_identity():
    events = [_event(1, date(2026, 9, 1)), _event(2, date(2027, 7, 1))]
    summary, audit, profile = _metadata(discovered=0)
    audit.update({"scope": "production-gaps", "existing_events_verified": 2})
    result = assess_release_candidate(venue_id="gaps", season="2026-27", events=events, summary=summary, source_audit=audit, capability_profile=profile)
    assert result["coverage_gate"] == "PASS"
    assert result["release_status"] == SAFE_RELEASE_CANDIDATE

    audit["existing_events_verified"] = 1
    result = assess_release_candidate(venue_id="gaps", season="2026-27", events=events, summary=summary, source_audit=audit, capability_profile=profile)
    assert result["coverage_gate"] == "FAIL"
    assert result["release_status"] == REVIEW_RELEASE_CANDIDATE
