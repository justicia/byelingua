from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


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
