from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import date
from typing import Callable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from season_ingestion.schema import CanonicalEvent


DETAIL_RE = re.compile(r"https://www\.opernhaus\.ch/(?:en/)?spielplan/calendar/[^\"' ]+/2026-2027/?")
JSONLD_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
ROLE_REVIEW_LABELS = {"inszenierung", "mise en scène", "austattung", "ausstattung", "lichtgestaltung", "dramaturgie", "choreinstudierung", "kostüme", "kostümbild", "bühnenbild"}
CAST_ROLE_LABELS = {"soprano", "sopran", "mezzo-soprano", "mezzosopran", "alto", "contralto", "tenor", "baritone", "bariton", "bass", "basso", "bass-baritone", "schauspieler"}
VOICE_TYPE_LABELS = {"soprano", "sopran", "mezzo-soprano", "mezzosopran", "alto", "contralto", "tenor", "baritone", "bariton", "bass", "basso", "bass-baritone"}
CONDUCTOR_LABELS = {"musikalische leitung", "conductor", "musical director", "chorus master", "chorus director", "choreinstudierung"}
ARTISTIC_LABELS = ROLE_REVIEW_LABELS | CONDUCTOR_LABELS | {"orchester", "orchestra", "chor", "choir", "ensemble", "music group", "statisten", "extras", "choreografie", "video", "austattung"}


def _jsonld_events(html_text: str) -> list[dict]:
    """Read official JSON-LD Event objects, including graph/list encodings."""
    output: list[dict] = []
    for raw_json in JSONLD_RE.findall(html_text):
        try:
            payload = json.loads(html.unescape(raw_json.strip()))
        except json.JSONDecodeError:
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                candidates.extend(graph)
            elif candidate.get("@type") == "Event" or "Event" in (candidate.get("@type") or []):
                output.append(candidate)
    return output


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or "")).replace("\xa0", " ")).strip()


def _composer_from_description(description: object, title: str) -> tuple[str | None, str | None]:
    text = html.unescape(str(description or "")).replace("\r", "")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return None, None
    first = lines[0]
    lowered = first.casefold()
    if _clean_text(first).casefold() == _clean_text(title).casefold():
        return None, None
    if lowered.startswith(("works by", "work by", "music by")):
        return None, "multiple works/composers stated without individual work titles"
    if "," in first or " & " in first or lowered.startswith(("concertant", "guest performance", "special concert")):
        return None, None
    if lowered in {"guest performance", "concert performance", "recital", "matinee", "gala"}:
        return None, None
    if " by " in lowered and len(first.split()) > 2:
        first = re.split(r"\s+by\s+", first, maxsplit=1, flags=re.IGNORECASE)[-1].strip()
    return first or None, "official detail JSON-LD description first attribution line"


def _programme_for(payload: dict, page_url: str, title: str) -> tuple[list[dict], str, str]:
    composer, composer_reason = _composer_from_description(payload.get("description"), title)
    provenance = {"source_url": page_url, "source_field": "jsonld.description", "raw_source_block": payload.get("description")}
    if composer:
        return ([{
            "source_title": title,
            "raw_title": title,
            "composer": composer,
            "composer_candidate": {"raw_name": composer, "normalized_name": _clean_text(composer), "source_field": "jsonld.description", "source_url": page_url, "confidence": "official composer attribution"},
            "source_programme_index": 1,
            "raw_programme_index": 1,
            "original_programme_order": 1,
            "resolution_status": "pending_global_resolution",
            "provenance": provenance,
        }], "PROGRAMME_EVIDENCE_FOUND", "official detail JSON-LD supplies composer attribution")
    if composer_reason:
        return ([], "DETAIL_PARSE_REVIEW", composer_reason)
    return ([], "NO_PROGRAMME_EVIDENCE", "official detail has no programme/work/composer attribution")


def _credits_for(payload: dict, page_url: str) -> list[dict]:
    credits: list[dict] = []
    performers = payload.get("performer") or []
    if isinstance(performers, dict):
        performers = [performers]
    for index, performer in enumerate(performers, start=1):
        if not isinstance(performer, dict):
            continue
        name = _clean_text(performer.get("name"))
        role = _clean_text(performer.get("description"))
        if not name:
            continue
        lowered = role.casefold()
        is_voice_type = lowered in VOICE_TYPE_LABELS
        kind = "cast"
        if performer.get("@type") == "MusicGroup" or lowered in {"orchester", "orchestra", "chor", "choir", "ensemble"}:
            kind = "ensemble"
        elif lowered in ARTISTIC_LABELS or any(label in lowered for label in CONDUCTOR_LABELS):
            kind = "artistic_team"
        credit = {
            "artist_name": name,
            "source_role": role,
            "function": role.casefold() or None,
            "credit_kind": kind,
            "source_url": page_url,
            "source_field": f"jsonld.performer[{index}]",
            "raw_source_block": performer,
            "provenance": {"source_url": page_url, "credit_section": "jsonld.performer", "source_field": f"jsonld.performer[{index}]"},
        }
        # Voice type is performer metadata, never a dramatic Character.
        # Character assignment requires explicit official role evidence.
        if is_voice_type:
            credit["voice_type"] = role
        elif kind == "cast":
            credit["character"] = role
        credits.append(credit)
    return credits


def _detail_urls(season_html: str) -> list[str]:
    absolute = set(DETAIL_RE.findall(season_html))
    relative = re.findall(r"/(?:en/)?spielplan/calendar/[^\"' ]+/2026-2027/?", season_html)
    absolute.update(urljoin("https://www.opernhaus.ch", path) for path in relative)
    return sorted(absolute)


def parse_detail(html_text: str, page_url: str, settings: dict, *, season_start: str, season_end: str) -> list[CanonicalEvent]:
    events: list[CanonicalEvent] = []
    for payload in _jsonld_events(html_text):
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
        programme, programme_status, programme_reason = _programme_for(payload, page_url, title)
        credits = _credits_for(payload, page_url)
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
            programme=programme,
            credits=credits,
            data_quality={"programme": {"status": programme_status, "reason": programme_reason}, "character": {"status": "available" if any(c.get("character") for c in credits) else "unavailable"}, "detail_enrichment": {"status": "complete", "source_url": page_url}},
            raw={"season_source_url": settings["official_source"], "detail_source_url": page_url, "source_title": title, "source_description": payload.get("description"), "source_event_jsonld": payload},
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
            last_exc: Exception | None = None
            for attempt in range(2):
                try:
                    detail_html = self._fetch(detail_url)
                    events = parse_detail(detail_html, detail_url, self.settings, season_start=season_start, season_end=season_end)
                    if not events:
                        # A production page can be linked from the season overview while
                        # its remaining dates fall outside the requested season window.
                        # Count the official page as fetched, but do not invent an event.
                        if not _jsonld_events(detail_html):
                            raise ValueError("official detail page contained no season event JSON-LD")
                    self.source_pages[detail_url] = detail_url
                    self.successful_months.append(detail_url)
                    output.extend(events)
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt == 0:
                        time.sleep(1)
            if last_exc is not None:
                exc = last_exc
                self.failed_months.append(detail_url)
                self.last_errors.append({"url": detail_url, "error": f"{type(exc).__name__}: {exc}"})
        return sorted({event.event_key: event for event in output}.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))

