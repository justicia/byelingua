"""Deterministic, non-sensitive source fingerprints for incremental ingestion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


SOURCE_STATE_SCHEMA_VERSION = "europe-auto-ingestion-source-state-v1"

# Only source facts participate in the fingerprint.  In particular, Global
# Master rows, resolved UIDs, credentials, and raw HTML are intentionally not
# part of this state file.
_EVENT_FIELDS = (
    "event_key", "source", "source_event_id", "source_url", "organization",
    "venue", "city", "country", "timezone", "title", "date", "start_time",
    "end_time", "room", "event_type", "classification",
)
_PROGRAMME_FIELDS = (
    "source_title", "composer", "source_programme_index",
    "original_programme_order", "resolution_status", "resolution_reason",
)
_CREDIT_FIELDS = (
    "artist_name", "character", "function", "source_role", "credit_kind",
    "voice_type", "source_url", "source_field", "source_event_id",
)
_PROVENANCE_FIELDS = ("source_url", "source_field", "source_event_id")


def _pick(row: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: row.get(field) for field in fields if field in row}


def _source_event_facts(event: Any) -> dict[str, Any]:
    row = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    programme = []
    for item in row.get("programme") or []:
        item = dict(item)
        programme.append({
            **_pick(item, _PROGRAMME_FIELDS),
            "provenance": _pick(dict(item.get("provenance") or {}), _PROVENANCE_FIELDS),
        })
    credits = []
    for credit in row.get("credits") or []:
        credit = dict(credit)
        credits.append({
            **_pick(credit, _CREDIT_FIELDS),
            "provenance": _pick(dict(credit.get("provenance") or {}), _PROVENANCE_FIELDS),
        })
    return {**_pick(row, _EVENT_FIELDS), "programme": programme, "credits": credits}


def source_fingerprint(events: Iterable[Any]) -> str:
    """Return a stable SHA-256 over canonical official source facts."""
    facts = [_source_event_facts(event) for event in events]
    facts.sort(key=lambda row: (str(row.get("event_key") or ""), str(row.get("source_url") or "")))
    encoded = json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_source_state(path: Path) -> dict[str, str]:
    """Read the ephemeral hash state; malformed state safely means no prior run."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}
    if not isinstance(payload, dict) or payload.get("schema_version") != SOURCE_STATE_SCHEMA_VERSION:
        return {}
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in entries.items()
        if isinstance(key, str) and isinstance(value, str) and value
    }


def save_source_state(path: Path, entries: dict[str, str]) -> None:
    """Persist only venue-season source hashes in the runner workspace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SOURCE_STATE_SCHEMA_VERSION,
        "entries": {key: entries[key] for key in sorted(entries)},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def state_key(venue_id: str, season: str) -> str:
    return f"{venue_id}|{season}"


def compare_source_fingerprint(previous: str | None, current: str | None) -> dict[str, Any]:
    changed = not previous or not current or previous != current
    return {
        "source_changed": changed,
        "previous_source_hash": previous,
        "current_source_hash": current,
        "action": "PROCESS" if changed else "NOOP",
    }
