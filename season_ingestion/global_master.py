from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .contracts import ENTITY_KINDS, GlobalEntitySnapshot, empty_global_snapshot


EXPECTED_PROJECT_REF = "pdtunknwruokybtuehua"
GLOBAL_MASTER_PAGE_SIZE = 1000


class GlobalMasterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def normalize_identity(value: str) -> str:
    """Shared deterministic identity key for names from source and Global Master."""
    value = unicodedata.normalize("NFKD", str(value or "")).casefold().replace("ß", "ss")
    value = "".join(char for char in value if not unicodedata.combining(char) and unicodedata.category(char) != "Cf")
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
        raise GlobalMasterError("GLOBAL_MASTER_CONFIG_ERROR", "SUPABASE_URL and SUPABASE_READONLY_KEY are required")
    match = re.match(r"https://([a-z0-9]+)\.supabase\.co/?$", url, re.I)
    target_ref = match.group(1) if match else None
    if target_ref != EXPECTED_PROJECT_REF:
        raise GlobalMasterError("GLOBAL_MASTER_PROJECT_MISMATCH", "configured Supabase project does not match the Global Master project")
    entities: dict[str, list[dict[str, Any]]] = {}
    table_fields = {
        "composer": ("composers", "id,canonical_name,identity_key"),
        "artist": ("artists", "id,artist_name"),
        "work": ("works", "id,title,composer_id,identity_key,normalization_status,work_kind,parent_work_id"),
        "character": ("characters", "id,canonical_name"),
    }
    def fetch(table: str, fields: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            query = urlencode({"select": fields, "order": "id.asc", "limit": str(GLOBAL_MASTER_PAGE_SIZE), "offset": str(offset)})
            request = Request(f"{url}/rest/v1/{table}?{query}", headers={"apikey": key, "Authorization": f"Bearer {key}"})
            try:
                with urlopen(request, timeout=60) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                code = "GLOBAL_MASTER_AUTH_ERROR" if exc.code in {401, 403} else "GLOBAL_MASTER_QUERY_ERROR"
                raise GlobalMasterError(code, f"{table} query failed with HTTP {exc.code}") from exc
            except (URLError, TimeoutError, ValueError) as exc:
                raise GlobalMasterError("GLOBAL_MASTER_QUERY_ERROR", f"{table} query failed: {type(exc).__name__}") from exc
            if not isinstance(payload, list):
                raise GlobalMasterError("GLOBAL_MASTER_QUERY_ERROR", f"{table} query returned a non-list payload")
            rows.extend(payload)
            if len(payload) < GLOBAL_MASTER_PAGE_SIZE:
                return rows
            offset += GLOBAL_MASTER_PAGE_SIZE

    for kind in ENTITY_KINDS:
        table, fields = table_fields[kind]
        rows = fetch(table, fields)
        if kind == "artist":
            for row in rows:
                row["canonical_name"] = row.get("artist_name")
        if kind == "work":
            for row in rows:
                row["canonical_name"] = row.get("title")
        entities[kind] = rows
    composer_aliases = fetch("composer_aliases", "id,composer_id,alias,language,source")
    work_aliases = fetch("work_aliases", "id,work_id,alias,language,source")
    loaded_at = datetime.now(timezone.utc).isoformat()
    health = {
        "preflight_status": "PASS" if entities["composer"] and entities["work"] else "FAIL",
        "global_master_loaded": bool(entities["composer"] and entities["work"]),
        "project_target_verified": target_ref == EXPECTED_PROJECT_REF,
        "target_project_ref": target_ref,
        "credential_configured": bool(key),
        "composers_count": len(entities["composer"]),
        "composer_aliases_count": len(composer_aliases),
        "works_count": len(entities["work"]),
        "work_aliases_count": len(work_aliases),
        "loaded_at": loaded_at,
        "query_errors": 0,
    }
    snapshot = GlobalEntitySnapshot(
        generated_at=loaded_at,
        source="supabase-read-only",
        freshness_seconds=0,
        entities=entities,
        composer_aliases=composer_aliases,
        work_aliases=work_aliases,
        health=health,
    )
    snapshot.validate()
    if not health["global_master_loaded"]:
        snapshot.health.update({"error_code": "GLOBAL_MASTER_EMPTY", "error_message": "Global Master composers and works queries returned no rows"})
    return snapshot


def resolve_work(source_title: str, composer: dict[str, Any] | str | None, snapshot: GlobalEntitySnapshot) -> dict[str, Any]:
    normalized = normalize_identity(source_title)
    composer_id = composer.get("entity_id") if isinstance(composer, dict) and composer.get("status") == "existing" else None
    candidates = []
    for row in snapshot.entities.get("work", []):
        if composer_id and row.get("composer_id") and row.get("composer_id") != composer_id:
            continue
        canonical_key = normalize_identity(str(row.get("canonical_name") or row.get("title") or ""))
        if normalized and normalized == canonical_key:
            candidates.append((row, "exact"))
            continue
        aliases = [alias.get("alias") for alias in snapshot.work_aliases if alias.get("work_id") == row.get("id")]
        if normalized and any(normalized == normalize_identity(str(alias or "")) for alias in aliases):
            candidates.append((row, "alias"))
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
