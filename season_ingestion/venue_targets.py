from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


TARGETS_PATH = Path(__file__).with_name("venue_targets.yml")
SCHEMA_VERSION = "venue-onboarding-targets-v1"
_PENDING_ONBOARDING_STATUSES = {
    "PENDING",
    "TARGET_REGISTERED",
    "PUBLISHED",
    "PARTIALLY_PUBLISHED",
    "REVIEW_REQUIRED",
    "HUMAN_PDF_REQUIRED",
}


def target_requires_processing(target: dict[str, Any]) -> bool:
    """Return whether a target still belongs in the one-click processing queue.

    Production visibility is not a completion signal.  Explicit target state
    wins when present; legacy targets retain the original onboarding-status
    behavior until their processing state is recorded.
    """
    if target.get("processing_complete") is True:
        return False
    if target.get("requires_processing") is True:
        return True
    return str(target.get("onboarding_status") or "").strip().upper() in _PENDING_ONBOARDING_STATUSES


def load_targets(path: Path = TARGETS_PATH, *, season: str | None = None, scope: str = "all-enabled", selected: list[str] | None = None) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported venue target schema")
    targets = payload.get("targets")
    if not isinstance(targets, list):
        raise ValueError("venue targets must be a list")
    ids = [str(item.get("venue_id", "")) for item in targets]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("venue target venue_id values must be unique")
    if "munich_bayerische_staatsoper" in ids:
        raise ValueError("legacy Munich alias must not be a factory target")
    result = []
    for target in targets:
        if not target.get("enabled", False):
            continue
        if season and target.get("season") != season:
            continue
        if scope == "pending" and not target_requires_processing(target):
            continue
        if scope == "selected" and target.get("venue_id") not in set(selected or []):
            continue
        result.append(dict(target))
    if scope not in {"all-enabled", "pending", "selected"}:
        raise ValueError("scope must be all-enabled, pending, or selected")
    return result


def matrix_targets(targets: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"venue_id": str(target["venue_id"]), "season": str(target["season"])} for target in targets]
