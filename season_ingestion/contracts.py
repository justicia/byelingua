from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from datetime import date as date_type
import re
from typing import Any, Iterable, Mapping

from .unicode_integrity import validate_unicode_integrity


ENTITY_KINDS = ("composer", "artist", "work", "character")
STAGES = ("source_audit", "raw", "normalized", "snapshot", "resolution_staging", "final_staging")
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class GlobalEntitySnapshot:
    generated_at: str
    source: str
    freshness_seconds: int | None
    entities: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    composer_aliases: list[dict[str, Any]] = field(default_factory=list)
    work_aliases: list[dict[str, Any]] = field(default_factory=list)
    artist_aliases: list[dict[str, Any]] = field(default_factory=list)
    character_aliases: list[dict[str, Any]] = field(default_factory=list)
    work_characters: list[dict[str, Any]] = field(default_factory=list)
    health: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.generated_at or not self.source:
            raise ValueError("global snapshot requires generated_at and source")
        unknown = set(self.entities) - set(ENTITY_KINDS)
        if unknown:
            raise ValueError(f"unknown global entity kinds: {sorted(unknown)}")


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def validate_programme(programme: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in programme]
    for expected, row in enumerate(rows, start=1):
        _require_text(row.get("source_title"), "programme.source_title")
        order = row.get("source_programme_index", row.get("raw_programme_index"))
        if order != expected:
            raise ValueError("programme order must be contiguous and 1-based")
        if row.get("original_programme_order") != expected:
            raise ValueError("original_programme_order must preserve source order")
        row.setdefault("resolution_status", "review_required")
        row.setdefault("resolution_reason", "global matcher not yet approved")
    return rows


def validate_canonical_event(event: Any) -> None:
    event.validate()
    validate_unicode_integrity(event.to_dict())
    validate_programme(event.programme)
    for credit in event.credits:
        if not isinstance(credit, Mapping):
            raise ValueError("credits must be objects")
        if credit.get("credit_kind") in {"cast", "character"} and credit.get("function") in {
            "conductor", "director", "orchestra", "chorus", "designer"
        }:
            raise ValueError("artistic team credit contaminated cast/character boundary")


def schedule_integrity_report(events: Iterable[Any]) -> dict[str, int]:
    """Validate deterministic schedule identity without resolving master data."""
    rows = [event.to_dict() if hasattr(event, "to_dict") else dict(event) for event in events]
    report = {key: 0 for key in (
        "duplicate_event_identity", "duplicate_performance_slot", "null_timed_shadow_duplicates",
        "ambiguous_same_day_occurrence", "year_inferred_without_production_evidence", "year_unverified",
        "untraceable_source", "invalid_date", "invalid_time", "missing_venue", "missing_organization",
    )}
    event_keys: set[str] = set()
    slots: set[tuple[str, str, str, str, str | None]] = set()
    days: defaultdict[tuple[str, str, str, str], set[str | None]] = defaultdict(set)
    for row in rows:
        event_key = str(row.get("event_key") or "")
        if event_key in event_keys:
            report["duplicate_event_identity"] += 1
        if event_key:
            event_keys.add(event_key)
        organization = str(row.get("organization") or "")
        venue = str(row.get("venue") or "")
        title = str(row.get("title") or row.get("production_title") or "")
        event_date = row.get("date")
        start_time = row.get("start_time")
        if not organization:
            report["missing_organization"] += 1
        if not venue:
            report["missing_venue"] += 1
        if not str(row.get("source_url") or "").strip():
            report["untraceable_source"] += 1
        try:
            date_type.fromisoformat(str(event_date))
        except (TypeError, ValueError):
            report["invalid_date"] += 1
        if start_time is not None and not _TIME_RE.fullmatch(str(start_time)):
            report["invalid_time"] += 1
        slot = (organization, venue, title, str(event_date), start_time)
        if slot in slots:
            report["duplicate_performance_slot"] += 1
        slots.add(slot)
        days[(organization, venue, title, str(event_date))].add(start_time)
        schedule = row.get("data_quality", {}).get("schedule", {}) if isinstance(row.get("data_quality"), dict) else {}
        if schedule.get("year_status") == "YEAR_UNVERIFIED":
            report["year_unverified"] += 1
        if schedule.get("year_inferred_without_production_evidence"):
            report["year_inferred_without_production_evidence"] += 1
    for times in days.values():
        if None in times and any(value is not None for value in times):
            report["null_timed_shadow_duplicates"] += 1
        if len({value for value in times if value is not None}) > 1:
            continue
        if len(times) > 1 and None not in times:
            report["ambiguous_same_day_occurrence"] += 1
    return report


def validate_schedule_integrity(events: Iterable[Any]) -> dict[str, int]:
    """Return contract counters and raise for malformed schedule fields."""
    report = schedule_integrity_report(events)
    hard_shape_failures = {key: value for key, value in report.items() if key in {
        "invalid_date", "invalid_time", "missing_venue", "missing_organization"
    } and value}
    if hard_shape_failures:
        raise ValueError(f"event schedule contract violation: {hard_shape_failures}")
    return report


def empty_global_snapshot(generated_at: str) -> GlobalEntitySnapshot:
    snapshot = GlobalEntitySnapshot(
        generated_at=generated_at,
        source="read-only-empty-fallback",
        freshness_seconds=0,
        entities={kind: [] for kind in ENTITY_KINDS},
        health={
            "preflight_status": "FAIL",
            "global_master_loaded": False,
            "project_target_verified": False,
            "composers_count": 0,
            "composer_aliases_count": 0,
            "works_count": 0,
            "work_aliases_count": 0,
            "loaded_at": generated_at,
            "query_errors": 1,
            "error_code": "GLOBAL_MASTER_UNAVAILABLE",
        },
    )
    snapshot.validate()
    return snapshot
