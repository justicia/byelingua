"""Read-only raw parser for the Auditorio Nacional programme site.

This module intentionally stops at source material.  It does not classify
programme structure, resolve entities, or write to a database.  In particular,
each discovery row is an occurrence even when its detail URL is shared.
"""
from __future__ import annotations

import hashlib
import re
import warnings
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable, Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from season_ingestion.schema import CanonicalEvent


SOURCE = "auditorio_nacional"
BASE_URL = "https://auditorionacional.inaem.gob.es"
DISCOVERY_URL = f"{BASE_URL}/es/programacion"
PAGE_SIZE = 12
USER_AGENT = "ByelinguaAuditorioParser/1.0 (read-only dry run)"

ROOM_PATTERNS = (
    ("Sala Sinfónica", "SALA_SINFONICA"),
    ("Sala de Cámara", "SALA_DE_CAMARA"),
)


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def node_text(node: Tag | None) -> str:
    return clean(node.get_text(" ", strip=True)) if node else ""


def _lines(node: Tag) -> list[str]:
    """Return source lines in DOM order, using only whitespace cleanup."""
    lines: list[str] = []
    for part in node.stripped_strings:
        value = clean(str(part))
        if value:
            lines.append(value)
    return lines


def _room_match(value: str) -> tuple[str, str] | None:
    folded = clean(value).casefold()
    for raw, normalized in ROOM_PATTERNS:
        if raw.casefold() in folded:
            return raw, normalized
    return None


def resolve_detail_room(info: list[dict], blocks: list[dict]) -> dict:
    """Resolve room from explicit detail-page evidence only."""
    evidence: list[dict] = []
    for item in info:
        text = clean(" ".join((item.get("raw_label", ""), item.get("raw_text", ""))))
        match = _room_match(text)
        if match:
            evidence.append({"room_raw": match[0], "normalized_room": match[1], "method": "detail_info", "raw_text": text})
    for block in blocks:
        text = clean(block.get("raw_text", ""))
        match = _room_match(text)
        if match:
            evidence.append({"room_raw": match[0], "normalized_room": match[1], "method": "detail_content", "raw_text": text})
    normalized = {item["normalized_room"] for item in evidence}
    if len(normalized) == 1:
        selected = evidence[0]
        return {"room_raw": selected["room_raw"], "normalized_room": selected["normalized_room"], "status": "DETAIL_ROOM_VERIFIED", "evidence": evidence}
    if len(normalized) > 1:
        return {"room_raw": None, "normalized_room": "CONFLICTING_SOURCE_EVIDENCE", "status": "REVIEW_LOCATION", "evidence": evidence}
    return {"room_raw": None, "normalized_room": "ROOM_NOT_STATED", "status": "REVIEW_LOCATION", "evidence": []}


def page_url(offset: int, discovery_url: str = DISCOVERY_URL) -> str:
    separator = "&" if "?" in discovery_url else "?"
    return f"{discovery_url}{separator}b_start:int={offset}"


def parse_discovery_page(html: str, discovery_url: str, *, offset: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for row_index, card in enumerate(soup.select("article.eventitem")):
        title_node = card.select_one(".eventitem__title a[href]")
        date_node = card.select_one(".event-date .weekday")
        if not title_node or not date_node:
            continue
        href = clean(title_node.get("href"))
        raw_datetime = clean(date_node.get_text(" ", strip=True))
        if not href or not raw_datetime:
            continue
        rows.append({
            "source": SOURCE,
            "source_url": urljoin(BASE_URL, href),
            "discovery_url": discovery_url,
            "raw_title": node_text(title_node),
            "raw_datetime": raw_datetime,
            "raw_venue": node_text(card.select_one(".eventitem__text .location span")) or None,
            "discovery_order": offset + row_index,
            "source_occurrence": {
                "discovery_page_offset": offset,
                "discovery_row_index": row_index,
                "discovery_page_size": PAGE_SIZE,
            },
        })
    return rows


def parse_detail_page(html: str, detail_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = node_text(soup.select_one("#portal-content article#content h1"))
    content = soup.select_one("#portal-content article#content .content")
    blocks: list[dict] = []
    if content:
        for order, heading in enumerate(content.find_all("h4")):
            lines = _lines(heading)
            if not lines:
                continue
            blocks.append({
                "order": order,
                "tag": "h4",
                "raw_text": "\n".join(lines),
                "raw_lines": lines,
            })

    info: list[dict] = []
    for item in soup.select("#portal-content article#content .rightColumn__item"):
        label = node_text(item.select_one(".rightColumn__item__label"))
        value_node = item.select_one(".rightColumn__item__text")
        value_lines = _lines(value_node) if value_node else []
        if label or value_lines:
            info.append({"raw_label": label, "raw_lines": value_lines,
                         "raw_text": "\n".join(value_lines)})

    # The site's current layout uses separate h4 blocks for credits and
    # programme.  Keep the split positional and transparent; this is not
    # semantic structure classification.  raw_content_blocks remains the
    # authoritative source for layouts that do not follow that convention.
    raw_artist_lines = blocks[0]["raw_lines"] if len(blocks) >= 2 else []
    raw_programme_lines = [line for block in blocks[1:] for line in block["raw_lines"]]
    return {
        "detail_url": detail_url,
        "raw_detail_title": title or None,
        "raw_content_blocks": blocks,
        "raw_artist_lines": raw_artist_lines,
        "raw_programme_lines": raw_programme_lines,
        "raw_info": info,
        "room_resolution": resolve_detail_room(info, blocks),
    }


def _fetch_url(url: str, *, insecure_tls: bool = False) -> str:
    if insecure_tls:
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    response = requests.get(url, timeout=45, headers={"User-Agent": USER_AGENT},
                            verify=not insecure_tls)
    response.raise_for_status()
    # The official pages declare UTF-8.  Do not use apparent_encoding here:
    # proxy/HTML heuristics can misclassify Spanish text as Latin-1 and corrupt
    # the raw source material this phase is specifically meant to preserve.
    if not response.encoding:
        response.encoding = "utf-8"
    return response.text


def discover(
    fetch: Callable[[str], str],
    *,
    season_start: str = "2026-09-01",
    season_end: str = "2027-08-31",
    discovery_url: str = DISCOVERY_URL,
) -> tuple[list[dict], list[dict]]:
    """Fetch all HTML pagination pages and retain occurrences in the season."""
    first = datetime.fromisoformat(season_start).date()
    last = datetime.fromisoformat(season_end).date()
    occurrences: list[dict] = []
    page_records: list[dict] = []
    offset = 0
    while True:
        url = page_url(offset, discovery_url)
        html = fetch(url)
        rows = parse_discovery_page(html, url, offset=offset)
        page_records.append({"discovery_url": url, "offset": offset,
                             "row_count": len(rows)})
        for row in rows:
            try:
                occurrence_date = datetime.fromisoformat(row["raw_datetime"]).date()
            except ValueError:
                continue
            if first <= occurrence_date <= last:
                occurrences.append(row)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return occurrences, page_records


def attach_details(
    occurrences: Iterable[dict],
    fetch: Callable[[str], str],
    *,
    max_workers: int = 8,
) -> tuple[list[dict], list[dict]]:
    """Fetch each detail URL once, then copy its raw parse onto each occurrence."""
    cache: dict[str, dict] = {}
    errors: list[dict] = []
    urls = list(dict.fromkeys(row["source_url"] for row in occurrences))

    def fetch_one(url: str) -> tuple[str, dict, dict | None]:
        try:
            return url, parse_detail_page(fetch(url), url), None
        except Exception as exc:  # retain the occurrence even when source fetch fails
            failure = {
                "detail_url": url, "raw_detail_title": None,
                "raw_content_blocks": [], "raw_artist_lines": [],
                "raw_programme_lines": [], "raw_info": [],
                "room_resolution": {"room_raw": None, "normalized_room": "ROOM_NOT_STATED", "status": "REVIEW_LOCATION", "evidence": []},
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
    result = []
    for occurrence in occurrences:
        row = dict(occurrence)
        row.update(cache[row["source_url"]])
        row["raw_listing_venue"] = row.get("raw_venue")
        resolution = row.get("room_resolution") or {}
        row["official_room_raw"] = resolution.get("room_raw")
        row["normalized_room"] = resolution.get("normalized_room", "ROOM_NOT_STATED")
        row["room_resolution_status"] = resolution.get("status", "REVIEW_LOCATION")
        row["room_evidence"] = resolution.get("evidence", [])
        row["raw_venue"] = row.get("official_room_raw")
        result.append(row)
    return deduplicate_occurrences(result), errors


def deduplicate_occurrences(occurrences: Iterable[dict]) -> list[dict]:
    """Treat room disagreement as an attribute conflict, never a new event."""
    selected: dict[tuple[str, str, str], dict] = {}
    for occurrence in occurrences:
        key = (occurrence.get("source_url", ""), occurrence.get("raw_datetime", ""), occurrence.get("raw_title", ""))
        current = selected.get(key)
        if current is None:
            selected[key] = dict(occurrence)
            continue
        current_room = current.get("normalized_room")
        new_room = occurrence.get("normalized_room")
        if current_room == "ROOM_NOT_STATED" and new_room not in {None, "ROOM_NOT_STATED"}:
            selected[key] = dict(occurrence)
        elif current_room != new_room and new_room not in {None, "ROOM_NOT_STATED"}:
            current["official_room_raw"] = None
            current["normalized_room"] = "CONFLICTING_SOURCE_EVIDENCE"
            current["room_resolution_status"] = "REVIEW_LOCATION"
            current["room_evidence"] = list(current.get("room_evidence") or []) + list(occurrence.get("room_evidence") or [])
            current["raw_venue"] = None
    return list(selected.values())


def summarize(occurrences: list[dict], pages: list[dict], errors: list[dict]) -> dict:
    parsed_dates = []
    for row in occurrences:
        try:
            parsed_dates.append(datetime.fromisoformat(row["raw_datetime"]))
        except ValueError:
            pass
    duplicate_keys = [(row["source_url"], row["raw_datetime"], row["raw_title"]) for row in occurrences]
    counts = Counter(duplicate_keys)
    detail_counts = Counter(row["source_url"] for row in occurrences)
    # Coverage is reported at detail-page level.  Occurrences are intentionally
    # repeated in the parser output when a page has multiple performances, but
    # a page should count once in these content-coverage fields.
    detail_pages = {}
    for row in occurrences:
        detail_pages.setdefault(row["source_url"], row)
    programme_pages = sum(bool(row.get("raw_programme_lines")) for row in detail_pages.values())
    artist_pages = sum(bool(row.get("raw_artist_lines")) for row in detail_pages.values())
    no_programme = sum(not row.get("raw_programme_lines") for row in detail_pages.values())
    unknown = sum(
        bool(row.get("raw_fetch_error")) or not row.get("raw_content_blocks")
        or (not row.get("raw_programme_lines") and not row.get("raw_artist_lines"))
        for row in detail_pages.values()
    )
    monthly = Counter(value.strftime("%Y-%m") for value in parsed_dates)
    return {
        "source": SOURCE,
        "discovery_page_count": len(pages),
        "discovery_occurrence_count": len(occurrences),
        "unique_detail_url_count": len(detail_counts),
        "detail_urls_reused_by_multiple_performances": sum(v > 1 for v in detail_counts.values()),
        "minimum_datetime": min(parsed_dates).isoformat() if parsed_dates else None,
        "maximum_datetime": max(parsed_dates).isoformat() if parsed_dates else None,
        "monthly_occurrence_distribution": dict(sorted(monthly.items())),
        "detail_fetch_success_count": len(detail_counts) - len(errors),
        "detail_fetch_failure_count": len(errors),
        "pages_with_programme": programme_pages,
        "pages_with_artist_credit_content": artist_pages,
        "pages_with_no_programme": no_programme,
        "unknown_unparsed_raw_content_count": unknown,
        "duplicate_discovery_occurrence_count": sum(v - 1 for v in counts.values() if v > 1),
        "database_writes": 0,
        "detail_fetch_errors": errors,
    }


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
            artist, raw_role = text, "ensemble"
            function = "ensemble"
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
    """Canonical-event adapter over the official paginated Auditorio site.

    Discovery rows remain occurrence-level.  A reused detail page is fetched
    once, but its official date/time rows produce separate canonical events.
    """

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
            occurrences, pages = discover(self._fetch, season_start=start, season_end=end, discovery_url=discovery_url)
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
        enriched, errors = attach_details(occurrences, self._fetch, max_workers=int(self.settings.get("detail_workers", 8)))
        detail_urls = list(dict.fromkeys(row["source_url"] for row in occurrences))
        self.detail_pages_requested.extend(detail_urls)
        self.detail_pages_successful.extend(url for url in detail_urls if url not in {item["source_url"] for item in errors})
        self.detail_pages_failed.extend(item["source_url"] for item in errors)
        self.requested_months.extend(detail_urls)
        self.successful_months.extend(self.detail_pages_successful)
        self.failed_months.extend(self.detail_pages_failed)
        self.source_pages.update({url: url for url in self.detail_pages_successful})
        self.last_errors.extend(errors)

        events: list[CanonicalEvent] = []
        slots: set[tuple[str, str, str, str | None]] = set()
        for row in enriched:
            try:
                parsed = datetime.fromisoformat(str(row["raw_datetime"]))
            except (KeyError, TypeError, ValueError):
                self.date_candidates_rejected += 1
                continue
            event_date, start_time = parsed.date().isoformat(), parsed.strftime("%H:%M")
            title = clean(row.get("raw_detail_title") or row.get("raw_title")) or "Auditorio Nacional event"
            room = row.get("official_room_raw") if row.get("room_resolution_status") == "DETAIL_ROOM_VERIFIED" else None
            programme, programme_status = _auditorio_programme(row.get("raw_programme_lines") or [], title, row["source_url"])
            slot = (title, event_date, start_time, room)
            if slot in slots:
                self.duplicate_performance_slot += 1
            slots.add(slot)
            source_event_id = hashlib.sha256(f"{row['source_url']}|{row['raw_datetime']}".encode("utf-8")).hexdigest()[:24]
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
                    "room": row.get("room_resolution") or {},
                    "detail_enrichment": {"status": "complete", "source_url": row["source_url"]},
                },
                raw={
                    "listing_source_url": row.get("discovery_url"),
                    "detail_source_url": row["source_url"],
                    "source_occurrence": row.get("source_occurrence"),
                    "raw_datetime": row.get("raw_datetime"),
                },
            )
            event.validate()
            events.append(event)
            self.date_candidates_accepted += 1
        return sorted({event.event_key: event for event in events}.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
