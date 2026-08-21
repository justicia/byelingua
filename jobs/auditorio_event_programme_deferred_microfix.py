import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from auditorio_event_programme_deferred_resolution import build_apply, build_validation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "global-entities"

SUMMARY = OUT / "auditorio-event-programme-deferred-resolution-summary.json"
CURRENT = OUT / "auditorio-event-programme-deferred-current-state.json"
DESIRED = OUT / "auditorio-event-programme-deferred-desired-state.json"
BACKLOG = OUT / "auditorio-event-programme-final-residual-backlog.json"

MESSIAEN_OLD = "3a0a42ca-35d0-4a2d-b273-58ab01bde2b5"
MESSIAEN_NEW = "21e99c87-798c-412d-9f9d-9e95e788dfc5"
BRITTEN_BAD = "b78744eb-51b9-48e3-9f44-ffd939c7d215"
BRITTEN_GOOD = "8c31da8d-1038-4117-9ee9-486132c25df0"
LA_FLAUTA = "18999bca-ba78-4658-b63d-123701cdcd60"
MOVE_BACK = {
    "072264f4-b6b0-44f5-9bd6-4c711f6f8e30": "canonical_master_defect_review",
    "bf7d7437-5c71-4911-a5d6-a0beb8078af6": "parser_structure_unresolved",
}
MESSIAEN_EVENTS = {
    "0f78b159-c511-4a60-b976-ebabf9217d1e",
    "642c41c0-723c-4d11-98f5-8ac7d0f9f2a6",
    "e7b0abe1-be1f-442f-a954-925be3dd920f",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    summary = load(SUMMARY)
    current_doc = load(CURRENT)
    desired_doc = load(DESIRED)
    backlog_doc = load(BACKLOG)

    assert summary["second_batch_deterministic_events"] == 13
    assert summary["current_rows"] == 81
    assert summary["desired_rows"] == 45
    assert summary["baseline"]["auditorio_event_programme"] == 2862

    deterministic = [x for x in summary["second_batch_event_ids"] if x not in MOVE_BACK]
    current = [r for r in current_doc["rows"] if r["event_id"] in deterministic]
    desired = [dict(r) for r in desired_doc["rows"] if r["event_id"] in deterministic]

    for row in desired:
        if row["event_id"] in MESSIAEN_EVENTS and row["work_id"] == MESSIAEN_OLD:
            row["work_id"] = MESSIAEN_NEW
        if row["event_id"] == "724a01df-5cdd-4ae3-b04d-639f620e54da" and row["work_id"] == BRITTEN_BAD:
            row["work_id"] = BRITTEN_GOOD

    desired = [r for r in desired if r["event_id"] != "b6261109-846e-4d47-b6cb-2cbc3bb4455b"]
    desired.append({
        "event_id": "b6261109-846e-4d47-b6cb-2cbc3bb4455b",
        "order": 1,
        "work_id": LA_FLAUTA,
        "source_occurrence_id": "auditorio_nacional:performance:247",
        "raw_title": "La Flauta Mágica",
        "canonical_work_title": "La Flauta Mágica",
    })
    desired.sort(key=lambda r: (r["event_id"], int(r["order"])))

    assert len(deterministic) == 11
    assert len(current) == 69
    assert len(desired) == 36
    assert not any(r["event_id"] in MOVE_BACK for r in current + desired)
    assert not any(r["work_id"] == MESSIAEN_OLD for r in desired if r["event_id"] in MESSIAEN_EVENTS)
    assert not any(r["work_id"] == BRITTEN_BAD for r in desired if r["event_id"] == "724a01df-5cdd-4ae3-b04d-639f620e54da")
    assert [r for r in desired if r["event_id"] == "b6261109-846e-4d47-b6cb-2cbc3bb4455b"] == [next(r for r in desired if r["event_id"] == "b6261109-846e-4d47-b6cb-2cbc3bb4455b")]
    assert len({(r["event_id"], r["work_id"]) for r in desired}) == len(desired)

    baseline = summary["baseline"]
    after = baseline["auditorio_event_programme"] - len(current) + len(desired)
    assert after == 2829
    rows = list(backlog_doc["events"])
    existing = {x["event_id"] for x in rows}
    for eid, reason in MOVE_BACK.items():
        if eid in existing:
            for x in rows:
                if x["event_id"] == eid:
                    x["bucket"] = "FINAL_RESIDUAL_BACKLOG"; x["primary_reason"] = reason
        else:
            rows.append({"event_id": eid, "bucket": "FINAL_RESIDUAL_BACKLOG", "primary_reason": reason, "priority": "P1", "review_row_count": 0})
    rows.sort(key=lambda x: x["event_id"])

    new_summary = dict(summary)
    new_summary.update({
        "second_batch_deterministic_events": 11,
        "final_residual_backlog_events": len(rows),
        "second_batch_event_ids": deterministic,
        "current_rows": len(current),
        "desired_rows": len(desired),
        "rows_deleted": len(current),
        "rows_inserted": len(desired),
        "expected_after": after,
        "same_event_same_work_duplicates": 0,
        "microfix_applied": {
            "messiaen_work_replacements": sorted(MESSIAEN_EVENTS),
            "britten_work_replacement": "724a01df-5cdd-4ae3-b04d-639f620e54da",
            "b6261109_programme_work": LA_FLAUTA,
            "moved_back_to_residual": MOVE_BACK,
        },
        "database_writes": 0,
        "no_sql_executed": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
    (SUMMARY).write_text(json.dumps(new_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (CURRENT).write_text(json.dumps({**current_doc, "baseline": baseline, "rows": current, "database_writes": 0}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DESIRED).write_text(json.dumps({**desired_doc, "rows": desired, "database_writes": 0}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (BACKLOG).write_text(json.dumps({**backlog_doc, "events": rows, "database_writes": 0}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "auditorio-event-programme-deferred-cleanup-production-apply.sql").write_text(build_apply(current, desired, deterministic, baseline, len(current), len(desired), after), encoding="utf-8")
    (OUT / "auditorio-event-programme-deferred-cleanup-production-validation.sql").write_text(build_validation(desired, deterministic, baseline, len(current), len(desired), after), encoding="utf-8")
    print(json.dumps({"deterministic_events": 11, "current_rows": 69, "desired_rows": 36, "expected_after": 2829, "database_writes": 0, "no_sql_executed": True}, indent=2))


if __name__ == "__main__":
    main()
