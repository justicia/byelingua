from __future__ import annotations

import re
from datetime import date
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from season_ingestion.credit_resolution import canonical_role
from ingestion.schema import canonical_event_type, stable_event_identity
from season_ingestion.schema import CanonicalEvent


SOURCE = "teatro_real"
BASE_URL = "https://www.teatroreal.es"
BOX_ID_RE = re.compile(r"box(\d{2})-(\d{4})-(\d{2})")
TIME_RE = re.compile(r"[0-2]\d:[0-5]\d")


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


def parse_calendar(
    html: str,
    page_url: str,
    settings: dict,
    *,
    season_start: str,
    season_end: str,
) -> list[CanonicalEvent]:
    """Parse audited calendar discovery into performance-level staging rows."""
    soup = BeautifulSoup(html, "html.parser")
    first, last = date.fromisoformat(season_start), date.fromisoformat(season_end)
    events: list[CanonicalEvent] = []
    seen: set[str] = set()

    for box in soup.select(".calendario-mensual-sidebar .item-box[id]"):
        match = BOX_ID_RE.fullmatch(str(box.get("id", "")))
        if not match:
            continue
        month, year, day = map(int, match.groups())
        performance_date = date(year, month, day)
        if not first <= performance_date <= last:
            continue

        for card in box.select(":scope > .contentbox"):
            title_node = card.select_one(".item-box--premiere__text--title h3 a[href]")
            if not title_node:
                continue
            title = _text(title_node)
            source_url = urljoin(BASE_URL, str(title_node.get("href", "")))
            category = _text(card.select_one(".item-box--premiere__text--title span"))
            event_type = canonical_event_type(category)
            for start_time in dict.fromkeys(
                value for node in card.select(".item-box--premiere__text--btn a")
                if (value := _text(node)) and TIME_RE.fullmatch(value)
            ):
                # Keep the already-shipped Teatro Real identity algorithm. It
                # deliberately includes occurrence date/time and excludes title.
                identity_input = {
                    "source": SOURCE,
                    "source_url": source_url,
                    "organization": settings["organization"],
                    "venue": settings["venue"],
                    "room": None,
                    "date": performance_date.isoformat(),
                    "start_time": start_time,
                }
                source_event_id = stable_event_identity(identity_input)
                if source_event_id in seen:
                    continue
                seen.add(source_event_id)
                event = CanonicalEvent(
                    source=SOURCE,
                    source_event_id=source_event_id,
                    source_url=source_url,
                    organization=settings["organization"],
                    venue=settings["venue"],
                    city=settings["city"],
                    country=settings["country"],
                    timezone=settings["timezone"],
                    title=title,
                    date=performance_date.isoformat(),
                    start_time=start_time,
                    end_time=None,
                    room=None,
                    event_type=event_type,
                    classification=event_type,
                    programme=[{
                        "title": title,
                        "composer": None,
                        "source_title": title,
                        "source_programme_index": 1,
                        "raw_programme_index": 1,
                        "original_programme_order": 1,
                        "status": "review_required",
                        "normalization_status": "review_required",
                        "source_quality_reason": "calendar_does_not_identify_composer_or_work",
                    }],
                    credits=[],
                    data_quality={
                        "credits": {
                            "status": "incomplete_source_data",
                            "reason": "calendar_discovery_does_not_provide_cast_or_credits",
                        }
                    },
                    raw={
                        "calendar_url": page_url,
                        "calendar_box_id": box["id"],
                        "source_event_type": category,
                    },
                )
                event.validate()
                events.append(event)
    return events


class TeatroRealAdapter:
    def __init__(self, settings: dict, fetch: Callable[[str], str] | None = None):
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

    @staticmethod
    def _fetch_url(url: str) -> str:
        response = requests.get(
            url, timeout=30, headers={"User-Agent": "ByelinguaSeasonIngestion/1.0"}
        )
        response.raise_for_status()
        return response.text

    @staticmethod
    def _detail_credits(detail: dict, event: CanonicalEvent, page_url: str) -> list[dict]:
        rows: list[dict] = []
        for item in detail.get("artistic_team", []):
            role = canonical_role(item.get("artistic_function") or item.get("raw_role_label"))
            raw_role = str(item.get("raw_role_label") or item.get("artistic_function") or "").strip()
            person = str(item.get("person") or "").strip()
            if not person or not raw_role:
                continue
            kind = "ensemble" if role in {"orchestra", "choir", "chorus", "ensemble"} else "artistic_team"
            rows.append({
                "artist_name": person,
                "source_role": raw_role,
                "function": role or raw_role,
                "credit_kind": kind,
                "source_url": page_url,
                "source_field": "official.detail.artistic_team",
                "raw_source_block": raw_role,
                "provenance": {"source_url": page_url, "source_field": "official.detail.artistic_team"},
            })
        for item in detail.get("cast", []):
            if item.get("applicable_dates") and event.date not in set(item["applicable_dates"]):
                continue
            person = str(item.get("person") or "").strip()
            character = str(item.get("character_role") or item.get("raw_role_label") or "").strip()
            if not person or not character:
                continue
            rows.append({
                "artist_name": person,
                "source_role": str(item.get("raw_role_label") or character).strip(),
                "function": "performer",
                "character": character,
                "raw_character": character,
                "credit_kind": "cast",
                "source_url": page_url,
                "source_field": "official.detail.cast",
                "raw_source_block": str(item.get("raw_role_label") or character),
                "provenance": {"source_url": page_url, "source_field": "official.detail.cast"},
            })
        return rows

    @staticmethod
    def _detail_programme(detail: dict, event: CanonicalEvent, page_url: str) -> list[dict]:
        result = []
        for index, item in enumerate(detail.get("programme", []), start=1):
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            composer = str(item.get("composer") or "").strip() or None
            result.append({
                "source_title": title,
                "raw_title": title,
                "composer": composer,
                "composer_candidate": {
                    "raw_name": composer,
                    "normalized_name": composer,
                    "source_field": "official.detail.programme",
                    "source_url": page_url,
                    "confidence": "official detail structured field",
                } if composer else {},
                "source_programme_index": index,
                "raw_programme_index": index,
                "original_programme_order": index,
                "resolution_status": "pending_global_resolution",
                "provenance": {"source_url": page_url, "source_field": "official.detail.programme"},
            })
        return result

    def ingest(self, season: str) -> list[CanonicalEvent]:
        from season_ingestion.season import resolve_season_bounds

        season_start, season_end = resolve_season_bounds(season, self.settings)
        url = self.settings["calendar_url"]
        self.requested_months.append(url)
        self.listing_pages_requested.append(url)
        try:
            events = parse_calendar(
                self._fetch(url), url, self.settings,
                season_start=season_start, season_end=season_end,
            )
            self.successful_months.append(url)
            self.listing_pages_successful.append(url)
            self.source_pages[url] = url
        except Exception as exc:
            self.failed_months.append(url)
            self.listing_pages_failed.append(url)
            self.last_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
            return []
        if not self.settings.get("detail_enrichment"):
            return sorted(events, key=lambda event: (event.date, event.start_time or "", event.event_key))

        detail_cache: dict[str, dict] = {}
        self.productions_discovered = len(set(event.source_url for event in events))
        for page_url in dict.fromkeys(event.source_url for event in events):
            self.requested_months.append(page_url)
            self.detail_pages_requested.append(page_url)
            try:
                from ingestion.adapters.teatro_real import parse_detail_html
                detail_cache[page_url] = parse_detail_html(self._fetch(page_url))
                self.successful_months.append(page_url)
                self.detail_pages_successful.append(page_url)
                self.source_pages[page_url] = page_url
            except Exception as exc:
                self.failed_months.append(page_url)
                self.detail_pages_failed.append(page_url)
                self.last_errors.append({"url": page_url, "error": f"{type(exc).__name__}: {exc}"})

        enriched: list[CanonicalEvent] = []
        for event in events:
            detail = detail_cache.get(event.source_url)
            if not detail:
                enriched.append(event)
                continue
            programme = self._detail_programme(detail, event, event.source_url)
            enriched.append(CanonicalEvent(
                source=event.source,
                source_event_id=event.source_event_id,
                source_url=event.source_url,
                organization=event.organization,
                venue=event.venue,
                city=event.city,
                country=event.country,
                timezone=event.timezone,
                title=detail.get("title") or event.title,
                date=event.date,
                start_time=event.start_time,
                end_time=event.end_time,
                room=event.room,
                event_type=event.event_type,
                classification=event.classification,
                programme=programme or event.programme,
                credits=self._detail_credits(detail, event, event.source_url),
                data_quality={
                    "programme": {
                        "status": "PROGRAMME_EVIDENCE_FOUND" if programme else "NO_PROGRAMME_EVIDENCE",
                        "reason": "official production detail page",
                    },
                    "detail_enrichment": {
                        "status": "complete",
                        "source_url": event.source_url,
                        "propagation": "production_level_with_date_specific_cast_filter",
                    },
                },
                raw=event.raw | {"detail_source_url": event.source_url},
            ))
        return sorted(enriched, key=lambda event: (event.date, event.start_time or "", event.event_key))
