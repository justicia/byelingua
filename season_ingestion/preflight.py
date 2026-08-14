from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import os
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SUPPORTED_VENUES = {
    "wiener_staatsoper",
    "operadeparis",
    "philharmonie_paris",
    "teatro_real",
}
RISK_ONLY_VENUES = {"auditorio_nacional"}


@dataclass(frozen=True)
class ExistingSource:
    event_id: str
    event_key: str | None
    source: str | None
    source_event_id: str | None
    source_url: str | None
    title: str | None
    date: str | None


def _text(value: Any) -> str | None:
    value = "" if value is None else str(value).strip()
    return value or None


def _existing(row: dict[str, Any]) -> ExistingSource:
    event = row.get("events") or {}
    if isinstance(event, list):
        event = event[0] if event else {}
    return ExistingSource(
        event_id=str(row.get("event_id") or ""),
        event_key=_text(row.get("event_key") or event.get("event_key")),
        source=_text(row.get("source")),
        source_event_id=_text(row.get("source_event_id")),
        source_url=_text(row.get("source_url")),
        title=_text(row.get("title") or event.get("title")),
        date=_text(row.get("date") or event.get("date")),
    )


def fetch_existing_sources() -> list[ExistingSource]:
    """Read event provenance only; this function never issues a write request."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_READONLY_KEY")
    if not url or not key:
        raise RuntimeError("preflight requires SUPABASE_URL and SUPABASE_READONLY_KEY")
    params = urlencode({"select": "event_id,source,source_event_id,source_url,events!inner(event_key,title,date)", "limit": "10000"})
    request = Request(f"{url}/rest/v1/event_sources?{params}", headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urlopen(request, timeout=60) as response:
        return [_existing(row) for row in json.load(response)]


def _fingerprint(row: dict[str, Any]) -> tuple[Any, ...]:
    return (row.get("title"), row.get("date"), row.get("start_time"), row.get("end_time"), row.get("room"))


def reconcile(venue: str, staging: Iterable[dict[str, Any]], existing: Iterable[ExistingSource]) -> dict[str, Any]:
    rows = list(staging)
    current = list(existing)
    by_identity: dict[tuple[str, str], list[ExistingSource]] = defaultdict(list)
    by_key: dict[str, list[ExistingSource]] = defaultdict(list)
    for item in current:
        if item.source and item.source_event_id:
            by_identity[(item.source, item.source_event_id)].append(item)
        if item.event_key:
            by_key[item.event_key].append(item)

    staging_identity_counts: dict[tuple[str, str], int] = defaultdict(int)
    staging_key_identities: dict[str, set[tuple[str | None, str | None]]] = defaultdict(set)
    for row in rows:
        identity = (_text(row.get("source")), _text(row.get("source_event_id")))
        if identity[0] and identity[1]:
            staging_identity_counts[identity] += 1
        if _text(row.get("event_key")):
            staging_key_identities[_text(row["event_key"])].add(identity)

    result: dict[str, Any] = {
        "venue": venue,
        "counts": {status: 0 for status in ("inserted", "updated", "unchanged", "quarantined", "ambiguous")},
        "events": [],
        "duplicate_anomalies": [],
        "apply_blocked": False,
    }

    for identity, count in staging_identity_counts.items():
        if count > 1:
            result["duplicate_anomalies"].append({"type": "duplicate_source_event_id_in_staging", "source": identity[0], "source_event_id": identity[1], "count": count})
    for key, identities in staging_key_identities.items():
        if len(identities) > 1:
            result["duplicate_anomalies"].append({"type": "event_key_has_multiple_source_identities", "event_key": key, "identities": sorted(identities)})
    for identity, matches in by_identity.items():
        if len(matches) > 1:
            result["duplicate_anomalies"].append({"type": "duplicate_source_identity_in_existing", "source": identity[0], "source_event_id": identity[1], "count": len(matches)})
        if len({item.event_id for item in matches}) > 1:
            result["duplicate_anomalies"].append({"type": "source_identity_maps_to_multiple_events", "source": identity[0], "source_event_id": identity[1], "event_ids": sorted({item.event_id for item in matches})})
    for key, matches in by_key.items():
        identities = {(item.source, item.source_event_id) for item in matches}
        if len(identities) > 1:
            result["duplicate_anomalies"].append({"type": "event_key_has_multiple_source_identities_in_existing", "event_key": key, "identities": sorted(identities)})

    for row in rows:
        source = _text(row.get("source"))
        source_event_id = _text(row.get("source_event_id"))
        event_key = _text(row.get("event_key"))
        reason: str | None = None
        status: str
        match: ExistingSource | None = None

        if venue in RISK_ONLY_VENUES:
            status, reason = "quarantined", "risk_only_venue_not_eligible_for_apply"
        elif venue not in SUPPORTED_VENUES:
            status, reason = "quarantined", "venue_not_in_preflight_scope"
        elif not source or not source_event_id:
            status, reason = "quarantined", "missing_source_identity"
        elif staging_identity_counts[(source, source_event_id)] > 1:
            status, reason = "ambiguous", "duplicate_source_identity_in_staging"
        elif event_key and len(staging_key_identities[event_key]) > 1:
            status, reason = "ambiguous", "event_key_has_multiple_source_identities"
        else:
            identity_matches = by_identity.get((source, source_event_id), [])
            event_ids = {item.event_id for item in identity_matches}
            if len(event_ids) > 1:
                status, reason = "ambiguous", "source_identity_maps_to_multiple_events"
            elif len(event_ids) == 1:
                match = identity_matches[0]
            elif event_key:
                key_matches = by_key.get(event_key, [])
                key_event_ids = {item.event_id for item in key_matches}
                key_identities = {(item.source, item.source_event_id) for item in key_matches}
                if len(key_event_ids) == 1 and len(key_identities) <= 1 and (not key_matches[0].source_event_id or key_identities == {(source, source_event_id)}):
                    match = key_matches[0]
                elif key_matches:
                    status, reason = "ambiguous", "event_key_not_strictly_one_to_one"

            if reason is None:
                if match is None:
                    status = "inserted"
                elif _fingerprint(row) == (match.title, match.date, row.get("start_time"), row.get("end_time"), row.get("room")):
                    status = "unchanged"
                else:
                    status = "updated"

        if venue == "wiener_staatsoper" and row.get("date") == "2027-02-05" and "zauberfl" in str(row.get("title", "")).lower():
            status, reason = "quarantined", "review_required_wiener_2027_02_05_do_not_delete"

        result["counts"][status] += 1
        if status in {"ambiguous", "quarantined"}:
            result["events"].append({"source_event_id": source_event_id, "title": row.get("title"), "date": row.get("date"), "status": status, "reason": reason})

    result["apply_blocked"] = bool(result["counts"]["ambiguous"] or result["counts"]["quarantined"] or result["duplicate_anomalies"])
    return result
