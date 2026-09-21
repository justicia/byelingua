"""Generic, bounded recovery of missing official content.

Occurrence acquisition and content acquisition are separate concerns.  This
module only revisits an already identified official detail URL when an event
is missing programme or credit evidence.  It reuses the shared detail
extractors; it does not contain venue-specific selectors or database writes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .adapters.detail_linked_listing import (
    _composer as _detail_composer,
    _credits as _detail_credits,
    _detail_title,
    _jsonld_documents,
)
from .adapters.europe_venue import _credits as _jsonld_credits
from .adapters.europe_venue import _documents as _europe_documents
from .adapters.europe_venue import _programme as _jsonld_programme
from .schema import CanonicalEvent
from .credit_resolution import normalize_credit_row
from .global_master import normalize_identity


PROGRAMME_TERMINAL_CAUSES = {
    "PROGRAMME_SOURCE_NOT_PUBLISHED",
    "PROGRAMME_SOURCE_UNREADABLE",
    "PROGRAMME_RESOLUTION_FAILED",
    "PROGRAMME_HUMAN_PDF_REQUIRED",
}
CAST_TERMINAL_CAUSES = {
    "CAST_SOURCE_NOT_PUBLISHED",
    "CAST_SOURCE_UNREADABLE",
    "CAST_RESOLUTION_FAILED",
    "CAST_HUMAN_PDF_REQUIRED",
}


def _normalise_url(value: Any) -> str:
    if not value:
        return ""
    parsed = urlsplit(str(value).strip())
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path.rstrip("/"), parsed.query, ""))


def _official_hosts(config: dict[str, Any]) -> set[str]:
    hosts = set()
    for key in ("official_source", "listing_source"):
        host = urlsplit(str(config.get(key) or "")).netloc.casefold()
        if host:
            hosts.add(host)
    return hosts


def _candidate_urls(event: CanonicalEvent, config: dict[str, Any]) -> list[str]:
    """Return only traceable official detail candidates, most specific first."""
    raw = event.raw if isinstance(event.raw, dict) else {}
    nested = raw.get("source_event") if isinstance(raw.get("source_event"), dict) else {}
    primary_values: list[str] = []
    fallback_values: list[str] = []
    primary_keys = ("detail_source_url", "source_detail_url", "detail_url", "official_detail_url", "url")
    fallback_keys = (
        "production_detail_url", "production_url", "source_production_url",
        "production_source_url", "parent_detail_url", "parent_source_url",
    )
    for source in (raw, nested):
        for key in primary_keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                primary_values.append(value.strip())
        for key in fallback_keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                fallback_values.append(value.strip())
        source_records = source.get("source_records")
        if isinstance(source_records, list):
            for record in source_records:
                if not isinstance(record, dict):
                    continue
                value = record.get("source_url")
                if isinstance(value, str) and value.strip():
                    primary_values.append(value.strip())
    if event.source_url:
        primary_values.append(event.source_url)

    hosts = _official_hosts(config)
    listing_urls = {
        _normalise_url(config.get("official_source")),
        _normalise_url(config.get("listing_source")),
    }
    result: list[str] = []
    for value in primary_values + fallback_values:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.casefold() not in hosts:
            continue
        normalised = _normalise_url(value)
        if not normalised or normalised in listing_urls:
            continue
        if value not in result:
            result.append(value)
    return result


def _dedupe_programme(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        title = str(row.get("source_title") or "").strip()
        provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
        work_key = str(row.get("work_id") or row.get("canonical_work_id") or "").strip() or normalize_identity(title)
        key = (work_key, normalize_identity(row.get("composer") or row.get("composer_name")))
        if not title:
            continue
        row = dict(row)
        prior = seen.get(key)
        if prior is not None:
            sources = list(prior.get("provenance_sources") or [])
            source = dict(provenance)
            if source and source not in sources:
                sources.append(source)
            if sources:
                prior["provenance_sources"] = sources
            continue
        row["source_programme_index"] = len(result) + 1
        row["original_programme_order"] = len(result) + 1
        row["provenance_sources"] = [dict(provenance)] if provenance else []
        seen[key] = row
        result.append(row)
    return result


def _dedupe_credits(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        normalized = normalize_credit_row(row)
        artist = str(normalized.get("artist_name") or normalized.get("source_artist_name") or "").strip()
        character = str(row.get("character") or row.get("raw_character") or "").strip()
        key = (
            normalize_identity(artist),
            normalize_identity(normalized.get("canonical_role") or normalized.get("source_role")),
            normalize_identity(character),
            str(normalized.get("instrument") or ""),
            str(normalized.get("voice_type") or ""),
        )
        if not artist:
            continue
        prior = seen.get(key)
        if prior is not None:
            sources = list(prior.get("provenance_sources") or [])
            provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
            if provenance and provenance not in sources:
                sources.append(dict(provenance))
            if sources:
                prior["provenance_sources"] = sources
            continue
        enriched = dict(row)
        enriched.update({"canonical_role": normalized.get("canonical_role"), "instrument": normalized.get("instrument"), "voice_type": normalized.get("voice_type")})
        provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
        enriched["provenance_sources"] = [dict(provenance)] if provenance else []
        seen[key] = enriched
        result.append(enriched)
    return result


def _programme_row(title: str, composer: str | None, page_url: str, source_field: str) -> dict[str, Any]:
    return {
        "source_title": title,
        "raw_title": title,
        "composer": composer,
        "composer_candidate": {
            "raw_name": composer,
            "normalized_name": composer,
            "source_field": source_field,
            "source_url": page_url,
            "confidence": "official detail structured field",
        } if composer else {},
        "source_programme_index": 1,
        "raw_programme_index": 1,
        "original_programme_order": 1,
        "resolution_status": "pending_global_resolution",
        "provenance": {"source_url": page_url, "source_field": source_field},
    }


def extract_detail_content(page: str, page_url: str, event: CanonicalEvent) -> dict[str, Any]:
    """Extract source-supported programme and credits from one official page."""
    soup = BeautifulSoup(page, "html.parser")
    documents = _jsonld_documents(page)
    if not documents:
        documents = _europe_documents(page)
    title = _detail_title(soup, documents, event.title) or event.title

    programme: list[dict[str, Any]] = []
    for document in documents:
        programme.extend(_jsonld_programme(document, title, page_url))
    composer, composer_reason = _detail_composer(soup, documents, title, page_url)
    if composer:
        programme.append(_programme_row(title, composer, page_url, "detail.composer"))

    credits: list[dict[str, Any]] = []
    for document in documents:
        credits.extend(_jsonld_credits(document, page_url))
    credits.extend(_detail_credits(soup, page_url, event.date))
    programme = _dedupe_programme(programme)
    credits = _dedupe_credits(credits)
    return {
        "title": title,
        "programme": programme,
        "credits": credits,
        "programme_evidence": bool(programme),
        "credits_evidence": bool(credits),
        "composer_reason": composer_reason,
        "source_url": page_url,
    }


def _expected_layers(event: CanonicalEvent) -> dict[str, bool]:
    raw = event.raw if isinstance(event.raw, dict) else {}
    explicit_type_signal = " ".join(
        str(raw.get(key) or "")
        for key in ("source_event_type", "event_type", "classification", "category", "type")
    )
    type_signal = " ".join((str(event.event_type or ""), explicit_type_signal)).casefold()
    title_signal = str(event.title or "").casefold()
    non_performance = any(
        token in title_signal
        for token in ("guided tour", "tour", "visit", "museum", "architecture", "access to")
    )
    staged = not non_performance and (
        any(token in type_signal for token in ("opera", "operatic", "ballet", "dance", "musical"))
        or any(token in title_signal for token in ("opera", "operatic", "ballet", "dance", "musical"))
        or any(token in type_signal for token in ("theatre", "theater", "play", "performance"))
    )
    concert = not non_performance and (
        any(token in type_signal for token in ("concert", "symphony", "orchestra", "recital", "piano", "violin"))
        or any(token in title_signal for token in ("concert", "symphony", "orchestra", "recital"))
    )
    return {
        "work": staged or concert,
        "programme": staged or concert,
        "cast": staged,
        "artistic_team": staged or concert,
    }


def _merge_event(event: CanonicalEvent, content: dict[str, Any], page_url: str) -> tuple[CanonicalEvent, bool, bool]:
    programme = list(event.programme)
    credits = list(event.credits)
    programme_recovered = not programme and bool(content.get("programme"))
    credits_recovered = not credits and bool(content.get("credits"))
    if programme_recovered:
        programme = list(content["programme"])
    elif programme and content.get("programme"):
        programme = _dedupe_programme(programme + list(content["programme"]))
    if credits_recovered:
        credits = list(content["credits"])
    elif credits and content.get("credits"):
        credits = _dedupe_credits(credits + list(content["credits"]))
    if not programme_recovered and not credits_recovered:
        return event, False, False

    quality = dict(event.data_quality)
    programme_quality = dict(quality.get("programme") or {})
    if programme:
        programme_quality.update({"status": "PROGRAMME_EVIDENCE_FOUND", "reason": "official detail content recovery", "recovery_source_url": page_url})
    quality["programme"] = programme_quality
    quality["content_recovery"] = {
        "source_url": page_url,
        "programme": "RESOLVED" if programme else "UNRESOLVED",
        "cast": "RESOLVED" if credits else "UNRESOLVED",
    }
    raw = dict(event.raw)
    recovery_sources = list(raw.get("content_recovery_sources") or [])
    if page_url not in recovery_sources:
        recovery_sources.append(page_url)
    raw["content_recovery_sources"] = recovery_sources
    return replace(event, programme=programme, credits=credits, data_quality=quality, raw=raw), programme_recovered, credits_recovered


def _terminal_cause(layer: str, *, candidate_urls: list[str], fetch_failed: bool, parsed: bool, config: dict[str, Any]) -> str:
    prefix = "PROGRAMME" if layer == "programme" else "CAST"
    if fetch_failed and not parsed:
        return f"{prefix}_SOURCE_UNREADABLE"
    if not candidate_urls:
        return f"{prefix}_RESOLUTION_FAILED"
    if parsed:
        return f"{prefix}_SOURCE_NOT_PUBLISHED"
    if config.get("official_pdf_sources"):
        return f"{prefix}_HUMAN_PDF_REQUIRED"
    return f"{prefix}_RESOLUTION_FAILED"


def recover_missing_content(
    events: list[CanonicalEvent],
    *,
    adapter: Any,
    config: dict[str, Any],
    season: str,
    discover: Any | None = None,
) -> dict[str, Any]:
    """Recover missing layers with one cached fetch per official detail URL.

    ``discover`` is an optional generic, targeted source-discovery callback.
    It is invoked only when the existing production source records do not
    contain a usable official detail URL.  The callback returns a list of
    official URLs and is deliberately kept outside the parser so the same
    recovery path works for every venue.
    """
    current = list(events)
    fetch = getattr(adapter, "_fetch", None)
    report_events: list[dict[str, Any]] = []
    cache: dict[str, dict[str, Any]] = {}
    source_use_counts: Counter[str] = Counter()
    recovered_programme = 0
    recovered_credits = 0
    discovery_attempted = 0
    discovery_passed = 0
    discovery_failed = 0
    discovered_urls: list[str] = []
    discovery_cache: dict[str, dict[str, Any]] = {}

    for index, event in enumerate(current):
        urls = _candidate_urls(event, config)
        attempted_urls: list[str] = []
        failed_source_urls: list[str] = []
        raw = event.raw if isinstance(event.raw, dict) else {}
        production_gap = raw.get("production_gap") if isinstance(raw.get("production_gap"), dict) else {}
        existing_programme = bool(production_gap.get("programme_present"))
        existing_credits = bool(production_gap.get("credits_present"))
        needs_programme = not bool(event.programme) and not existing_programme
        needs_credits = not bool(event.credits) and not existing_credits
        if not needs_programme and not needs_credits:
            expected = _expected_layers(event)
            report_events.append({
                "event_key": event.event_key,
                "title": event.title,
                "date": event.date,
                "programme_status": "RESOLVED",
                "cast_status": "RESOLVED",
                "expected_work": expected["work"],
                "expected_cast": expected["cast"],
                "expected_artistic_team": expected["artistic_team"],
                "source_urls": [],
            })
            continue
        if not urls and callable(discover):
            discovery_key = str(
                raw.get("production_key")
                or raw.get("production_id")
                or raw.get("source_title")
                or event.title
            ).casefold()
            discovery_attempted += 1
            cached_discovery = discovery_cache.get(discovery_key)
            if cached_discovery is None:
                try:
                    discovered = discover(event)
                    if isinstance(discovered, str):
                        discovered = [discovered]
                    if not isinstance(discovered, list):
                        discovered = []
                    safe_discovered = [
                        str(value).strip()
                        for value in discovered
                        if isinstance(value, str) and value.strip()
                    ]
                    cached_discovery = {"urls": list(dict.fromkeys(safe_discovered))}
                    discovery_cache[discovery_key] = cached_discovery
                except Exception as exc:
                    cached_discovery = {"error": f"{type(exc).__name__}: {exc}"}
                    discovery_cache[discovery_key] = cached_discovery
            if cached_discovery.get("urls"):
                urls.extend(str(value) for value in cached_discovery["urls"])
                discovered_urls.extend(str(value) for value in cached_discovery["urls"])
                discovery_passed += 1
                raw = dict(raw)
                raw["discovered_detail_source_urls"] = list(cached_discovery["urls"])
                event = replace(event, raw=raw)
            else:
                discovery_failed += 1
        content: dict[str, Any] | None = None
        fetch_failed = False
        # A performance URL may be stale while a traceable production page is
        # still valid.  Keep the recovery bounded to the primary URL plus one
        # source-provided fallback, and cache the fallback for sibling events.
        for url in urls[:2]:
            attempted_urls.append(url)
            source_use_counts[url] += 1
            if not callable(fetch):
                break
            if url not in cache:
                try:
                    page = fetch(url)
                    if isinstance(page, bytes):
                        page = page.decode("utf-8", errors="strict")
                    cache[url] = {"content": extract_detail_content(str(page), url, event)}
                except Exception as exc:
                    cache[url] = {"error": f"{type(exc).__name__}: {exc}"}
            cached = cache[url]
            if cached.get("content"):
                content = cached["content"]
                if content.get("programme") or content.get("credits"):
                    break
            if cached.get("error"):
                fetch_failed = True
                failed_source_urls.append(url)

        if content is None:
            content = {"programme": [], "credits": []}
        if existing_programme:
            content["programme"] = []
        if existing_credits:
            content["credits"] = []
        merged, did_programme, did_credits = _merge_event(event, content, str(content.get("source_url") or (attempted_urls[0] if attempted_urls else event.source_url)))
        current[index] = merged
        recovered_programme += int(did_programme)
        recovered_credits += int(did_credits)
        expected = _expected_layers(event)
        programme_status = "RESOLVED" if (merged.programme or existing_programme) else _terminal_cause("programme", candidate_urls=attempted_urls, fetch_failed=fetch_failed, parsed=bool(content.get("source_url")), config=config)
        cast_status = "RESOLVED" if (merged.credits or existing_credits) else _terminal_cause("cast", candidate_urls=attempted_urls, fetch_failed=fetch_failed, parsed=bool(content.get("source_url")), config=config)
        quality = dict(merged.data_quality)
        programme_quality = dict(quality.get("programme") or {})
        if not merged.programme:
            programme_quality["recovery_status"] = programme_status
            programme_quality["recovery_reason"] = "generic content recovery exhausted official detail evidence"
        quality["programme"] = programme_quality
        quality["content_recovery"] = {
            "programme_status": programme_status,
            "cast_status": cast_status,
            "expected_work": expected["work"],
            "expected_cast": expected["cast"],
            "expected_artistic_team": expected["artistic_team"],
            "attempted_source_urls": attempted_urls,
            "failed_source_urls": failed_source_urls,
            "fallback_source_url": attempted_urls[1] if len(attempted_urls) > 1 else None,
        }
        current[index] = replace(merged, data_quality=quality)
        report_events.append({
            "event_key": merged.event_key,
            "title": merged.title,
            "date": merged.date,
            "programme_status": programme_status,
            "cast_status": cast_status,
            "expected_work": expected["work"],
            "expected_cast": expected["cast"],
            "expected_artistic_team": expected["artistic_team"],
            "source_urls": attempted_urls,
            "failed_source_urls": failed_source_urls,
            "fallback_source_url": attempted_urls[1] if len(attempted_urls) > 1 else None,
        })

    def layer_counts(layer: str) -> dict[str, Any]:
        field = "programme_status" if layer == "programme" else "cast_status"
        statuses = [str(row[field]) for row in report_events]
        counter = Counter(status for status in statuses if status != "RESOLVED")
        return {
            "resolved_events": sum(status == "RESOLVED" for status in statuses),
            "unresolved_events": sum(status != "RESOLVED" for status in statuses),
            "terminal_failures_by_reason": dict(sorted(counter.items())),
        }

    expected_cast_events = [row for row in report_events if row["expected_cast"]]
    expected_team_events = [row for row in report_events if row["expected_artistic_team"]]
    report = {
        "season": season,
        "status": "COMPLETE",
        "events_considered": len(current),
        "events_with_work": sum(bool(event.programme) for event in current),
        "events_with_programme": sum(bool(event.programme) for event in current),
        "events_with_cast": sum(bool(event.credits) for event in current),
        "events_with_artistic_team": sum(any(str(row.get("credit_kind") or "") == "artistic_team" for row in event.credits) for event in current),
        "expected_cast_events": len(expected_cast_events),
        "expected_cast_events_without_cast": sum(row["cast_status"] != "RESOLVED" for row in expected_cast_events),
        "events_without_artistic_team": sum(row["expected_artistic_team"] and not any(str(credit.get("credit_kind") or "") == "artistic_team" for credit in current[index].credits) for index, row in enumerate(report_events)),
        "programme_recovered": recovered_programme,
        "credits_recovered": recovered_credits,
        "programme": layer_counts("programme"),
        "cast": layer_counts("cast"),
        "events": report_events,
        "cached_source_pages": len(cache),
        "source_pages_reused_across_events": sum(count > 1 for count in source_use_counts.values()),
        "production_level_enrichment_reuse": "PASS" if any(count > 1 for count in source_use_counts.values()) else "NOT_OBSERVED",
        "source_page_errors": {url: value["error"] for url, value in cache.items() if value.get("error")},
        "unexplained_zero_content_events": 0,
        "discovery_attempted": discovery_attempted,
        "discovery_passed": discovery_passed,
        "discovery_failed": discovery_failed,
        "discovered_detail_source_urls": sorted(set(discovered_urls)),
    }
    # Keep these values explicit even when no event was classified as a cast or
    # team expectation; the factory can safely aggregate them across venues.
    report["expected_artistic_team_events"] = len(expected_team_events)
    return {"events": current, "report": report}
