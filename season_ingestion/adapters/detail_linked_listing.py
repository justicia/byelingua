from __future__ import annotations

import hashlib
import html
import re
from calendar import month_name
from datetime import date
from typing import Any, Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from season_ingestion.schema import CanonicalEvent


JSONLD_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
ISO_DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?")
TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
ITALIAN_MONTHS = {"gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12}
ROLE_LABELS = {
    "conductor": "conductor", "direttore": "conductor", "musical director": "conductor",
    "stage director": "stage_director", "regia": "stage_director", "director": "stage_director",
    "orchestra": "orchestra", "orchestra": "orchestra", "chorus": "chorus", "coro": "chorus",
}


class OutOfSeasonDetail(Exception):
    """The official detail page explicitly belongs to another season."""


def _text(node: Any) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


def _jsonld_documents(page: str) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for raw in JSONLD_RE.findall(page):
        try:
            import json
            payload = json.loads(html.unescape(raw.strip()))
        except Exception:
            continue
        values = payload if isinstance(payload, list) else [payload]
        for value in values:
            if isinstance(value, dict):
                documents.append(value)
                graph = value.get("@graph")
                if isinstance(graph, list):
                    documents.extend(item for item in graph if isinstance(item, dict))
    return documents


def _season_bounds(season: str, settings: dict[str, Any]) -> tuple[date, date]:
    start_year, end_year = (int(value) for value in season.split("-", 1))
    if end_year < 100:
        end_year += (start_year // 100) * 100
    configured = (settings.get("season_bounds") or {}).get(season)
    if configured:
        return date.fromisoformat(configured["season_start"]), date.fromisoformat(configured["season_end"])
    start_month = int(settings.get("season_start_month", 8))
    end_month = int(settings.get("season_end_month", start_month - 1 or 12))
    start = date(start_year, start_month, 1)
    end_year = end_year if end_month >= start_month else end_year
    if end_month == 12:
        end = date(end_year, 12, 31)
    else:
        end = date(end_year, end_month + 1, 1).replace(day=1)
        end = date.fromordinal(end.toordinal() - 1)
    return start, end


def _infer_year(month: int, season: str, settings: dict[str, Any]) -> int:
    start_year, end_year = (int(value) for value in season.split("-", 1))
    if end_year < 100:
        end_year += (start_year // 100) * 100
    start_month = int(settings.get("season_start_month", 8))
    return start_year if month >= start_month else end_year


def _parse_date_time(value: str, *, season: str, settings: dict[str, Any]) -> tuple[str, str | None] | None:
    value = html.unescape(value or "")
    iso = ISO_DATE_RE.search(value)
    if iso:
        year, month, day, hour, minute = iso.groups()
        return f"{year}-{month}-{day}", f"{int(hour):02d}:{minute}" if hour is not None else None
    match = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](20\d{2}))?\b", value)
    if match:
        day, month, year = match.groups()
        year = year or str(_infer_year(int(month), season, settings))
        clock = TIME_RE.search(value)
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}", f"{int(clock.group(1)):02d}:{clock.group(2)}" if clock else None
    month_match = re.search(r"\b(\d{1,2})\s+([A-Za-zÀ-ÿ]{3,9})(?:\s+(20\d{2}))?\b", value, re.I)
    if month_match:
        day, raw_month, year = month_match.groups()
        key = raw_month.casefold()[:3]
        month = ITALIAN_MONTHS.get(key) or next((i for i, name in enumerate(month_name) if name and name.casefold().startswith(key)), None)
        if month:
            year = year or str(_infer_year(month, season, settings))
            clock = TIME_RE.search(value)
            return f"{int(year):04d}-{month:02d}-{int(day):02d}", f"{int(clock.group(1)):02d}:{clock.group(2)}" if clock else None
    return None


def _in_season(event_date: str, season: str, settings: dict[str, Any]) -> bool:
    start, end = _season_bounds(season, settings)
    return start.isoformat() <= event_date <= end.isoformat()


def _composer(detail: BeautifulSoup, documents: list[dict[str, Any]], title: str, page_url: str) -> tuple[str | None, str | None]:
    labels = r"(?:Musica\s+di|Musik\s+von|Music\s+by|Composer|Composed\s+by)"
    for node in detail.select(".composer, [data-role='composer'], .music, .musica, [class*='composer'], [class*='musica'], dt, p, li"):
        text = _text(node)
        if len(text) > 250:
            continue
        match = re.search(rf"{labels}\s*[:\-]?\s*([^|;\n]+)", text, re.I)
        if not match and re.fullmatch(labels, text, re.I):
            sibling = node.find_next_sibling()
            sibling_text = _text(sibling)
            if sibling_text:
                match = re.match(r"(.+)", sibling_text)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" -–—:")
            value = re.sub(r"^[Â\u00a0]+", "", value).strip()
            value = re.split(r"\s+(?:Libretto|Lyrics|Regia|Stage direction|Directed by|Text von|Text by|Uraufführung|Premiere)\b", value, maxsplit=1, flags=re.I)[0].strip(" -–—:;")
            if len(value) > 120:
                continue
            if value and value.casefold() != title.casefold():
                return value, "official detail composer label"
    for document in documents:
        description = str(document.get("description") or "")
        match = re.search(rf"{labels}\s*[:\-]?\s*([^|;\n]+)", description, re.I)
        if match:
            return re.sub(r"^[Â\u00a0]+", "", match.group(1).strip()), "official detail JSON-LD description"
    return None, None


def _credits(detail: BeautifulSoup, page_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in detail.select("dt, .credit, [data-role='credit'], .cast, .artists"):
        text = _text(node)
        lowered = text.casefold()
        role = next((canonical for label, canonical in ROLE_LABELS.items() if label in lowered), None)
        if not role:
            continue
        value = re.sub(r"^.*?(?:[:\-]|\b(?:conductor|direttore|regia|director|orchestra|chorus|coro)\b)\s*", "", text, flags=re.I).strip()
        if not value or value.casefold() == lowered:
            sibling = node.find_next_sibling()
            value = _text(sibling)
        if value:
            rows.append({"artist_name": value, "source_role": text, "function": role, "credit_kind": "artistic_team" if role not in {"orchestra", "chorus"} else "ensemble", "source_url": page_url, "source_field": "detail.credit", "raw_source_block": text, "provenance": {"source_url": page_url, "source_field": "detail.credit"}})
    return rows


def _detail_title(detail: BeautifulSoup, documents: list[dict[str, Any]], fallback: str) -> str:
    for selector in ("h1", "[data-role='title']", ".entry-title", ".show-title"):
        value = _text(detail.select_one(selector))
        if value:
            return value
    for document in documents:
        value = str(document.get("name") or "").strip()
        if value:
            return value
    return fallback


class DetailLinkedListingAdapter:
    """Shared read-only parser for official listing pages with detail links."""

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
        self.detail_pages_out_of_season_skipped = 0
        self.date_candidates_found = 0
        self.date_candidates_accepted = 0
        self.date_candidates_rejected = 0
        self.date_year_unverified = 0
        self.events_outside_season = 0
        self.basel_activity_date_contamination = 0

    @staticmethod
    def _fetch_url(url: str) -> str:
        response = requests.get(url, timeout=60, headers={"User-Agent": "ByelinguaSeasonIngestion/1.0", "Accept": "text/html,application/xhtml+xml"})
        response.raise_for_status()
        return response.text

    def _listing_urls(self, html_text: str, page_url: str) -> list[str]:
        soup = BeautifulSoup(html_text, "html.parser")
        prefixes = tuple(self.settings.get("detail_path_prefixes", []))
        pattern = self.settings.get("detail_link_pattern")
        urls: list[str] = []
        for link in soup.select(self.settings.get("detail_link_selector", "a[href]")):
            href = str(link.get("href") or "").strip()
            absolute = urljoin(page_url, href)
            path = absolute.split("?", 1)[0]
            if prefixes and not any(prefix in path for prefix in prefixes):
                continue
            if pattern and not re.search(pattern, absolute):
                continue
            if absolute not in urls:
                urls.append(absolute)
        return urls

    def _page_season_proven(self, soup: BeautifulSoup, season: str) -> bool:
        selector = self.settings.get("page_season_selector")
        pattern = self.settings.get("page_season_pattern")
        if not selector or not pattern:
            return False
        nodes = soup.select(selector)
        text = " ".join(_text(node) for node in nodes)
        matches = re.findall(pattern, text, re.I)
        if not matches:
            return False
        wanted = re.sub(r"[^0-9]", "", season)
        start_year, end_year = season.split("-", 1)
        full_end = end_year if len(end_year) == 4 else start_year[:2] + end_year
        for match in matches:
            value = "".join(match) if isinstance(match, tuple) else str(match)
            digits = re.sub(r"[^0-9]", "", value)
            if digits in {wanted, start_year + full_end}:
                return True
        return False

    def _page_season_matches(self, soup: BeautifulSoup, season: str) -> bool:
        selector = self.settings.get("page_season_selector")
        pattern = self.settings.get("page_season_pattern")
        if not selector or not pattern:
            return True
        nodes = soup.select(selector)
        text = " ".join(_text(node) for node in nodes)
        matches = re.findall(pattern, text, re.I)
        return not matches or self._page_season_proven(soup, season)

    def _performance_values(self, soup: BeautifulSoup) -> list[str]:
        container_selector = self.settings.get("performance_container_selector")
        date_selector = self.settings.get("performance_date_selector")
        time_selector = self.settings.get("performance_time_selector")
        if not container_selector:
            # Legacy fixtures only; registered live venues provide an explicit
            # performance container and never use this page-wide fallback.
            return [str(node.get("datetime") or node.get("data-date") or node.get("data-start") or _text(node)) for node in soup.select("time[datetime], [data-date], .datelist li, [data-start]")]
        containers = soup.select(container_selector)
        values: list[str] = []
        for container in containers:
            date_nodes = [container]
            if date_selector and date_selector != ":scope":
                date_nodes = container.select(date_selector)
            for date_node in date_nodes:
                raw_date = str(date_node.get("datetime") or date_node.get("data-date") or date_node.get("data-start") or _text(date_node))
                if not raw_date:
                    continue
                clocks = []
                if time_selector:
                    clocks = [_text(node) or str(node.get("datetime") or node.get("data-time") or "") for node in container.select(time_selector)]
                values.extend([f"{raw_date} {clock}" for clock in clocks] or [raw_date])
        return values

    def _events_from_detail(self, page: str, page_url: str, fallback_title: str, season: str) -> list[CanonicalEvent]:
        soup = BeautifulSoup(page, "html.parser")
        documents = _jsonld_documents(page)
        if not self._page_season_matches(soup, season):
            raise OutOfSeasonDetail(page_url)
        title = _detail_title(soup, documents, fallback_title)
        composer, composer_reason = _composer(soup, documents, title, page_url)
        programme = [{"source_title": title, "raw_title": title, "composer": composer, "composer_candidate": {"raw_name": composer, "normalized_name": composer, "source_field": "detail.composer", "source_url": page_url, "confidence": "official composer label"} if composer else {}, "source_programme_index": 1, "raw_programme_index": 1, "original_programme_order": 1, "resolution_status": "pending_global_resolution", "provenance": {"source_url": page_url, "source_field": "detail.composer" if composer else "detail.title"}}]
        occurrences: list[tuple[str, str | None]] = []
        for document in documents:
            start = document.get("startDate") or document.get("startTime")
            if start:
                self.date_candidates_found += 1
                if not re.search(r"20\d{2}", str(start)) and self.settings.get("page_season_selector") and not self._page_season_proven(soup, season):
                    self.date_year_unverified += 1
                    self.date_candidates_rejected += 1
                    continue
                parsed = _parse_date_time(str(start), season=season, settings=self.settings)
                if parsed:
                    occurrences.append(parsed)
        for value in self._performance_values(soup):
            self.date_candidates_found += 1
            has_year = bool(re.search(r"20\d{2}", value))
            if not has_year and self.settings.get("page_season_selector") and not self._page_season_proven(soup, season):
                self.date_year_unverified += 1
                self.date_candidates_rejected += 1
                continue
            parsed = _parse_date_time(value, season=season, settings=self.settings)
            if parsed:
                occurrences.append(parsed)
            elif not has_year:
                self.date_year_unverified += 1
                self.date_candidates_rejected += 1
        unique = []
        for item in dict.fromkeys(occurrences):
            if _in_season(item[0], season, self.settings):
                unique.append(item)
                self.date_candidates_accepted += 1
            else:
                self.date_candidates_rejected += 1
        credits = _credits(soup, page_url)
        events: list[CanonicalEvent] = []
        for event_date, start_time in unique:
            source_event_id = hashlib.sha256(f"{page_url}|{event_date}|{start_time or ''}".encode()).hexdigest()[:24]
            event = CanonicalEvent(source=self.settings.get("source_id", "detail_linked_listing"), source_event_id=source_event_id, source_url=page_url, organization=self.settings["organization"], venue=self.settings["venue"], city=self.settings["city"], country=self.settings["country"], timezone=self.settings["timezone"], title=title, date=event_date, start_time=start_time, end_time=None, room=None, event_type="performance", classification="performance", programme=programme, credits=credits, data_quality={"programme": {"status": "PROGRAMME_EVIDENCE_FOUND" if composer else "DETAIL_PARSE_REVIEW", "reason": composer_reason or "official detail title found without explicit composer label"}, "detail_enrichment": {"status": "complete", "source_url": page_url}}, raw={"listing_source_url": self.settings.get("listing_source"), "detail_source_url": page_url, "source_title": title})
            event.validate()
            events.append(event)
        return events

    def ingest(self, season: str) -> list[CanonicalEvent]:
        listing_url = self.settings.get("listing_source") or self.settings["official_source"]
        self.requested_months.append(listing_url)
        self.listing_pages_requested.append(listing_url)
        try:
            listing_page = self._fetch(listing_url)
            self.successful_months.append(listing_url)
            self.listing_pages_successful.append(listing_url)
            self.source_pages[listing_url] = listing_url
        except Exception as exc:
            self.failed_months.append(listing_url)
            self.listing_pages_failed.append(listing_url)
            self.last_errors.append({"url": listing_url, "error": f"{type(exc).__name__}: {exc}"})
            return []
        detail_urls = self._listing_urls(listing_page, listing_url)
        self.productions_discovered = len(detail_urls)
        self.requested_months.extend(detail_urls)
        self.detail_pages_requested.extend(detail_urls)
        output: list[CanonicalEvent] = []
        for detail_url in detail_urls:
            try:
                detail_page = self._fetch(detail_url)
                self.successful_months.append(detail_url)
                self.detail_pages_successful.append(detail_url)
                self.source_pages[detail_url] = detail_url
                output.extend(self._events_from_detail(detail_page, detail_url, detail_url.rstrip("/").rsplit("/", 1)[-1], season))
            except OutOfSeasonDetail:
                self.detail_pages_out_of_season_skipped += 1
            except Exception as exc:
                self.failed_months.append(detail_url)
                self.detail_pages_failed.append(detail_url)
                self.last_errors.append({"url": detail_url, "error": f"{type(exc).__name__}: {exc}"})
        return sorted({event.event_key: event for event in output}.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
