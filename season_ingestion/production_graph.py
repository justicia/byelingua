"""Shared atomic production graph writer for approved final staging."""
from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .unicode_integrity import validate_unicode_integrity
from .product_contract import (
    declare_product_contract,
    validate_product_contract_metadata,
)


RPC_PATH = "/rest/v1/rpc/apply_canonical_production_graph"


class ProductionGraphRPCError(RuntimeError):
    """Sanitized, response-only diagnostic for a failed graph RPC."""

    def __init__(self, status: int, body: str | bytes) -> None:
        self.http_status = status
        self.response_body = _decode_response_body(body)
        self.error = parse_rpc_error_body(self.response_body)
        self.error_code = self.error.get("error_code")
        self.message = self.error.get("message")
        self.details = self.error.get("details")
        self.hint = self.error.get("hint")
        diagnostic = self.message or self.response_body
        super().__init__(f"production graph RPC returned HTTP {status}: {diagnostic}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "APPLY_FAILED",
            "http_status": self.http_status,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "hint": self.hint,
            "response_body": self.error.get("response_body"),
        }


def _decode_response_body(body: str | bytes | None) -> str:
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="backslashreplace")
    return str(body or "")


def _redact_response_text(text: str) -> str:
    """Remove credentials if a server error echoes request metadata."""
    redacted = text
    for name in ("SUPABASE_SECRET_KEY", "SUPABASE_READONLY_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        value = os.getenv(name, "")
        if value:
            redacted = redacted.replace(value, "[REDACTED]")
    redacted = re.sub(
        r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^,;}\s\"']+",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)((?:apikey|api_key|secret_key)\s*[:=]\s*)[^,;}\s\"']+",
        r"\1[REDACTED]",
        redacted,
    )
    return redacted


def parse_rpc_error_body(body: str | bytes | None) -> dict[str, Any]:
    """Parse common PostgREST/Postgres error fields without trusting the body."""
    sanitized = _redact_response_text(_decode_response_body(body))
    try:
        parsed: Any = json.loads(sanitized)
    except (TypeError, ValueError):
        parsed = sanitized
    fields = parsed if isinstance(parsed, dict) else {}
    message = fields.get("message") or fields.get("error") or (sanitized or None)
    return {
        "error_code": fields.get("code") or fields.get("error_code") or fields.get("errorCode"),
        "message": message,
        "details": fields.get("details"),
        "hint": fields.get("hint"),
        "response_body": parsed,
    }


def _nonblank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def normalize_graph_staging(staging: dict[str, Any]) -> tuple[list[dict], list[dict], dict[str, int]]:
    """Keep existing Work UUIDs and valid new candidates on separate paths."""
    raw_works = staging.get("work", {}).get("safe", []) if isinstance(staging.get("work"), dict) else []
    raw_relationships: list[dict] = []
    relationship_groups = staging.get("relationships") if isinstance(staging.get("relationships"), dict) else {}
    for key in ("safe_existing", "safe_new"):
        rows = relationship_groups.get(key, [])
        if isinstance(rows, list):
            raw_relationships.extend(row for row in rows if isinstance(row, dict))

    candidate_works: list[dict] = []
    existing_by_candidate: dict[str, str] = {}
    diagnostics = {
        "null_work_candidate_key": 0,
        "null_work_normalized_title": 0,
        "null_work_canonical_title": 0,
        "excluded_malformed_works": 0,
        "excluded_unresolved_relationships": 0,
        "safe_graph_null_candidate_keys": 0,
    }
    for row in raw_works if isinstance(raw_works, list) else []:
        if not isinstance(row, dict):
            diagnostics["excluded_malformed_works"] += 1
            continue
        existing_id = _nonblank(row.get("id")) or _nonblank(row.get("work_id"))
        candidate_key = _nonblank(row.get("candidate_key"))
        normalized_title = _nonblank(row.get("normalized_source_title"))
        canonical_title = _nonblank(row.get("proposed_canonical_title"))
        if existing_id:
            if candidate_key:
                existing_by_candidate[candidate_key] = existing_id
            # Existing production Works are referenced by relationship.work_id;
            # they must never be sent through the RPC's new-candidate loop.
            continue
        missing = False
        if not candidate_key:
            diagnostics["null_work_candidate_key"] += 1
            missing = True
        if not normalized_title:
            diagnostics["null_work_normalized_title"] += 1
            missing = True
        if not canonical_title:
            diagnostics["null_work_canonical_title"] += 1
            missing = True
        if missing:
            diagnostics["excluded_malformed_works"] += 1
            continue
        candidate_works.append(dict(row))

    candidate_keys = {str(row["candidate_key"]) for row in candidate_works}
    safe_relationships: list[dict] = []
    for row in raw_relationships:
        work_id = _nonblank(row.get("work_id"))
        candidate_key = _nonblank(row.get("candidate_key"))
        normalized = dict(row)
        if work_id:
            normalized["work_id"] = work_id
            normalized.pop("candidate_key", None)
            safe_relationships.append(normalized)
            continue
        if candidate_key in existing_by_candidate:
            normalized["work_id"] = existing_by_candidate[candidate_key]
            normalized.pop("candidate_key", None)
            safe_relationships.append(normalized)
            continue
        if candidate_key and candidate_key in candidate_keys:
            normalized["candidate_key"] = candidate_key
            normalized.pop("work_id", None)
            safe_relationships.append(normalized)
            continue
        diagnostics["excluded_unresolved_relationships"] += 1
    return candidate_works, safe_relationships, diagnostics


def validate_production_graph_contract(payload: dict[str, Any]) -> None:
    """Validate the exact Work candidate/relationship contract before RPC."""
    works = payload.get("works") if isinstance(payload.get("works"), list) else []
    candidate_keys: set[str] = set()
    for row in works:
        if not isinstance(row, dict) or not _nonblank(row.get("candidate_key")):
            raise ValueError("NULL_WORK_CANDIDATE_KEY")
        if not _nonblank(row.get("normalized_source_title")):
            raise ValueError("NULL_WORK_NORMALIZED_TITLE")
        if not _nonblank(row.get("proposed_canonical_title")):
            raise ValueError("NULL_WORK_CANONICAL_TITLE")
        candidate_keys.add(str(row["candidate_key"]).strip())
    relationships = payload.get("relationships") if isinstance(payload.get("relationships"), list) else []
    for row in relationships:
        if not isinstance(row, dict):
            raise ValueError("UNRESOLVED_RELATIONSHIP_WORK_IDENTITY")
        work_id = _nonblank(row.get("work_id"))
        candidate_key = _nonblank(row.get("candidate_key"))
        if work_id and candidate_key:
            raise ValueError("AMBIGUOUS_RELATIONSHIP_WORK_IDENTITY")
        if not work_id and (not candidate_key or candidate_key not in candidate_keys):
            raise ValueError("UNRESOLVED_RELATIONSHIP_WORK_IDENTITY")


def add_original_title(event: dict) -> dict:
    """Map the official Event source title; never derive it from programme Works."""
    source_title = (event.get("raw") or {}).get("source_title") or event.get("title")
    if not source_title:
        raise ValueError(f"event {event.get('event_key')} has no official source title")
    provenance = dict(event.get("raw") or {})
    provenance["original_title_source_path"] = "raw.source_title" if provenance.get("source_title") else "title"
    return {**event, "title": event.get("title") or source_title, "original_title": source_title, "raw": provenance}


def build_payload(events: list[dict], staging: dict, *, organization: dict, venue: dict) -> dict:
    safe_events = [add_original_title(event) for event in events]
    if len({e["event_key"] for e in safe_events}) != len(safe_events):
        raise ValueError("duplicate event_key in approved event staging")
    if any(not e.get("source_url") or not e.get("source_event_id") for e in safe_events):
        raise ValueError("approved event is missing source provenance")
    safe_composers = staging["composer"]["safe"]
    safe_works, safe_relationships, _ = normalize_graph_staging(staging)
    credit_staging = staging.get("credit_resolution") or {}
    safe_credits = credit_staging.get("safe_event_credits", [])
    if any(not row.get("credit", {}).get("canonical_role") or not row.get("credit", {}).get("artist_resolution", {}).get("status", "").startswith("SAFE_") for row in safe_credits):
        raise ValueError("review credit entered safe production payload")
    artists = credit_staging.get("safe_new_artists", [])
    event_credits = []
    projected_ids = set()
    for row in safe_credits:
        credit = row["credit"]
        artist = credit["artist_resolution"]
        character = credit["character_resolution"]
        artist_identity_key = artist.get("lookup_key")
        projected_id = (
            row["event_key"],
            artist.get("artist_id") or artist_identity_key,
            credit["canonical_role"],
            character.get("character_id"),
            credit.get("instrument"),
            credit.get("voice_type"),
        )
        if projected_id in projected_ids:
            continue
        projected_ids.add(projected_id)
        event_credits.append({"event_key": row["event_key"], "artist_id": artist.get("artist_id"), "artist_identity_key": artist_identity_key, "artist_name": artist.get("canonical_name") or credit.get("source_artist_name"), "role": credit["canonical_role"], "instrument": credit.get("instrument"), "voice_type": credit.get("voice_type"), "character_id": character.get("character_id"), "character": character.get("character"), "raw_character": credit.get("source_character"), "source_url": credit.get("source_url"), "source_field": credit.get("source_field")})
    payload = {
        "source": safe_events[0]["source"],
        "organization": organization,
        "venue": venue,
        "events": safe_events,
        "composers": safe_composers,
        "works": safe_works,
        "relationships": safe_relationships,
        "artists": artists,
        "event_credits": event_credits,
        "expected": {"events": len(safe_events), "composers": len(safe_composers), "works": len(safe_works), "relationships": len(safe_relationships), "artists": len(artists), "event_credits": len(event_credits)},
    }
    declare_product_contract(payload)
    validate_unicode_integrity(payload)
    validate_production_graph_contract(payload)
    return payload


def apply_graph(payload: dict, *, sender=urlopen) -> dict:
    validate_product_contract_metadata(payload)
    validate_unicode_integrity(payload)
    validate_production_graph_contract(payload)
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        raise RuntimeError("production graph apply requires SUPABASE_URL and SUPABASE_SECRET_KEY")
    request = Request(url + RPC_PATH, data=json.dumps({"p_payload": payload}, ensure_ascii=False).encode(), method="POST", headers={
        "apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation",
    })
    try:
        with sender(request, timeout=120) as response:
            body = response.read().decode("utf-8")
            if response.status not in (200, 201):
                raise ProductionGraphRPCError(response.status, body)
    except HTTPError as exc:
        try:
            body = exc.read()
        except OSError:
            body = b""
        raise ProductionGraphRPCError(exc.code, body) from exc
    return json.loads(body) if body else {}

