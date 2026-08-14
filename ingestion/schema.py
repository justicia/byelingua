from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from typing import Any


def normalize_search_key(value: str | None) -> str:
    """Return a comparison-only key without changing the displayed source text."""
    text = (value or "").replace("œ", "oe").replace("Œ", "OE")
    text = text.replace("æ", "ae").replace("Æ", "AE")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def canonical_event_type(source_label: str | None) -> str:
    key = normalize_search_key(source_label)
    if any(token in key for token in ("opera", "lirica", "oratorio")):
        return "opera"
    if "danza" in key or "ballet" in key:
        return "dance"
    if "recital" in key:
        return "recital"
    if any(token in key for token in ("concierto", "camara", "sinfoni")):
        return "concert"
    if "flamenco" in key:
        return "dance"
    return "other"


def stable_event_identity(event: dict[str, Any]) -> str:
    # A production page/detail URL is the stable source identifier.  The
    # calendar title is deliberately excluded because Teatro Real publishes
    # language-specific titles (for example, English vs. Spanish) for the
    # same production.  Date, time, venue and room keep each performance
    # occurrence separate and make repeated ingestion idempotent.
    parts = (
        event.get("source"),
        event.get("source_url"),
        event.get("organization"),
        event.get("venue"),
        event.get("room"),
        event.get("date"),
        event.get("start_time"),
    )
    material = "|".join(normalize_search_key(str(value or "")) for value in parts)
    return "teatro-real:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def searchable_text(event: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("title", "display_title", "organization", "venue", "city"):
        values.append(str(event.get(key) or ""))
    for work in event.get("programme", []):
        values.extend((str(work.get("title") or ""), str(work.get("composer") or "")))
    for credit in event.get("credits", []):
        values.extend(
            (
                str(credit.get("person") or ""),
                str(credit.get("character_role") or ""),
                str(credit.get("artistic_function") or ""),
                str(credit.get("raw_role_label") or ""),
            )
        )
    return normalize_search_key(" ".join(values))


def validate_event(event: dict[str, Any]) -> None:
    required = ("source", "source_event_id", "source_url", "organization", "venue", "city", "date", "start_time", "event_type", "title")
    missing = [key for key in required if not event.get(key)]
    if missing:
        raise ValueError(f"normalized event missing required fields: {', '.join(missing)}")
    date.fromisoformat(str(event["date"]))
    if not re.fullmatch(r"[0-2]\d:[0-5]\d", str(event["start_time"])):
        raise ValueError(f"invalid start_time: {event['start_time']!r}")
    if event["event_type"] not in {"opera", "concert", "recital", "dance", "other"}:
        raise ValueError(f"invalid event_type: {event['event_type']!r}")
    for row in event.get("cast", []):
        if not row.get("character_role") or not row.get("person"):
            raise ValueError("cast rows require original character_role and person")
    for row in event.get("artistic_team", []):
        if row.get("character_role"):
            raise ValueError("artistic-team rows cannot contain character roles")
