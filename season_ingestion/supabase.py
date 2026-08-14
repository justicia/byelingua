from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .reconciliation import ExistingRecord


def apply_events(events: list[dict]) -> int:
    """Upsert without any delete operation; source failures can never erase rows."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        raise RuntimeError("apply requires SUPABASE_URL and SUPABASE_SECRET_KEY")
    endpoint = f"{url}/rest/v1/events?{urlencode({'on_conflict': 'event_key'})}"
    request = Request(endpoint, data=json.dumps(events, ensure_ascii=False).encode(), method="POST", headers={
        "apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    })
    with urlopen(request, timeout=60) as response:
        if response.status not in (200, 201, 204):
            raise RuntimeError(f"Supabase upsert returned HTTP {response.status}")
    return len(events)


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
        query = urlencode({"select": "event_id,source,source_event_id,source_url,events!inner(event_key,title,date)", "source": f"eq.{source}", "order": "event_id", "limit": page_size, "offset": offset})
        request = Request(f"{url}/rest/v1/event_sources?{query}", method="GET", headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"})
        with fetcher(request, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError(f"Supabase read returned HTTP {response.status}")
            page = json.loads(response.read().decode("utf-8"))
        for item in page:
            event = item.get("events") or {}
            if isinstance(event, list):
                event = event[0] if event else {}
            rows.append(ExistingRecord(str(item.get("event_id") or ""), str(item.get("source") or ""), item.get("source_event_id"), item.get("source_url"), event.get("event_key"), event.get("title"), event.get("date")))
        if len(page) < page_size:
            return rows
        offset += page_size
