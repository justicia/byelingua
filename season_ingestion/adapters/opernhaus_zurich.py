from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date
from typing import Callable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from season_ingestion.schema import CanonicalEvent


DETAIL_RE = re.compile(r"https://www\.opernhaus\.ch/(?:en/)?spielplan/calendar/[^\"' ]+/2026-2027/?")
JSONLD_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)


def _detail_urls(season_html: str) -> list[str]:
    absolute = set(DETAIL_RE.findall(season_html))
    relative = re.findall(r"/(?:en/)?spielplan/calendar/[^\"' ]+/2026-2027/?", season_html)
    absolute.update(urljoin("https://www.opernhaus.ch", path) for path in relative)
    return sorted(absolute)


def parse_detail(html_text: str, page_url: str, settings: dict, *, season_start: str, season_end: str) -> list[CanonicalEvent]:
    events: list[CanonicalEvent] = []
    for raw_json in JSONLD_RE.findall(html_text):
        try:
            payload = json.loads(html.unescape(raw_json.strip()))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("@type") != "Event":
            continue
        start = str(payload.get("startDate") or "")
        if len(start) < 16 or start[10] != "T":
            continue
        event_date, start_time = start[:10], start[11:16]
        if not (season_start <= event_date <= season_end):
            continue
        title = str(payload.get("name") or "").strip()
        if not title:
            continue
        location = payload.get("location") or {}
        if not isinstance(location, dict):
            location = {}
        venue = str(location.get("name") or settings["venue"]).strip()
        source_url = str(payload.get("url") or page_url)
        source_event_id = hashlib.sha256(f"{source_url}|{start}".encode()).hexdigest()[:24]
        event = CanonicalEvent(
            source="opernhaus_zurich",
            source_event_id=source_event_id,
            source_url=source_url,
            organization=settings["organization"],
            venue=venue,
            city=settings["city"],
            country=settings["country"],
            timezone=settings["timezone"],
            title=title,
            date=event_date,
            start_time=start_time,
            end_time=str(payload.get("endDate") or "")[11:16] or None,
            room=venue,
            event_type="performance",
            programme=[{
                "source_title": title,
                "composer": None,
                "source_programme_index": 1,
                "raw_programme_index": 1,
                "original_programme_order": 1,
                "resolution_status": "review_required",
                "resolution_reason": "official detail page does not expose a machine-readable composer field",
            }],
            credits=[],
            data_quality={"composer": {"status": "unavailable_in_structured_source"}, "character": {"status": "unavailable"}},
            raw={"season_source_url": settings["official_source"], "detail_source_url": page_url, "source_title": title, "source_description": payload.get("description")},
        )
        event.validate()
        events.append(event)
    return events


class OpernhausZurichAdapter:
    def __init__(self, settings: dict, fetch: Callable[[str], str] | None = None):
        self.settings, self._fetch = settings, fetch or self._fetch_url
        self.last_errors: list[dict[str, str]] = []
        self.requested_months: list[str] = []
        self.successful_months: list[str] = []
        self.failed_months: list[str] = []
        self.source_pages: dict[str, str] = {}

    @staticmethod
    def _fetch_url(url: str) -> str:
        request = Request(url, headers={"User-Agent": "ByelinguaSeasonIngestion/1.0 (+https://github.com/justicia/byelingua)", "Accept": "text/html,application/xhtml+xml"})
        with urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8")

    def ingest(self, season: str) -> list[CanonicalEvent]:
        from season_ingestion.season import resolve_season_bounds
        season_start, season_end = resolve_season_bounds(season, self.settings)
        season_url = self.settings["official_source"]
        try:
            season_html = self._fetch(season_url)
            detail_urls = _detail_urls(season_html)
        except Exception as exc:
            self.last_errors.append({"url": season_url, "error": f"{type(exc).__name__}: {exc}"})
            self.failed_months.append("season")
            self.requested_months.append("season")
            return []
        self.requested_months = detail_urls[:]
        output: list[CanonicalEvent] = []
        for detail_url in detail_urls:
            try:
                detail_html = self._fetch(detail_url)
                events = parse_detail(detail_html, detail_url, self.settings, season_start=season_start, season_end=season_end)
                if not events:
                    raise ValueError("official detail page contained no season event JSON-LD")
                self.source_pages[detail_url] = detail_url
                self.successful_months.append(detail_url)
                output.extend(events)
            except Exception as exc:
                self.failed_months.append(detail_url)
                self.last_errors.append({"url": detail_url, "error": f"{type(exc).__name__}: {exc}"})
        return sorted({event.event_key: event for event in output}.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
