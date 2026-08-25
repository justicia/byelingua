"""Shared atomic production graph writer for approved final staging."""
from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen

from .unicode_integrity import validate_unicode_integrity


RPC_PATH = "/rest/v1/rpc/apply_canonical_production_graph"


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
    safe_works = staging["work"]["safe"]
    safe_relationships = staging["relationships"]["safe_existing"] + staging["relationships"]["safe_new"]
    credit_staging = staging.get("credit_resolution") or {}
    safe_credits = credit_staging.get("safe_event_credits", [])
    if any(not row.get("credit", {}).get("canonical_role") or not row.get("credit", {}).get("artist_resolution", {}).get("status", "").startswith("SAFE_") for row in safe_credits):
        raise ValueError("review credit entered safe production payload")
    artists = credit_staging.get("safe_new_artists", [])
    event_credits = []
    for row in safe_credits:
        credit = row["credit"]
        artist = credit["artist_resolution"]
        character = credit["character_resolution"]
        event_credits.append({"event_key": row["event_key"], "artist_id": artist.get("artist_id"), "artist_name": artist.get("canonical_name") or credit.get("source_artist_name"), "role": credit["canonical_role"], "character_id": character.get("character_id"), "character": character.get("character"), "raw_character": credit.get("source_character"), "source_url": credit.get("source_url"), "source_field": credit.get("source_field")})
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
    validate_unicode_integrity(payload)
    return payload


def apply_graph(payload: dict, *, sender=urlopen) -> dict:
    validate_unicode_integrity(payload)
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        raise RuntimeError("production graph apply requires SUPABASE_URL and SUPABASE_SECRET_KEY")
    request = Request(url + RPC_PATH, data=json.dumps({"p_payload": payload}, ensure_ascii=False).encode(), method="POST", headers={
        "apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation",
    })
    with sender(request, timeout=120) as response:
        body = response.read().decode("utf-8")
        if response.status not in (200, 201):
            raise RuntimeError(f"production graph RPC returned HTTP {response.status}: {body[:500]}")
    return json.loads(body) if body else {}
