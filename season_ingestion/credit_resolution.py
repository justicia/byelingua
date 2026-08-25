from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .global_master import normalize_identity


ROLE_ALIASES = {
    "musikalische leitung": "conductor", "dirigent": "conductor", "conductor": "conductor",
    "musical direction": "conductor", "direction musicale": "conductor",
    "regie": "stage_director", "inszenierung": "stage_director", "mise en scène": "stage_director", "stage direction": "stage_director",
    "bühnenbild": "set_designer", "set design": "set_designer", "sets": "set_designer", "décors": "set_designer",
    "kostüme": "costume_designer", "kostümbild": "costume_designer", "costume design": "costume_designer", "costumes": "costume_designer",
    "licht": "lighting_designer", "lichtgestaltung": "lighting_designer", "lighting": "lighting_designer", "lumières": "lighting_designer",
    "choreografie": "choreographer", "choreography": "choreographer", "chorégraphie": "choreographer",
    "dramaturgie": "dramaturg", "dramaturgy": "dramaturg",
    "chorleitung": "chorus_master", "chorus master": "chorus_master", "chef des chœurs": "chorus_master",
    "orchester": "orchestra", "orchestra": "orchestra", "chor": "choir", "choir": "choir", "chorus": "choir",
    "ensemble": "ensemble", "music group": "ensemble",
    "singer": "singer", "sänger": "singer", "cantante": "singer", "chanteur": "singer",
    "soloist": "soloist", "solist": "soloist", "actor": "actor", "schauspieler": "actor",
}
VOICE_TYPES = {"soprano", "sopran", "mezzo-soprano", "mezzosopran", "alto", "contralto", "tenor", "baritone", "bariton", "bass", "basso", "bass-baritone"}
SAFE_ROLES = set(ROLE_ALIASES.values())


def canonical_role(value: object) -> str | None:
    key = " ".join(str(value or "").casefold().strip().split())
    if key in VOICE_TYPES:
        return "singer"
    if key in ROLE_ALIASES:
        return ROLE_ALIASES[key]
    return None


def _artist_resolution(name: str, snapshot: Any) -> dict[str, Any]:
    lookup = normalize_identity(name)
    if not lookup:
        return {"status": "REVIEW_SOURCE_AMBIGUOUS", "artist_id": None}
    rows = snapshot.entities.get("artist", [])
    exact = [r for r in rows if normalize_identity(r.get("artist_name")) == lookup]
    aliases = [a for a in getattr(snapshot, "artist_aliases", []) if normalize_identity(a.get("alias")) == lookup]
    ids = {r.get("id") for r in exact} | {a.get("artist_id") for a in aliases}
    matches = [r for r in rows if r.get("id") in ids]
    if len(matches) == 1:
        return {"status": "SAFE_EXISTING", "artist_id": matches[0].get("id"), "canonical_name": matches[0].get("artist_name"), "lookup_key": lookup}
    if len(matches) > 1:
        return {"status": "REVIEW_ARTIST_CONFLICT", "artist_id": None, "lookup_key": lookup, "candidate_ids": [r.get("id") for r in matches]}
    return {"status": "SAFE_NEW_ARTIST", "artist_id": None, "canonical_name": name.strip(), "lookup_key": lookup}


def _character_resolution(raw: str | None, work_id: str | None, snapshot: Any) -> dict[str, Any]:
    if not raw:
        return {"status": "SAFE_ROLE", "character_id": None, "character": None}
    if not work_id:
        return {"status": "REVIEW_CHARACTER_CONFLICT", "character_id": None, "character": raw}
    rows = [r for r in getattr(snapshot, "work_characters", []) if str(r.get("work_id")) == str(work_id)]
    aliases = {str(a.get("character_id")): a for a in getattr(snapshot, "character_aliases", [])}
    matches = []
    for row in rows:
        if normalize_identity(row.get("canonical_name")) == normalize_identity(raw) or normalize_identity(aliases.get(str(row.get("character_uid")), {}).get("alias")) == normalize_identity(raw):
            matches.append(row)
    if len(matches) == 1:
        return {"status": "SAFE_CHARACTER", "character_id": matches[0].get("character_uid"), "character": matches[0].get("canonical_name")}
    return {"status": "REVIEW_CHARACTER_CONFLICT", "character_id": None, "character": raw}


def resolve_credit(raw: dict[str, Any], *, work_id: str | None, snapshot: Any) -> dict[str, Any]:
    source_role = str(raw.get("source_role") or raw.get("function") or "").strip()
    role = canonical_role(source_role)
    artist_name = str(raw.get("artist_name") or raw.get("source_artist_name") or "").strip()
    artist = _artist_resolution(artist_name, snapshot)
    source_character = raw.get("character") if source_role.casefold() not in VOICE_TYPES else None
    character = _character_resolution(source_character, work_id, snapshot)
    status = "SAFE_ROLE" if role else "REVIEW_ROLE_UNKNOWN"
    if artist["status"].startswith("REVIEW"):
        status = artist["status"]
    elif character["status"].startswith("REVIEW"):
        status = character["status"]
    return {"source_artist_name": artist_name, "source_role": source_role, "source_character": source_character, "canonical_role": role, "artist_resolution": artist, "character_resolution": character, "credit_kind": raw.get("credit_kind") or ("cast" if source_character else "artistic_team"), "source_url": raw.get("source_url"), "source_field": raw.get("source_field"), "provenance": raw.get("provenance") or {}, "resolution_status": status}


def stage_credits(events: list[Any], resolutions: list[dict[str, Any]], snapshot: Any) -> dict[str, Any]:
    work_by_event = {row.get("event_key"): row.get("work_id") for row in resolutions if row.get("work_id")}
    all_rows = []
    for event in events:
        for raw in event.credits:
            all_rows.append({"event_key": event.event_key, "credit": resolve_credit(raw, work_id=work_by_event.get(event.event_key), snapshot=snapshot)})
    safe, review, seen = [], [], set()
    for row in all_rows:
        credit = row["credit"]
        key = (row["event_key"], credit["artist_resolution"].get("lookup_key"), credit.get("canonical_role"), credit["character_resolution"].get("character_id"))
        if key in seen:
            continue
        seen.add(key)
        (safe if credit["resolution_status"].startswith("SAFE_") else review).append(row)
    artists = {r["credit"]["artist_resolution"]["canonical_name"]: r["credit"]["artist_resolution"] for r in safe if r["credit"]["artist_resolution"]["status"] == "SAFE_NEW_ARTIST"}
    return {"safe_existing_artists": [r["credit"]["artist_resolution"] for r in safe if r["credit"]["artist_resolution"]["status"] == "SAFE_EXISTING"], "safe_new_artists": list(artists.values()), "safe_cast_assignments": [r for r in safe if r["credit"].get("credit_kind") == "cast"], "safe_artistic_team": [r for r in safe if r["credit"].get("credit_kind") == "artistic_team"], "safe_ensembles": [r for r in safe if r["credit"].get("credit_kind") == "ensemble"], "review_artist_conflicts": [r for r in review if r["credit"]["resolution_status"] == "REVIEW_ARTIST_CONFLICT"], "review_character_conflicts": [r for r in review if r["credit"]["resolution_status"] == "REVIEW_CHARACTER_CONFLICT"], "review_unknown_roles": [r for r in review if r["credit"]["resolution_status"] == "REVIEW_ROLE_UNKNOWN"], "review_source_ambiguous": [r for r in review if r["credit"]["resolution_status"] == "REVIEW_SOURCE_AMBIGUOUS"], "safe_event_credits": safe, "review_event_credits": review, "counts": {"credits_raw": len(all_rows), "credits_safe": len(safe), "credits_review": len(review), "role_safe": sum(bool(r["credit"].get("canonical_role")) for r in safe), "role_review": sum(not bool(r["credit"].get("canonical_role")) for r in review), "artist_existing": sum(r["credit"]["artist_resolution"]["status"] == "SAFE_EXISTING" for r in safe), "artist_new_safe": sum(r["credit"]["artist_resolution"]["status"] == "SAFE_NEW_ARTIST" for r in safe), "artist_review": sum(r["credit"]["artist_resolution"]["status"].startswith("REVIEW") for r in review), "character_safe": sum(r["credit"]["character_resolution"]["status"] == "SAFE_CHARACTER" for r in safe), "character_review": sum(r["credit"]["character_resolution"]["status"].startswith("REVIEW") for r in review)}}
