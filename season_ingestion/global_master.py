from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import ENTITY_KINDS, GlobalEntitySnapshot, empty_global_snapshot


def normalize_identity(value: str) -> str:
    """Shared deterministic identity key for names from source and Global Master."""
    value = unicodedata.normalize("NFKD", str(value or "")).casefold().replace("ß", "ss")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"\([^)]*(?:\d{3,4}|born|died|b\.|d\.)[^)]*\)", " ", value)
    value = re.sub(r"\b(?:composer|composed by|music by)\s*[:\-]?\s*", " ", value)
    value = re.sub(r"\b(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2})?\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


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
    table_fields = {
        "composer": ("composers", "id,canonical_name"),
        "artist": ("artists", "id,artist_name"),
        "work": ("works", "id,title,composer_id,work_kind,parent_work_id"),
        "character": ("characters", "id,canonical_name"),
    }
    for kind in ENTITY_KINDS:
        table, fields = table_fields[kind]
        query = urlencode({"select": fields, "order": "id.asc", "limit": "10000"})
        request = Request(f"{url}/rest/v1/{table}?{query}", headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urlopen(request, timeout=60) as response:
            rows = json.loads(response.read().decode("utf-8"))
            if kind == "artist":
                for row in rows:
                    row["canonical_name"] = row.get("artist_name")
            if kind == "work":
                for row in rows:
                    row["canonical_name"] = row.get("title")
            entities[kind] = rows
    alias_query = urlencode({"select": "id,composer_id,alias,language,source", "order": "id.asc", "limit": "10000"})
    alias_request = Request(f"{url}/rest/v1/composer_aliases?{alias_query}", headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urlopen(alias_request, timeout=60) as response:
        composer_aliases = json.loads(response.read().decode("utf-8"))
    snapshot = GlobalEntitySnapshot(
        generated_at=datetime.now(timezone.utc).isoformat(),
        source="supabase-read-only",
        freshness_seconds=0,
        entities=entities,
        composer_aliases=composer_aliases,
    )
    snapshot.validate()
    return snapshot


def resolve_work(source_title: str, composer: dict[str, Any] | str | None, snapshot: GlobalEntitySnapshot) -> dict[str, Any]:
    normalized = normalize_identity(source_title)
    composer_id = composer.get("entity_id") if isinstance(composer, dict) and composer.get("status") == "existing" else None
    candidates = []
    for row in snapshot.entities.get("work", []):
        if composer_id and row.get("composer_id") and row.get("composer_id") != composer_id:
            continue
        names = [row.get("canonical_name"), row.get("title"), *(row.get("aliases") or [])]
        for position, name in enumerate(names):
            if normalized and normalized == normalize_identity(str(name or "")):
                candidates.append((row, "exact" if position == 0 else "alias"))
    if len(candidates) == 1:
        row, method = candidates[0]
        return {"status": "existing", "work_id": row.get("id"), "match_method": method, "reason": f"{method} global work match with resolved composer context"}
    return {"status": "review_required", "work_id": None, "reason": "no unique global Work match; do not auto-create"}


def resolve_entity(kind: str, raw_name: str, snapshot: GlobalEntitySnapshot) -> dict[str, Any]:
    """Shared read-only resolver surface for Composer/Artist/Work/Character."""
    if kind not in ENTITY_KINDS:
        raise ValueError(f"unsupported global entity kind: {kind}")
    lookup_key = normalize_identity(raw_name)
    rows = snapshot.entities.get(kind, [])
    canonical_matches = [row for row in rows if lookup_key == normalize_identity(str(row.get("canonical_name") or row.get("name") or ""))]
    if len(canonical_matches) == 1:
        row = canonical_matches[0]
        return {"status": "existing", "entity_id": row.get("id"), "canonical_name": row.get("canonical_name"), "match_method": "exact", "lookup_key": lookup_key, "reason": f"canonical exact global {kind} match"}
    if kind == "composer":
        composer_by_id = {row.get("id"): row for row in rows}
        alias_matches = []
        for alias in snapshot.composer_aliases:
            if lookup_key == normalize_identity(str(alias.get("alias") or "")) and alias.get("composer_id") in composer_by_id:
                alias_matches.append((composer_by_id[alias["composer_id"]], alias))
        if len(alias_matches) == 1:
            row, alias = alias_matches[0]
            return {"status": "existing", "entity_id": row.get("id"), "canonical_name": row.get("canonical_name"), "matched_alias": alias.get("alias"), "match_method": "alias", "lookup_key": lookup_key, "reason": "known composer alias match"}
        normalized_matches = [row for row in rows if lookup_key == normalize_identity(str(row.get("canonical_name") or ""))]
        if len(normalized_matches) == 1:
            row = normalized_matches[0]
            return {"status": "existing", "entity_id": row.get("id"), "canonical_name": row.get("canonical_name"), "match_method": "normalized", "lookup_key": lookup_key, "reason": "normalized global composer match"}
    return {"status": "review_required", "entity_id": None, "lookup_key": lookup_key, "candidate_matches": [row.get("canonical_name") for row in canonical_matches], "reason": f"no unique global {kind} match; do not auto-create"}
