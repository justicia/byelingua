from __future__ import annotations

import hashlib
import re
import time
from datetime import date
from typing import Callable
from urllib.parse import urljoin
from urllib.error import HTTPError

from html.parser import HTMLParser

from season_ingestion.schema import CanonicalEvent


MONTHS = {"September": 9, "Oktober": 10, "November": 11, "Dezember": 12, "Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6, "Juli": 7, "August": 8}
EVENT_RE = re.compile(r"(\d{1,2})\.\s*(\d{1,2}):([0-5]\d)\s*Uhr.*?([A-ZÄÖÜ][^|]{2,80}?)(?:\s+([A-ZÄÖÜ][^|]{2,60}))?\s*$")
OCCURRENCE_URL_RE = re.compile(
    r"/stuecke/(?P<slug>[^/?#]+)/(?P<date>\d{4}-\d{2}-\d{2})-(?P<hour>[0-2]\d)(?P<minute>[0-5]\d)-(?P<occurrence_id>\d+)(?:[/?#]|$)",
    re.IGNORECASE,
)


def _text(node) -> str:
    return re.sub(r"\s+", " ", node).strip()


class _LinkTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href", "")
            self._parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, _text(" ".join(self._parts))))
            self._href, self._parts = None, []


def _clean_calendar_title(text: str, slug: str | None = None) -> str:
    venue_split = re.split(r"\|\s*Nationaltheater\s*", text, maxsplit=1, flags=re.IGNORECASE)
    candidate = venue_split[1] if len(venue_split) == 2 else ""
    candidate = re.split(
        r"\b(?:Preise|Prices|Abo-Serie|Familienvorstellung|mehr anzeigen|weniger anzeigen|show more|show less|Weitere Informationen)\b",
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    uppercase_title = re.match(r"([A-ZÄÖÜẞ0-9][A-ZÄÖÜẞ0-9\s’'\-–—:,.!?]+?)(?=\s+[A-ZÄÖÜ][a-zäöüß]|$)", candidate)
    if uppercase_title:
        title = re.sub(r"\s+", " ", uppercase_title.group(1)).strip(" -–—,.")
        if title:
            return title
    if slug:
        return re.sub(r"\s+", " ", slug.replace("-", " ")).strip().title()
    return candidate


def parse_calendar(html: str, page_url: str, settings: dict, *, season_start: str, season_end: str) -> list[CanonicalEvent]:
    parser = _LinkTextParser()
    parser.feed(html)
    page_month = page_url.rstrip("/").split("/")[-1].split("?")[0]
    if len(page_month) != 7 or page_month[4] != "-":
        return []
    year, month = int(page_month[:4]), int(page_month[5:])
    events: list[CanonicalEvent] = []
    for href, text in parser.links:
        if not re.search(r"\|\s*Nationaltheater(?=\s|[A-ZÄÖÜ]|$)", text):
            continue
        source_url = urljoin(page_url, href)
        occurrence_match = OCCURRENCE_URL_RE.search(source_url)
        if occurrence_match:
            performance_date = date.fromisoformat(occurrence_match.group("date"))
            hour = int(occurrence_match.group("hour"))
            minute = occurrence_match.group("minute")
            title_part = _clean_calendar_title(text, occurrence_match.group("slug"))
        else:
            match = re.search(r"(\d{1,2})\..*?\b(\d{1,2})[.:]([0-5]\d)\s*Uhr.*?\|\s*Nationaltheater", text, re.IGNORECASE)
            meridiem = None
            if not match:
                match = re.search(r"(\d{1,2})\..*?\b(\d{1,2}):([0-5]\d)\s*(am|pm).*?\|\s*Nationaltheater", text, re.IGNORECASE)
                meridiem = match.group(4).lower() if match else None
            if not match:
                continue
            day, hour, minute = int(match.group(1)), int(match.group(2)), match.group(3)
            if meridiem:
                hour = hour % 12 + (12 if meridiem == "pm" else 0)
            performance_date = date(year, month, day)
            title_part = _clean_calendar_title(text)
        if not title_part or not re.search(r"[A-ZÄÖÜ]{2,}", title_part):
            continue
        location = "Nationaltheater"
        if location != settings["venue"] or performance_date.year != year or performance_date.month != month:
            continue
        if not (season_start <= performance_date.isoformat() <= season_end):
            continue
        source_event_id = hashlib.sha256(f"{source_url}|{performance_date}|{hour:02d}:{minute}".encode()).hexdigest()[:24]
        event = CanonicalEvent(source="munich_bayerische_staatsoper", source_event_id=source_event_id, source_url=source_url or page_url, organization=settings["organization"], venue=settings["venue"], city=settings["city"], country=settings["country"], timezone=settings["timezone"], title=title_part, date=performance_date.isoformat(), start_time=f"{hour:02d}:{minute}", end_time=None, room=location, event_type="performance", programme=[{"source_title": title_part, "composer": None, "source_programme_index": 1, "raw_programme_index": 1, "original_programme_order": 1, "resolution_status": "review_required"}], credits=[], raw={"calendar_url": page_url, "source_title": title_part})
        event.validate()
        events.append(event)
    unique = {event.event_key: event for event in events}
    return sorted(unique.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))


class MunichBayerischeStaatsoperAdapter:
    def __init__(self, settings: dict, fetch: Callable[[str], str] | None = None):
        self.settings, self._fetch = settings, fetch or self._fetch_url
        self.last_errors: list[dict[str, str]] = []
        self.requested_months: list[str] = []
        self.successful_months: list[str] = []
        self.failed_months: list[str] = []
        self.source_pages: dict[str, str] = {}

    @staticmethod
    def _fetch_url(url: str) -> str:
        from urllib.request import Request, urlopen
        last_error = None
        for attempt in range(3):
            try:
                request = Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; ByelinguaSeasonIngestion/1.0; +https://github.com/justicia/byelingua)",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                })
                with urlopen(request, timeout=60) as response:
                    return response.read().decode("utf-8")
            except HTTPError as exc:
                last_error = exc
                if exc.code not in {403, 429, 500, 502, 503, 504} or attempt == 2:
                    raise
                time.sleep(min(2 ** attempt, 4))
        raise last_error

    def ingest(self, season: str) -> list[CanonicalEvent]:
        from season_ingestion.season import resolve_season_bounds
        start, end = resolve_season_bounds(season, self.settings)
        start_year = int(season[:4])
        output: list[CanonicalEvent] = []
        for month in range(9, 21):
            year, month_number = start_year + (month - 1) // 12, ((month - 1) % 12) + 1
            month_key = f"{year:04d}-{month_number:02d}"
            self.requested_months.append(month_key)
            url = self.settings["source"].format(year_month=f"{year:04d}-{month_number:02d}")
            try:
                try:
                    html = self._fetch(url)
                    source_url = url
                except HTTPError as primary_error:
                    fallback = self.settings.get("fallback_source")
                    if not fallback:
                        raise
                    source_url = fallback.format(year_month=f"{year:04d}-{month_number:02d}")
                    html = self._fetch(source_url)
                self.source_pages[month_key] = source_url
                output.extend(parse_calendar(html, source_url, self.settings, season_start=start, season_end=end))
                self.successful_months.append(month_key)
            except Exception as exc:
                self.failed_months.append(month_key)
                self.last_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        return sorted({event.event_key: event for event in output}.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
