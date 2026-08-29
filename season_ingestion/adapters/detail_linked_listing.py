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

from season_ingestion.credit_resolution import canonical_role
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
SCALA_TEAM_ROLES = {
    "conductor": "conductor",
    "staging": "stage_director",
    "stage direction": "stage_director",
    "sets": "set_designer",
    "costumes": "costume_designer",
    "sets and costumes": "production_designer",
    "lights": "lighting_designer",
    "lighting": "lighting_designer",
    "dramaturgy": "dramaturg",
    "choreography": "choreographer",
    "choreography and staging": "choreographer",
    "staging and choreography": "stage_director",
    "staging and sets": "stage_director",
    "staging and lyrics": "stage_director",
    "concept and staging": "stage_director",
    "costumes and lights": "production_designer",
    "music and sound design": "sound_designer",
    "chorus master": "chorus_master",
    "chorus conductor": "chorus_master",
    "musical dramaturgy": "dramaturg",
    "projections": "video_designer",
    "illustrations": "visual_designer",
    "revived by": "stage_director",
    "video": "video_designer",
}
SCALA_PERFORMER_LABELS = {
    "violin", "viola", "cello", "double bass", "bass", "piano", "flute", "oboe", "clarinet", "bassoon", "horn", "guitar",
    "soprano", "mezzo-soprano", "tenor", "baritone", "soprano and cello", "soprano and violin", "tenor and piano",
    "tenor and viola", "tenor and violin",
}
SCALA_NON_CREDIT_LABELS = {"music", "after", "© the george balanchine trust"}
SCALA_MONTHS = {name.casefold()[:3]: index for index, name in enumerate(month_name) if name}


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


GENERIC_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "ene": 1, "abr": 4, "ago": 8, "dic": 12, "janv": 1, "févr": 2,
    "avr": 4, "juil": 7, "sept": 9, "oct": 10, "déc": 12,
}


def _role_from_label(value: str) -> str | None:
    normalized = " ".join(value.casefold().strip().split())
    direct = next((role for label, role in ROLE_LABELS.items() if normalized == label or normalized.startswith(f"{label}:") or normalized.startswith(f"{label} -")), None)
    return direct or canonical_role(value)


def _split_credit_values(value: str, *, split_commas: bool = False) -> list[str]:
    separators = r"\s*(?:/|;|\n|•|·)\s*"
    values = [item.strip(" -–—:•·\u00a0") for item in re.split(separators, value or "") if item.strip()]
    if split_commas:
        values = [part.strip() for value in values for part in re.split(r"\s*,\s*", value) if part.strip()]
    return values


def _generic_assignment_applies(raw: str, event_date: str | None) -> tuple[str, bool]:
    annotations = re.findall(r"\(([^()]*)\)", raw or "")
    artist = re.sub(r"\s*\([^()]*\)\s*$", "", raw or "").strip(" /,\u00a0")
    if not annotations or not event_date:
        return artist, True
    annotation = annotations[-1]
    event = date.fromisoformat(event_date)
    explicit_dates = set()
    for value in re.findall(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", annotation):
        parts = re.split(r"[-/.]", value)
        explicit_dates.add((int(parts[0]), int(parts[1]), int(parts[2])))
    if explicit_dates:
        return artist, (event.year, event.month, event.day) in explicit_dates
    months = set()
    for token in re.findall(r"[A-Za-zÀ-ÿ]{3,9}", annotation):
        folded = token.casefold()
        month = GENERIC_MONTHS.get(folded[:4]) or GENERIC_MONTHS.get(folded[:3])
        if month:
            months.add(month)
    days = {int(value) for value in re.findall(r"(?<!\d)([0-3]?\d)(?!\d)", annotation) if 1 <= int(value) <= 31}
    return artist, (not months or event.month in months) and (not days or event.day in days)


def _credit_payload(artist: str, label: str, role: str, kind: str, page_url: str, field: str, *, character: str | None = None, raw_block: str | None = None) -> dict[str, Any]:
    payload = {
        "artist_name": artist,
        "source_role": label,
        "function": role,
        "credit_kind": kind,
        "source_url": page_url,
        "source_field": field,
        "raw_source_block": raw_block or artist,
        "provenance": {"source_url": page_url, "source_field": field},
    }
    if character:
        payload["character"] = character
        payload["raw_character"] = character
    return payload


def _credits(detail: BeautifulSoup, page_url: str, event_date: str | None = None) -> list[dict[str, Any]]:
    """Extract structured cast/team rows without relying on venue names.

    A table header or definition-list label is a team role.  A two-cell row
    whose first cell is marked ``dt`` (the common cast layout) is a character
    assignment.  The detail page is fetched once and reused for every
    occurrence; parenthetical dates narrow only the matching occurrence.
    """
    rows: list[dict[str, Any]] = []

    def add(payload: dict[str, Any]) -> None:
        key = (payload["artist_name"].casefold(), payload["function"], str(payload.get("character") or "").casefold())
        if payload["artist_name"].strip() and not any((row["artist_name"].casefold(), row["function"], str(row.get("character") or "").casefold()) == key for row in rows):
            rows.append(payload)

    for table in detail.select("table"):
        for row in table.select("tr"):
            cells = row.find_all(["th", "td"], recursive=False) or row.select("th, td")
            if len(cells) < 2:
                continue
            header = row.find("th")
            label_node = header or row.select_one("td.dt") or cells[0]
            label = _text(label_node)
            value = _text(cells[1])
            if not label or not value:
                continue
            cast_row = header is None and bool(row.select_one("td.dt"))
            if cast_row:
                for assignment in _split_credit_values(value):
                    artist, applies = _generic_assignment_applies(assignment, event_date)
                    if applies and artist:
                        add(_credit_payload(artist, label, "performer", "cast", page_url, "detail.cast.table", character=label, raw_block=value))
                continue
            role = _role_from_label(label)
            if not role:
                continue
            kind = "ensemble" if role in {"orchestra", "choir", "chorus", "ensemble"} else "artistic_team"
            for artist in _split_credit_values(value, split_commas=kind == "ensemble"):
                add(_credit_payload(artist, label, role, kind, page_url, "detail.team.table", raw_block=value))

    for node in detail.select("dt"):
        label = _text(node)
        role = _role_from_label(label)
        sibling = node.find_next_sibling()
        value = _text(sibling)
        if not role or not value:
            continue
        kind = "ensemble" if role in {"orchestra", "choir", "chorus", "ensemble"} else "artistic_team"
        for artist in _split_credit_values(value, split_commas=kind == "ensemble"):
            add(_credit_payload(artist, label, role, kind, page_url, "detail.credit.definition_list", raw_block=value))

    for node in detail.select(".credit, [data-role='credit'], .artists"):
        text = _text(node)
        if not text:
            continue
        match = re.match(r"^(.+?)\s*[:\-–—]\s*(.+)$", text)
        label, value = (match.group(1).strip(), match.group(2).strip()) if match else (text, _text(node.find_next_sibling()))
        role = _role_from_label(label)
        if not role or not value:
            continue
        kind = "ensemble" if role in {"orchestra", "choir", "chorus", "ensemble"} else "artistic_team"
        for artist in _split_credit_values(value, split_commas=kind == "ensemble"):
            add(_credit_payload(artist, label, role, kind, page_url, "detail.credit", raw_block=text))
    return rows


def _scala_assignment_applies(raw: str, event_date: str) -> tuple[str, bool]:
    annotations = re.findall(r"\(([^()]*)\)", raw)
    artist = re.sub(r"\s*\([^()]*\)\s*$", "", raw).strip(" /,\u00a0")
    if not annotations:
        return artist, True
    annotation = annotations[-1]
    event = date.fromisoformat(event_date)
    mentioned_months = {
        SCALA_MONTHS[token.casefold()[:3]]
        for token in re.findall(r"[A-Za-z]{3,9}", annotation)
        if token.casefold()[:3] in SCALA_MONTHS
    }
    days = {int(value) for value in re.findall(r"(?<!\d)([0-3]?\d)(?!\d)", annotation) if 1 <= int(value) <= 31}
    month_matches = not mentioned_months or event.month in mentioned_months
    return artist, month_matches and (not days or event.day in days)


def _scala_credits(detail: BeautifulSoup, page_url: str, event_date: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    billing_order = 1
    for table in detail.select("table"):
        for row in table.select("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            label = _text(row.find("th") or row.select_one("td.dt") or (cells[0] if cells else None))
            value = _text(cells[1]) if len(cells) > 1 else ""
            if not label or not value:
                continue
            is_cast_row = bool(row.select_one("td.dt")) and not row.find("th")
            if is_cast_row:
                for assignment in re.split(r"\s+/\s+", value):
                    artist, applies = _scala_assignment_applies(assignment, event_date)
                    if artist and applies:
                        rows.append({
                            "artist_name": artist,
                            "source_role": label,
                            "function": "performer",
                            "character": label,
                            "credit_kind": "cast",
                            "billing_order": billing_order,
                            "source_url": page_url,
                            "source_field": "detail.cast.table",
                            "raw_source_block": value,
                            "provenance": {"source_url": page_url, "source_field": "detail.cast.table"},
                        })
                        billing_order += 1
                continue
            normalized_label = label.casefold()
            canonical_role = SCALA_TEAM_ROLES.get(normalized_label)
            credit_kind = "artistic_team"
            if normalized_label in SCALA_PERFORMER_LABELS:
                canonical_role = "performer"
                credit_kind = "cast"
            if normalized_label in SCALA_NON_CREDIT_LABELS:
                canonical_role = None
            if not canonical_role:
                continue
            for artist in (item.strip() for item in re.split(r"\s*(?:/|,)\s*", value)):
                if artist:
                    rows.append({
                        "artist_name": artist,
                        "source_role": label,
                        "function": canonical_role,
                        "credit_kind": credit_kind,
                        "billing_order": billing_order,
                        "source_url": page_url,
                        "source_field": "detail.team.table",
                        "raw_source_block": value,
                        "provenance": {"source_url": page_url, "source_field": "detail.team.table"},
                    })
                    billing_order += 1
    page_text = _text(detail)
    ensemble_candidates = []
    if re.search(r"(?:Teatro alla Scala Orchestra|Orchestra (?:and Chorus )?of Teatro alla Scala)", page_text, re.I):
        ensemble_candidates.append(("Teatro alla Scala Orchestra", "orchestra"))
    if re.search(r"(?:Teatro alla Scala (?:Orchestra and )?Chorus|Chorus of Teatro alla Scala)", page_text, re.I):
        ensemble_candidates.append(("Teatro alla Scala Chorus", "choir"))
    if re.search(r"Teatro alla Scala Ballet Company", page_text, re.I):
        ensemble_candidates.append(("Teatro alla Scala Ballet Company", "ensemble"))
    for artist, role in ensemble_candidates:
        rows.append({
            "artist_name": artist,
            "source_role": artist,
            "function": role,
            "credit_kind": "ensemble",
            "billing_order": billing_order,
            "source_url": page_url,
            "source_field": "detail.production.summary",
            "raw_source_block": artist,
            "provenance": {"source_url": page_url, "source_field": "detail.production.summary"},
        })
        billing_order += 1
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["artist_name"].casefold(), row["function"], str(row.get("character") or "").casefold())
        unique.setdefault(key, row)
    return list(unique.values())


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
        events: list[CanonicalEvent] = []
        for event_date, start_time in unique:
            credits = _scala_credits(soup, page_url, event_date) if self.settings.get("detail_profile") == "teatro_alla_scala" else _credits(soup, page_url, event_date)
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
