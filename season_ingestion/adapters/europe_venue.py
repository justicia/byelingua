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
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Any, Callable
from urllib.parse import urljoin
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


_EMBEDDED_JSON_RE = re.compile(
    r"<script[^>]*(?:type=[\"']application/json[\"']|id=[\"'](?:__NEXT_DATA__|__NUXT_DATA__)[\"'])[^>]*>(.*?)</script>",
    re.I | re.S,
)
_EMBEDDED_DATE_KEYS = ("startDate", "start_date", "dateFrom", "date_from", "start", "date")
_EMBEDDED_TITLE_KEYS = ("name", "title", "eventTitle", "event_title")


def _decode_json_payload(page: str) -> Any:
    raw_text = str(page or "").strip()
    candidates = [raw_text, html.unescape(raw_text)]
    candidates.extend(match.strip() for match in _EMBEDDED_JSON_RE.findall(raw_text))
    candidates.extend(html.unescape(match.strip()) for match in _EMBEDDED_JSON_RE.findall(raw_text))
    for candidate in candidates:
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        # One official JSON:API endpoint currently transports its payload as a
        # JSON array of byte values. Decode that transport wrapper only; the
        # factual payload is still parsed and validated as ordinary JSON.
        if isinstance(value, list) and value and all(isinstance(item, int) and 0 <= item <= 255 for item in value):
            try:
                value = json.loads(bytes(value).decode("utf-8"))
            except (UnicodeDecodeError, TypeError, ValueError):
                pass
        return value
    return None


def _rbo_event_documents(value: Any, page_url: str) -> list[dict[str, Any]]:
    """Adapt the Royal Ballet and Opera JSON:API payload without guessing."""
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        return []
    rows = value["data"]
    if not rows or any(not isinstance(row, dict) or row.get("type") != "event" for row in rows):
        return []

    tag_titles = {
        str(item.get("id")): _embedded_text((item.get("attributes") or {}).get("title"))
        for item in value.get("included", [])
        if isinstance(item, dict) and item.get("type") == "tags"
    }
    documents: list[dict[str, Any]] = []
    for row in rows:
        attributes = row.get("attributes") or {}
        title = _embedded_text(attributes.get("title"))
        if not title:
            continue
        tag_ids = [
            str(item.get("id"))
            for item in (((row.get("relationships") or {}).get("tags") or {}).get("data") or [])
            if isinstance(item, dict) and item.get("id") is not None
        ]
        tags = [tag_titles[tag_id] for tag_id in tag_ids if tag_titles.get(tag_id)]
        tag_set = set(tags)
        if "Tours" in tag_set:
            event_type = "visitor_activity"
        elif "Rehearsals" in tag_set:
            event_type = "rehearsal"
        elif "Talks and insights" in tag_set:
            event_type = "other"
        elif "Family events" in tag_set or "Workshops and activities" in tag_set:
            event_type = "children_family"
        elif title in {"Recitals at Lunch", "Live at Lunch"}:
            event_type = "recital"
        elif title in {"Dish from Waitrose", "Tea Dance"}:
            event_type = "other"
        elif "in Concert" in title and "Opera and music" in tag_set:
            event_type = "opera_en_concert"
        elif "Opera and music" in tag_set:
            event_type = "opera"
        elif "Ballet and dance" in tag_set:
            event_type = "ballet"
        elif re.search(r"\brecitals?\b", title, re.I):
            event_type = "recital"
        else:
            event_type = "performance"

        detail_url = _embedded_text(attributes.get("productionPageUrl"))
        source_url = urljoin(page_url, detail_url) if detail_url else page_url
        for performance in attributes.get("performances") or []:
            if not isinstance(performance, dict) or not performance.get("date"):
                continue
            start = str(performance["date"])
            performance_type = _embedded_text(performance.get("performanceType"))
            documents.append({
                "@type": "Event",
                "@id": f"{row.get('id') or attributes.get('slug') or title}|{start}|{performance_type or ''}",
                "name": title,
                "startDate": start,
                "url": source_url,
                "_event_type": event_type,
                "_official_tags": tags,
                "_performance_type": performance_type,
            })
    return documents


def _rbo_production_documents(page: str, page_url: str) -> list[dict[str, Any]]:
    """Read dated, per-performance cast from RBO's server-rendered state."""
    soup = BeautifulSoup(page, "html.parser")
    marker = "window.__REACT_QUERY_DEHYDRATED_STATE__"
    payload: dict[str, Any] | None = None
    for script in soup.find_all("script"):
        raw = script.string or script.get_text() or ""
        if marker not in raw:
            continue
        candidate = raw.split("=", 1)[1].strip().rstrip(";").strip()
        try:
            decoded = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(decoded, dict):
            payload = decoded
            break
    if payload is None:
        return []

    documents: list[dict[str, Any]] = []
    for query in payload.get("queries") or []:
        if not isinstance(query, dict):
            continue
        data = (((query.get("state") or {}).get("data") or {}).get("data") or {})
        stage = data.get("stage")
        if not isinstance(stage, dict):
            continue
        stage_title = _embedded_text(stage.get("title"))
        if not stage_title:
            continue
        for activity in stage.get("activities") or []:
            if not isinstance(activity, dict):
                continue
            attributes = activity.get("attributes") or {}
            start = attributes.get("date")
            if not start:
                continue
            tags = [
                _embedded_text((item.get("tags") or {}).get("title"))
                for item in attributes.get("tags") or []
                if isinstance(item, dict)
            ]
            tags = [tag for tag in tags if tag]
            tag_set = set(tags)
            event_type = "opera" if "Opera and music" in tag_set else "ballet" if "Ballet and dance" in tag_set else "performance"
            credits: list[dict[str, Any]] = []
            for billing_order, cast in enumerate(attributes.get("prioritisedCast") or [], start=1):
                if not isinstance(cast, dict):
                    continue
                artist = _embedded_text(cast.get("name"))
                role = _embedded_text(cast.get("role"))
                if not artist or not role:
                    continue
                role_key = role.casefold()
                if role_key == "conductor":
                    function, credit_kind, character = "conductor", "artistic_team", None
                elif role_key in {"orchestra", "chorus", "choir", "ensemble"}:
                    function, credit_kind, character = role_key, "ensemble", None
                else:
                    function, credit_kind, character = "performer", "cast", role
                credits.append({
                    "artist_name": artist.strip(),
                    "source_role": role,
                    "function": function,
                    "character": character,
                    "credit_kind": credit_kind,
                    "billing_order": billing_order,
                    "source_url": page_url,
                    "source_field": "rbo.stage.activities.prioritisedCast",
                    "raw_source_block": f"{role}: {artist.strip()}",
                    "provenance": {"source_url": page_url, "source_field": "rbo.stage.activities.prioritisedCast", "activity_id": str(activity.get("id") or "")},
                })
            documents.append({
                "@type": "Event",
                "@id": str(activity.get("id") or f"{stage_title}|{start}"),
                "name": stage_title,
                "startDate": str(start),
                "url": page_url,
                "location": {"name": _embedded_text(((attributes.get("locations") or [{}])[0].get("locations") or {}).get("title"))} if attributes.get("locations") else None,
                "_event_type": event_type,
                "_official_tags": tags,
                "_official_credits": credits,
                "_cast_list_url": urljoin(page_url, str(attributes.get("castListUrl") or "")),
            })
    return documents


def _embedded_date(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("value", "datetime", "date", "ts", "timestamp"):
            if value.get(key) is not None:
                return _embedded_date(value[key])
        return None
    if isinstance(value, (int, float)) and value > 0:
        seconds = float(value) / 1000 if value > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    raw = str(value or "").strip()
    return raw or None


def _embedded_text(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("en", "en_GB", "name", "value", "text", "label"):
            if value.get(key):
                result = _embedded_text(value[key])
                if result:
                    return result
        return None
    if isinstance(value, list):
        return next((result for item in value if (result := _embedded_text(item))), None)
    raw = re.sub(r"<[^>]+>", " ", str(value or ""))
    raw = re.sub(r"\s+", " ", html.unescape(raw)).strip()
    return raw or None


def _embedded_event_documents(value: Any, page_url: str) -> list[dict[str, Any]]:
    """Find explicit dated records in generic official JSON/embedded payloads."""
    documents: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}

    def index(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                index(item)
            return
        if not isinstance(node, dict):
            return
        if isinstance(node.get("attributes"), dict):
            flattened = {**node, **node["attributes"]}
            node = flattened
        for key in ("id", "@id", "production_id", "productionId"):
            if node.get(key) is not None:
                by_id[str(node[key])] = node
                break
        for child in node.values():
            if isinstance(child, (dict, list)):
                index(child)

    index(value)

    def visit(node: Any, inherited: dict[str, Any]) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item, inherited)
            return
        if not isinstance(node, dict):
            return
        if isinstance(node.get("attributes"), dict):
            node = {**node, **node["attributes"]}

        context = dict(inherited)
        relation = node.get("production") or node.get("production_id") or node.get("productionId")
        if isinstance(relation, dict):
            relation = relation.get("id") or relation.get("data", {}).get("id") if isinstance(relation.get("data"), dict) else relation.get("id")
        if relation is not None and str(relation) in by_id:
            related = by_id[str(relation)]
            for key in _EMBEDDED_TITLE_KEYS + ("url", "href", "composer", "performer", "performers", "artist", "artists", "conductor"):
                if related.get(key) is not None and node.get(key) is None:
                    node = {**related, **node}
        for key in _EMBEDDED_TITLE_KEYS:
            title = _embedded_text(node.get(key))
            if title:
                context["title"] = title
                break
        for key in ("url", "href", "detail_url", "detailUrl", "source_url"):
            source_url = _embedded_text(node.get(key))
            if source_url:
                context["url"] = urljoin(page_url, source_url)
                break
        for key in ("composer", "performer", "performers", "artist", "artists", "conductor"):
            if node.get(key) is not None:
                context[key] = node[key]
        for key in _EMBEDDED_DATE_KEYS:
            raw_date = _embedded_date(node.get(key))
            if raw_date and context.get("title"):
                identity = _embedded_text(node.get("id") or node.get("@id") or node.get("event_id"))
                document: dict[str, Any] = {
                    "@type": "Event",
                    "@id": identity or context.get("url") or f"{context['title']}|{raw_date}",
                    "name": context["title"],
                    "startDate": raw_date,
                    "url": context.get("url") or page_url,
                }
                if context.get("composer") is not None:
                    document["workPerformed"] = {"name": context["title"], "composer": context["composer"]}
                for credit_key in ("performer", "performers", "artist", "artists", "conductor"):
                    if context.get(credit_key) is not None:
                        document[credit_key] = context[credit_key]
                documents.append(document)
                break
        for child in node.values():
            if isinstance(child, (dict, list)):
                visit(child, context)

    visit(value, {})
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for document in documents:
        key = (str(document.get("@id")), str(document.get("startDate")), str(document.get("name")))
        if key not in seen:
            unique.append(document)
            seen.add(key)
    return unique


def _official_event_overview(page: str, page_url: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Adapt the shared official EventOverview API shape to Event documents."""
    try:
        payload = json.loads(page)
    except (TypeError, ValueError):
        return [], {}
    if not isinstance(payload, dict) or not isinstance(payload.get("EventOverview"), list):
        return [], {}
    documents: list[dict[str, Any]] = []
    for row in payload["EventOverview"]:
        if not isinstance(row, dict):
            continue
        title = _as_name(row.get("Title"))
        start = row.get("DateFrom")
        if not title or not start:
            continue
        detail_url = urljoin(page_url, str(row.get("Slug") or row.get("Url") or "").strip())
        documents.append({
            "@type": "Event",
            "@id": str(row.get("IdEventDate") or row.get("IdEventCluster") or ""),
            "name": title,
            "startDate": start,
            "endDate": row.get("DateTo"),
            "url": detail_url or page_url,
            "location": {"name": _as_name(row.get("Location"))} if _as_name(row.get("Location")) else None,
            "_official_detail_url": detail_url or None,
        })
    return documents, payload.get("Pager") if isinstance(payload.get("Pager"), dict) else {}


def _api_page_urls(page: str, page_url: str) -> list[str]:
    """Expand an observed official paginated API endpoint without guessing."""
    _, pager = _official_event_overview(page, page_url)
    last_page = pager.get("LastIndex")
    if not isinstance(last_page, int) or last_page < 2 or last_page > 100:
        return []
    if "{page}" in page_url:
        return [page_url.replace("{page}", str(index)) for index in range(2, last_page + 1)]
    if re.search(r"([?&]p=)\d+", page_url):
        return [re.sub(r"([?&]p=)\d+", rf"\g<1>{index}", page_url) for index in range(2, last_page + 1)]
    return []


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
    match = re.search(r"\b(20\d{2})[/.](\d{1,2})[/.](\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?", raw)
    if match:
        year, month, day, hour, minute = match.groups()
        try:
            event_date = date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            return None
        return event_date, f"{int(hour):02d}:{minute}" if hour is not None else None
    match = re.search(r"\b(\d{1,2})[.](\d{1,2})[.](20\d{2})(?:[ T](\d{1,2}):(\d{2}))?", raw)
    if match:
        day, month, year, hour, minute = match.groups()
        try:
            event_date = date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            return None
        return event_date, f"{int(hour):02d}:{minute}" if hour is not None else None
    month_names = {
        "jan": 1, "january": 1, "janvier": 1, "januar": 1,
        "feb": 2, "february": 2, "février": 2, "februar": 2,
        "mar": 3, "march": 3, "mars": 3, "märz": 3, "maerz": 3,
        "apr": 4, "april": 4, "avril": 4,
        "may": 5, "mai": 5,
        "jun": 6, "june": 6, "juin": 6, "juni": 6,
        "jul": 7, "july": 7, "juillet": 7, "juli": 7,
        "aug": 8, "august": 8, "août": 8,
        "sep": 9, "sept": 9, "september": 9, "septiembre": 9, "septembre": 9, "september": 9,
        "oct": 10, "october": 10, "octubre": 10, "oktober": 10,
        "nov": 11, "november": 11, "noviembre": 11,
        "dec": 12, "december": 12, "décembre": 12, "dezember": 12,
    }
    match = re.search(r"\b(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\.?['’]?\s*(20\d{2}|\d{2})\b", raw, re.I)
    if match:
        day, month_name, year = match.groups()
        month = month_names.get(month_name.casefold())
        year_value = int(year) if len(year) == 4 else 2000 + int(year)
        if month:
            try:
                return date(year_value, month, int(day)).isoformat(), None
            except ValueError:
                return None
    return None


def _decode_js_string(value: str) -> str:
    try:
        return str(json.loads(f'"{value}"'))
    except (TypeError, ValueError):
        return html.unescape(value)


def _html_event_documents(page: str, page_url: str) -> list[dict[str, Any]]:
    """Extract explicit dates from reusable calendar/card markup and payloads."""
    soup = BeautifulSoup(page, "html.parser")
    documents: list[dict[str, Any]] = []

    def add(card: Any, raw_date: Any, source_url: str | None = None) -> None:
        parsed = _parse_explicit(raw_date)
        if not parsed:
            return
        if parsed[1] is None:
            time_match = TIME_RE.search(_text(card)) if card else None
            if time_match:
                parsed = (parsed[0], time_match.group(0))
        title_node = card.select_one("h1, h2, h3, h4, h5, h6, [class*='title'], [class*='name'], [data-role='title']")
        title = _clean_title(_text(title_node)) if title_node else ""
        link = card.select_one("a[href]") if card else None
        href = (card.get("data-href") if card and card.get("data-href") else (link.get("href") if link else None))
        source = urljoin(page_url, str(source_url or href or page_url))
        if (not title or title.casefold() in {"header", "calendar", "event"}) and link:
            title = _clean_title(_text(link))
        if not title or _generic_event_title(title):
            return
        documents.append({
            "@type": "Event",
            "@id": f"{source}|{parsed[0]}|{title}",
            "name": title,
            "startDate": f"{parsed[0]}T{parsed[1]}" if parsed[1] else parsed[0],
            "url": source,
        })

    for day_node in soup.select("[data-day]"):
        raw_date = day_node.get("data-day")
        for card in day_node.select("article, li, [class*='event'], [class*='calendar']"):
            add(card, raw_date)

    for node in soup.select("[data-date], [data-start], [data-event-date], time[datetime], time[data-date], time[data-start]"):
        raw_date = node.get("data-date") or node.get("data-event-date") or node.get("data-start") or node.get("datetime")
        card = node
        for _ in range(6):
            classes = " ".join(card.get("class", [])) if getattr(card, "get", None) else ""
            if getattr(card, "name", None) in {"article", "li"} or "event" in classes.casefold() or "calendar" in classes.casefold():
                break
            card = card.parent or card
        add(card, raw_date)

    date_text_re = re.compile(
        r"\b\d{1,2}\s+(?:Jan(?:uary|vier)?|Feb(?:ruary|ruar)?|Mar(?:ch|s)?|Apr(?:il|il)?|May|Mai|Jun(?:e|i)?|Jul(?:y|i)?|Aug(?:ust)?|Sep(?:t|tember|tiembre|tembre)?|Oct(?:ober|ubre)?|Nov(?:ember|iembre)?|Dec(?:ember|embre)?|Dezember)\.?['’]?\s*\d{2,4}\b",
        re.I,
    )
    for link in soup.select("a[href]"):
        href = str(link.get("href") or "")
        if not href or href.startswith(("#", "javascript:")):
            continue
        card = link
        for _ in range(8):
            text = _text(card)
            match = date_text_re.search(text)
            if match:
                add(card, match.group(0), source_url=href)
                break
            card = card.parent or card

    # Nuxt/devalue-style rendered payloads are not JSON, but their literal
    # date_start and name fields remain source-supported and deterministic.
    for match in re.finditer(r"(?:date_start|dateStart|startDate|date):\"(?P<value>20\d{2}[-/.]\d{2}[-/.]\d{2}(?:T[^\"]+)?)\"", page):
        window = page[match.end(): match.end() + 2600]
        title = None
        for title_match in re.finditer(r"(?:name|title|subtitle):\"(?P<title>[^\"]{2,180})\"", window):
            candidate = _clean_title(_decode_js_string(title_match.group("title")))
            if candidate and not _generic_event_title(candidate):
                title = candidate
                break
        if not title:
            continue
        parsed = _parse_explicit(_decode_js_string(match.group("value")))
        if not parsed:
            continue
        documents.append({
            "@type": "Event",
            "@id": f"{page_url}|{parsed[0]}|{title}",
            "name": title,
            "startDate": _decode_js_string(match.group("value")),
            "url": page_url,
        })

    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for document in documents:
        key = (str(document.get("name")), str(document.get("startDate")))
        if key not in seen:
            unique.append(document)
            seen.add(key)
    return unique


def _season_month_urls(template: str, season: str) -> list[str]:
    """Expand an observed month template across the requested season only."""
    if not any(token in template for token in ("YYYY-MM", "{YYYY-MM}", "{year_month}")):
        return [template]
    start_year, end_short = (int(part) for part in season.split("-", 1))
    end_year = start_year // 100 * 100 + end_short
    urls: list[str] = []
    year, month = start_year, 9
    for _ in range(12):
        value = f"{year:04d}-{month:02d}"
        url = template.replace("{YYYY-MM}", value).replace("YYYY-MM", value).replace("{year_month}", value)
        if url not in urls:
            urls.append(url)
        month += 1
        if month == 13:
            month = 1
            year += 1
    if year != end_year:
        raise ValueError(f"season month expansion crossed unexpected end year for {season}")
    return urls


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
    return []


GENERIC_EVENT_TITLES = {"season", "what's on", "classical music", "programme", "calendar", "events"}


def _generic_event_title(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value.casefold()).strip()
    return normalized in GENERIC_EVENT_TITLES or normalized.startswith("season 20") or normalized.startswith("what's on") or "classical music |" in normalized


def _credits(document: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field, role, kind in (
        ("performer", "performer", "cast"),
        ("performers", "performer", "cast"),
        ("artist", "performer", "cast"),
        ("artists", "performer", "cast"),
        ("actor", "performer", "cast"),
        ("director", "stage_director", "artistic_team"),
        ("conductor", "conductor", "artistic_team"),
    ):
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
        self.source_duplicates_collapsed = 0
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
        rbo_detail_documents = _rbo_production_documents(page, page_url) if detail else []
        overview_documents, _ = _official_event_overview(page, page_url)
        documents = rbo_detail_documents or overview_documents or [document for document in _documents(page) if "event" in _types(document)]
        if not documents:
            decoded_payload = _decode_json_payload(page)
            documents = _rbo_event_documents(decoded_payload, page_url)
            if not documents:
                documents = _embedded_event_documents(decoded_payload, page_url)
        if not documents:
            documents = _html_event_documents(page, page_url)
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
            parsed = None
            if isinstance(start_raw, str) and re.search(r"[+-]\d{2}:\d{2}$|Z$", start_raw):
                try:
                    parsed_at = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(ZoneInfo(self.settings["timezone"]))
                    parsed = (parsed_at.date().isoformat(), parsed_at.strftime("%H:%M"))
                except (ValueError, KeyError, ZoneInfoNotFoundError):
                    parsed = None
            parsed = parsed or _parse_explicit(start_raw)
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
            if _generic_event_title(title):
                self.date_candidates_rejected += 1
                continue
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
                event_type=str(document.get("_event_type") or self.settings.get("default_event_type", "performance")),
                classification=str(document.get("_event_type") or self.settings.get("default_event_type", "performance")),
                programme=_programme(document, title, source_url),
                credits=list(document.get("_official_credits") or _credits(document, source_url)),
                data_quality={"schedule": {"year_status": "YEAR_EXPLICIT", "source_field": "jsonld.startDate"}, "programme": {"status": "PROGRAMME_EVIDENCE_FOUND" if document.get("workPerformed") or document.get("work") else "NO_PROGRAMME_EVIDENCE", "reason": "official source Event JSON-LD"}},
                raw={"source_title": title, "source_occurrence": {"startDate": start_raw, "source_identity": source_identity, "performance_type": document.get("_performance_type")}, "source_url": source_url, "listing_source_url": page_url if not detail else self.settings.get("listing_source", page_url), "source_document_type": "jsonld.event" if documents else "html.time", "official_tags": document.get("_official_tags", [])},
            )
            event.validate()
            events.append(event)
            self.date_candidates_accepted += 1
        return events

    def ingest(self, season: str) -> list[CanonicalEvent]:
        listing_template = self.settings.get("listing_source") or self.settings["official_source"]
        listing_pages: list[tuple[str, str]] = []
        result: list[CanonicalEvent] = []
        detail_urls: list[str] = []
        for listing_url in _season_month_urls(listing_template, season):
            self.requested_months.append(listing_url)
            self.listing_pages_requested.append(listing_url)
            try:
                listing_page = self._fetch(listing_url)
            except Exception as exc:
                self.failed_months.append(listing_url)
                self.listing_pages_failed.append(listing_url)
                self.last_errors.append({"url": listing_url, "error": f"{type(exc).__name__}: {exc}"})
                continue
            self.successful_months.append(listing_url)
            self.listing_pages_successful.append(listing_url)
            self.source_pages[listing_url] = listing_url
            listing_pages.append((listing_page, listing_url))
            listing_events = self._event_rows(listing_page, listing_url, season)
            result.extend(listing_events)
            detail_urls.extend(url for url in self._detail_urls(listing_page, listing_url) if url not in detail_urls)
            prefixes = tuple(self.settings.get("detail_path_prefixes", []))
            for event in listing_events:
                if event.source_url != listing_url and (not prefixes or any(prefix in event.source_url for prefix in prefixes)) and event.source_url not in detail_urls:
                    detail_urls.append(event.source_url)
            for api_page_url in _api_page_urls(listing_page, listing_url):
                self.listing_pages_requested.append(api_page_url)
                try:
                    api_page = self._fetch(api_page_url)
                    self.successful_months.append(api_page_url)
                    self.listing_pages_successful.append(api_page_url)
                    self.source_pages[api_page_url] = api_page_url
                    listing_pages.append((api_page, api_page_url))
                    result.extend(self._event_rows(api_page, api_page_url, season))
                except Exception as exc:
                    self.failed_months.append(api_page_url)
                    self.listing_pages_failed.append(api_page_url)
                    self.last_errors.append({"url": api_page_url, "error": f"{type(exc).__name__}: {exc}"})
        for source_page, source_page_url in listing_pages:
            api_documents, _ = _official_event_overview(source_page, source_page_url)
            for document in api_documents:
                detail_url = document.get("_official_detail_url")
                if isinstance(detail_url, str) and detail_url and detail_url not in detail_urls:
                    detail_urls.append(detail_url)
        max_detail_pages = self.settings.get("max_detail_pages")
        if isinstance(max_detail_pages, int) and max_detail_pages >= 0:
            detail_urls = detail_urls[:max_detail_pages]
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
                self.source_duplicates_collapsed += 1
            unique[event.event_key] = event
        # Listing endpoints and production pages can assign different source
        # IDs to the same literal occurrence. Collapse an exact performance
        # slot and prefer a richer detail-page record.
        slots: dict[tuple[str, str, str, str], CanonicalEvent] = {}
        for event in unique.values():
            slot = (
                event.venue.casefold(),
                re.sub(r"\s+", " ", event.title).strip().casefold(),
                event.date,
                event.start_time or "",
            )
            current = slots.get(slot)
            if current is None:
                slots[slot] = event
                continue
            self.source_duplicates_collapsed += 1
            event_score = (
                int("/api/" not in event.source_url),
                len(event.programme) + len(event.credits),
                int(bool(event.room)),
                len(event.source_url),
            )
            current_score = (
                int("/api/" not in current.source_url),
                len(current.programme) + len(current.credits),
                int(bool(current.room)),
                len(current.source_url),
            )
            if event_score > current_score:
                preferred, fallback = event, current
            else:
                preferred, fallback = current, event
            # Detail pages usually carry the cast and the best canonical URL,
            # while listing APIs carry the venue's authoritative category
            # tags.  Preserve both when they describe the same literal slot.
            preferred_raw = dict(preferred.raw)
            preferred_tags = list(preferred_raw.get("official_tags") or [])
            fallback_tags = list((fallback.raw or {}).get("official_tags") or [])
            preferred_raw["official_tags"] = list(dict.fromkeys(preferred_tags + fallback_tags))
            preferred_type = preferred.event_type
            if preferred_type in {"", "performance", "unclassified_performance"} and fallback.event_type not in {
                "", "performance", "unclassified_performance",
            }:
                preferred_type = fallback.event_type
            slots[slot] = replace(
                preferred,
                event_type=preferred_type,
                classification=preferred_type,
                raw=preferred_raw,
            )
        return sorted(slots.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))
