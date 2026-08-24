from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .unicode_integrity import validate_unicode_integrity


ENTITY_KINDS = ("composer", "artist", "work", "character")
STAGES = ("source_audit", "raw", "normalized", "snapshot", "resolution_staging", "final_staging")


@dataclass(frozen=True)
class GlobalEntitySnapshot:
    generated_at: str
    source: str
    freshness_seconds: int | None
    entities: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    composer_aliases: list[dict[str, Any]] = field(default_factory=list)
    work_aliases: list[dict[str, Any]] = field(default_factory=list)
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
