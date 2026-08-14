from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .reconciliation import ExistingRecord, field_update_plan, reconcile


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


def fetch_existing_sources(source: str, *, page_size: int = 500, fetcher=urlopen) -> list[ExistingRecord]:
    """Read one source at a time with server-side filtering and pagination."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        raise RuntimeError("preflight requires SUPABASE_URL and SUPABASE_SECRET_KEY")
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    rows: list[ExistingRecord] = []
    offset = 0
    while True:
        query = urlencode({"select": "event_id,source,source_event_id,source_url,events!inner(*)", "source": f"eq.{source}", "order": "event_id", "limit": page_size, "offset": offset})
        request = Request(f"{url}/rest/v1/event_sources?{query}", method="GET", headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"})
        with fetcher(request, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError(f"Supabase read returned HTTP {response.status}")
            page = json.loads(response.read().decode("utf-8"))
        for item in page:
            event = item.get("events") or {}
            if isinstance(event, list):
                event = event[0] if event else {}
            rows.append(ExistingRecord(str(item.get("event_id") or ""), str(item.get("source") or ""), item.get("source_event_id"), item.get("source_url"), event.get("event_key"), event.get("title"), event.get("date"), event, frozenset(event)))
        if len(page) < page_size:
            return rows
        offset += page_size
