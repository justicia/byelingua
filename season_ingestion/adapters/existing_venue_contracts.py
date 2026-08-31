"""Stable existing-venue adapters backed by official detail contracts.

This module is intentionally read-only.  It converts official Auditorio
Nacional discovery rows and detail pages into the shared canonical event
shape while preserving every performance occurrence, including rows that
reuse a detail URL.
"""
from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable, Iterable
from urllib.parse import urljoin

from season_ingestion.adapters.auditorio_nacional import (
    BASE_URL,
    DISCOVERY_URL,
    PAGE_SIZE,
    SOURCE,
    _fetch_url,
    clean,
    node_text,
    parse_detail_page,
    parse_discovery_page,
)
from season_ingestion.schema import CanonicalEvent


ROOM_PATTERNS = (
    ("Sala Sinfónica", "SALA_SINFONICA"),
    ("Sala de Cámara", "SALA_DE_CAMARA"),
)

_VOICE_ROLES = {
    "soprano", "mezzosoprano", "mezzo-soprano", "contralto", "tenor",
    "barítono", "baritono", "baritone", "bajo", "bass", "solista",
    "narrador", "narradora", "violín", "violin", "viola", "violonchelo",
    "violoncello", "contrabajo", "piano", "órgano", "organo", "guitarra",
}
_TEAM_ROLES = {
    "director": "conductor", "directora": "conductor", "dirección": "conductor",
    "direccion": "conductor", "maestro": "conductor", "regia": "stage_director",
    "escena": "stage_director", "director de escena": "stage_director",
    "solista": "performer",
}


def page_url(offset: int, discovery_url: str = DISCOVERY_URL) -> str:
    separator = "&" if "?" in discovery_url else "?"
    return f"{discovery_url}{separator}b_start:int={offset}"


def _room_match(value: str) -> tuple[str, str] | None:
    folded = clean(value).casefold()
    for raw, normalized in ROOM_PATTERNS:
        if raw.casefold() in folded:
            return raw, normalized
    return None


def resolve_detail_room(info: list[dict], blocks: list[dict]) -> dict:
    """Resolve a room only from explicit official detail-page evidence."""
    evidence: list[dict] = []
    for item in info:
        text = clean(" ".join((item.get("raw_label", ""), item.get("raw_text", ""))))
        match = _room_match(text)
        if match:
            evidence.append({
                "room_raw": match[0],
                "normalized_room": match[1],
                "method": "detail_info",
                "raw_text": text,
            })
    for block in blocks:
        text = clean(block.get("raw_text", ""))
        match = _room_match(text)
        if match:
            evidence.append({
                "room_raw": match[0],
                "normalized_room": match[1],
                "method": "detail_content",
                "raw_text": text,
            })
    normalized = {item["normalized_room"] for item in evidence}
    if len(normalized) == 1:
        selected = evidence[0]
        return {
            "room_raw": selected["room_raw"],
            "normalized_room": selected["normalized_room"],
            "status": "DETAIL_ROOM_VERIFIED",
            "evidence": evidence,
        }
    if len(normalized) > 1:
        return {
            "room_raw": None,
            "normalized_room": "CONFLICTING_SOURCE_EVIDENCE",
            "status": "REVIEW_LOCATION",
            "evidence": evidence,
        }
    return {
        "room_raw": None,
        "normalized_room": "ROOM_NOT_STATED",
        "status": "REVIEW_LOCATION",
        "evidence": [],
    }


def _discover(
    fetch: Callable[[str], str],
    *,
    season_start: str,
    season_end: str,
    discovery_url: str,
) -> tuple[list[dict], list[dict]]:
    first = datetime.fromisoformat(season_start).date()
    last = datetime.fromisoformat(season_end).date()
    occurrences: list[dict] = []
    pages: list[dict] = []
    offset = 0
    while True:
        url = page_url(offset, discovery_url)
        html = fetch(url)
        rows = parse_discovery_page(html, url, offset=offset)
        pages.append({"discovery_url": url, "offset": offset, "row_count": len(rows)})
        for row in rows:
            try:
                occurrence_date = datetime.fromisoformat(row["raw_datetime"]).date()
            except (KeyError, TypeError, ValueError):
                continue
            if first <= occurrence_date <= last:
                occurrences.append(row)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return occurrences, pages


def _attach_details(
    occurrences: Iterable[dict],
    fetch: Callable[[str], str],
    *,
    max_workers: int = 8,
) -> tuple[list[dict], list[dict]]:
    """Fetch each detail URL once without collapsing occurrence rows."""
    cache: dict[str, dict] = {}
    errors: list[dict] = []
    urls = list(dict.fromkeys(row["source_url"] for row in occurrences))

    def fetch_one(url: str) -> tuple[str, dict, dict | None]:
        try:
            return url, parse_detail_page(fetch(url), url), None
        except Exception as exc:  # retain the occurrence for review
            failure = {
                "detail_url": url,
                "raw_detail_title": None,
                "raw_content_blocks": [],
                "raw_artist_lines": [],
                "raw_programme_lines": [],
                "raw_info": [],
                "raw_fetch_error": f"{type(exc).__name__}: {exc}",
            }
            return url, failure, {"source_url": url, "error": failure["raw_fetch_error"]}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_one, url) for url in urls]
        for future in as_completed(futures):
            url, parsed, error = future.result()
            cache[url] = parsed
            if error:
                errors.append(error)
    errors.sort(key=lambda item: item["source_url"])
    result: list[dict] = []
    for occurrence in occurrences:
        row = dict(occurrence)
        row.update(cache[row["source_url"]])
        result.append(row)
    return result, errors


def _auditorio_credits(lines: Iterable[str], detail_url: str) -> list[dict]:
    """Turn explicit detail-page role suffixes into reviewable credit rows."""
    result: list[dict] = []
    for raw in lines:
        text = clean(raw)
        if not text:
            continue
        match = re.match(r"^(.*?)[,;]\s*([^,;]+)$", text)
        if match:
            artist, raw_role = (clean(value) for value in match.groups())
            normalized = raw_role.casefold()
            function = _TEAM_ROLES.get(normalized)
            if function is None and normalized in _VOICE_ROLES:
                function = "performer"
            if function is None:
                function = "artist"
        else:
            artist, raw_role, function = text, "ensemble", "ensemble"
        kind = "cast" if function == "performer" else "ensemble" if function == "ensemble" else "artistic_team"
        result.append({
            "artist_name": artist,
            "source_role": raw_role,
            "function": function,
            "credit_kind": kind,
            "source_url": detail_url,
            "source_field": "official.detail.raw_artist_lines",
            "raw_source_block": text,
            "provenance": {"source_url": detail_url, "source_field": "official.detail.raw_artist_lines"},
        })
    return result


def _auditorio_programme(lines: Iterable[str], title: str, detail_url: str) -> tuple[list[dict], str]:
    values = [clean(line) for line in lines if clean(line)]
    if not values:
        return ([{
            "source_title": title,
            "raw_title": title,
            "composer": None,
            "source_programme_index": 1,
            "raw_programme_index": 1,
            "original_programme_order": 1,
            "resolution_status": "review_required",
            "provenance": {"source_url": detail_url, "source_field": "official.detail.title"},
        }], "NO_PROGRAMME_EVIDENCE")
    return ([{
        "source_title": value,
        "raw_title": value,
        "composer": None,
        "source_programme_index": index,
        "raw_programme_index": index,
        "original_programme_order": index,
        "resolution_status": "pending_global_resolution",
        "provenance": {"source_url": detail_url, "source_field": "official.detail.programme"},
    } for index, value in enumerate(values, start=1)], "PROGRAMME_EVIDENCE_FOUND")


class AuditorioNacionalAdapter:
    """Read-only adapter over official paginated discovery and detail pages."""

    def __init__(self, settings: dict, fetch: Callable[[str], str] | None = None):
        self.settings = settings
        self._fetch = fetch or _fetch_url
        self.last_errors: list[dict[str, str]] = []
        self.requested_months: list[str] = []
        self.successful_months: list[str] = []
        self.failed_months: list[str] = []
        self.source_pages: dict[str, str] = {}
        self.listing_pages_requested: list[str] = []
        self.listing_pages_successful: list[str] = []
        self.listing_pages_failed: list[str] = []
        self.detail_pages_requested: list[str] = []
        self.detail_pages_successful: list[str] = []
        self.detail_pages_failed: list[str] = []
        self.productions_discovered = 0
        self.detail_pages_out_of_season_skipped = 0
        self.date_candidates_found = 0
        self.date_candidates_accepted = 0
        self.date_candidates_rejected = 0
        self.date_year_unverified = 0
        self.events_outside_season = 0
        self.duplicate_performance_slot = 0
        self.ambiguous_same_day_occurrence = 0
        self.null_timed_shadow_duplicates = 0
        self.year_inferred_without_production_evidence = 0

    def ingest(self, season: str) -> list[CanonicalEvent]:
        from season_ingestion.season import resolve_season_bounds

        start, end = resolve_season_bounds(season, self.settings)
        discovery_url = self.settings.get("discovery_source") or self.settings.get("official_source", DISCOVERY_URL)
        try:
            occurrences, pages = _discover(
                self._fetch,
                season_start=start,
                season_end=end,
                discovery_url=discovery_url,
            )
        except Exception as exc:
            self.requested_months.append(discovery_url)
            self.listing_pages_requested.append(discovery_url)
            self.failed_months.append(discovery_url)
            self.listing_pages_failed.append(discovery_url)
            self.last_errors.append({"url": discovery_url, "error": f"{type(exc).__name__}: {exc}"})
            return []
        for page in pages:
            url = page["discovery_url"]
            self.requested_months.append(url)
            self.listing_pages_requested.append(url)
            self.successful_months.append(url)
            self.listing_pages_successful.append(url)
            self.source_pages[url] = url
        self.productions_discovered = len({row["source_url"] for row in occurrences})
        self.date_candidates_found = len(occurrences)
        enriched, errors = _attach_details(
            occurrences,
            self._fetch,
            max_workers=int(self.settings.get("detail_workers", 8)),
        )
        detail_urls = list(dict.fromkeys(row["source_url"] for row in occurrences))
        error_urls = {item["source_url"] for item in errors}
        self.detail_pages_requested.extend(detail_urls)
        self.detail_pages_successful.extend(url for url in detail_urls if url not in error_urls)
        self.detail_pages_failed.extend(item["source_url"] for item in errors)
        self.requested_months.extend(detail_urls)
        self.successful_months.extend(self.detail_pages_successful)
        self.failed_months.extend(self.detail_pages_failed)
        self.source_pages.update({url: url for url in self.detail_pages_successful})
        self.last_errors.extend(errors)

        events: list[CanonicalEvent] = []
        seen_slots: set[tuple[str, str, str | None]] = set()
        for row in enriched:
            try:
                parsed = datetime.fromisoformat(str(row["raw_datetime"]))
            except (KeyError, TypeError, ValueError):
                self.date_candidates_rejected += 1
                continue
            event_date, start_time = parsed.date().isoformat(), parsed.strftime("%H:%M")
            title = clean(row.get("raw_detail_title") or row.get("raw_title")) or "Auditorio Nacional event"
            room_resolution = resolve_detail_room(row.get("raw_info") or [], row.get("raw_content_blocks") or [])
            room = room_resolution["room_raw"] if room_resolution["status"] == "DETAIL_ROOM_VERIFIED" else None
            programme, programme_status = _auditorio_programme(
                row.get("raw_programme_lines") or [], title, row["source_url"]
            )
            slot = (title, event_date, start_time)
            if slot in seen_slots:
                self.duplicate_performance_slot += 1
            seen_slots.add(slot)
            occurrence = row.get("source_occurrence") or {}
            identity = json.dumps(occurrence, ensure_ascii=False, sort_keys=True)
            source_event_id = hashlib.sha256(
                f"{row['source_url']}|{row['raw_datetime']}|{identity}".encode("utf-8")
            ).hexdigest()[:24]
            event = CanonicalEvent(
                source=self.settings.get("source_id", SOURCE),
                source_event_id=source_event_id,
                source_url=row["source_url"],
                organization=self.settings["organization"],
                venue=self.settings["venue"],
                city=self.settings["city"],
                country=self.settings["country"],
                timezone=self.settings["timezone"],
                title=title,
                date=event_date,
                start_time=start_time,
                end_time=None,
                room=room,
                event_type="performance",
                classification="performance",
                programme=programme,
                credits=_auditorio_credits(row.get("raw_artist_lines") or [], row["source_url"]),
                data_quality={
                    "programme": {"status": programme_status, "reason": "official Auditorio detail page"},
                    "room": room_resolution,
                    "detail_enrichment": {"status": "complete", "source_url": row["source_url"]},
                },
                raw={
                    "listing_source_url": row.get("discovery_url"),
                    "detail_source_url": row["source_url"],
                    "source_occurrence": occurrence,
                    "raw_datetime": row.get("raw_datetime"),
                },
            )
            event.validate()
            events.append(event)
            self.date_candidates_accepted += 1
        return sorted(events, key=lambda event: (event.date, event.start_time or "", event.event_key))
