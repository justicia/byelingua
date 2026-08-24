from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Callable
from urllib.parse import urljoin

from html.parser import HTMLParser

from season_ingestion.schema import CanonicalEvent


MONTHS = {"September": 9, "Oktober": 10, "November": 11, "Dezember": 12, "Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6, "Juli": 7, "August": 8}
EVENT_RE = re.compile(r"(\d{1,2})\.\s*(\d{1,2}):([0-5]\d)\s*Uhr.*?([A-ZÄÖÜ][^|]{2,80}?)(?:\s+([A-ZÄÖÜ][^|]{2,60}))?\s*$")


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


def parse_calendar(html: str, page_url: str, settings: dict, *, season_start: str, season_end: str) -> list[CanonicalEvent]:
    parser = _LinkTextParser()
    parser.feed(html)
    page_month = page_url.rstrip("/").split("/")[-1].split("?")[0]
    if len(page_month) != 7 or page_month[4] != "-":
        return []
    year, month = int(page_month[:4]), int(page_month[5:])
    events: list[CanonicalEvent] = []
    for href, text in parser.links:
        match = re.search(r"(\d{1,2})\..*?\b(\d{1,2})[.:]([0-5]\d)\s*Uhr.*?\|\s*([^|]+)", text)
        if not match:
            continue
        day, hour, minute = int(match.group(1)), int(match.group(2)), match.group(3)
        title_part = re.sub(r"\s+", " ", match.group(4)).strip()
        if title_part.startswith("Nationaltheater"):
            title_part = title_part[len("Nationaltheater"):].strip()
        title_part = re.sub(r"\s+(Preise|Abo-Serie|Familienvorstellung|<30)\b.*$", "", title_part).strip()
        if not title_part or not re.search(r"[A-ZÄÖÜ]{2,}", title_part):
            continue
        location = "Nationaltheater" if "Nationaltheater" in text else None
        if location != settings["venue"]:
            continue
        performance_date = date(year, month, day)
        if not (season_start <= performance_date.isoformat() <= season_end):
            continue
        source_url = urljoin(page_url, href)
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

    @staticmethod
    def _fetch_url(url: str) -> str:
        from urllib.request import Request, urlopen
        request = Request(url, headers={"User-Agent": "ByelinguaSeasonIngestion/1.0"})
        with urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8")

    def ingest(self, season: str) -> list[CanonicalEvent]:
        from season_ingestion.season import resolve_season_bounds
        start, end = resolve_season_bounds(season, self.settings)
        start_year = int(season[:4])
        output: list[CanonicalEvent] = []
        for month in range(9, 21):
            year, month_number = start_year + (month - 1) // 12, ((month - 1) % 12) + 1
            url = self.settings["source"].format(year_month=f"{year:04d}-{month_number:02d}")
            try:
                output.extend(parse_calendar(self._fetch(url), url, self.settings, season_start=start, season_end=end))
            except Exception as exc:
                self.last_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        return sorted({event.event_key: event for event in output}.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
