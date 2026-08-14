from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .reconciliation import ExistingRecord, field_update_plan, reconcile
from .schema import PATCHABLE_EVENT_FIELDS
from .season import resolve_season_bounds


class PreflightConfigurationError(RuntimeError):
    def __init__(self, missing_fields: list[str], message: str):
        super().__init__(message)
        self.missing_fields = missing_fields


def build_event_updates(events: list[dict], existing: list[ExistingRecord]) -> list[dict]:
    """Build PATCH targets while preserving every database event identity."""
    report = reconcile(events, existing, existing[0].source if existing else "wiener_staatsoper")
    if report["collision_guard_blocked"] or report["counts"]["safe_insert"]:
        raise RuntimeError("apply blocked by reconciliation collision guard")
    by_identity = {(item.source, item.source_event_id): item for item in existing}
    updates: list[dict] = []
    for event in events:
        identity = (str(event.get("source") or ""), str(event.get("source_event_id") or ""))
        current = by_identity.get(identity)
        if current is None or not current.event_id or not current.event_key:
            raise RuntimeError("apply requires a unique existing event identity and event_key")
        plan = field_update_plan(event, current)
        if plan["blocked"]:
            raise RuntimeError("apply blocked by field-level quality guard")
        if plan["payload"] or plan["source_url"]:
            updates.append({"event_id": current.event_id, "source": current.source, "event_patch": plan["payload"], "source_url": plan["source_url"]})
    return updates


def apply_events(events: list[dict], existing: list[ExistingRecord], *, sender=urlopen) -> int:
    """Update matched existing events only; never insert, upsert, or delete."""
    updates = build_event_updates(events, existing)
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        raise RuntimeError("apply requires SUPABASE_URL and SUPABASE_SECRET_KEY")
    updated = 0
    for update in updates:
        event_id, payload = update["event_id"], update["event_patch"]
        if payload:
            endpoint = f"{url}/rest/v1/events?{urlencode({'id': f'eq.{event_id}'})}"
            request = Request(endpoint, data=json.dumps(payload, ensure_ascii=False).encode(), method="PATCH", headers={
                "apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=minimal",
            })
            with sender(request, timeout=60) as response:
                if response.status not in (200, 204):
                    raise RuntimeError(f"Supabase event update returned HTTP {response.status}")
            updated += 1
        if update["source_url"]:
            source_query = urlencode({"event_id": f"eq.{event_id}", "source": f"eq.{update['source']}"})
            endpoint = f"{url}/rest/v1/event_sources?{source_query}"
            request = Request(endpoint, data=json.dumps({"source_url": update["source_url"]}, ensure_ascii=False).encode(), method="PATCH", headers={
                "apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=minimal",
            })
            with sender(request, timeout=60) as response:
                if response.status not in (200, 204):
                    raise RuntimeError(f"Supabase source update returned HTTP {response.status}")
            updated += 1
    return updated


def fetch_existing_sources(
    source: str,
    season: str = "2026-27",
    *,
    season_start: str | None = None,
    season_end: str | None = None,
    apply_mode: bool = False,
    page_size: int = 500,
    fetcher=urlopen,
) -> list[ExistingRecord]:
    """Read one source at a time with server-side filtering and pagination."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key_name = "SUPABASE_SECRET_KEY" if apply_mode else "SUPABASE_READONLY_KEY"
    key = os.environ.get(key_name, "")
    if not url or not key:
        raise RuntimeError(f"{'apply' if apply_mode else 'preflight'} requires SUPABASE_URL and {key_name}")
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    rows: list[ExistingRecord] = []
    if (season_start is None) != (season_end is None):
        raise ValueError("season_start and season_end must be provided together")
    if season_start is None:
        start_date, end_date = resolve_season_bounds(season)
    else:
        # Validate caller-provided boundaries with the same generic resolver.
        start_date, end_date = resolve_season_bounds(season, {
            "season_bounds": {season: {
                "season_start": season_start,
                "season_end": season_end,
            }}
        })
    event_columns = ",".join(("id", "event_key", "title", "date", *PATCHABLE_EVENT_FIELDS))
    selection = f"event_id,source,source_event_id,source_url,events!inner({event_columns})"
    offset = 0
    while True:
        query = urlencode([
            ("select", selection),
            ("source", f"eq.{source}"),
            ("events.date", f"gte.{start_date}"),
            ("events.date", f"lte.{end_date}"),
            ("order", "event_id"),
            ("limit", page_size),
            ("offset", offset),
        ])
        request = Request(f"{url}/rest/v1/event_sources?{query}", method="GET", headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"})
        try:
            with fetcher(request, timeout=60) as response:
                if response.status != 200:
                    raise PreflightConfigurationError(list(PATCHABLE_EVENT_FIELDS), f"Supabase preflight read returned HTTP {response.status}")
                page = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {400, 401, 403}:
                raise PreflightConfigurationError(list(PATCHABLE_EVENT_FIELDS), f"Supabase preflight cannot read required event columns (HTTP {exc.code})") from exc
            raise
        for item in page:
            event = item.get("events") or {}
            if isinstance(event, list):
                event = event[0] if event else {}
            rows.append(ExistingRecord(str(item.get("event_id") or ""), str(item.get("source") or ""), item.get("source_event_id"), item.get("source_url"), event.get("event_key"), event.get("title"), event.get("date"), event, frozenset(event)))
        if len(page) < page_size:
            return rows
        offset += page_size
