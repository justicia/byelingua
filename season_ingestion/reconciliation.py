from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable


VENUE_SOURCES = {
    "wiener_staatsoper": "wiener_staatsoper",
    "operadeparis": "operadeparis",
    "philharmonie_paris": "philharmonie_paris",
    "teatro_real": "teatro_real",
    "auditorio_nacional": "auditorio_nacional",
}


@dataclass(frozen=True)
class ExistingRecord:
    event_id: str
    source: str
    source_event_id: str | None
    source_url: str | None
    event_key: str | None
    title: str | None
    date: str | None
    fields: dict[str, Any] = field(default_factory=dict)


MUTABLE_EVENT_FIELDS = ("organization", "venue", "city", "country", "timezone", "title", "date", "start_time", "end_time", "room", "event_type", "classification", "data_quality", "normalization_status", "verification_status", "credits", "programme", "artists")
COLLECTION_FIELDS = {"credits", "programme", "artists"}
QUALITY_RANK = {"incomplete_source_data": 0, "review_required": 0, "source_verified": 1, "canonical_verified": 2, "human_confirmed": 3, "manually_confirmed": 3}


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _summary(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return f"{type(value).__name__}(len={len(value)})"
    text = str(value)
    return text if len(text) <= 80 else text[:77] + "..."


def _status(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("verification_status", "normalization_status", "status"):
            if value.get(key):
                return str(value[key]).lower()
    if isinstance(value, list):
        statuses = [_status(item) for item in value]
        statuses = [item for item in statuses if item]
        return min(statuses, key=lambda item: QUALITY_RANK.get(item, 1)) if statuses else None
    if isinstance(value, str):
        lowered = value.lower()
        return lowered if lowered in QUALITY_RANK else None
    return None


def _quality_downgrade(old: Any, new: Any) -> bool:
    old_status, new_status = _status(old), _status(new)
    return bool(old_status and new_status and QUALITY_RANK.get(new_status, 1) < QUALITY_RANK.get(old_status, 1))


def _field_value(item: ExistingRecord, name: str) -> Any:
    if name in item.fields:
        return item.fields[name]
    return getattr(item, name, None)


def field_update_plan(row: dict[str, Any], existing: ExistingRecord, *, url_conflict: bool = False) -> dict[str, Any]:
    """Decide safe field changes without changing database identity fields."""
    stats = {"unchanged": 0, "fill_missing": 0, "change_nonempty": 0, "protected_from_null_overwrite": 0, "protected_from_quality_downgrade": 0, "blocked_field_conflicts": 0}
    payload: dict[str, Any] = {}
    changes: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for name in MUTABLE_EVENT_FIELDS:
        if name not in row:
            continue
        old, new = _field_value(existing, name), row.get(name)
        if old == new:
            stats["unchanged"] += 1
        elif _empty(new) and not _empty(old):
            stats["protected_from_null_overwrite"] += 1
        elif not _empty(new) and _empty(old):
            if name not in COLLECTION_FIELDS:
                payload[name] = new
            stats["fill_missing"] += 1
        elif _quality_downgrade(old, new) or (name in COLLECTION_FIELDS and _status(row.get("data_quality")) in {"incomplete_source_data", "review_required"}):
            stats["protected_from_quality_downgrade"] += 1
            stats["blocked_field_conflicts"] += 1
            blocked.append({"field": name, "reason": "staging quality would downgrade existing data", "old_value_summary": _summary(old), "new_value_summary": _summary(new)})
        else:
            if name not in COLLECTION_FIELDS:
                payload[name] = new
            stats["change_nonempty"] += 1
            changes.append({"source": row.get("source"), "source_event_id": row.get("source_event_id"), "event_id": existing.event_id, "field": name, "old_value_summary": _summary(old), "new_value_summary": _summary(new)})

    source_url = None
    if row.get("source_url") != existing.source_url:
        if _empty(row.get("source_url")) and not _empty(existing.source_url):
            stats["protected_from_null_overwrite"] += 1
        elif url_conflict:
            stats["blocked_field_conflicts"] += 1
            blocked.append({"field": "source_url", "reason": "source URL conflict", "old_value_summary": _summary(existing.source_url), "new_value_summary": _summary(row.get("source_url"))})
        elif not _empty(row.get("source_url")):
            source_url = row["source_url"]
            stats["change_nonempty"] += 1
            changes.append({"source": row.get("source"), "source_event_id": row.get("source_event_id"), "event_id": existing.event_id, "field": "source_url", "old_value_summary": _summary(existing.source_url), "new_value_summary": _summary(source_url)})
    return {"payload": payload, "source_url": source_url, "stats": stats, "changes": changes, "blocked": blocked}


def reconcile(staging: Iterable[dict[str, Any]], existing: Iterable[ExistingRecord], venue: str) -> dict[str, Any]:
    staged = list(staging)
    current = list(existing)
    by_identity: dict[tuple[str, str], list[ExistingRecord]] = defaultdict(list)
    by_url: dict[str, list[ExistingRecord]] = defaultdict(list)
    for item in current:
        if item.source_event_id:
            by_identity[(item.source, item.source_event_id)].append(item)
        if item.source_url:
            by_url[item.source_url].append(item)

    staged_identity_counts: dict[tuple[str, str], int] = defaultdict(int)
    staged_by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in staged:
        identity = (str(row.get("source") or ""), str(row.get("source_event_id") or ""))
        if identity[0] and identity[1]:
            staged_identity_counts[identity] += 1
        if row.get("source_url"):
            staged_by_url[str(row["source_url"])].append(row)

    anomalies: list[dict[str, Any]] = []
    for identity, count in staged_identity_counts.items():
        if count > 1:
            anomalies.append({"type": "staging_source_identity_duplicate", "source": identity[0], "source_event_id": identity[1], "count": count})
    for identity, matches in by_identity.items():
        if len({item.event_id for item in matches}) > 1:
            anomalies.append({"type": "source_identity_one_to_many", "source": identity[0], "source_event_id": identity[1], "event_ids": sorted({item.event_id for item in matches})})

    matched_event_ids: set[str] = set()
    counts = {key: 0 for key in ("source_identity_matches", "source_url_only_matches", "one_to_many_conflicts", "many_to_one_conflicts", "safe_update", "safe_insert", "must_reconcile", "manual_review")}
    field_stats = {key: 0 for key in ("unchanged", "fill_missing", "change_nonempty", "protected_from_null_overwrite", "protected_from_quality_downgrade", "blocked_field_conflicts")}
    field_changes: list[dict[str, Any]] = []
    blocked_field_conflicts: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for row in staged:
        source = str(row.get("source") or "")
        source_event_id = str(row.get("source_event_id") or "")
        identity_matches = by_identity.get((source, source_event_id), []) if source and source_event_id else []
        url_matches = by_url.get(str(row.get("source_url")), []) if row.get("source_url") else []
        reason: str | None = None
        if staged_identity_counts[(source, source_event_id)] > 1:
            counts["many_to_one_conflicts"] += 1
            reason = "staging source identity maps to multiple staging events"
        elif len({item.event_id for item in identity_matches}) > 1:
            counts["one_to_many_conflicts"] += 1
            reason = "existing source identity maps to multiple events"
        elif len(identity_matches) == 1:
            existing_item = identity_matches[0]
            matched_event_ids.add(existing_item.event_id)
            counts["source_identity_matches"] += 1
            if not existing_item.event_key:
                counts["must_reconcile"] += 1
                reason = "existing record is missing event_key"
            elif url_matches and {item.event_id for item in url_matches} != {existing_item.event_id}:
                counts["manual_review"] += 1
                reason = "source URL exists with a different identity"
            else:
                plan = field_update_plan(row, existing_item)
                for key, value in plan["stats"].items():
                    field_stats[key] += value
                field_changes.extend(plan["changes"])
                blocked_field_conflicts.extend(plan["blocked"])
                if plan["blocked"]:
                    counts["manual_review"] += 1
                    reason = "field update would downgrade existing data"
                else:
                    counts["safe_update"] += 1
        elif url_matches:
            counts["source_url_only_matches"] += 1
            counts["manual_review"] += 1
            reason = "source URL matches but source identity does not"
        else:
            counts["safe_insert"] += 1

        if reason:
            details.append({"source_event_id": row.get("source_event_id"), "title": row.get("title"), "date": row.get("date"), "reason": reason})

    missing_event_keys = sum(1 for item in current if not item.event_key)
    unmatched_existing = len(set(item.event_id for item in current) - matched_event_ids)
    counts["must_reconcile"] += missing_event_keys
    if unmatched_existing:
        anomalies.append({"type": "existing_records_unmatched_to_staging", "count": unmatched_existing})
        counts["must_reconcile"] += unmatched_existing
    for url, url_rows in staged_by_url.items():
        identities = {(str(row.get("source") or ""), str(row.get("source_event_id") or "")) for row in url_rows}
        existing_identities = {(item.source, item.source_event_id) for item in by_url.get(url, [])}
        if existing_identities and identities and identities != existing_identities:
            anomalies.append({"type": "source_url_identity_collision", "source_url": url, "staging_identities": sorted(identities), "existing_identities": sorted(existing_identities)})

    coverage: dict[str, Any] = {}
    if venue == "teatro_real":
        monthly: dict[str, int] = defaultdict(int)
        for item in current:
            if item.date and len(item.date) >= 7:
                monthly[item.date[:7]] += 1
        coverage = {"monthly_dates": dict(sorted(monthly.items())), "records_after_2027_02_19": sum(1 for item in current if item.date and item.date > "2027-02-19")}

    collision_guard_blocked = bool(anomalies or counts["manual_review"] or counts["must_reconcile"] or counts["one_to_many_conflicts"] or counts["many_to_one_conflicts"] or field_stats["blocked_field_conflicts"])
    return {
        "venue": venue,
        "source": VENUE_SOURCES[venue],
        "existing_records": len(current),
        "staging_records": len(staged),
        "existing_missing_event_key": missing_event_keys,
        "counts": counts,
        "field_stats": field_stats,
        "field_changes": field_changes,
        "blocked_field_conflicts": blocked_field_conflicts,
        "anomalies": anomalies,
        "review_events": details,
        "teatro_real_coverage": coverage,
        "collision_guard_blocked": collision_guard_blocked,
    }
