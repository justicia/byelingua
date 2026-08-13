"""Enrich Auditorio Nacional events from their existing official detail URLs.

The venue uses several promoter-specific layouts.  This adapter deliberately
works only with event_sources already attached to ``auditorio_nacional`` and
only accepts official Auditorio programme URLs.  It is idempotent: entities
and relations are looked up before insertion, and existing relations are kept.
"""
from __future__ import annotations

import argparse
import re
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from api.index import supabase_service


SOURCE = "auditorio_nacional"
OFFICIAL_PREFIX = "https://auditorionacional.inaem.gob.es/es/programacion/"

ROLE_WORDS = {
    "acordeon", "actor", "actriz", "arpa", "artist", "artista", "bajo",
    "baritono", "bateria", "cantaor", "cantaora", "cantante", "canto",
    "clarinete", "clave", "concertino", "contralto", "contrabajo", "coro",
    "direccion", "director", "directora", "ensemble", "fagot", "flauta",
    "guitarra", "laud", "mezzosoprano", "narrador", "narradora", "oboe",
    "orchestra", "orquesta", "organo", "percusion", "piano", "saxofon",
    "solista", "soprano", "tenor", "tenores", "tiorba", "trombon",
    "trompa", "trompeta", "violines", "viola", "violin", "violonchelo",
    "voz", "voces", "director musical", "direccion musical",
}
PROGRAMME_MARKERS = {
    "programa", "programme", "programa:", "programme:", "obras",
    "repertorio", "1a parte", "1ª parte", "primera parte",
}
NON_WORK_LINES = {
    "i", "ii", "iii", "iv", "v", "vi", "vii", "intervalo", "pausa",
    "------pausa-----", "segunda parte", "2a parte", "2ª parte",
}
COMPOSER_HINTS = {
    "bach", "barber", "beethoven", "berlioz", "bizet", "brahms", "bruckner",
    "charpentier", "chopin", "debussy", "donizetti", "dvorak", "dvořák",
    "falla", "faure", "fauré", "gershwin", "handel", "händel", "haydn",
    "holst", "honneger", "janacek", "janácek", "mahler", "mendelssohn",
    "messiaen", "monteverdi", "mozart", "prokofiev", "puccini", "purcell",
    "rachmaninov", "rajmaninov", "ravel", "respighi", "rodrigo", "rossini",
    "saint-saens", "saint-saëns", "satie", "schoenberg", "schubert",
    "schumann", "shostakovich", "shostakóvich", "sibelius", "strauss",
    "stravinsky", "tchaikovsky", "chaikovski", "tchaikovsky", "tchaikovsky",
    "tchaikovski", "chaikovsky", "verdi", "vivaldi", "wagner", "walton",
}


def fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in value if not unicodedata.combining(ch)).casefold().strip()


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" \t\r\n|;")


def is_role(value: str) -> bool:
    text = fold(value).strip(" .:")
    return text in ROLE_WORDS or any(text.startswith(x + " ") for x in ROLE_WORDS)


def is_marker(value: str) -> bool:
    return fold(value).strip(" .:") in {fold(x).strip(" .:") for x in PROGRAMME_MARKERS}


def is_composer(value: str) -> bool:
    text = fold(value)
    if re.search(r"\((?:ca\.\s*)?\d{3,4}\s*[-–]\s*(?:ca\.\s*)?\d{3,4}\)", text):
        return True
    words = set(re.findall(r"[a-zà-ÿ]+", text))
    return bool(words & {fold(x) for x in COMPOSER_HINTS}) and not is_role(value)


def looks_like_artist(value: str) -> bool:
    text = fold(value)
    if is_role(value) or is_composer(value) or is_marker(value):
        return False
    group_words = {
        "academia", "band", "cantoria", "choir", "coro", "ensemble",
        "filarmonica", "filarmonia", "grupo", "la fortuna", "orchestra",
        "orquesta", "quartet", "quinteto", "sociedad coral", "sinfonica",
        "trio", "cuarteto",
    }
    if any(word in text for word in group_words):
        return True
    if any(text.endswith(" " + fold(role)) for role in ROLE_WORDS):
        return True
    if re.match(r"^.{2,}?\s*[,·]\s*.{2,}$", value):
        return True
    words = re.findall(r"[A-Za-zÀ-ÿ'’.-]+", value)
    return 2 <= len(words) <= 6 and not any(ch in value for ch in ('"', "“", "”", "«", "»", ":"))


def looks_like_person_name(value: str) -> bool:
    if any(ch in value for ch in (",", ":", "·", "—", "–", '"', "“", "»", "«")):
        return False
    words = re.findall(r"[A-Za-zÀ-ÿ'’.-]+", value)
    if not 1 <= len(words) <= 6:
        return False
    connectors = {"da", "de", "del", "di", "do", "dos", "la", "van", "von", "y"}
    return all(fold(word).strip(".") in connectors or word[0].isupper() for word in words)


def explicit_work(value: str) -> tuple[str | None, str] | None:
    value = clean(value)
    # Composer and work printed on one line: "BRAHMS Concierto...",
    # "Beethoven, Sinfonía...", "Händel · El Mesías".
    match = re.match(r"^([^,·:—–]{2,50})\s*[,·:—–]\s*(.{3,})$", value)
    if match and is_composer(match.group(1)):
        return clean(match.group(1)), clean(match.group(2))
    first, sep, rest = value.partition(" ")
    if sep and fold(first) in {fold(x) for x in COMPOSER_HINTS} and len(rest) > 3:
        return first, clean(rest)
    # Work followed by abbreviated composer in parentheses.
    match = re.match(r"^(.{3,}?)\s*\(([A-ZÁÉÍÓÚÜÑ][^()]*)\)$", value)
    if match and not re.search(r"\d", match.group(2)):
        return clean(match.group(2)), clean(match.group(1))
    return None


@dataclass
class ParsedPage:
    url: str
    artists: list[dict]
    programme: list[dict]
    error: str | None = None


def split_content(blocks: list[list[str]]) -> tuple[list[str], list[str]]:
    blocks = [[clean(x) for x in block if clean(x)] for block in blocks]
    blocks = [block for block in blocks if block]
    if not blocks:
        return [], []
    lines = [line for block in blocks for line in block]

    for index, line in enumerate(lines):
        if is_marker(line):
            return lines[:index], lines[index + 1 :]

    # Multiple meaningful h4 blocks normally separate cast and repertoire.
    if len(blocks) >= 2:
        return blocks[0], [line for block in blocks[1:] for line in block]

    # In mixed blocks, the first composer or explicit composer/work line starts
    # the programme.  This covers OCNE, ORCAM, Excelentia and La Filarmónica.
    for index, line in enumerate(lines):
        if explicit_work(line) or is_composer(line):
            if index:
                return lines[:index], lines[index:]

    # Film and popular programmes print a quoted show title after the ensemble
    # and conductor.  Keep it as programme text rather than an artist.
    for index, line in enumerate(lines):
        if index >= 1 and (line.startswith(('"', "“", "«")) or fold(line).startswith("bandas sonoras")):
            return lines[:index], lines[index:]
    return lines, []


def parse_artists(lines: Iterable[str]) -> list[dict]:
    result: list[dict] = []
    pending: list[int] = []
    for raw in lines:
        value = clean(raw)
        if not value or is_marker(value):
            continue
        if is_role(value):
            targets = pending or ([len(result) - 1] if result else [])
            for index in targets:
                if not result[index]["role"]:
                    result[index]["role"] = value
            pending = []
            continue
        match = re.match(r"^(.{2,}?)\s*[,·]\s*(.{2,})$", value)
        role = None
        name = value
        if match and (is_role(match.group(2)) or any(fold(match.group(2)).startswith(fold(x)) for x in ROLE_WORDS)):
            name, role = clean(match.group(1)), clean(match.group(2))
        elif ":" in value:
            left, right = [clean(x) for x in value.split(":", 1)]
            if is_role(left):
                name, role = right, left
        if role is None:
            group_roles = {"artist", "artista", "coro", "ensemble", "orchestra", "orquesta"}
            for candidate in sorted(ROLE_WORDS - group_roles, key=len, reverse=True):
                normalized = fold(candidate)
                if fold(value).endswith(" " + normalized):
                    count = len(candidate.split())
                    parts = value.split()
                    name, role = " ".join(parts[:-count]), " ".join(parts[-count:])
                    break
        if not looks_like_artist(value):
            continue
        if len(name) < 2 or fold(name) in {"solistas", "musicos", "artistas"}:
            continue
        result.append({"artist_name": name, "role": role or "performer"})
        if role is None:
            pending.append(len(result) - 1)
        else:
            pending = []
    deduped = []
    seen = set()
    for item in result:
        key = (fold(item["artist_name"]), fold(item["role"]))
        if key not in seen:
            seen.add(key); deduped.append(item)
    return deduped


def parse_programme(lines: Iterable[str]) -> list[dict]:
    result: list[dict] = []
    composer: str | None = None
    values = [clean(raw) for raw in lines if clean(raw)]
    for index, raw in enumerate(values):
        value = clean(raw)
        normalized = fold(value).strip(" .:")
        if not value or is_marker(value) or normalized in NON_WORK_LINES:
            continue
        pair = explicit_work(value)
        if pair:
            composer, title = pair
            result.append({"composer": composer, "work_title": title})
            continue
        if is_composer(value):
            composer = re.sub(r"\s*\((?:ca\.\s*)?\d{3,4}.*?\)\s*$", "", value).strip()
            continue
        next_value = values[index + 1] if index + 1 < len(values) else ""
        if looks_like_person_name(value) and next_value and not (
            is_composer(next_value) or explicit_work(next_value) or is_marker(next_value)
        ):
            composer = value
            continue
        if value.startswith("*") or normalized.startswith(("estreno absoluto", "obra encargo", "concierto en colaboracion")):
            continue
        # Movement-only labels remain attached to their parent work and are not
        # promoted to standalone canonical works.
        if re.match(r"^(?:[IVXLCDM]+|\d+)[.)]\s", value, re.I):
            continue
        result.append({"composer": composer, "work_title": value})
    deduped = []
    seen = set()
    for item in result:
        key = (fold(item.get("composer") or ""), fold(item["work_title"]))
        if key not in seen and len(item["work_title"]) >= 3:
            seen.add(key); deduped.append(item)
    return deduped


def fetch_page(url: str) -> ParsedPage:
    if not url.startswith(OFFICIAL_PREFIX):
        return ParsedPage(url, [], [], "non-official or non-programme URL")
    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "Byelingua venue enrichment/1.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.select_one(".content")
        if not content:
            return ParsedPage(url, [], [], "missing content container")
        blocks = [[clean(x) for x in heading.stripped_strings] for heading in content.find_all("h4")]
        artist_lines, programme_lines = split_content(blocks)
        return ParsedPage(url, parse_artists(artist_lines), parse_programme(programme_lines))
    except Exception as exc:  # source failure is quarantined, not guessed
        return ParsedPage(url, [], [], str(exc))


def batched(values: list[str], size: int = 50):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def load_all(path: str, select: str, page_size: int = 1000):
    rows = []
    offset = 0
    while True:
        page = supabase_service("GET", path, params={
            "select": select, "limit": str(page_size), "offset": str(offset)
        }) or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def load_events():
    catalog = supabase_service("GET", "/rest/v1/event_catalog_v1", params={
        "select": "event_id,title,source_url", "source": f"eq.{SOURCE}", "limit": "1000"
    }) or []
    events = supabase_service("GET", "/rest/v1/events", params={
        "select": "id,event_key", "event_key": f"like.{SOURCE}:*", "limit": "1000"
    }) or []
    key_to_id = {row["event_key"]: row["id"] for row in events}
    by_url = defaultdict(list)
    for row in catalog:
        if row.get("source_url") and key_to_id.get(row["event_id"]):
            by_url[row["source_url"]].append(key_to_id[row["event_id"]])
    return by_url


def relation_sets(event_ids: list[str]):
    programme, credits = set(), set()
    max_order = defaultdict(int)
    for group in batched(event_ids):
        ids = ",".join(group)
        for row in supabase_service("GET", "/rest/v1/event_programme", params={
            "select": "event_id,work_id,order", "event_id": f"in.({ids})", "limit": "5000"
        }) or []:
            programme.add((row["event_id"], row["work_id"]))
            max_order[row["event_id"]] = max(max_order[row["event_id"]], row.get("order") or 0)
        for row in supabase_service("GET", "/rest/v1/event_credits", params={
            "select": "event_id,artist_id,role", "event_id": f"in.({ids})", "limit": "5000"
        }) or []:
            credits.add((row["event_id"], row["artist_id"], fold(row.get("role") or "")))
    return programme, credits, max_order


def find_or_create_work(item: dict, dry_run: bool, cache: dict):
    key = (fold(item.get("composer") or ""), fold(item["work_title"]))
    if key in cache:
        return cache[key]
    if dry_run:
        cache[key] = f"dry-work:{len(cache)}"; return cache[key]
    created = supabase_service("POST", "/rest/v1/works", payload={
        "title": item["work_title"], "composer": item.get("composer")
    }, prefer="return=representation") or []
    if created:
        cache[key] = created[0]["id"]; return cache[key]
    return None


def find_or_create_artist(item: dict, dry_run: bool, cache: dict):
    key = fold(item["artist_name"])
    if key in cache:
        return cache[key]
    if dry_run:
        cache[key] = f"dry-artist:{len(cache)}"; return cache[key]
    created = supabase_service("POST", "/rest/v1/artists", payload={
        "artist_name": item["artist_name"]
    }, prefer="return=representation") or []
    if created:
        cache[key] = created[0]["id"]; return cache[key]
    return None


def prepare_entities(parsed: list[ParsedPage], dry_run: bool, work_cache: dict, artist_cache: dict):
    missing_works = {}
    missing_artists = {}
    for page in parsed:
        for item in page.programme:
            key = (fold(item.get("composer") or ""), fold(item["work_title"]))
            if key not in work_cache:
                missing_works.setdefault(key, item)
        for item in page.artists:
            key = fold(item["artist_name"])
            if key not in artist_cache:
                missing_artists.setdefault(key, item)
    if dry_run:
        for key in missing_works:
            work_cache[key] = f"dry-work:{len(work_cache)}"
        for key in missing_artists:
            artist_cache[key] = f"dry-artist:{len(artist_cache)}"
        return
    for group in batched(list(missing_works.values()), 150):
        payload = [{"title": item["work_title"], "composer": item.get("composer")} for item in group]
        for row in supabase_service("POST", "/rest/v1/works", payload=payload, prefer="return=representation") or []:
            work_cache[(fold(row.get("composer") or ""), fold(row["title"]))] = row["id"]
    for group in batched(list(missing_artists.values()), 150):
        payload = [{"artist_name": item["artist_name"]} for item in group]
        for row in supabase_service("POST", "/rest/v1/artists", payload=payload, prefer="return=representation") or []:
            artist_cache[fold(row["artist_name"])] = row["id"]


def run(*, dry_run: bool = True, workers: int = 8):
    by_url = load_events()
    parsed = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(fetch_page, url) for url in by_url]
        for future in as_completed(futures):
            parsed.append(future.result())
    event_ids = sorted({event_id for ids in by_url.values() for event_id in ids})
    existing_programme, existing_credits, max_order = relation_sets(event_ids)
    work_cache = {
        (fold(row.get("composer") or ""), fold(row["title"])): row["id"]
        for row in load_all("/rest/v1/works", "id,title,composer")
        if row.get("title")
    }
    artist_cache = {
        fold(row["artist_name"]): row["id"]
        for row in load_all("/rest/v1/artists", "id,artist_name")
        if row.get("artist_name")
    }
    prepare_entities(parsed, dry_run, work_cache, artist_cache)
    programme_rows, credit_rows = [], []
    errors = []
    for page in parsed:
        if page.error:
            errors.append({"url": page.url, "error": page.error}); continue
        for event_id in by_url[page.url]:
            next_order = max_order[event_id] + 1
            for item in page.programme:
                work_id = find_or_create_work(item, dry_run, work_cache)
                if work_id and (event_id, work_id) not in existing_programme:
                    programme_rows.append({"event_id": event_id, "work_id": work_id, "order": next_order})
                    existing_programme.add((event_id, work_id))
                    next_order += 1
            max_order[event_id] = next_order - 1
            for item in page.artists:
                artist_id = find_or_create_artist(item, dry_run, artist_cache)
                key = (event_id, artist_id, fold(item["role"]))
                if artist_id and key not in existing_credits:
                    credit_rows.append({"event_id": event_id, "artist_id": artist_id, "role": item["role"]})
                    existing_credits.add(key)
    if not dry_run:
        for group in batched(programme_rows, 250):
            supabase_service("POST", "/rest/v1/event_programme", payload=group, prefer="return=minimal")
        for group in batched(credit_rows, 250):
            supabase_service("POST", "/rest/v1/event_credits", payload=group, prefer="return=minimal")
    summary = {
        "dry_run": dry_run, "events": len(event_ids), "source_urls": len(by_url),
        "pages_with_programme": sum(bool(x.programme) for x in parsed),
        "pages_with_artists": sum(bool(x.artists) for x in parsed),
        "programme_relations_to_add": len(programme_rows),
        "credit_relations_to_add": len(credit_rows), "quarantined_pages": len(errors),
    }
    print(summary)
    if errors:
        print("Quarantine:")
        for item in errors:
            print("-", item["url"], "=>", item["error"])
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write idempotent relations to Supabase")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    run(dry_run=not args.apply, workers=args.workers)


if __name__ == "__main__":
    main()
