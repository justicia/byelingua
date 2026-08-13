"""Conservative adapters for existing official raw fixtures.

This first adapter layer deliberately does not scrape.  It consumes raw files
already present in venue-ingestion-batch/raw and emits only records that have a
stable JSON-LD @id or an explicit source event id.  Unknown records go to
quarantine instead of being guessed into production.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from .model import CanonicalEvent


def _text(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))).strip()


def _json_ld(raw: str):
    for block in re.findall(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", raw, re.I | re.S):
        try:
            value = json.loads(html.unescape(block.strip()))
        except json.JSONDecodeError:
            continue
        yield from (value if isinstance(value, list) else [value])


def extract_fixture(manifest: dict, raw_path: Path) -> tuple[list[CanonicalEvent], list[dict]]:
    raw = raw_path.read_text(encoding="utf-8", errors="ignore")
    events, quarantine = [], []
    for item in _json_ld(raw):
        if not isinstance(item, dict):
            continue
        type_value = item.get("@type")
        types = set(type_value) if isinstance(type_value, list) else {type_value}
        if not types.intersection({"Event", "MusicEvent", "TheaterEvent"}):
            continue
        source_id = str(item.get("@id") or item.get("identifier") or "").strip()
        start = str(item.get("startDate") or "")
        if not source_id or not start:
            quarantine.append({"raw": item, "errors": ["missing stable JSON-LD source identity or startDate"]})
            continue
        date, _, time = start.partition("T")
        venue = item.get("location") if isinstance(item.get("location"), dict) else {}
        event = CanonicalEvent(
            source=manifest["source"], source_event_id=source_id,
            source_url=str(item.get("url") or manifest["source"]),
            venue=str(venue.get("name") or manifest["venue"]), city=manifest["city"], country=manifest["country"],
            title=_text(item.get("name")), date=date, start_time=time or None,
        )
        errors = event.validate()
        if errors:
            quarantine.append({"raw": item, "errors": errors})
        else:
            events.append(event)
    return events, quarantine
