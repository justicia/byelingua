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


def _canonical_event_type(label: str, page_url: str) -> str:
    value = f"{label} {page_url}".casefold()
    if any(token in value for token in ("children", "family", "kids", "school")):
        return "children_family"
    if "ballet" in value or "dance" in value:
        return "ballet"
    if "chamber" in value:
        return "chamber_music"
    if "recital" in value or "pianist" in value or "voice" in value:
        return "recital"
    if "concert" in value or "orchestra" in value or "musical-institutions" in value:
        return "concert"
    if "opera" in value:
        return "opera"
    return "other"


def _first_table_line(node: Any) -> str:
    if not node:
        return ""
    fragment = re.split(r"<br\s*/?>", str(node), maxsplit=1, flags=re.I)[0]
    return _text(BeautifulSoup(fragment, "html.parser"))


def _candidate(raw_name: str, page_url: str, source_field: str) -> dict[str, Any]:
    return {
        "raw_name": raw_name,
        "normalized_name": raw_name,
        "source_field": source_field,
        "source_url": page_url,
        "confidence": "official detail structured field",
    }


def _scala_programme(
    detail: BeautifulSoup,
    *,
    title: str,
    category: str,
    composer: str | None,
    page_url: str,
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    section_selector = settings.get("programme_section_selector", "section#programme")
    row_selector = settings.get("programme_row_selector", "table tbody tr")
    section = detail.select_one(section_selector)
    if not section:
        if category == "opera" and composer:
            source_field = "detail.header.composer"
            return ([{
                "source_title": title,
                "raw_title": title,
                "composer": composer,
                "composer_candidate": _candidate(composer, page_url, source_field),
                "source_programme_index": 1,
                "raw_programme_index": 1,
                "original_programme_order": 1,
                "resolution_status": "pending_global_resolution",
                "provenance": {"source_url": page_url, "source_field": source_field},
            }], False)
        return [], False

    rows: list[dict[str, Any]] = []
    for index, row in enumerate(section.select(row_selector), start=1):
        cells = row.find_all("td", recursive=False) or row.select("td")
        if len(cells) < 2:
            continue
        first, second = cells[0], cells[1]
        if category == "ballet":
            source_title = _text(first)
            row_composer = None
            for strong in second.select("strong"):
                tail = str(strong.next_sibling or "")
                if "music" in tail.casefold():
                    row_composer = _text(strong)
                    break
            if not row_composer:
                match = re.search(r"([^,\n]+),\s*music\b", _text(second), re.I)
                row_composer = match.group(1).strip() if match else None
            source_field = f"detail.programme.row[{index}].music"
        else:
            row_composer = _text(first) or composer
            source_title = _first_table_line(second)
            source_field = f"detail.programme.row[{index}]"
        if not source_title:
            continue
        item = {
            "source_title": source_title,
            "raw_title": source_title,
            "composer": row_composer or None,
            "composer_candidate": _candidate(row_composer, page_url, source_field) if row_composer else {},
            "source_programme_index": index,
            "raw_programme_index": index,
            "original_programme_order": index,
            "resolution_status": "pending_global_resolution",
            "provenance": {"source_url": page_url, "source_field": source_field},
        }
        rows.append(item)
    return rows, True


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
        self.detail_year_hints: dict[str, int] = {}
        self.productions_discovered = 0
        self.detail_pages_out_of_season_skipped = 0
        self.date_candidates_found = 0
        self.date_candidates_accepted = 0
        self.date_candidates_rejected = 0
        self.date_year_unverified = 0
        self.events_outside_season = 0
        self.basel_activity_date_contamination = 0
        self.duplicate_performance_slot = 0
        self.ambiguous_same_day_occurrence = 0
        self.null_timed_shadow_duplicates = 0
        self.year_inferred_without_production_evidence = 0

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
            context_node = link
            context = ""
            for _ in range(4):
                context = _text(context_node)
                if re.search(r"20\d{2}", context):
                    break
                if context_node is None:
                    break
                context_node = context_node.parent
            years = [int(match.group(1)) for match in re.finditer(r"(?<![/-])(20\d{2})(?![/-])", context)]
            if years:
                self.detail_year_hints[absolute] = max(years)
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
                    clocks = [_text(node) or str(node.get("datetime") or node.get("data-time") or "") for node in date_node.select(time_selector)]
                values.extend([f"{raw_date} {clock}" for clock in clocks] or [raw_date])
        return values

    def _production_year_hint(self, soup: BeautifulSoup, title: str) -> int | None:
        text = _text(soup)
        match = re.search(rf"{re.escape(title)}.{{0,240}}?(?<![/-])(20\d{{2}})(?![/-])", text, re.I)
        return int(match.group(1)) if match else None

    def _events_from_detail(self, page: str, page_url: str, fallback_title: str, season: str, year_hint: int | None = None) -> list[CanonicalEvent]:
        soup = BeautifulSoup(page, "html.parser")
        documents = _jsonld_documents(page)
        if not self._page_season_matches(soup, season):
            raise OutOfSeasonDetail(page_url)
        title = _detail_title(soup, documents, fallback_title)
        production_year_hint = year_hint or self._production_year_hint(soup, title)
        if self.settings.get("detail_profile") == "teatro_alla_scala":
            source_type = _text(soup.select_one(self.settings.get("detail_type_selector", ".cnt__leaf")))
            event_type = _canonical_event_type(source_type, page_url)
            header_composer = _text(soup.select_one(self.settings.get("detail_composer_selector", ".cnt__subtitle"))) or None
            programme, programme_section_present = _scala_programme(
                soup, title=title, category=event_type, composer=header_composer,
                page_url=page_url, settings=self.settings,
            )
            composer = header_composer
            composer_reason = "official detail header composer" if header_composer else None
            if programme:
                programme_status = "PROGRAMME_EVIDENCE_FOUND"
                programme_reason = "official structured detail programme"
            elif programme_section_present:
                programme_status = "PROGRAMME_SOURCE_AMBIGUOUS"
                programme_reason = "official Programme section has no deterministic Work rows"
            else:
                programme_status = "NO_PROGRAMME_EVIDENCE"
                programme_reason = "official detail page has no structured programme list"
        else:
            composer, composer_reason = _composer(soup, documents, title, page_url)
            event_type = "performance"
            programme_status = "PROGRAMME_EVIDENCE_FOUND" if composer else "DETAIL_PARSE_REVIEW"
            programme_reason = composer_reason or "official detail title found without explicit composer label"
            programme = [{"source_title": title, "raw_title": title, "composer": composer, "composer_candidate": _candidate(composer, page_url, "detail.composer") if composer else {}, "source_programme_index": 1, "raw_programme_index": 1, "original_programme_order": 1, "resolution_status": "pending_global_resolution", "provenance": {"source_url": page_url, "source_field": "detail.composer" if composer else "detail.title"}}]
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
            if not has_year and production_year_hint:
                if re.search(r"\d{1,2}[./-]\d{1,2}", value):
                    value = re.sub(r"(\d{1,2}[./-]\d{1,2})", rf"\1/{production_year_hint}", value, count=1)
                else:
                    value = re.sub(r"(\d{1,2}\s+[A-Za-zÀ-ÿ]{3,9})", rf"\1 {production_year_hint}", value, count=1)
                has_year = True
            if not has_year and self.settings.get("page_season_selector") and not self._page_season_proven(soup, season):
                self.date_year_unverified += 1
                self.date_candidates_rejected += 1
                continue
            if not has_year and not self._page_season_proven(soup, season):
                self.year_inferred_without_production_evidence += 1
            parsed = _parse_date_time(value, season=season, settings=self.settings)
            if parsed:
                occurrences.append(parsed)
            elif not has_year:
                self.date_year_unverified += 1
                self.date_candidates_rejected += 1
        grouped: dict[str, list[str | None]] = {}
        for item in occurrences:
            if _in_season(item[0], season, self.settings):
                grouped.setdefault(item[0], []).append(item[1])
            else:
                self.date_candidates_rejected += 1
        unique = []
        for event_date, times in grouped.items():
            distinct: list[str | None] = []
            for start_time in times:
                if start_time in distinct:
                    self.duplicate_performance_slot += 1
                    continue
                distinct.append(start_time)
            if None in distinct and any(value is not None for value in distinct):
                distinct.remove(None)
                self.null_timed_shadow_duplicates += 1
            for start_time in distinct:
                unique.append((event_date, start_time))
                self.date_candidates_accepted += 1
        credits = _credits(soup, page_url)
        events: list[CanonicalEvent] = []
        for event_date, start_time in unique:
            source_event_id = hashlib.sha256(f"{page_url}|{event_date}|{start_time or ''}".encode()).hexdigest()[:24]
            event = CanonicalEvent(source=self.settings.get("source_id", "detail_linked_listing"), source_event_id=source_event_id, source_url=page_url, organization=self.settings["organization"], venue=self.settings["venue"], city=self.settings["city"], country=self.settings["country"], timezone=self.settings["timezone"], title=title, date=event_date, start_time=start_time, end_time=None, room=None, event_type=event_type, classification=event_type, programme=programme, credits=credits, data_quality={"programme": {"status": programme_status, "reason": programme_reason}, "detail_enrichment": {"status": "complete", "source_url": page_url, "source_type": source_type if self.settings.get("detail_profile") == "teatro_alla_scala" else None}}, raw={"listing_source_url": self.settings.get("listing_source"), "detail_source_url": page_url, "source_title": title, "source_event_type": source_type if self.settings.get("detail_profile") == "teatro_alla_scala" else None})
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
                output.extend(self._events_from_detail(detail_page, detail_url, detail_url.rstrip("/").rsplit("/", 1)[-1], season, self.detail_year_hints.get(detail_url)))
            except OutOfSeasonDetail:
                self.detail_pages_out_of_season_skipped += 1
            except Exception as exc:
                self.failed_months.append(detail_url)
                self.detail_pages_failed.append(detail_url)
                self.last_errors.append({"url": detail_url, "error": f"{type(exc).__name__}: {exc}"})
        return sorted({event.event_key: event for event in output}.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
