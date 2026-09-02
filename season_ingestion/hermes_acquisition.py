"""Read-only Hermes bridge for eligible deterministic source failures.

This module owns the subprocess boundary only.  It validates the source-facts
contract exported by the worker, converts source observations into the
existing ``CanonicalEvent`` shape, and leaves all shared identity resolution
to the normal pipeline.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from jobs.hermes_acquire_worker import validate_source_facts
from .schema import CanonicalEvent


DEFAULT_TIMEOUT_SECONDS = 900


class HermesAcquisitionError(RuntimeError):
    """A concrete read-only Hermes bridge failure."""


def eligible_for_fallback(*, events: list[Any], adapter: Any, force: bool = False) -> bool:
    """Return true when deterministic acquisition produced no usable events."""
    return bool(force or not events)


def build_request(*, venue: str, season: str, config: dict[str, Any], reason: str) -> dict[str, Any]:
    official_url = config.get("official_source") or config.get("listing_source")
    if not isinstance(official_url, str) or not official_url.strip():
        raise HermesAcquisitionError(f"{venue}: official source URL is not configured")
    return {
        "venue_id": venue,
        "season": season,
        "official_source_url": official_url,
        "source_id": config.get("source_id", venue),
        "organization": config.get("organization"),
        "venue": config.get("venue"),
        "city": config.get("city"),
        "country": config.get("country"),
        "timezone": config.get("timezone"),
        "source_contract": config.get("source_contract", {}),
        "fallback_reason": reason,
    }


def _command_tokens(command: str) -> list[str]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        raise HermesAcquisitionError(f"Hermes command is not parseable: {exc}") from exc
    if not tokens:
        raise HermesAcquisitionError("BYELINGUA_HERMES_ACQUIRE_COMMAND is empty")
    return tokens


def acquire_source_facts(request: dict[str, Any], *, command: str | None = None) -> dict[str, Any]:
    """Invoke the configured worker and validate its stdout contract."""
    command = command if command is not None else os.environ.get("BYELINGUA_HERMES_ACQUIRE_COMMAND", "")
    tokens = _command_tokens(command)
    timeout_seconds = int(os.getenv("BYELINGUA_HERMES_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    try:
        completed = subprocess.run(
            tokens,
            cwd=Path(__file__).resolve().parents[1],
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HermesAcquisitionError(f"Hermes worker timed out after {timeout_seconds}s") from exc
    except OSError as exc:
        raise HermesAcquisitionError(f"Hermes worker could not start: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()
        suffix = f": {detail[-1][:300]}" if detail else ""
        raise HermesAcquisitionError(f"Hermes worker exited with code {completed.returncode}{suffix}")
    try:
        facts = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HermesAcquisitionError(f"Hermes worker stdout is malformed JSON: {exc.msg}") from exc
    try:
        validate_source_facts(facts)
    except Exception as exc:
        raise HermesAcquisitionError(f"Hermes source-facts validation failed: {exc}") from exc
    if not facts["events"]:
        raise HermesAcquisitionError("Hermes source-facts validation failed: events must be non-empty")
    return facts


def facts_to_events(facts: dict[str, Any], *, venue: str, config: dict[str, Any]) -> list[CanonicalEvent]:
    """Convert raw source facts to existing canonical event candidates."""
    validate_source_facts(facts)
    source = str(facts.get("source_id") or config.get("source_id") or venue)
    events: list[CanonicalEvent] = []
    for raw_event in facts["events"]:
        source_url = raw_event["source_url"]
        programme = []
        for row in raw_event["programme"]:
            item = dict(row)
            provenance = dict(item.get("provenance") or {})
            provenance.setdefault("source_url", source_url)
            item["provenance"] = provenance
            programme.append(item)
        credits = []
        for row in raw_event["credits"]:
            item = dict(row)
            item.setdefault("source_url", source_url)
            provenance = dict(item.get("provenance") or {})
            provenance.setdefault("source_url", item["source_url"])
            item["provenance"] = provenance
            credits.append(item)
        quality = dict(raw_event.get("data_quality") or {})
        schedule_quality = dict(quality.get("schedule") or {})
        schedule_quality.setdefault("year_status", "YEAR_EXPLICIT")
        schedule_quality.setdefault("source_field", "hermes.source_facts.date")
        quality["schedule"] = schedule_quality
        programme_quality = dict(quality.get("programme") or {})
        programme_quality.setdefault("status", "PROGRAMME_EVIDENCE_FOUND" if programme else "NO_PROGRAMME_EVIDENCE")
        quality["programme"] = programme_quality
        events.append(
            CanonicalEvent(
                source=source,
                source_event_id=raw_event["source_event_id"],
                source_url=source_url,
                organization=config["organization"],
                venue=config["venue"],
                city=config["city"],
                country=config["country"],
                timezone=config["timezone"],
                title=raw_event["title"],
                date=raw_event["date"],
                start_time=raw_event["start_time"],
                end_time=raw_event.get("end_time"),
                room=raw_event.get("room"),
                event_type=raw_event.get("event_type") or config.get("default_event_type", "performance"),
                classification=raw_event.get("classification") or config.get("default_event_type", "performance"),
                programme=programme,
                credits=credits,
                data_quality=quality,
                raw={
                    "source_facts_schema_version": facts["schema_version"],
                    "source_contract": facts["source_contract"],
                    "source_event": raw_event,
                },
            )
        )
    return events


def acquire_events(*, venue: str, season: str, config: dict[str, Any], reason: str) -> tuple[dict[str, Any], list[CanonicalEvent]]:
    request = build_request(venue=venue, season=season, config=config, reason=reason)
    facts = acquire_source_facts(request)
    return facts, facts_to_events(facts, venue=venue, config=config)
