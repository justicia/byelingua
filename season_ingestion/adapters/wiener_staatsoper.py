from __future__ import annotations

import re
from calendar import month_name
from datetime import date
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from season_ingestion.schema import CanonicalEvent

SOURCE = "wiener_staatsoper"
BASE_URL = "https://www.wiener-staatsoper.at"
DETAIL_RE = re.compile(r"/calendar/detail/([^/]+)/(\d{4}-\d{2}-\d{2})/?(?:[?#].*)?$")
TIME_RE = re.compile(r"(\d{1,2})[:.]([0-5]\d)")

FUNCTIONS = {
    "musikalische leitung": "conductor", "dirigent": "conductor", "conductor": "conductor",
    "inszenierung": "stage_director", "regie": "stage_director", "bühne": "set_designer",
    "kostüm": "costume_designer", "licht": "lighting_designer", "video": "video_designer",
    "dramaturg": "dramaturg",
}


def _production_function(label: str) -> str | None:
    key = label.casefold().strip()
    if key in FUNCTIONS:
        return FUNCTIONS[key]
    # The site also uses combined labels and inflected job titles.
    for token, function in (
        ("inszenierung", "stage_director"), ("regie", "stage_director"),
        ("bühne", "set_designer"), ("kostüm", "costume_designer"),
        ("licht", "lighting_designer"), ("video", "video_designer"),
        ("dramaturg", "dramaturg"),
    ):
        if token in key:
            return function
    return None


def _text(node: Tag | None) -> str:
    # get_text(strip=True) does not collapse whitespace embedded in a text node.
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


def _event_type(label: str) -> str:
    key = label.casefold()
    if "operette" in key: return "operetta"
    if "oper" in key: return "opera"
    if "ballett" in key or "ballet" in key: return "ballet"
    if "konzert" in key or "concert" in key: return "concert"
    return "other"


def _classification(label: str, title: str, event_type: str) -> str:
    """Keep non-performance activities from looking like ordinary concerts."""
    value = f"{label} {title}".casefold()
    for needle, classification in (
        ("workshop", "workshop"), ("open class", "open_class"),
        ("opera ball", "opera_ball"), ("opernball", "opera_ball"),
        ("guided tour", "guided_tour"), ("führung", "guided_tour"),
    ):
        if needle in value:
            return classification
    return event_type


def _programme(title: str, lead: Tag | None) -> list[dict]:
    raw_lead = lead.get_text(" ", strip=True) if lead else ""
    cleaned = re.sub(r"\s+", " ", raw_lead).strip(" ,")
    # The calendar renders multiple names as comma-separated template blocks.
    composers = [part.strip() for part in cleaned.split(",") if part.strip()]
    if not composers:
        return [{"title": title, "composer": None, "source_title": title,
                 "status": "review_required", "normalization_status": "review_required",
                 "source_quality_reason": "calendar_does_not_identify_composer_or_work"}]
    return [{"title": title, "composer": composer, "source_title": title,
             "status": "source_verified", "normalization_status": "source_verified"}
            for composer in composers]


def _times(value: str) -> tuple[str | None, str | None]:
    values = [f"{int(h):02d}:{m}" for h, m in TIME_RE.findall(value)]
    return (values[0] if values else None, values[1] if len(values) > 1 else None)


def parse_calendar(html: str, page_url: str, settings: dict) -> list[CanonicalEvent]:
    soup = BeautifulSoup(html, "html.parser")
    time_by_id = {
        str(node.get("data-event")): _times(_text(node.select_one(".production-time")))
        for node in soup.select(".sticky-date[data-event]")
    }
    events: list[CanonicalEvent] = []
    seen: set[str] = set()
    for title_node in soup.select(".event-list-item .event-title"):
        card = title_node.find_parent(class_="event-list-item")
        if not card or not card.get("id"): continue
        link = title_node if title_node.name == "a" else title_node.find_parent("a")
        if not link:
            link = next((candidate for candidate in card.select("a[href]")
                         if DETAIL_RE.search(str(candidate.get("href", "")))), None)
        if not link or not link.get("href"): continue
        match = DETAIL_RE.search(str(link["href"]))
        if not match: continue
        slug, event_date = match.groups()
        source_id = f"{slug}:{event_date}"
        if source_id in seen: continue
        seen.add(source_id)
        title = _text(title_node)
        genre = _text(card.select_one(".event-genre"))
        lead = card.select_one(".event-lead")
        event_type = _event_type(genre)
        classification = _classification(genre, title, event_type)
        credits = []
        for row in card.select(".production-cast .d-flex.justify-content-between"):
            label = _text(row.find("p"))
            right = row.select_one(".text-end")
            people = right.select("a, .text-primary") if right else []
            for person_node in people:
                person = _text(person_node)
                if not label or not person: continue
                function = _production_function(label)
                credit = {"person": person, "raw_role_label": label}
                if function:
                    credit.update(role="production", artistic_function=function)
                elif event_type in {"opera", "operetta", "ballet"}:
                    credit.update(role="performer", character=label)
                else:
                    credit.update(role="production", artistic_function=label)
                credits.append(credit)
        # sticky-date is a sibling of the actual event card. data-event is the
        # explicit association supplied by the site; DOM proximity is unsafe.
        start, end = time_by_id.get(str(card["id"]), (None, None))
        data_quality = {}
        if start is None:
            data_quality["start_time"] = {
                "status": "missing_at_source",
                "reason": "calendar_sticky_time_not_provided",
            }
        if not credits and event_type in {"opera", "operetta", "concert"}:
            data_quality["credits"] = {
                "status": "incomplete_source_data",
                "reason": "calendar_cast_or_credits_not_provided",
            }
        event = CanonicalEvent(
            source=SOURCE, source_event_id=source_id,
            source_url=urljoin(BASE_URL, str(link["href"])),
            organization=settings["organization"], venue=settings["venue"],
            city=settings["city"], country=settings["country"], timezone=settings["timezone"],
            title=title, date=date.fromisoformat(event_date).isoformat(), start_time=start,
            end_time=end, room=_text(card.select_one(".event-room")) or None,
            event_type=event_type, classification=classification,
            programme=_programme(title, lead), credits=credits, data_quality=data_quality,
            raw={"calendar_url": page_url, "card_id": card["id"], "genre": genre,
                 "source_lead": lead.get_text(" ", strip=True) if lead else None},
        )
        event.validate()
        events.append(event)
    return events


class WienerStaatsoperAdapter:
    def __init__(self, settings: dict, fetch: Callable[[str], str] | None = None):
        self.settings = settings
        self._fetch = fetch or self._fetch_url
        self.last_errors: list[dict[str, str]] = []

    @staticmethod
    def _fetch_url(url: str) -> str:
        response = requests.get(url, timeout=30, headers={"User-Agent": "ByelinguaSeasonIngestion/1.0"})
        response.raise_for_status()
        return response.text

    def ingest(self, season: str) -> list[CanonicalEvent]:
        match = re.fullmatch(r"(\d{4})-(\d{2})", season)
        if not match: raise ValueError("season must look like 2026-27")
        first = int(match.group(1))
        if int(match.group(2)) != (first + 1) % 100: raise ValueError("season years must be consecutive")
        events: list[CanonicalEvent] = []
        for year, month in [(first, m) for m in range(9, 13)] + [(first + 1, m) for m in range(1, 9)]:
            url = self.settings["calendar_url"].format(year=year, month=month_name[month].lower())
            try:
                # Exactly one request per month; all data comes from the calendar DOM.
                events.extend(parse_calendar(self._fetch(url), url, self.settings))
            except Exception as exc:
                self.last_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        unique = {event.event_key: event for event in events}
        return sorted(unique.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
