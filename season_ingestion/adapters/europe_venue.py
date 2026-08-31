"""Shared source adapter for Wave 1 European venues.

The adapter deliberately stops at source facts.  It extracts explicit
occurrences and source-labelled programme/credit observations, while global
Composer/Work/Artist/Character identity remains owned by the shared pipeline.
Venue registry entries only describe how to find the official source.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date
from typing import Any, Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from season_ingestion.schema import CanonicalEvent


JSONLD_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.I | re.S,
)
ISO_RE = re.compile(r"^(20\d{2})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?")
TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


def _text(node: Any) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


def _documents(page: str) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for raw in JSONLD_RE.findall(page):
        try:
            value = json.loads(html.unescape(raw.strip()))
        except (TypeError, ValueError):
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, dict):
                continue
            documents.append(item)
            graph = item.get("@graph")
            if isinstance(graph, list):
                documents.extend(node for node in graph if isinstance(node, dict))
    return documents


def _types(document: dict[str, Any]) -> set[str]:
    value = document.get("@type")
    values = value if isinstance(value, list) else [value]
    return {str(item).casefold() for item in values if item}


def _as_name(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("name") or value.get("caption")
    if isinstance(value, list):
        for item in value:
            name = _as_name(item)
            if name:
                return name
        return None
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value or None


def _names(value: Any) -> list[str]:
    if not isinstance(value, list):
        value = [value]
    result: list[str] = []
    for item in value:
        name = _as_name(item)
        if name and name not in result:
            result.append(name)
    return result


def _clean_title(value: str) -> str:
    # Duration is source metadata, never Work identity.
    value = re.sub(r"\s*\((?:approx\.?\s*)?\d{1,3}\s*(?:min\.?|m|')\)\s*$", "", value, flags=re.I)
    value = re.sub(r"\s*[-–—]\s*\d{1,3}\s*(?:min\.?|m)\s*$", "", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip(" -–—")


def _parse_explicit(value: Any) -> tuple[str, str | None] | None:
    raw = str(value or "").strip()
    match = ISO_RE.search(raw)
    if match:
        year, month, day, hour, minute = match.groups()
        try:
            event_date = date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            return None
        return event_date, f"{int(hour):02d}:{minute}" if hour is not None else None
    return None


def _programme(document: dict[str, Any], title: str, source_url: str) -> list[dict[str, Any]]:
    works = document.get("workPerformed") or document.get("work")
    if not isinstance(works, list):
        works = [works] if works else []
    rows: list[dict[str, Any]] = []
    for index, work in enumerate(works, start=1):
        work_title = _as_name(work) or title
        composer = _as_name(work.get("composer")) if isinstance(work, dict) else None
        rows.append({
            "source_title": _clean_title(work_title),
            "raw_title": work_title,
            "composer": composer,
            "composer_candidate": {"raw_name": composer, "source_url": source_url, "source_field": "jsonld.workPerformed.composer"} if composer else {},
            "source_programme_index": index,
            "raw_programme_index": index,
            "original_programme_order": index,
            "resolution_status": "pending_global_resolution",
            "provenance": {"source_url": source_url, "source_field": "jsonld.workPerformed"},
        })
    if rows:
        return rows
    composer = _as_name(document.get("composer"))
    return [{
        "source_title": _clean_title(title),
        "raw_title": title,
        "composer": composer,
        "composer_candidate": {"raw_name": composer, "source_url": source_url, "source_field": "jsonld.composer"} if composer else {},
        "source_programme_index": 1,
        "raw_programme_index": 1,
        "original_programme_order": 1,
        "resolution_status": "pending_global_resolution",
        "provenance": {"source_url": source_url, "source_field": "jsonld.composer" if composer else "jsonld.name"},
    }]


def _credits(document: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field, role, kind in (("performer", "performer", "cast"), ("actor", "performer", "cast"), ("director", "stage_director", "artistic_team"), ("conductor", "conductor", "artistic_team")):
        for name in _names(document.get(field)):
            rows.append({
                "artist_name": name,
                "source_role": field,
                "function": role,
                "credit_kind": kind,
                "source_url": source_url,
                "source_field": f"jsonld.{field}",
                "raw_source_block": name,
                "provenance": {"source_url": source_url, "source_field": f"jsonld.{field}"},
            })
    return rows


class EuropeVenueAdapter:
    """Read explicit Event JSON-LD and detail-page occurrences from one source."""

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

    @staticmethod
    def _fetch_url(url: str) -> str:
        response = requests.get(url, timeout=60, headers={"User-Agent": "ByelinguaSeasonIngestion/1.0", "Accept": "text/html,application/xhtml+xml"})
        response.raise_for_status()
        return response.text

    def _in_season(self, value: str, season: str) -> bool:
        start_year, end_short = (int(part) for part in season.split("-", 1))
        end_year = start_year // 100 * 100 + end_short
        start = (start_year, 9, 1)
        end = (end_year, 8, 31)
        configured = (self.settings.get("season_bounds") or {}).get(season)
        if configured:
            start = tuple(int(part) for part in configured["season_start"].split("-"))
            end = tuple(int(part) for part in configured["season_end"].split("-"))
        current = tuple(int(part) for part in value.split("-"))
        return start <= current <= end

    def _detail_urls(self, page: str, page_url: str) -> list[str]:
        soup = BeautifulSoup(page, "html.parser")
        prefixes = tuple(self.settings.get("detail_path_prefixes", []))
        pattern = self.settings.get("detail_link_pattern")
        result: list[str] = []
        for link in soup.select(self.settings.get("detail_link_selector", "a[href]")):
            absolute = urljoin(page_url, str(link.get("href") or "").strip())
            path = absolute.split("?", 1)[0]
            if prefixes and not any(prefix in path for prefix in prefixes):
                continue
            if pattern and not re.search(pattern, absolute):
                continue
            if absolute not in result:
                result.append(absolute)
        return result

    def _event_rows(self, page: str, page_url: str, season: str, *, detail: bool = False) -> list[CanonicalEvent]:
        soup = BeautifulSoup(page, "html.parser")
        documents = [document for document in _documents(page) if "event" in _types(document)]
        if not documents:
            for node in soup.select("time[datetime], time[data-date], [data-start]"):
                raw = node.get("datetime") or node.get("data-date") or node.get("data-start")
                parsed = _parse_explicit(raw)
                if parsed:
                    card = node.find_parent(["article", "li", "div"])
                    title_node = card.select_one("h1, h2, h3, h4, [data-role='title'], .title") if card else None
                    title = _clean_title(_text(title_node) or _text(soup.select_one("h1, [data-role='title'], .entry-title, title")))
                    documents.append({"@type": "Event", "name": title or "Official event", "startDate": raw, "url": page_url})
                elif raw:
                    self.date_year_unverified += 1
        events: list[CanonicalEvent] = []
        for index, document in enumerate(documents):
            start_raw = document.get("startDate") or document.get("startTime")
            self.date_candidates_found += 1
            parsed = _parse_explicit(start_raw)
            if not parsed:
                self.date_year_unverified += 1
                self.date_candidates_rejected += 1
                continue
            event_date, start_time = parsed
            if not self._in_season(event_date, season):
                self.events_outside_season += 1
                self.date_candidates_rejected += 1
                continue
            title = _clean_title(_as_name(document.get("name")) or page_url.rstrip("/").rsplit("/", 1)[-1] or "Official event")
            source_url = str(document.get("url") or page_url)
            source_url = urljoin(page_url, source_url)
            source_identity = str(document.get("@id") or document.get("url") or f"{title}|{index}")
            source_event_id = hashlib.sha256(f"{source_url}|{source_identity}|{start_raw}".encode("utf-8")).hexdigest()[:24]
            location = document.get("location") if isinstance(document.get("location"), dict) else {}
            room = _as_name(location.get("name"))
            event = CanonicalEvent(
                source=self.settings.get("source_id", self.settings["venue_id"]),
                source_event_id=source_event_id,
                source_url=source_url,
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
                event_type=self.settings.get("default_event_type", "performance"),
                classification=self.settings.get("default_event_type", "performance"),
                programme=_programme(document, title, source_url),
                credits=_credits(document, source_url),
                data_quality={"schedule": {"year_status": "YEAR_EXPLICIT", "source_field": "jsonld.startDate"}, "programme": {"status": "PROGRAMME_EVIDENCE_FOUND" if document.get("workPerformed") or document.get("work") or document.get("composer") else "DETAIL_PARSE_REVIEW", "reason": "official source Event JSON-LD"}},
                raw={"source_title": title, "source_occurrence": {"startDate": start_raw, "source_identity": source_identity}, "source_url": source_url, "listing_source_url": page_url if not detail else self.settings.get("listing_source", page_url), "source_document_type": "jsonld.event" if documents else "html.time"},
            )
            event.validate()
            events.append(event)
            self.date_candidates_accepted += 1
        return events

    def ingest(self, season: str) -> list[CanonicalEvent]:
        listing_url = self.settings.get("listing_source") or self.settings["official_source"]
        self.requested_months.append(listing_url)
        self.listing_pages_requested.append(listing_url)
        try:
            listing_page = self._fetch(listing_url)
        except Exception as exc:
            self.failed_months.append(listing_url)
            self.listing_pages_failed.append(listing_url)
            self.last_errors.append({"url": listing_url, "error": f"{type(exc).__name__}: {exc}"})
            return []
        self.successful_months.append(listing_url)
        self.listing_pages_successful.append(listing_url)
        self.source_pages[listing_url] = listing_url
        result = self._event_rows(listing_page, listing_url, season)
        detail_urls = self._detail_urls(listing_page, listing_url)
        self.productions_discovered_before_scope = len(detail_urls)
        self.productions_discovered = len(detail_urls) or len(result)
        self.detail_pages_requested.extend(detail_urls)
        for detail_url in detail_urls:
            try:
                detail_page = self._fetch(detail_url)
                self.successful_months.append(detail_url)
                self.detail_pages_successful.append(detail_url)
                self.source_pages[detail_url] = detail_url
                result.extend(self._event_rows(detail_page, detail_url, season, detail=True))
            except Exception as exc:
                self.failed_months.append(detail_url)
                self.detail_pages_failed.append(detail_url)
                self.last_errors.append({"url": detail_url, "error": f"{type(exc).__name__}: {exc}"})
        unique: dict[str, CanonicalEvent] = {}
        for event in result:
            if event.event_key in unique:
                self.duplicate_performance_slot += 1
            unique[event.event_key] = event
        return sorted(unique.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
