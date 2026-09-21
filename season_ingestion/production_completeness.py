"""Read, enrich, and stage content gaps from already-published Events.

This module deliberately does not acquire occurrences.  It reads the current
production Event/source identities, selects only Events with missing content
layers, and sends those existing identities through the shared content
recovery and canonical resolution pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .hermes_acquisition import acquire_source_discovery, build_request
from .registry import load_registry
from .schema import CanonicalEvent
from .supabase import ExistingRecord, fetch_existing_sources


class ProductionGapEvent(CanonicalEvent):
    """CanonicalEvent that preserves the already-published event_key."""

    @property
    def event_key(self) -> str:
        raw = self.raw if isinstance(self.raw, dict) else {}
        production_key = raw.get("production_event_key")
        return str(production_key) if isinstance(production_key, str) and production_key.strip() else super().event_key


def _in_filter(values: list[str]) -> str:
    escaped = []
    for value in values:
        text = str(value)
        if all(char.isalnum() or char in "-_.:" for char in text):
            escaped.append(text)
        else:
            escaped.append('"' + text.replace('"', '\\"') + '"')
    return "in.(" + ",".join(escaped) + ")"


def _readonly_rows(
    table: str,
    select: str,
    event_ids: list[str],
    *,
    page_size: int = 500,
    prefer_secret: bool = False,
) -> list[dict[str, Any]]:
    """Read one relationship table without performing any database write."""
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key_name = "SUPABASE_SECRET_KEY" if prefer_secret else "SUPABASE_READONLY_KEY"
    key = os.getenv(key_name, "").strip()
    if not key:
        key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not base_url or not key:
        raise RuntimeError("production completeness scan requires SUPABASE_URL and a read credential")
    if not event_ids:
        return []
    rows: list[dict[str, Any]] = []
    for start in range(0, len(event_ids), page_size):
        batch = event_ids[start:start + page_size]
        query = urlencode({"select": select, "event_id": _in_filter(batch), "limit": str(page_size)})
        request = Request(
            f"{base_url}/rest/v1/{table}?{query}",
            method="GET",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
                if response.status != 200:
                    raise RuntimeError(f"production completeness {table} read returned HTTP {response.status}: {body[:300]}")
        except HTTPError as exc:
            raise RuntimeError(f"production completeness {table} read returned HTTP {exc.code}") from exc
        value = json.loads(body) if body else []
        if not isinstance(value, list):
            raise RuntimeError(f"production completeness {table} read did not return an array")
        rows.extend(row for row in value if isinstance(row, dict))
    return rows


def _source_configs(registry: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    """Map each production source ID to one canonical registry configuration."""
    result: dict[str, tuple[str, dict[str, Any]]] = {}
    for key, raw_config in (registry.get("venues") or {}).items():
        if not isinstance(raw_config, dict):
            continue
        source_id = str(raw_config.get("source_id") or key).strip()
        if not source_id or source_id in result:
            continue
        config = dict(raw_config)
        config.setdefault("venue_id", str(key))
        config.setdefault("source_id", source_id)
        result[source_id] = (str(key), config)
    return result


def _normalise_time(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) >= 2 and all(part.isdigit() for part in parts[:2]):
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    return text[:5] if len(text) >= 5 else text


def _preferred_source(records: list[ExistingRecord], config: dict[str, Any]) -> ExistingRecord:
    listing = {str(config.get("official_source") or "").rstrip("/"), str(config.get("listing_source") or "").rstrip("/")}
    def rank(record: ExistingRecord) -> tuple[int, int]:
        url = str(record.source_url or "")
        path = urlsplit(url).path.casefold()
        is_pdf = int(path.endswith(".pdf"))
        is_listing = int(url.rstrip("/") in listing)
        return (is_pdf * 2 + is_listing, 0 if url else 1)
    return sorted(records, key=rank)[0]


def _build_gap_event(records: list[ExistingRecord], config: dict[str, Any], *, programme_present: bool, credits_present: bool) -> ProductionGapEvent:
    primary = _preferred_source(records, config)
    fields = dict(primary.fields or {})
    title = str(primary.title or fields.get("title") or "").strip()
    source_event_id = str(primary.source_event_id or "").strip()
    source_url = str(primary.source_url or "").strip()
    event_id = str(primary.event_id or "").strip()
    if not title or not source_event_id or not source_url or not event_id or not primary.event_key:
        raise ValueError("production Event/source identity is incomplete")
    source_records = [
        {"event_id": record.event_id, "source": record.source, "source_event_id": record.source_event_id, "source_url": record.source_url}
        for record in records
        if record.source_event_id and record.source_url
    ]
    raw = {
        "source_title": title,
        "production_event_key": str(primary.event_key),
        "production_key": title.casefold(),
        "source_records": source_records,
        "detail_source_url": source_url if not urlsplit(source_url).path.casefold().endswith(".pdf") else None,
        "production_gap": {"programme_present": programme_present, "credits_present": credits_present},
    }
    return ProductionGapEvent(
        source=str(primary.source or config.get("source_id") or config.get("venue_id")),
        source_event_id=source_event_id,
        source_url=source_url,
        organization=str(config.get("organization") or ""),
        venue=str(config.get("venue") or ""),
        city=str(config.get("city") or ""),
        country=str(config.get("country") or ""),
        timezone=str(config.get("timezone") or "UTC"),
        title=title,
        date=str(primary.date or ""),
        start_time=_normalise_time(fields.get("start_time")),
        end_time=_normalise_time(fields.get("end_time")),
        room=fields.get("room"),
        event_type=str(fields.get("event_type") or "performance"),
        classification=str(fields.get("event_type") or "performance"),
        programme=[],
        credits=[],
        data_quality={
            "programme": {"status": "EXISTING_RELATIONSHIP" if programme_present else "NO_PROGRAMME_EVIDENCE"},
            "content_recovery": {"scope": "production-gaps"},
        },
        raw=raw,
    )


def collect_production_gap_events(
    season: str,
    *,
    selected: list[str] | None = None,
    registry: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return current production gap groups and a read-only baseline report."""
    registry = registry or load_registry()
    selected_set = {str(value).strip() for value in (selected or []) if str(value).strip()}
    configs = _source_configs(registry)
    groups: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    total_events = total_programme = total_credits = 0
    total_no_programme = total_no_credits = 0

    for source_id, (venue_key, config) in configs.items():
        if selected_set and not (source_id in selected_set or venue_key in selected_set):
            continue
        bounds = (config.get("season_bounds") or {}).get(season) or {}
        prefer_secret = bool(os.getenv("SUPABASE_SECRET_KEY", "").strip())
        try:
            records = fetch_existing_sources(
                source_id,
                season,
                season_start=bounds.get("season_start"),
                season_end=bounds.get("season_end"),
                apply_mode=prefer_secret,
            )
            by_event: dict[str, list[ExistingRecord]] = defaultdict(list)
            for record in records:
                if record.event_id:
                    by_event[record.event_id].append(record)
            event_ids = sorted(by_event)
            programme_rows = _readonly_rows("event_programme", "event_id,work_id,order", event_ids, prefer_secret=prefer_secret)
            credit_rows = _readonly_rows("event_credits", "event_id,artist_id,role,character", event_ids, prefer_secret=prefer_secret)
        except Exception as exc:
            errors.append({"source_id": source_id, "error": f"{type(exc).__name__}: {exc}"})
            continue

        programme_counts = defaultdict(int)
        credit_counts = defaultdict(int)
        for row in programme_rows:
            if row.get("event_id"):
                programme_counts[str(row["event_id"])] += 1
        for row in credit_rows:
            if row.get("event_id"):
                credit_counts[str(row["event_id"])] += 1
        gap_events: list[ProductionGapEvent] = []
        for event_id in event_ids:
            programme_present = programme_counts[event_id] > 0
            credits_present = credit_counts[event_id] > 0
            total_events += 1
            total_programme += programme_counts[event_id]
            total_credits += credit_counts[event_id]
            total_no_programme += int(not programme_present)
            total_no_credits += int(not credits_present)
            if not programme_present or not credits_present:
                try:
                    gap_events.append(_build_gap_event(by_event[event_id], config, programme_present=programme_present, credits_present=credits_present))
                except ValueError as exc:
                    errors.append({"source_id": source_id, "event_id": event_id, "error": str(exc)})
        if gap_events:
            groups.append({"venue_id": venue_key, "source_id": source_id, "season": season, "config": config, "events": gap_events})

    baseline = {
        "season": season,
        "events": total_events,
        "programme_relationships": total_programme,
        "credits": total_credits,
        "events_without_programme": total_no_programme,
        "events_without_credits": total_no_credits,
        "production_gap_events": sum(len(group["events"]) for group in groups),
        "errors": errors,
    }
    return groups, baseline


def build_targeted_discovery(
    *,
    venue_id: str,
    season: str,
    config: dict[str, Any],
    artifact_root: Path,
    command: str | None = None,
) -> Callable[[CanonicalEvent], list[str]]:
    """Create a generic targeted Hermes discovery callback for one venue."""
    official_hosts = {
        urlsplit(str(config.get(key) or "")).netloc.casefold()
        for key in ("official_source", "listing_source")
        if urlsplit(str(config.get(key) or "")).netloc
    }

    def discover(event: CanonicalEvent) -> list[str]:
        request = build_request(venue=venue_id, season=season, config=config, reason="production_content_gap")
        request["targeted_enrichment"] = {
            "event_title": event.title,
            "event_date": event.date,
            "existing_source_url": event.source_url,
            "goal": "find the official event detail or production page for this existing occurrence",
        }
        key = hashlib.sha256(event.event_key.encode("utf-8")).hexdigest()[:20]
        result = acquire_source_discovery(
            request,
            command=command,
            artifact_dir=artifact_root / "hermes" / key,
        )
        candidates = result.get("detail_urls") if isinstance(result.get("detail_urls"), list) else []
        endpoint = result.get("discovered_endpoint")
        if isinstance(endpoint, str) and endpoint.strip():
            candidates.insert(0, endpoint.strip())
        safe: list[str] = []
        for value in candidates:
            if not isinstance(value, str) or not value.strip():
                continue
            parsed = urlsplit(value.strip())
            if parsed.scheme in {"http", "https"} and parsed.netloc.casefold() in official_hosts and value.strip() not in safe:
                safe.append(value.strip())
        if not safe:
            raise RuntimeError("Hermes targeted discovery returned no official detail URL")
        return safe

    return discover


def scan_production_gaps(season: str, *, selected: list[str] | None = None) -> dict[str, Any]:
    """Return the current read-only completeness counts."""
    _groups, baseline = collect_production_gap_events(season, selected=selected)
    return baseline
