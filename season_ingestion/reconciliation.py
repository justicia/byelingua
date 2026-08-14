from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
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
            elif row.get("event_key") and row["event_key"] != existing_item.event_key:
                counts["manual_review"] += 1
                reason = "source identity matches but event_key differs"
            elif url_matches and {item.event_id for item in url_matches} != {existing_item.event_id}:
                counts["manual_review"] += 1
                reason = "source URL exists with a different identity"
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

    collision_guard_blocked = bool(anomalies or counts["manual_review"] or counts["must_reconcile"] or counts["one_to_many_conflicts"] or counts["many_to_one_conflicts"])
    return {
        "venue": venue,
        "source": VENUE_SOURCES[venue],
        "existing_records": len(current),
        "staging_records": len(staged),
        "existing_missing_event_key": missing_event_keys,
        "counts": counts,
        "anomalies": anomalies,
        "review_events": details,
        "teatro_real_coverage": coverage,
        "collision_guard_blocked": collision_guard_blocked,
    }
