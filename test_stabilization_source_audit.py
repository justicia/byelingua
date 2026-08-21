import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "artifacts" / "stabilization"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def test_input_baselines_are_exact():
    auditorio = load("input/auditorio-room-candidate-input.json")
    times = load("input/wiener-start-time-candidate-input.json")
    programme = load("input/wiener-nonwork-relationship-input.json")
    assert auditorio["group_count"] == 44 and len(auditorio["groups"]) == 44
    assert times["count"] == 312 and len(times["events"]) == 312
    assert programme["relationship_count"] == 80
    assert programme["distinct_work_count"] == 25
    assert len(programme["relationships"]) == 80


def test_all_auditorio_groups_are_classified_with_official_room_evidence():
    audit = load("auditorio-room-identity-audit.json")
    assert audit["groups_source_audited"] == 44
    assert sum(audit["classification_counts"].values()) == 44
    for group in audit["groups"]:
        assert group["classification"] in {
            "ROOM_PARSER_DUPLICATION_DETERMINISTIC",
            "TRUE_MULTI_ROOM_PERFORMANCES",
            "SOURCE_ROOM_CONFLICT",
            "EVENT_IDENTITY_AMBIGUOUS",
        }
        assert group["official_source_urls"]
        assert group["official_evidence"]


def test_auditorio_cleanup_is_deterministic_only():
    audit = load("auditorio-room-identity-audit.json")
    staging = load("auditorio-room-duplicate-cleanup-staging.json")
    assert all(x["classification"] == "ROOM_PARSER_DUPLICATION_DETERMINISTIC" for x in staging["cleanup_candidates"])
    assert len(staging["cleanup_candidates"]) == audit["classification_counts"]["ROOM_PARSER_DUPLICATION_DETERMINISTIC"]
    for item in staging["cleanup_candidates"]:
        assert item["official_room_text"]
        assert item["official_evidence"]


def test_wiener_corrected_time_events_are_source_audited_without_inference():
    audit = load("wiener-staatsoper-start-time-audit-2026-27.json")
    staging = load("wiener-staatsoper-start-time-staging-2026-27.json")
    assert audit["input_events"] == 312 and audit["source_audited"] == 312
    assert sum(audit["classification_counts"].values()) == 312
    assert audit["classification_counts"]["SOURCE_TIME_FOUND"] == 10
    assert audit["classification_counts"]["SOURCE_TIME_NOT_PUBLISHED"] == 302
    assert len(staging["updates"]) == 10
    assert staging["database_writes"] == 0 and staging["sql_generated"] is False
    found = {x["source_event_id"]: x for x in audit["events"] if x["classification"] == "SOURCE_TIME_FOUND"}
    assert found["vienna-opera-ball:2027-02-04"]["normalized_start_time"] == "20:15"
    assert found["matinee-zu-ballo-in-maschera:2027-02-14"]["normalized_start_time"] == "11:00"
    assert all(x["official_time_source_type"] in {"DETAIL_PAGE", "MONTHLY_CALENDAR", "OFFICIAL_REDIRECT"} for x in found.values())
    assert all("detail page was checked" in x["reason"] and "monthly calendar" in x["reason"] for x in audit["events"] if x["classification"] == "SOURCE_TIME_NOT_PUBLISHED")


def test_wiener_nonwork_all_relationships_audited_and_staged_with_evidence():
    audit = load("wiener-staatsoper-programme-nonwork-audit.json")
    staging = load("wiener-staatsoper-programme-cleanup-staging.json")
    assert audit["relationships_source_audited"] == 80
    assert sum(audit["classification_counts"].values()) == 80
    assert len(staging["cleanup_relationships"]) == 80
    for item in staging["cleanup_relationships"]:
        assert item["classification"] in {
            "EVENT_TITLE_AS_WORK",
            "EVENT_FORMAT_AS_WORK",
            "PERSON_OR_RECITAL_HEADING_AS_WORK",
            "ANNOTATION_AS_WORK",
        }
        assert item["source_url"] and item["official_evidence"]
        assert set(item) >= {"event_id", "work_id", "programme_order"}


def test_zauberfloete_is_closed_and_both_events_retained():
    audit = load("wiener-staatsoper-zauberfloete-duplicate-audit.json")
    assert audit["status"] == "CLOSED"
    assert audit["classification"] == "TWO_REAL_PERFORMANCES"
    assert len(audit["retained_event_ids"]) == 2


def test_global_safety_contract():
    for name in [
        "auditorio-room-identity-audit.json",
        "auditorio-room-duplicate-cleanup-staging.json",
        "wiener-staatsoper-start-time-audit-2026-27.json",
        "wiener-staatsoper-start-time-staging-2026-27.json",
        "wiener-staatsoper-programme-nonwork-audit.json",
        "wiener-staatsoper-programme-cleanup-staging.json",
        "wiener-staatsoper-zauberfloete-duplicate-audit.json",
    ]:
        assert load(name)["database_writes"] == 0
