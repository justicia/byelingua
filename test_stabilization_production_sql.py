from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent / "artifacts" / "stabilization"


def sql(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_paris_sql_is_scoped_and_guarded():
    apply = sql("paris-opera-event-type-production-apply.sql")
    assert apply.count("UPDATE public.events") == 1
    assert "o.slug='opera-national-de-paris'" in apply
    assert "paris-opera" not in apply
    assert "506" in apply
    for n in (207, 43, 69, 177, 1, 9):
        assert str(n) in apply
    assert "event_type" in apply and "start_time" not in apply


def test_auditorio_sql_has_orphan_and_dependency_guards():
    apply = sql("auditorio-orphan-production-apply.sql")
    assert "ab000640-fb8e-43ba-850b-c3da076f00b9" in apply
    assert "f6778b5d-1f92-4089-b5cb-1567f47c3da5" in apply
    for table in ("event_sources", "event_programme", "event_credits", "user_event_relations", "schedule_events"):
        assert table in apply
    assert apply.count("DELETE FROM public.events") == 1
    assert "SELECT e.* INTO candidate" in apply
    assert "SELECT e.* INTO survivor" in apply
    assert "auditorio-nacional-inaem" in apply
    assert "ROW_COUNT" in apply and "<>1" in apply
    duplicate = sql("auditorio-duplicate-production-apply.sql")
    assert "DELETE FROM public.events" not in duplicate
    assert "44" in duplicate and "DEPENDENCY_MERGE_REQUIRED" in duplicate


def test_wiener_programme_sql_only_deletes_relationships():
    apply = sql("wiener-staatsoper-programme-cleanup-production-apply.sql")
    assert apply.count("DELETE FROM public.event_programme") == 1
    assert "DELETE FROM public.works" not in apply
    assert "UPDATE public.works" not in apply
    assert "count(*) FROM _wiener_programme_targets)<>80" in apply
    assert "count(DISTINCT work_id) FROM _wiener_programme_targets)<>25" in apply
    assert "o.slug<>'wiener-staatsoper'" in apply
    assert "ROW_COUNT expected 80" in apply
    assert apply.count("::uuid") >= 160


def test_wiener_time_sql_is_null_guarded_and_start_time_only():
    apply = sql("wiener-staatsoper-start-time-production-apply.sql")
    assert apply.count("UPDATE public.events") == 1
    assert "SET start_time" in apply
    assert "start_time IS NULL" in apply
    assert "count(*) FROM _wiener_time_targets)<>10" in apply
    assert "source_event_id" in apply and "source_url" in apply
    assert "es.source_event_id=t.source_event_id" in apply
    assert "es.source_url=t.source_url" in apply
    assert "ROW_COUNT expected 10" in apply
    assert "e.start_time IS DISTINCT FROM t.start_time" in apply
    assert "<>302" in apply
    assert "end_time" not in apply
    assert "timezone" not in apply


def test_all_apply_files_are_transactional_and_non_executed_here():
    names = [
        "paris-opera-event-type-production-apply.sql",
        "auditorio-orphan-production-apply.sql",
        "wiener-staatsoper-programme-cleanup-production-apply.sql",
        "wiener-staatsoper-start-time-production-apply.sql",
    ]
    for name in names:
        text = sql(name)
        assert "BEGIN;" in text and "COMMIT;" in text
        assert "DO NOT EXECUTE" in text
    assert not list(ROOT.glob("*.executed"))


def test_validation_contracts_report_required_post_states():
    assert "opera-national-de-paris" in sql("paris-opera-event-type-production-validation.sql")
    aud = sql("auditorio-orphan-production-validation.sql")
    assert "candidate_count" in aud and "survivor_count" in aud
    prog = sql("wiener-staatsoper-programme-cleanup-production-validation.sql")
    for marker in ("remaining_target_relationships", "target_events_missing", "target_works_missing", "target_events_outside_wiener"):
        assert marker in prog
    assert "target_relationship_count" in prog and "target_distinct_work_count" in prog
    assert "target_events AS (SELECT DISTINCT event_id FROM targets)" in prog
    assert "target_works AS (SELECT DISTINCT work_id FROM targets)" in prog
    assert prog.count("::uuid") == 160
    assert "o.slug IS DISTINCT FROM 'wiener-staatsoper'" in prog
    assert "SELECT 'target_events_outside_wiener',0" not in prog
    time = sql("wiener-staatsoper-start-time-production-validation.sql")
    assert time.count("::uuid") == 10
    assert "target_events_missing" in time and "target_events_outside_wiener" in time
    assert "LEFT JOIN public.events" in time and "LEFT JOIN public.organizations" in time
    assert "incorrect_target_times" in time and "e.start_time IS DISTINCT FROM t.expected_start_time" in time
    assert "remaining_wiener_null_start_time" in time and "302" in time
    assert sum(line.count(";") for line in time.splitlines() if not line.lstrip().startswith("--")) == 1
    assert "checks(check_name,value) AS" in time
    assert "SELECT check_name,value FROM checks" in time
    assert "targets" not in time.split("SELECT check_name,value FROM checks", 1)[1]
