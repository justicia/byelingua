from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ingestion.schema import canonical_event_type, normalize_search_key, searchable_text, stable_event_identity, validate_event


BASE_URL = "https://www.teatroreal.es"
CALENDAR_URL = f"{BASE_URL}/es/calendario"
ORGANIZATION = "Teatro Real"
DEFAULT_VENUE = "Teatro Real"
CITY = "Madrid"

MONTHS = {"sep": 9, "oct": 10, "nov": 11, "dic": 12, "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7}

ARTISTIC_ROLE_MAP = {
    "direccion musical": "Conductor",
    "direccion de escena": "Stage Director",
    "director de escena": "Stage Director",
    "escenografia": "Sets",
    "vestuario": "Costumes",
    "iluminacion": "Lighting",
    "direccion del coro": "Chorus Master",
    "director del coro": "Chorus Master",
    "coreografia": "Choreography",
    "dramaturgia": "Dramaturgy",
    "video": "Video",
    "piano": "Piano",
    "orquesta": "Orchestra",
}

# These choices come from alternate title lines printed by the official PDF.
# If the PDF does not print an original-language title, the source display title is retained.
EXPLICIT_ORIGINAL_TITLES = {
    "las bodas de figaro": "Le nozze di Figaro",
    "el barbero de sevilla": "Il barbiere di Siviglia",
}

_ENGLISH_ROLE_STARTS = (
    "The ", "A ", "Count ", "Countess ", "Princess ", "Duke ", "King ", "Queen ",
    "Naval ", "Dancing ", "Singer ", "Innkeeper ", "Sergeant ", "Chorus ",
    "Soprano", "Countertenor", "Tenor", "Bass", "Baritone", "Mezzo-soprano",
)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ")).strip(" ,;–—")


def _smart_case(value: str) -> str:
    letters = [char for char in value if char.isalpha() and char not in "ºª"]
    if not letters or sum(char.isupper() for char in letters) / len(letters) < 0.8:
        return _clean(value)
    text = _clean(value).title()
    for token in (" A ", " De ", " Del ", " Di ", " En ", " La ", " Las ", " Los ", " Para ", " Y "):
        text = text.replace(token, token.lower())
    return text


def _original_role(raw_label: str) -> str:
    value = _clean(raw_label)
    for marker in _ENGLISH_ROLE_STARTS:
        pos = value.find(marker, 1)
        if pos > 0:
            return value[:pos].strip()
    return value


def _normalize_artistic_role(raw_label: str) -> str:
    key = normalize_search_key(raw_label)
    for source, target in ARTISTIC_ROLE_MAP.items():
        if key.startswith(source):
            return target
    return _clean(raw_label)


def _availability(raw: str, season_year: int = 2026) -> set[str]:
    result: set[str] = set()
    for segment in raw.casefold().split(";"):
        month_match = re.search(r"\b(" + "|".join(MONTHS) + r")\b", segment)
        if not month_match:
            continue
        month = MONTHS[month_match.group(1)]
        year = season_year if month >= 9 else season_year + 1
        for day_text in re.findall(r"\b([0-3]?\d)\b", segment[: month_match.start()]):
            day = int(day_text)
            if 1 <= day <= 31:
                result.add(f"{year:04d}-{month:02d}-{day:02d}")
    return result


def parse_calendar_html(html: str, *, season_start: date = date(2026, 9, 1), season_end: date = date(2027, 7, 31)) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for box in soup.select(".calendario-mensual-sidebar .item-box[id]"):
        match = re.fullmatch(r"box(\d{2})-(\d{4})-(\d{2})", box.get("id", ""))
        if not match:
            continue
        month, year, day = map(int, match.groups())
        event_date = date(year, month, day)
        if not season_start <= event_date <= season_end:
            continue
        for card in box.select(":scope > .contentbox"):
            title_node = card.select_one(".item-box--premiere__text--title h3 a[href]")
            if not title_node:
                continue
            title = _clean(title_node.get_text(" ", strip=True))
            href = title_node.get("href", "")
            category_node = card.select_one(".item-box--premiere__text--title span")
            category = _clean(category_node.get_text(" ", strip=True)) if category_node else ""
            times = []
            for node in card.select(".item-box--premiere__text--btn a"):
                candidate = _clean(node.get_text(" ", strip=True))
                if re.fullmatch(r"[0-2]\d:[0-5]\d", candidate):
                    times.append(candidate)
            for start_time in dict.fromkeys(times):
                dedupe_key = (event_date.isoformat(), start_time, urljoin(BASE_URL, href))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                row = {
                    "source": "teatro_real",
                    "source_url": urljoin(BASE_URL, href),
                    "organization": ORGANIZATION,
                    "venue": DEFAULT_VENUE,
                    "room": None,
                    "city": CITY,
                    "date": event_date.isoformat(),
                    "start_time": start_time,
                    "end_time": None,
                    "event_type": canonical_event_type(category),
                    "source_event_type": category,
                    "display_title": title,
                    "title": title,
                    "programme": [],
                    "cast": [],
                    "artistic_team": [],
                    "other_artists": [],
                    "credits": [],
                }
                row["source_event_id"] = stable_event_identity(row)
                events.append(row)
    return events


def _group_lines(words: Iterable[dict[str, Any]], tolerance: float = 1.4) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if not groups or abs(groups[-1][0]["top"] - word["top"]) > tolerance:
            groups.append([word])
        else:
            groups[-1].append(word)
    rows = []
    for group in groups:
        group.sort(key=lambda item: item["x0"])
        rows.append(
            {
                "top": min(item["top"] for item in group),
                "text": _clean(" ".join(item["text"] for item in group)),
                "fonts": {item.get("fontname", "") for item in group},
                "sizes": [float(item.get("size", 0)) for item in group],
                "demi_text": _clean(" ".join(item["text"] for item in group if "Demi" in item.get("fontname", ""))),
                "label_text": _clean(
                    " ".join(
                        item["text"] for item in group
                        if "Light" in item.get("fontname", "") or item.get("fontname", "").endswith("-Book")
                    )
                ),
            }
        )
    return rows


def _parse_credit_column(lines: list[dict[str, Any]], *, cast: bool) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    current_label: str | None = None
    current_raw_label: str | None = None
    for line in lines:
        text = line["text"]
        if not text or text in {"Reparto Cast", "Cast"}:
            continue
        fonts = " ".join(line["fonts"])
        is_person = bool(line["demi_text"])
        if any(marker in text for marker in ("Coro y Orquesta", "Orquesta Titular", "Orchestra", "Akademie für", "Kammerchor", "Symphony Orchestra")):
            continue
        inline_label = _clean(line.get("label_text", ""))
        if is_person and inline_label and inline_label not in {"_", "-"}:
            if current_label and inline_label.startswith(_ENGLISH_ROLE_STARTS):
                current_raw_label = _clean(f"{current_raw_label or current_label} / {inline_label}")
            else:
                current_label = inline_label
                current_raw_label = inline_label
        if is_person and current_label:
            person = line["demi_text"]
            if person:
                raw_role = current_raw_label or current_label
                item = {
                    "person": person,
                    "raw_role_label": raw_role,
                    "applicable_dates": sorted(_availability(text)),
                }
                if cast:
                    item.update({"role_type": "character", "character_role": _original_role(current_label), "artistic_function": None})
                else:
                    item.update({"role_type": "artistic", "character_role": None, "artistic_function": _normalize_artistic_role(raw_role)})
                result.append(item)
            continue
        if current_label and text.startswith(_ENGLISH_ROLE_STARTS):
            current_raw_label = _clean(f"{current_raw_label or current_label} / {text}")
            continue
        if "Light" in fonts or "Book" in fonts:
            current_label = text
            current_raw_label = text
    return result


def _title_metadata(words: list[dict[str, Any]]) -> tuple[str, list[str], str]:
    left = [word for word in words if word["x0"] < 280 and word["top"] < 120]
    lines = _group_lines(left)
    composer_lines = [line["text"] for line in lines if 7.8 <= max(line["sizes"], default=0) <= 8.2 and line["top"] < 70]
    composer = _smart_case(" ".join(composer_lines))
    title_lines = [line for line in lines if max(line["sizes"], default=0) >= 9.8 and line["top"] > 45]
    display_parts = [line["text"] for line in title_lines if max(line["sizes"], default=0) >= 18]
    aliases = [line["text"] for line in title_lines if max(line["sizes"], default=0) < 18]
    display_title = _smart_case(" ".join(display_parts))
    aliases = [_smart_case(alias) for alias in aliases if _clean(alias)]
    original = EXPLICIT_ORIGINAL_TITLES.get(normalize_search_key(display_title), display_title)
    return original, [display_title, *aliases, original], composer


def _additional_programme(words: list[dict[str, Any]]) -> list[dict[str, str]]:
    left = [word for word in words if word["x0"] < 225 and word["top"] > 150 and "Montserrat" in word.get("fontname", "")]
    lines = _group_lines(left)
    works: list[dict[str, str]] = []
    composer: str | None = None
    title_parts: list[str] = []
    for line in lines:
        size = max(line["sizes"], default=0)
        if 7.8 <= size <= 8.2:
            if composer and title_parts:
                works.append({"composer": _smart_case(composer), "title": _smart_case(" ".join(title_parts))})
            composer, title_parts = line["text"], []
        elif composer and 9.8 <= size <= 10.2:
            title_parts.append(line["text"])
        elif composer and title_parts and size < 9.0:
            works.append({"composer": _smart_case(composer), "title": _smart_case(" ".join(title_parts))})
            title_parts = []
    if composer and title_parts:
        works.append({"composer": _smart_case(composer), "title": _smart_case(" ".join(title_parts))})
    return works


def parse_season_pdf(pdf_path: str | Path) -> list[dict[str, Any]]:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - explicit runtime guidance
        raise RuntimeError("PDF extraction requires pdfplumber") from exc

    supplements: list[dict[str, Any]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if "Reparto Cast" not in text or not re.search(r"Música(?: y libreto)? Music", text):
                continue
            words = page.extract_words(extra_attrs=["fontname", "size"])
            original_title, aliases, composer = _title_metadata(words)
            if not original_title or not composer:
                continue
            main_work = {"composer": composer, "title": original_title}
            programme = [main_work]
            for work in _additional_programme(words):
                if normalize_search_key(work["title"]) not in {normalize_search_key(item["title"]) for item in programme}:
                    programme.append(work)

            right_lines = _group_lines(word for word in words if word["x0"] >= 290 and 90 <= word["top"] <= 410)
            middle_lines = _group_lines(word for word in words if 168 <= word["x0"] < 290 and 90 <= word["top"] <= 410)
            is_oratorio = "Oratorio en" in text and "Ópera en" not in text and "Dramma" not in text
            cast_rows = _parse_credit_column(right_lines, cast=not is_oratorio)
            team_rows = _parse_credit_column(middle_lines, cast=False)
            if is_oratorio:
                team_rows.extend(cast_rows)
                cast_rows = []
            supplements.append(
                {
                    "pdf_page": page_number,
                    "title": original_title,
                    "title_aliases": list(dict.fromkeys(aliases)),
                    "programme": programme,
                    "cast": cast_rows,
                    "artistic_team": team_rows,
                    "performance_kind": "oratorio" if is_oratorio else "opera",
                }
            )
    supplements.extend(_dance_supplements())
    return supplements


def _dance_credit(person: str, raw_role_label: str, artistic_function: str) -> dict[str, Any]:
    return {
        "person": person,
        "raw_role_label": raw_role_label,
        "applicable_dates": [],
        "role_type": "artistic",
        "character_role": None,
        "artistic_function": artistic_function,
    }


def _dance_supplements() -> list[dict[str, Any]]:
    """Production-level credits printed on the season PDF's Danza pages."""
    return [
        {
            "pdf_page": 56,
            "title": "Alvin Ailey American Dance Theater",
            "title_aliases": ["Alvin Ailey American Dance Theater"],
            "programme": [
                {"title": "Night Creature", "composer": "Duke Ellington"},
                {"title": "A Case of You", "composer": "Alice Coltrane; Laura Nyro; Chuck Griffin"},
                {"title": "Cry", "composer": "Joni Mitchell"},
                {"title": "Grace", "composer": "Various artists"},
                {"title": "Revelations", "composer": "Traditional music"},
                {"title": "Many Angels", "composer": "Gustav Mahler"},
                {"title": "Song of the Anchorite", "composer": "Maurice Ravel"},
                {"title": "A Song for You", "composer": "Leon Russell"},
            ],
            "cast": [],
            "artistic_team": [
                _dance_credit("Alvin Ailey", "Coreografía Choreography", "Choreography"),
                _dance_credit("Medhi Walerski", "Coreografía Choreography", "Choreography"),
                _dance_credit("Judith Jamison", "Coreografía Choreography", "Choreography"),
                _dance_credit("Lar Lubovitch", "Coreografía Choreography", "Choreography"),
                _dance_credit("Jamar Roberts", "Coreografía Choreography", "Choreography"),
                _dance_credit("Ronald K. Brown", "Coreografía Choreography", "Choreography"),
            ],
            "performance_kind": "dance",
        },
        {
            "pdf_page": 59,
            "title": "Compañía Nacional de Danza",
            "title_aliases": ["Compañía Nacional de Danza", "CompaÃ±Ã­a Nacional de Danza"],
            "programme": [
                {"title": "Serenade", "composer": "Piotr Ilich Chaikovski"},
                {"title": "Echoes from a Restless Soul", "composer": "Maurice Ravel"},
                {"title": "The Second Detail", "composer": "Thom Willems"},
            ],
            "cast": [],
            "artistic_team": [
                _dance_credit("George Balanchine", "Coreografía Choreography", "Choreography"),
                _dance_credit("Jacopo Godani", "Coreografía Choreography", "Choreography"),
                _dance_credit("William Forsythe", "Coreografía Choreography", "Choreography"),
                _dance_credit("Manuel Coves", "Dirección de orquesta Conductor", "Conductor"),
            ],
            "performance_kind": "dance",
        },
        {
            "pdf_page": 60,
            "title": "Tanztheater Wuppertal Pina Bausch",
            "title_aliases": ["Tanztheater Wuppertal Pina Bausch"],
            "programme": [
                {"title": "Café Müller", "composer": "Henry Purcell"},
                {"title": "La consagración de la primavera / Das Frühlingsopfer", "composer": "Ígor Stravinski"},
            ],
            "cast": [],
            "artistic_team": [
                _dance_credit("Pina Bausch", "Coreografía Choreography", "Choreography"),
                _dance_credit("Rolf Borzik", "Escenografía y vestuario Set and costume design", "Sets and Costumes"),
                _dance_credit("Henrik Schaefer", "Dirección de orquesta Conductor", "Conductor"),
            ],
            "performance_kind": "dance",
        },
    ]


def _applies(row: dict[str, Any], event_date: str) -> bool:
    dates = row.get("applicable_dates") or []
    return not dates or event_date in dates


def _preestreno_joven_work_title(title: str) -> str | None:
    match = re.fullmatch(r"Preestreno Joven\s+['‘](.+?)['’]", title)
    return _clean(match.group(1)) if match else None


def merge_sources(calendar_events: list[dict[str, Any]], supplements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_alias: dict[str, dict[str, Any]] = {}
    for supplement in supplements:
        for alias in supplement.get("title_aliases", []):
            by_alias[normalize_search_key(alias)] = supplement
    normalized: list[dict[str, Any]] = []
    for source_event in calendar_events:
        event = dict(source_event)
        supplement = None
        is_preestreno_joven = False
        if event["event_type"] in {"opera", "dance"} and "#actividadesCulturales" not in event["source_url"]:
            supplement = by_alias.get(normalize_search_key(event["display_title"]))
            if supplement is None:
                work_title = _preestreno_joven_work_title(event["display_title"])
                if work_title:
                    supplement = by_alias.get(normalize_search_key(work_title))
                    is_preestreno_joven = supplement is not None
        if supplement:
            event["title"] = supplement["title"]
            event["programme"] = supplement["programme"]
            event["cast"] = [] if is_preestreno_joven else [
                dict(row) for row in supplement["cast"] if _applies(row, event["date"])
            ]
            event["artistic_team"] = [dict(row) for row in supplement["artistic_team"] if _applies(row, event["date"])]
            if supplement["performance_kind"] == "opera":
                event["event_type"] = "opera"
            event["source_provenance"] = {"calendar": CALENDAR_URL, "season_pdf_page": supplement["pdf_page"]}
        else:
            event["source_provenance"] = {"calendar": CALENDAR_URL}
        event["credits"] = [*event["cast"], *event["artistic_team"], *event["other_artists"]]
        event["search_key"] = searchable_text(event)
        event["source_event_id"] = stable_event_identity(event)
        validate_event(event)
        normalized.append(event)
    return normalized


def build_preview(calendar_html: str, pdf_path: str | Path) -> dict[str, Any]:
    events = merge_sources(parse_calendar_html(calendar_html), parse_season_pdf(pdf_path))
    return {
        "source": "teatro_real",
        "season": "2026-27",
        "events": events,
        "audit": {
            "event_count": len(events),
            "opera_count": sum(event["event_type"] == "opera" for event in events),
            "events_with_programme": sum(bool(event["programme"]) for event in events),
            "events_with_cast": sum(bool(event["cast"]) for event in events),
            "events_with_artistic_team": sum(bool(event["artistic_team"]) for event in events),
            "duplicate_source_event_ids": len(events) - len({event["source_event_id"] for event in events}),
        },
    }
