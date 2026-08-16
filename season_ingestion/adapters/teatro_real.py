from __future__ import annotations

import re
from datetime import date
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

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

    @staticmethod
    def _fetch_url(url: str) -> str:
        response = requests.get(
            url, timeout=30, headers={"User-Agent": "ByelinguaSeasonIngestion/1.0"}
        )
        response.raise_for_status()
        return response.text

    def ingest(self, season: str) -> list[CanonicalEvent]:
        from season_ingestion.season import resolve_season_bounds

        season_start, season_end = resolve_season_bounds(season, self.settings)
        url = self.settings["calendar_url"]
        try:
            events = parse_calendar(
                self._fetch(url), url, self.settings,
                season_start=season_start, season_end=season_end,
            )
        except Exception as exc:
            self.last_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
            return []
        return sorted(events, key=lambda event: (event.date, event.start_time or "", event.event_key))
