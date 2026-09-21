"""Deterministic Tonhalle calendar acquisition after compact source discovery."""

from __future__ import annotations

import copy
import hashlib
import re
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from jobs.hermes_acquire_worker import validate_source_facts
from season_ingestion.adapters.europe_venue import EuropeVenueAdapter, _as_name, _credits, _documents, _programme
from season_ingestion.schema import CanonicalEvent


DEFAULT_CALENDAR_ENDPOINT = "https://www.tonhalle-orchester.ch/en/concerts/kalender/?date={month_epoch}"
REQUEST_TIMEOUT_SECONDS = 30
MAX_DETAIL_PAGES_PER_MONTH = 80


def _season_months(season: str) -> list[date]:
    start_year, end_short = (int(part) for part in season.split("-", 1))
    end_year = start_year // 100 * 100 + end_short
    months: list[date] = []
    year, month = start_year, 9
    while (year, month) <= (end_year, 8):
        months.append(date(year, month, 1))
        month += 1
        if month == 13:
            year += 1
            month = 1
    return months


def _month_epoch(month_start: date, timezone_name: str) -> int:
    local = datetime.combine(month_start, time(12, 0), tzinfo=ZoneInfo(timezone_name))
    return int(local.timestamp())


def _calendar_url(endpoint: str, month_start: date, timezone_name: str) -> str:
    epoch = str(_month_epoch(month_start, timezone_name))
    result = endpoint.replace("{month_epoch}", epoch).replace("{year}", f"{month_start.year:04d}").replace("{month}", f"{month_start.month:02d}")
    parts = urlsplit(result)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if any(key == "date" for key, _ in query):
        query = [(key, epoch if key == "date" else value) for key, value in query]
        result = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    elif result == endpoint and "?" not in result:
        result = f"{result}?date={epoch}"
    elif result == endpoint:
        separator = "&" if "?" in result else "?"
        result = f"{result}{separator}date={epoch}"
    return result


def _official_detail_urls(page: str, page_url: str, official_source: str) -> list[str]:
    official_host = urlsplit(official_source).netloc.casefold().removeprefix("www.")
    result: list[str] = []
    soup = BeautifulSoup(page, "html.parser")
    for link in soup.select("a[href]"):
        absolute = urljoin(page_url, str(link.get("href") or "").strip())
        parsed = urlsplit(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.casefold().removeprefix("www.") != official_host:
            continue
        path = parsed.path.casefold()
        if "/en/concerts/" not in path or path.rstrip("/") == "/en/concerts/kalender" or "saison-2026-27" in path:
            continue
        if absolute not in result:
            result.append(absolute)
    return result


def _fetch_text(session: Any, url: str) -> str:
    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": "ByelinguaTonhalleAcquisition/1.0", "Accept": "text/html,application/xhtml+xml"},
    )
    response.raise_for_status()
    return response.text


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _calendar_markup_events(page: str, page_url: str, config: dict[str, Any], season: str) -> list[CanonicalEvent]:
    """Parse Tonhalle's explicit server-rendered .row.data calendar records."""
    soup = BeautifulSoup(page, "html.parser")
    events: list[CanonicalEvent] = []
    timezone_name = str(config.get("timezone") or "Europe/Zurich")
    start_year, end_short = (int(part) for part in season.split("-", 1))
    end_year = start_year // 100 * 100 + end_short
    season_start = date(start_year, 9, 1)
    season_end = date(end_year, 8, 31)
    for row in soup.select(".js-calendarlist-list .row.data"):
        marker = row.select_one(".event[data-timestamp]")
        timestamp = marker.get("data-timestamp") if marker else row.get("data-timestamp")
        try:
            occurrence = datetime.fromtimestamp(int(str(timestamp)), ZoneInfo(timezone_name))
        except (TypeError, ValueError, OSError):
            continue
        if not (season_start <= occurrence.date() <= season_end):
            continue
        title = _clean((row.select_one(".event h3") or {}).get_text(" ", strip=True) if row.select_one(".event h3") else "")
        if not title:
            continue
        source_link = row.select_one("a.desktop-linkoverlay[href], a.mobile-linkoverlay[href]")
        source_url = urljoin(page_url, str(source_link.get("href") or "").strip()) if source_link else page_url
        source_event_id = hashlib.sha256(f"{source_url}|{timestamp}|{title}".encode("utf-8")).hexdigest()[:24]
        credits: list[dict[str, Any]] = []
        member = row.select_one(".member")
        if member:
            names = member.select(".member-name")
            functions = member.select(".member-function")
            for index, name_node in enumerate(names):
                name = _clean(name_node.get_text(" ", strip=True))
                function = _clean(functions[index].get_text(" ", strip=True)) if index < len(functions) else ""
                function = function.rstrip(",").strip()
                if not name or not function:
                    continue
                credits.append({
                    "artist_name": name,
                    "source_role": "performer",
                    "function": function.rstrip(","),
                    "credit_kind": "cast",
                    "source_url": source_url,
                    "source_field": "official.calendar.member",
                    "raw_source_block": name_node.parent.get_text(" ", strip=True) if name_node.parent else name,
                    "provenance": {"source_url": source_url, "source_field": "official.calendar.member"},
                })
        event = CanonicalEvent(
            source=config.get("source_id", config["venue_id"]),
            source_event_id=source_event_id,
            source_url=source_url,
            organization=config["organization"],
            venue=config["venue"],
            city=config["city"],
            country=config["country"],
            timezone=config["timezone"],
            title=title,
            date=occurrence.date().isoformat(),
            start_time=occurrence.strftime("%H:%M"),
            end_time=None,
            room=None,
            event_type=config.get("default_event_type", "performance"),
            classification=config.get("default_event_type", "performance"),
            programme=[],
            credits=credits,
            raw={"listing_source_url": page_url, "source_detail_url": source_url, "source_field": "official.calendar.row.data"},
        )
        event.validate()
        events.append(event)
    return events


def _detail_enrichment(page: str, source_url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract only the explicitly labelled artist/team and programme rows."""
    soup = BeautifulSoup(page, "html.parser")
    sections = [section for section in soup.select(".artists") if section.select_one(".name")]
    credits: list[dict[str, Any]] = []
    if sections:
        names = sections[0].select(".name")
        functions = sections[0].select(".function")
        for index, name_node in enumerate(names):
            name = _clean(name_node.get_text(" ", strip=True))
            function = _clean(functions[index].get_text(" ", strip=True)) if index < len(functions) else ""
            if not name or not function or "pause" in (functions[index].get("class") if index < len(functions) else []):
                continue
            credits.append({
                "artist_name": name,
                "source_role": "performer",
                "function": function,
                "credit_kind": "cast",
                "source_url": source_url,
                "source_field": "official.detail.artists",
                "raw_source_block": f"{name} — {function}",
                "provenance": {"source_url": source_url, "source_field": "official.detail.artists"},
            })
    programme: list[dict[str, Any]] = []
    if sections:
        for name_node, function_node in zip(sections[-1].select(".name"), sections[-1].select(".function")):
            composer = _clean(name_node.get_text(" ", strip=True))
            work_title = _clean(function_node.get_text(" ", strip=True))
            if not composer or not work_title or "pause" in (function_node.get("class") or []):
                continue
            programme.append({
                "source_title": work_title,
                "composer": composer,
                "source_programme_index": len(programme) + 1,
                "original_programme_order": len(programme) + 1,
                "resolution_status": "pending_global_resolution",
                "provenance": {"source_url": source_url, "source_field": "official.detail.programme"},
            })
    if not sections:
        for document in _documents(page):
            event_type = document.get("@type")
            event_types = event_type if isinstance(event_type, list) else [event_type]
            if not any(str(item).casefold() == "event" for item in event_types):
                continue
            title = _as_name(document.get("name")) or "Official event"
            return _programme(document, title, source_url), _credits(document, source_url)
    return programme, credits


def _event_identity(event: Any) -> tuple[str, str, str, str]:
    return (
        str(event.date),
        str(event.start_time or ""),
        " ".join(str(event.title).casefold().split()),
        " ".join(str(event.room or "").casefold().split()),
    )


def _row_identity(row: dict[str, Any], kind: str) -> tuple[str, ...]:
    if kind == "programme":
        return (
            " ".join(str(row.get("source_title") or "").casefold().split()),
            " ".join(str(row.get("composer") or "").casefold().split()),
            str((row.get("provenance") or {}).get("source_url") or ""),
        )
    return (
        " ".join(str(row.get("artist_name") or "").casefold().split()),
        " ".join(str(row.get("source_role") or "").casefold().split()),
        str(row.get("source_url") or ""),
    )


def _merge_event(target: Any, incoming: Any) -> None:
    for collection, kind in (("programme", "programme"), ("credits", "credit")):
        rows = getattr(target, collection)
        seen = {_row_identity(row, kind) for row in rows}
        for row in getattr(incoming, collection):
            if _row_identity(row, kind) not in seen:
                rows.append(copy.deepcopy(row))
                seen.add(_row_identity(row, kind))
    raw = target.raw.setdefault("source_records", [])
    if incoming.source_url not in [item.get("source_url") for item in raw if isinstance(item, dict)]:
        raw.append({"source_url": incoming.source_url, "source_field": "official.detail"})


def _as_source_fact(event: Any, *, listing_url: str) -> dict[str, Any]:
    event.validate()
    source = event.to_dict()
    payload = {key: source[key] for key in (
        "source_event_id", "source_url", "title", "date", "start_time", "end_time", "room",
        "event_type", "classification", "programme", "credits",
    )}
    payload["provenance"] = {
        "source_url": event.source_url,
        "source_field": "official.event.jsonld" if event.source_url != listing_url else "official.calendar.event",
    }
    for row in payload["programme"]:
        row.setdefault("provenance", {})
        row["provenance"].setdefault("source_url", event.source_url)
    for row in payload["credits"]:
        row.setdefault("provenance", {})
        row["provenance"].setdefault("source_url", row.get("source_url") or event.source_url)
    return payload


def acquire_source_facts(
    *,
    config: dict[str, Any],
    season: str,
    discovery: dict[str, Any],
    session: Any = requests,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetch Tonhalle calendar months and official detail pages deterministically."""
    endpoint = str(discovery.get("discovered_endpoint") or DEFAULT_CALENDAR_ENDPOINT)
    expected_host = urlsplit(str(config.get("official_source") or "")).netloc.casefold().removeprefix("www.")
    endpoint_host = urlsplit(endpoint).netloc.casefold().removeprefix("www.")
    if endpoint_host != expected_host:
        raise ValueError("discovered Tonhalle endpoint is outside the official venue domain")

    adapter = EuropeVenueAdapter(config)
    by_identity: dict[tuple[str, str, str, str], Any] = {}
    calendar_pages: list[str] = []
    detail_pages: list[str] = []
    failed_pages: list[dict[str, str]] = []
    detail_seen: set[str] = set()
    timezone_name = str(config.get("timezone") or "Europe/Zurich")

    for month_start in _season_months(season):
        calendar_url = _calendar_url(endpoint, month_start, timezone_name)
        calendar_pages.append(calendar_url)
        try:
            page = _fetch_text(session, calendar_url)
        except Exception as exc:
            failed_pages.append({"url": calendar_url, "error": f"{type(exc).__name__}: {exc}"})
            continue
        markup_events = _calendar_markup_events(page, calendar_url, config, season)
        page_events = markup_events or adapter._event_rows(page, calendar_url, season)
        for event in page_events:
            by_identity.setdefault(_event_identity(event), event)
        detail_urls = _official_detail_urls(page, calendar_url, str(config["official_source"]))
        for event in page_events:
            detail_url = str(event.raw.get("source_detail_url") or "")
            if detail_url and detail_url not in detail_urls:
                detail_urls.append(detail_url)
        for detail_url in detail_urls[:MAX_DETAIL_PAGES_PER_MONTH]:
            if detail_url in detail_seen:
                continue
            detail_seen.add(detail_url)
            detail_pages.append(detail_url)
            try:
                detail_page = _fetch_text(session, detail_url)
            except Exception as exc:
                failed_pages.append({"url": detail_url, "error": f"{type(exc).__name__}: {exc}"})
                continue
            programme, credits = _detail_enrichment(detail_page, detail_url)
            for event in by_identity.values():
                if str(event.raw.get("source_detail_url") or "") != detail_url:
                    continue
                for row in programme:
                    if _row_identity(row, "programme") not in {_row_identity(item, "programme") for item in event.programme}:
                        event.programme.append(copy.deepcopy(row))
                for row in credits:
                    if _row_identity(row, "credit") not in {_row_identity(item, "credit") for item in event.credits}:
                        event.credits.append(copy.deepcopy(row))

    events = sorted(by_identity.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
    facts = {
        "schema_version": "hermes-source-facts-v1",
        "venue_id": config["venue_id"],
        "season": season,
        "source_id": config.get("source_id", config["venue_id"]),
        "source_type": "html",
        "official_source_url": config["official_source"],
        "source_contract": {
            **dict(config.get("source_contract") or {}),
            "writes": False,
            "acquisition_mode": "deterministic_monthly_calendar",
            "discovery": {key: discovery.get(key) for key in ("discovered_mode", "discovered_endpoint", "pagination", "detail_url_pattern", "season_filter") if discovery.get(key) is not None},
        },
        "events": [_as_source_fact(event, listing_url=config.get("listing_source") or config["official_source"]) for event in events],
    }
    validate_source_facts(facts)
    metadata = {
        "calendar_pages": calendar_pages,
        "detail_pages": detail_pages,
        "failed_pages": failed_pages,
        "discovered_endpoint": endpoint,
        "events": len(facts["events"]),
        "programme": sum(len(event["programme"]) for event in facts["events"]),
        "credits": sum(len(event["credits"]) for event in facts["events"]),
    }
    return facts, metadata
