from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .season import resolve_season_bounds


PRODUCTION_SOURCES = (
    "wiener_staatsoper",
    "operadeparis",
    "philharmonie_paris",
    "teatro_real",
    "auditorio_nacional",
)
IDENTITY_SHAPES = (
    "numeric",
    "uuid",
    "source_prefixed",
    "date_composite",
    "slug_or_text",
    "url_like",
    "other",
)
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_DATE = re.compile(r"(?:^|[^0-9])\d{4}-\d{2}-\d{2}(?:[^0-9]|$)")
_TEXT = re.compile(r"^[\w][\w .:/+'()–—-]*$", re.UNICODE)
_URL = re.compile(r"^(?:https?://|//|www\.)", re.IGNORECASE)


class AuditReadError(RuntimeError):
    def __init__(self, message: str, *, code: str = "read_or_configuration_error"):
        super().__init__(message)
        self.code = code


def classify_identity(value: object, source: str) -> str:
    text = str(value or "").strip()
    if text.isdigit():
        return "numeric"
    if _UUID.fullmatch(text):
        return "uuid"
    if text.startswith(f"{source}:") and len(text) > len(source) + 1:
        return "source_prefixed"
    if _URL.match(text):
        return "url_like"
    if _DATE.search(text):
        return "date_composite"
    if text and _TEXT.fullmatch(text) and any(character.isalpha() for character in text):
        return "slug_or_text"
    return "other"


def fetch_source_rows(
    source: str,
    season_start: str,
    season_end: str,
    *,
    page_size: int = 500,
    fetcher: Callable[..., Any] = urlopen,
    maximum_pages: int = 10_000,
) -> list[dict[str, Any]]:
    """Read one source and season through deterministic, filtered PostgREST pages."""
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_READONLY_KEY", "")
    if not base_url or not key:
        raise AuditReadError("SUPABASE_URL and SUPABASE_READONLY_KEY are required")
    if page_size <= 0 or maximum_pages <= 0:
        raise ValueError("page_size and maximum_pages must be positive")

    selection = "event_id,source,source_event_id,source_url,events!inner(id,event_key,date)"
    rows: list[dict[str, Any]] = []
    seen_source_rows: set[tuple[str, str, str]] = set()
    offset = 0
    page_number = 0
    while True:
        if page_number >= maximum_pages:
            raise AuditReadError("pagination did not terminate within the safety limit")
        query = urlencode(
            [
                ("select", selection),
                ("source", f"eq.{source}"),
                ("events.date", f"gte.{season_start}"),
                ("events.date", f"lte.{season_end}"),
                ("order", "event_id.asc,source_event_id.asc"),
                ("limit", page_size),
                ("offset", offset),
            ]
        )
        request = Request(
            f"{base_url}/rest/v1/event_sources?{query}",
            method="GET",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
            },
        )
        try:
            with fetcher(request, timeout=60) as response:
                if response.status != 200:
                    raise AuditReadError(f"Supabase audit read returned HTTP {response.status}")
                page = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise AuditReadError(f"Supabase audit read returned HTTP {exc.code}") from exc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuditReadError(f"Supabase audit read failed: {type(exc).__name__}") from exc
        if not isinstance(page, list):
            raise AuditReadError("Supabase audit response must be a JSON array")

        for raw in page:
            if not isinstance(raw, Mapping):
                raise AuditReadError("Supabase audit returned a non-object row")
            row = dict(raw)
            event = row.get("events") or {}
            if isinstance(event, list):
                event = event[0] if len(event) == 1 else {}
            if not isinstance(event, Mapping):
                event = {}
            event_id = str(row.get("event_id") or event.get("id") or "")
            source_row_identity = (
                str(row.get("source") or ""),
                str(row.get("source_event_id") or ""),
                event_id,
            )
            if source_row_identity in seen_source_rows:
                raise AuditReadError(
                    "pagination returned duplicate source row: "
                    f"source={source_row_identity[0]}, "
                    f"source_event_id={source_row_identity[1]}, event_id={event_id}",
                    code="pagination_duplicate_row",
                )
            seen_source_rows.add(source_row_identity)
            row["event_id"] = event_id
            row["event_key"] = event.get("event_key")
            row["date"] = event.get("date")
            rows.append(row)

        page_number += 1
        if len(page) < page_size:
            return rows
        offset += page_size


def _sample(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in ("event_id", "source_event_id", "event_key", "date", "source_url")
    }


def summarize_source(
    source: str,
    season_start: str,
    season_end: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    bounds_source: str,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    missing_ids = [row for row in rows if not str(row.get("source_event_id") or "").strip()]
    missing_keys = [row for row in rows if not str(row.get("event_key") or "").strip()]
    missing_urls = [row for row in rows if not str(row.get("source_url") or "").strip()]
    out_of_bounds = [
        row
        for row in rows
        if not isinstance(row.get("date"), str)
        or not (season_start <= str(row.get("date")) <= season_end)
    ]

    identities: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        identity = str(row.get("source_event_id") or "").strip()
        if identity:
            identities[identity].append(row)
    duplicate_groups = {key: value for key, value in identities.items() if len(value) > 1}
    duplicate_samples = []
    for identity, group in list(sorted(duplicate_groups.items()))[:20]:
        duplicate_samples.append(
            {
                "source_event_id": identity,
                "occurrences": len(group),
                "event_ids": sorted({str(row.get("event_id") or "") for row in group}),
            }
        )

    if not rows:
        failures.append({"code": "zero_records", "message": "database returned zero records"})
    if missing_ids:
        failures.append({"code": "missing_source_event_ids", "count": len(missing_ids), "samples": [_sample(row) for row in missing_ids[:20]]})
    if duplicate_groups:
        failures.append({"code": "duplicate_source_identities", "count": len(duplicate_groups), "samples": duplicate_samples})
    multi_event = [
        {
            "source_event_id": identity,
            "occurrences": len(group),
            "event_ids": sorted({str(row.get("event_id") or "") for row in group}),
        }
        for identity, group in sorted(duplicate_groups.items())
        if len({str(row.get("event_id") or "") for row in group}) > 1
    ]
    if multi_event:
        failures.append({"code": "source_identity_multiple_event_ids", "count": len(multi_event), "samples": multi_event[:20]})
    rows_by_event_id: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        event_id = str(row.get("event_id") or "").strip()
        if event_id:
            rows_by_event_id[event_id].append(row)
    multiple_identities = []
    for event_id, group in sorted(rows_by_event_id.items()):
        source_event_ids = sorted(
            {
                str(row.get("source_event_id") or "").strip()
                for row in group
                if str(row.get("source_event_id") or "").strip()
            }
        )
        if len(source_event_ids) > 1:
            multiple_identities.append(
                {
                    "event_id": event_id,
                    "source_event_ids": source_event_ids,
                    "record_count": len(group),
                }
            )
    if multiple_identities:
        failures.append(
            {
                "code": "multiple_source_identities_per_event_id",
                "count": len(multiple_identities),
                "samples": multiple_identities[:20],
            }
        )
    if out_of_bounds:
        failures.append({"code": "out_of_season_bounds", "count": len(out_of_bounds), "samples": [_sample(row) for row in out_of_bounds[:20]]})

    valid_dates = sorted(str(row.get("date")) for row in rows if isinstance(row.get("date"), str))
    ordered = sorted(rows, key=lambda row: (str(row.get("date") or ""), str(row.get("event_id") or "")))
    shape_counts = Counter(classify_identity(row.get("source_event_id"), source) for row in rows)
    key_shape_counts = Counter(classify_identity(row.get("event_key"), source) for row in rows)
    urls: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        url = str(row.get("source_url") or "").strip()
        if url:
            urls[url].append(row)
    reused = [(url, group) for url, group in urls.items() if len(group) > 1]
    reused.sort(key=lambda item: (-len(item[1]), item[0]))
    exact_key = sum(str(row.get("event_key") or "") == str(row.get("source_event_id") or "") for row in rows)
    prefixed_key = sum(str(row.get("event_key") or "") == f"{source}:{row.get('source_event_id')}" for row in rows)

    return {
        "source": source,
        "season_start": season_start,
        "season_end": season_end,
        "season_bounds_source": bounds_source,
        "record_count": len(rows),
        "first_date": valid_dates[0] if valid_dates else None,
        "last_date": valid_dates[-1] if valid_dates else None,
        "distinct_source_event_ids": len(identities),
        "distinct_event_keys": len({str(row.get("event_key")) for row in rows if row.get("event_key")}),
        "missing_source_event_ids": len(missing_ids),
        "missing_event_keys": len(missing_keys),
        "missing_source_urls": len(missing_urls),
        "duplicate_source_identities": {"count": len(duplicate_groups), "samples": duplicate_samples},
        "multiple_source_identities_per_event_id": {
            "count": len(multiple_identities),
            "samples": multiple_identities[:20],
        },
        "event_key_pattern_summary": {
            "identity_shape_counts": {shape: key_shape_counts.get(shape, 0) for shape in IDENTITY_SHAPES},
            "equals_source_event_id": exact_key,
            "equals_source_prefixed_id": prefixed_key,
        },
        "reused_url_count": len(reused),
        "top_reused_urls": [
            {"source_url": url, "record_count": len(group), "source_event_ids": [str(row.get("source_event_id") or "") for row in group[:20]]}
            for url, group in reused[:10]
        ],
        "identity_shape": {shape: shape_counts.get(shape, 0) for shape in IDENTITY_SHAPES},
        "sample_first_events": [_sample(row) for row in ordered[:10]],
        "sample_last_events": [_sample(row) for row in ordered[-10:]],
        "audit_passed": not failures,
        "failures": failures,
    }


def audit_season_sources(
    season: str,
    venue_config: Mapping[str, Any],
    sources: Sequence[str] = PRODUCTION_SOURCES,
    *,
    fetch_rows: Callable[[str, str, str], list[dict[str, Any]]] = fetch_source_rows,
) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    top_failures: list[dict[str, Any]] = []
    venues = venue_config.get("venues") if isinstance(venue_config, Mapping) else None
    for source in sources:
        try:
            if not isinstance(venues, Mapping) or source not in venues:
                raise ValueError(f"source is missing from config/venues.json: {source}")
            source_config = venues[source]
            if not isinstance(source_config, Mapping):
                raise ValueError(f"venue configuration must be an object: {source}")
            start, end = resolve_season_bounds(season, source_config)
            bounds_source = "configured" if season in source_config.get("season_bounds", {}) else "default"
            rows = fetch_rows(source, start, end)
            report = summarize_source(source, start, end, rows, bounds_source=bounds_source)
        except Exception as exc:  # Preserve a report for every source on read/config failures.
            try:
                fallback_config = venues.get(source, {}) if isinstance(venues, Mapping) else {}
                start, end = resolve_season_bounds(season, fallback_config)
                bounds_source = "configured" if season in fallback_config.get("season_bounds", {}) else "default"
            except Exception:
                start, end = None, None
                bounds_source = None
            failure = {
                "code": exc.code if isinstance(exc, AuditReadError) else "read_or_configuration_error",
                "message": str(exc),
            }
            report = {
                "source": source, "season_start": start, "season_end": end,
                "season_bounds_source": bounds_source, "record_count": 0, "first_date": None,
                "last_date": None, "distinct_source_event_ids": 0, "distinct_event_keys": 0,
                "missing_source_event_ids": 0, "missing_event_keys": 0, "missing_source_urls": 0,
                "duplicate_source_identities": {"count": 0, "samples": []},
                "multiple_source_identities_per_event_id": {"count": 0, "samples": []},
                "event_key_pattern_summary": {"identity_shape_counts": {shape: 0 for shape in IDENTITY_SHAPES}, "equals_source_event_id": 0, "equals_source_prefixed_id": 0},
                "reused_url_count": 0, "top_reused_urls": [],
                "identity_shape": {shape: 0 for shape in IDENTITY_SHAPES},
                "sample_first_events": [], "sample_last_events": [],
                "audit_passed": False, "failures": [failure],
            }
        reports.append(report)
        if not report["audit_passed"]:
            top_failures.append({"source": source, "failures": report["failures"]})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "season": season,
        "source_count": len(reports),
        "total_records": sum(report["record_count"] for report in reports),
        "audit_passed": not top_failures,
        "sources": reports,
        "failures": top_failures,
    }
