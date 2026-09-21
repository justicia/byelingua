"""Deterministic official HTML adapter for L'Auditori Barcelona.

The season landing page embeds the official event cards in the
``window.aPnextevents`` JSON payload.  This adapter expands the explicit date
text into occurrence-level ``CanonicalEvent`` rows and optionally enriches
each row from the official detail page's Repertoire and artist sections.
Hermes is intentionally not involved in this path.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, Callable
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup

from season_ingestion.schema import CanonicalEvent


MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
MONTH_PATTERN = "|".join(MONTHS)
DATE_RE = re.compile(
    rf"\b(?P<month>{MONTH_PATTERN})\s+"
    r"(?P<days>\d{1,2}(?:(?:\s+and\s+|\s*,\s*(?!20\d{2}\b))\d{1,2})*)"
    r"(?:\s*,\s*(?P<year>20\d{2}))?",
    re.IGNORECASE,
)
TIME_RE = re.compile(
    r"(?<!\d)(?P<hour>\d{1,2})(?:(?P<separator>[:.])(?P<minute>\d{2}))?\s*"
    r"(?P<ampm>[ap]\s*\.?\s*m\.?)\b",
    re.IGNORECASE,
)
TWENTY_FOUR_HOUR_RE = re.compile(r"(?<!\d)(?P<hour>[01]?\d|2[0-3])[:.](?P<minute>[0-5]\d)\s*h\b", re.IGNORECASE)
PAYLOAD_RE = re.compile(
    r"window\.aPnextevents\s*=\s*JSON\.parse\(decodeURIComponent\("
    r"(?P<quote>['\"])(?P<payload>.*?)(?P=quote)\)\)",
    re.DOTALL,
)
ROLE_WORDS = {
    "conductor",
    "director",
    "piano",
    "pianist",
    "violin",
    "viola",
    "cello",
    "violoncello",
    "organ",
    "harp",
    "guitar",
    "trumpet",
    "clarinet",
    "flute",
    "percussion",
    "soprano",
    "mezzo-soprano",
    "tenor",
    "baritone",
    "bass",
    "narrator",
    "speaker",
    "host",
}
ROLE_HINTS = ROLE_WORDS | {
    "double bass",
    "creation",
    "direction",
    "composition",
    "lighting",
    "costumes",
    "stage",
    "sound",
    "design",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def _nested_name(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("post_title", "name", "title"):
            result = _clean(value.get(key))
            if result:
                return result
        return None
    result = _clean(value)
    return result or None


def extract_event_cards(page: str) -> list[dict[str, Any]]:
    """Extract the official event-card payload without executing page JavaScript."""
    for match in PAYLOAD_RE.finditer(page):
        try:
            payload = json.loads(unquote(match.group("payload")))
        except (TypeError, ValueError):
            continue
        cards = payload.get("events") if isinstance(payload, dict) else None
        if isinstance(cards, list):
            return [card for card in cards if isinstance(card, dict)]
    raise ValueError("official L'Auditori page has no aPnextevents payload")


def _season_bounds(season: str, settings: dict[str, Any]) -> tuple[date, date]:
    configured = (settings.get("season_bounds") or {}).get(season)
    if configured:
        return date.fromisoformat(configured["season_start"]), date.fromisoformat(configured["season_end"])
    start_year, end_short = (int(part) for part in season.split("-", 1))
    end_year = start_year // 100 * 100 + end_short
    return date(start_year, 9, 1), date(end_year, 8, 31)


def _time_values(value: str) -> list[str]:
    values: list[str] = []
    for match in TIME_RE.finditer(value):
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or "00")
        meridiem = re.sub(r"\s|\.", "", match.group("ampm")).casefold()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        formatted = f"{hour:02d}:{minute:02d}"
        if formatted not in values:
            values.append(formatted)
    for match in TWENTY_FOUR_HOUR_RE.finditer(value):
        formatted = f"{int(match.group('hour')):02d}:{match.group('minute')}"
        if formatted not in values:
            values.append(formatted)
    return values


def expand_event_dates(value: str, *, season: str, settings: dict[str, Any] | None = None) -> list[dict[str, str | None]]:
    """Expand every explicit date in an Auditori event-date string.

    A year stated at the end of a month group is applied to the preceding
    month in that same group, matching the source's compact notation.  No
    date or time is fabricated when the source does not state it.
    """
    settings = settings or {}
    raw = _clean(value)
    parts = re.split(r"\s*[·•]\s*", raw, maxsplit=1)
    date_part = parts[0]
    time_part = parts[1] if len(parts) == 2 else ""
    times = _time_values(time_part)
    shared_time = times[0] if len(times) == 1 else None
    season_start, season_end = _season_bounds(season, settings)
    results: list[dict[str, str | None]] = []
    for segment in re.split(r"\s*;\s*", date_part):
        matches = list(DATE_RE.finditer(segment))
        for index, match in enumerate(matches):
            year_text = match.group("year")
            if year_text is None:
                for following in matches[index + 1 :]:
                    if following.group("year"):
                        year_text = following.group("year")
                        break
                if year_text is None:
                    for preceding in reversed(matches[:index]):
                        if preceding.group("year"):
                            year_text = preceding.group("year")
                            break
            if year_text is None:
                continue
            month = MONTHS[match.group("month").casefold()]
            for day_text in re.findall(r"\d{1,2}", match.group("days")):
                try:
                    occurrence = date(int(year_text), month, int(day_text))
                except ValueError:
                    continue
                if season_start <= occurrence <= season_end:
                    results.append({"date": occurrence.isoformat(), "start_time": shared_time})
    return results


def _section_lines(soup: BeautifulSoup, labels: set[str]) -> list[str]:
    for heading in soup.find_all(["h2", "h3", "h4"]):
        if _clean(heading.get_text(" ", strip=True)).casefold() not in labels:
            continue
        lines: list[str] = []
        sibling = heading.find_next_sibling()
        while sibling is not None and getattr(sibling, "name", None) not in {"h2", "h3", "h4"}:
            if getattr(sibling, "name", None) in {"p", "li"}:
                lines.extend(line for line in sibling.get_text("\n", strip=True).splitlines() if _clean(line))
            sibling = sibling.find_next_sibling()
        return [_clean(line) for line in lines if _clean(line)]
    return []


def parse_detail_enrichment(page: str, source_url: str) -> dict[str, list[dict[str, Any]]]:
    """Parse only explicit Repertoire and artist rows from an official detail page."""
    soup = BeautifulSoup(page, "html.parser")
    programme: list[dict[str, Any]] = []
    for line in _section_lines(soup, {"repertoire", "repertory", "works", "program", "programme"}):
        if ":" not in line:
            continue
        composer, work = (part.strip() for part in line.split(":", 1))
        if not composer or not work:
            continue
        index = len(programme) + 1
        programme.append({
            "source_title": work,
            "composer": composer,
            "composer_candidate": {"raw_name": composer, "source_url": source_url, "source_field": "official.repertoire"},
            "source_programme_index": index,
            "raw_programme_index": index,
            "original_programme_order": index,
            "resolution_status": "pending_global_resolution",
            "provenance": {"source_url": source_url, "source_field": "official.repertoire"},
        })

    credits: list[dict[str, Any]] = []
    for line in _section_lines(soup, {"artistas", "artists", "interpreters", "performers", "musicians", "cast"}):
        role = None
        parts = [part.strip() for part in line.split(",")]
        suffix = ", ".join(parts[1:]).casefold()
        if len(parts) > 1 and any(hint in suffix for hint in ROLE_HINTS):
            artist, role = parts[0], ", ".join(parts[1:])
        else:
            artist = line
        if not artist:
            continue
        credits.append({
            "artist_name": artist,
            "source_role": role or "performer",
            "function": role or "performer",
            "credit_kind": "artistic_team" if role else "cast",
            "source_url": source_url,
            "source_field": "official.artists",
            "raw_source_block": line,
            "provenance": {"source_url": source_url, "source_field": "official.artists"},
        })
    return {"programme": programme, "credits": credits}


def _listing_credits(card: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    credits: list[dict[str, Any]] = []
    for item in card.get("interpreters_obj") or []:
        artist = _nested_name((item or {}).get("artist") if isinstance(item, dict) else item)
        if not artist:
            continue
        credits.append({
            "artist_name": artist,
            "source_role": "performer",
            "function": "performer",
            "credit_kind": "cast",
            "source_url": source_url,
            "source_field": "listing.interpreters_obj",
            "raw_source_block": artist,
            "provenance": {"source_url": source_url, "source_field": "listing.interpreters_obj"},
        })
    return credits


class LauditoriBarcelonaAdapter:
    """Read-only deterministic L'Auditori season listing adapter."""

    source_time_optional = True

    def __init__(self, settings: dict[str, Any], fetch: Callable[[str], str] | None = None):
        self.settings = settings
        self._fetch = fetch or self._fetch_url
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
        self.productions_discovered_before_scope = 0
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
        self.event_cards = 0

    @staticmethod
    def _fetch_url(url: str) -> str:
        kwargs = {"timeout": 60, "headers": {"User-Agent": "Byelingua deterministic HTML acquisition/1.0", "Accept": "text/html,application/xhtml+xml"}}
        try:
            response = requests.get(url, **kwargs)
        except requests.exceptions.SSLError:
            # The managed Windows runtime may trust the site through the OS
            # certificate store while its bundled certifi store does not.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                response = requests.get(url, verify=False, **kwargs)
        response.raise_for_status()
        return response.text

    def _detail_urls(self, cards: list[dict[str, Any]], listing_url: str) -> list[str]:
        urls: list[str] = []
        for card in cards:
            value = card.get("link")
            if not isinstance(value, str) or not value.strip():
                continue
            absolute = urljoin(listing_url, value.strip())
            if absolute.startswith(("https://www.auditori.cat/", "https://auditori.cat/")) and absolute not in urls:
                urls.append(absolute)
        return urls

    def ingest(self, season: str) -> list[CanonicalEvent]:
        listing_url = self.settings.get("listing_source") or self.settings["official_source"]
        self.requested_months.append(listing_url)
        self.listing_pages_requested.append(listing_url)
        try:
            listing_page = self._fetch(listing_url)
            cards = extract_event_cards(listing_page)
        except Exception as exc:
            self.failed_months.append(listing_url)
            self.listing_pages_failed.append(listing_url)
            self.last_errors.append({"url": listing_url, "error": f"{type(exc).__name__}: {exc}"})
            return []
        self.successful_months.append(listing_url)
        self.listing_pages_successful.append(listing_url)
        self.source_pages[listing_url] = listing_url
        self.event_cards = len(cards)

        detail_urls = self._detail_urls(cards, listing_url)
        self.productions_discovered_before_scope = len(detail_urls)
        self.productions_discovered = len(detail_urls)
        self.detail_pages_requested.extend(detail_urls)
        def fetch_detail(detail_url: str) -> tuple[str, dict[str, list[dict[str, Any]]] | None, str | None]:
            try:
                detail_page = self._fetch(detail_url)
                return detail_url, parse_detail_enrichment(detail_page, detail_url), None
            except Exception as exc:
                return detail_url, None, f"{type(exc).__name__}: {exc}"

        details: dict[str, dict[str, list[dict[str, Any]]]] = {}
        worker_count = max(1, min(int(self.settings.get("detail_workers", 8)), 12))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            detail_results = list(executor.map(fetch_detail, detail_urls))
        for detail_url, enrichment, error in detail_results:
            if error is None and enrichment is not None:
                details[detail_url] = enrichment
                self.detail_pages_successful.append(detail_url)
                self.successful_months.append(detail_url)
                self.source_pages[detail_url] = detail_url
            else:
                self.detail_pages_failed.append(detail_url)
                self.failed_months.append(detail_url)
                self.last_errors.append({"url": detail_url, "error": error or "detail enrichment failed"})

        events: list[CanonicalEvent] = []
        for card_index, card in enumerate(cards):
            title = _nested_name(card.get("wp_post"))
            date_text = card.get("event_date_text")
            if not title or not isinstance(date_text, str):
                continue
            occurrences = expand_event_dates(date_text, season=season, settings=self.settings)
            self.date_candidates_found += len(occurrences)
            detail_url = urljoin(listing_url, str(card.get("link") or "")) if card.get("link") else listing_url
            detail = details.get(detail_url, {})
            programme = detail.get("programme", [])
            credits = detail.get("credits", []) or _listing_credits(card, listing_url)
            for occurrence in occurrences:
                event_date = occurrence["date"]
                start_time = occurrence["start_time"]
                source_event_id = hashlib.sha256(
                    f"{self.settings.get('source_id', self.settings['venue_id'])}|{detail_url}|{event_date}|{start_time or ''}".encode("utf-8")
                ).hexdigest()[:24]
                hall = card.get("hall_obj") if isinstance(card.get("hall_obj"), dict) else {}
                room = _nested_name(hall.get("wp_post"))
                event = CanonicalEvent(
                    source=self.settings.get("source_id", self.settings["venue_id"]),
                    source_event_id=source_event_id,
                    source_url=detail_url,
                    organization=self.settings["organization"],
                    venue=self.settings["venue"],
                    city=self.settings["city"],
                    country=self.settings["country"],
                    timezone=self.settings["timezone"],
                    title=title,
                    date=str(event_date),
                    start_time=start_time,
                    end_time=None,
                    room=room,
                    event_type=self.settings.get("default_event_type", "performance"),
                    classification=self.settings.get("default_event_type", "performance"),
                    programme=[dict(row) for row in programme],
                    credits=[dict(row) for row in credits],
                    data_quality={
                        "schedule": {"year_status": "YEAR_EXPLICIT", "source_field": "listing.event_date_text"},
                        "programme": {"status": "PROGRAMME_EVIDENCE_FOUND" if programme else "NO_PROGRAMME_EVIDENCE", "reason": "official detail Repertoire section" if programme else "detail page has no explicit Repertoire rows"},
                        "source_discovery": {"status": "PASS", "mode": "HTML", "listing_source_url": listing_url},
                    },
                    raw={
                        "source_title": title,
                        "source_url": detail_url,
                        "listing_source_url": listing_url,
                        "source_event_id": card.get("id", card_index),
                        "source_date_text": date_text,
                        "source_fields": {"title": "listing.wp_post.post_title", "date": "listing.event_date_text", "room": "listing.hall_obj.wp_post.post_title"},
                        "series": card.get("tax_cicles_str"),
                        "category": card.get("tax_ecategory_str"),
                    },
                )
                event.validate()
                events.append(event)
                self.date_candidates_accepted += 1

        unique: dict[str, CanonicalEvent] = {}
        for event in events:
            if event.event_key in unique:
                self.duplicate_performance_slot += 1
                continue
            unique[event.event_key] = event
        return sorted(unique.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
