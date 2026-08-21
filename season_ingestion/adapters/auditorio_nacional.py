"""Read-only raw parser for the Auditorio Nacional programme site.

This module intentionally stops at source material.  It does not classify
programme structure, resolve entities, or write to a database.  In particular,
each discovery row is an occurrence even when its detail URL is shared.
"""
from __future__ import annotations

import re
import warnings
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable, Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


SOURCE = "auditorio_nacional"
BASE_URL = "https://auditorionacional.inaem.gob.es"
DISCOVERY_URL = f"{BASE_URL}/es/programacion"
PAGE_SIZE = 12
USER_AGENT = "ByelinguaAuditorioParser/1.0 (read-only dry run)"


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def node_text(node: Tag | None) -> str:
    return clean(node.get_text(" ", strip=True)) if node else ""


def _lines(node: Tag) -> list[str]:
    """Return source lines in DOM order, using only whitespace cleanup."""
    lines: list[str] = []
    for part in node.stripped_strings:
        value = clean(str(part))
        if value:
            lines.append(value)
    return lines


def page_url(offset: int) -> str:
    return f"{DISCOVERY_URL}?b_start:int={offset}"


def parse_discovery_page(html: str, discovery_url: str, *, offset: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for row_index, card in enumerate(soup.select("article.eventitem")):
        title_node = card.select_one(".eventitem__title a[href]")
        date_node = card.select_one(".event-date .weekday")
        if not title_node or not date_node:
            continue
        href = clean(title_node.get("href"))
        raw_datetime = clean(date_node.get_text(" ", strip=True))
        if not href or not raw_datetime:
            continue
        rows.append({
            "source": SOURCE,
            "source_url": urljoin(BASE_URL, href),
            "discovery_url": discovery_url,
            "raw_title": node_text(title_node),
            "raw_datetime": raw_datetime,
            "raw_venue": node_text(card.select_one(".eventitem__text .location span")) or None,
            "discovery_order": offset + row_index,
            "source_occurrence": {
                "discovery_page_offset": offset,
                "discovery_row_index": row_index,
                "discovery_page_size": PAGE_SIZE,
            },
        })
    return rows


def parse_detail_page(html: str, detail_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = node_text(soup.select_one("#portal-content article#content h1"))
    content = soup.select_one("#portal-content article#content .content")
    blocks: list[dict] = []
    if content:
        for order, heading in enumerate(content.find_all("h4")):
            lines = _lines(heading)
            if not lines:
                continue
            blocks.append({
                "order": order,
                "tag": "h4",
                "raw_text": "\n".join(lines),
                "raw_lines": lines,
            })

    info: list[dict] = []
    for item in soup.select("#portal-content article#content .rightColumn__item"):
        label = node_text(item.select_one(".rightColumn__item__label"))
        value_node = item.select_one(".rightColumn__item__text")
        value_lines = _lines(value_node) if value_node else []
        if label or value_lines:
            info.append({"raw_label": label, "raw_lines": value_lines,
                         "raw_text": "\n".join(value_lines)})

    # The site's current layout uses separate h4 blocks for credits and
    # programme.  Keep the split positional and transparent; this is not
    # semantic structure classification.  raw_content_blocks remains the
    # authoritative source for layouts that do not follow that convention.
    raw_artist_lines = blocks[0]["raw_lines"] if len(blocks) >= 2 else []
    raw_programme_lines = [line for block in blocks[1:] for line in block["raw_lines"]]
    return {
        "detail_url": detail_url,
        "raw_detail_title": title or None,
        "raw_content_blocks": blocks,
        "raw_artist_lines": raw_artist_lines,
        "raw_programme_lines": raw_programme_lines,
        "raw_info": info,
    }


def _fetch_url(url: str, *, insecure_tls: bool = False) -> str:
    if insecure_tls:
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    response = requests.get(url, timeout=45, headers={"User-Agent": USER_AGENT},
                            verify=not insecure_tls)
    response.raise_for_status()
    # The official pages declare UTF-8.  Do not use apparent_encoding here:
    # proxy/HTML heuristics can misclassify Spanish text as Latin-1 and corrupt
    # the raw source material this phase is specifically meant to preserve.
    if not response.encoding:
        response.encoding = "utf-8"
    return response.text


def discover(
    fetch: Callable[[str], str],
    *,
    season_start: str = "2026-09-01",
    season_end: str = "2027-08-31",
) -> tuple[list[dict], list[dict]]:
    """Fetch all HTML pagination pages and retain occurrences in the season."""
    first = datetime.fromisoformat(season_start).date()
    last = datetime.fromisoformat(season_end).date()
    occurrences: list[dict] = []
    page_records: list[dict] = []
    offset = 0
    while True:
        url = page_url(offset)
        html = fetch(url)
        rows = parse_discovery_page(html, url, offset=offset)
        page_records.append({"discovery_url": url, "offset": offset,
                             "row_count": len(rows)})
        for row in rows:
            try:
                occurrence_date = datetime.fromisoformat(row["raw_datetime"]).date()
            except ValueError:
                continue
            if first <= occurrence_date <= last:
                occurrences.append(row)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return occurrences, page_records


def attach_details(
    occurrences: Iterable[dict],
    fetch: Callable[[str], str],
    *,
    max_workers: int = 8,
) -> tuple[list[dict], list[dict]]:
    """Fetch each detail URL once, then copy its raw parse onto each occurrence."""
    cache: dict[str, dict] = {}
    errors: list[dict] = []
    urls = list(dict.fromkeys(row["source_url"] for row in occurrences))

    def fetch_one(url: str) -> tuple[str, dict, dict | None]:
        try:
            return url, parse_detail_page(fetch(url), url), None
        except Exception as exc:  # retain the occurrence even when source fetch fails
            failure = {
                "detail_url": url, "raw_detail_title": None,
                "raw_content_blocks": [], "raw_artist_lines": [],
                "raw_programme_lines": [], "raw_info": [],
                "raw_fetch_error": f"{type(exc).__name__}: {exc}",
            }
            return url, failure, {"source_url": url, "error": failure["raw_fetch_error"]}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_one, url) for url in urls]
        for future in as_completed(futures):
            url, parsed, error = future.result()
            cache[url] = parsed
            if error:
                errors.append(error)
    errors.sort(key=lambda item: item["source_url"])
    result = []
    for occurrence in occurrences:
        row = dict(occurrence)
        row.update(cache[row["source_url"]])
        result.append(row)
    return result, errors


def summarize(occurrences: list[dict], pages: list[dict], errors: list[dict]) -> dict:
    parsed_dates = []
    for row in occurrences:
        try:
            parsed_dates.append(datetime.fromisoformat(row["raw_datetime"]))
        except ValueError:
            pass
    duplicate_keys = [
        (row["source_url"], row["raw_datetime"], row["raw_title"], row["raw_venue"])
        for row in occurrences
    ]
    counts = Counter(duplicate_keys)
    detail_counts = Counter(row["source_url"] for row in occurrences)
    # Coverage is reported at detail-page level.  Occurrences are intentionally
    # repeated in the parser output when a page has multiple performances, but
    # a page should count once in these content-coverage fields.
    detail_pages = {}
    for row in occurrences:
        detail_pages.setdefault(row["source_url"], row)
    programme_pages = sum(bool(row.get("raw_programme_lines")) for row in detail_pages.values())
    artist_pages = sum(bool(row.get("raw_artist_lines")) for row in detail_pages.values())
    no_programme = sum(not row.get("raw_programme_lines") for row in detail_pages.values())
    unknown = sum(
        bool(row.get("raw_fetch_error")) or not row.get("raw_content_blocks")
        or (not row.get("raw_programme_lines") and not row.get("raw_artist_lines"))
        for row in detail_pages.values()
    )
    monthly = Counter(value.strftime("%Y-%m") for value in parsed_dates)
    return {
        "source": SOURCE,
        "discovery_page_count": len(pages),
        "discovery_occurrence_count": len(occurrences),
        "unique_detail_url_count": len(detail_counts),
        "detail_urls_reused_by_multiple_performances": sum(v > 1 for v in detail_counts.values()),
        "minimum_datetime": min(parsed_dates).isoformat() if parsed_dates else None,
        "maximum_datetime": max(parsed_dates).isoformat() if parsed_dates else None,
        "monthly_occurrence_distribution": dict(sorted(monthly.items())),
        "detail_fetch_success_count": len(detail_counts) - len(errors),
        "detail_fetch_failure_count": len(errors),
        "pages_with_programme": programme_pages,
        "pages_with_artist_credit_content": artist_pages,
        "pages_with_no_programme": no_programme,
        "unknown_unparsed_raw_content_count": unknown,
        "duplicate_discovery_occurrence_count": sum(v - 1 for v in counts.values() if v > 1),
        "database_writes": 0,
        "detail_fetch_errors": errors,
    }
