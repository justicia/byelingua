from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import ENTITY_KINDS, GlobalEntitySnapshot, empty_global_snapshot


def load_global_snapshot(*, path: Path | None = None) -> GlobalEntitySnapshot:
    """Read the global master only; this module has no write path."""
    if path:
        payload = json.loads(path.read_text(encoding="utf-8"))
        snapshot = GlobalEntitySnapshot(**payload)
        snapshot.validate()
        return snapshot
    url, key = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_READONLY_KEY", "")
    if not url or not key:
        return empty_global_snapshot(datetime.now(timezone.utc).isoformat())
    entities: dict[str, list[dict[str, Any]]] = {}
    for kind in ENTITY_KINDS:
        table = f"{kind}s"
        query = urlencode({"select": "id,canonical_name", "order": "id.asc", "limit": "10000"})
        request = Request(f"{url}/rest/v1/{table}?{query}", headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urlopen(request, timeout=60) as response:
            entities[kind] = json.loads(response.read().decode("utf-8"))
    snapshot = GlobalEntitySnapshot(
        generated_at=datetime.now(timezone.utc).isoformat(),
        source="supabase-read-only",
        freshness_seconds=0,
        entities=entities,
    )
    snapshot.validate()
    return snapshot


def resolve_work(source_title: str, composer: str | None, snapshot: GlobalEntitySnapshot) -> dict[str, Any]:
    normalized = " ".join(source_title.casefold().split())
    candidates = []
    for row in snapshot.entities.get("work", []):
        names = [row.get("canonical_name"), row.get("title"), *(row.get("aliases") or [])]
        if normalized in {" ".join(str(name or "").casefold().split()) for name in names}:
            candidates.append(row)
    if len(candidates) == 1:
        return {"status": "existing", "work_id": candidates[0].get("id"), "reason": "exact global work match"}
    return {"status": "review_required", "work_id": None, "reason": "no unique global Work match; do not auto-create"}


def resolve_entity(kind: str, raw_name: str, snapshot: GlobalEntitySnapshot) -> dict[str, Any]:
    """Shared read-only resolver surface for Composer/Artist/Work/Character."""
    if kind not in ENTITY_KINDS:
        raise ValueError(f"unsupported global entity kind: {kind}")
    normalized = " ".join(raw_name.casefold().split())
    matches = [row for row in snapshot.entities.get(kind, []) if normalized == " ".join(str(row.get("canonical_name") or row.get("name") or "").casefold().split())]
    if len(matches) == 1:
        return {"status": "existing", "entity_id": matches[0].get("id"), "reason": f"exact global {kind} match"}
    return {"status": "review_required", "entity_id": None, "reason": f"no unique global {kind} match; do not auto-create"}
