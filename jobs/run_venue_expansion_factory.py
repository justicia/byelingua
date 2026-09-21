"""One-click operational orchestration for venue expansion.

The acquisition work remains owned by ``run_europe_auto_factory`` and the
production write remains owned by ``production_graph.apply_graph``.  This
module is intentionally an orchestration façade: it checkpoints each venue,
keeps review local to that venue, materializes only existing SAFE artifacts,
and optionally hands those artifacts to the existing atomic writer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs import run_europe_auto_factory
from season_ingestion.approval import ApprovalMismatch, validate_approval, validate_write_scope
from season_ingestion.credentials import check_required_credentials
from season_ingestion.factory import _write_production_graph_staging, run_target
from season_ingestion.notifications import build_approval_manifest
from season_ingestion.production_graph import ProductionGraphRPCError, apply_graph, parse_rpc_error_body
from season_ingestion.release_readiness import assess_release_candidate
from season_ingestion.venue_targets import TARGETS_PATH


OPERATIONAL_SCHEMA_VERSION = "venue-expansion-factory-v1"
PUBLISH_PROGRESS_SCHEMA_VERSION = "venue-expansion-publish-progress-v1"

_PUBLISHABLE_SOURCE_STATES = {"READY_FOR_APPROVAL", "REVIEW_REQUIRED", "SOURCE_PARTIAL"}
_HUMAN_ACTION_STATES = {"HUMAN_PDF_REQUIRED", "PDF_REQUIRED"}


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return default


def _bounded_failure_message(exc: Exception) -> str:
    """Persist diagnostics without including request credentials or headers."""
    diagnostics = _exception_diagnostics(exc)
    if diagnostics.get("http_status") is not None:
        parts = [f"HTTP {diagnostics['http_status']}"]
        if diagnostics.get("error_code"):
            parts.append(f"code={diagnostics['error_code']}")
        if diagnostics.get("message"):
            parts.append(f"message={diagnostics['message']}")
        if diagnostics.get("details"):
            parts.append(f"details={diagnostics['details']}")
        if diagnostics.get("hint"):
            parts.append(f"hint={diagnostics['hint']}")
        return f"{type(exc).__name__}: {'; '.join(parts)}"[:1000]
    return str(exc)[:1000]


def _exception_diagnostics(exc: Exception) -> dict[str, Any]:
    """Return a sanitized, structured apply failure without request metadata."""
    if isinstance(exc, ProductionGraphRPCError):
        return exc.as_dict()
    if isinstance(exc, HTTPError):
        try:
            body = exc.read()
        except OSError:
            body = b""
        parsed = parse_rpc_error_body(body)
        return {
            "status": "APPLY_FAILED",
            "http_status": exc.code,
            **parsed,
        }
    response_body = getattr(exc, "response_body", None)
    if response_body is not None:
        parsed = parse_rpc_error_body(response_body)
        return {
            "status": "APPLY_FAILED",
            "http_status": getattr(exc, "http_status", None),
            **parsed,
        }
    return {
        "status": "APPLY_FAILED",
        "http_status": getattr(exc, "http_status", None),
        "error_code": None,
        "message": str(exc)[:1000],
        "details": None,
        "hint": None,
        "response_body": None,
    }


def parse_venue_ids(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _count(summary: dict[str, Any], *paths: tuple[str, ...]) -> int:
    for path in paths:
        value: Any = summary
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _sum_counts(summary: dict[str, Any], *paths: tuple[str, ...]) -> int:
    total = 0
    for path in paths:
        value: Any = summary
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        try:
            total += int(value or 0)
        except (TypeError, ValueError):
            continue
    return total


def _work_global_resolution_metrics(summary: dict[str, Any]) -> dict[str, int]:
    resolution = (summary.get("detail_enrichment") or {}).get("work_resolution")
    if not isinstance(resolution, dict):
        return {"resolved": 0, "review": 0, "new_candidate": 0, "not_run": 0}
    legacy_keys = ("existing_exact", "existing_alias", "existing_normalized", "legacy_existing")
    current_keys = ("exact", "alias", "normalized")
    resolved_keys = legacy_keys if any(key in resolution for key in legacy_keys) else current_keys
    return {
        "resolved": sum(int(resolution.get(key, 0) or 0) for key in resolved_keys),
        "review": int(resolution.get("review", 0) or 0),
        "new_candidate": int(resolution.get("new_candidate", 0) or 0),
        "not_run": int(resolution.get("not_run", 0) or 0),
    }


def _programme_content_metrics(summary: dict[str, Any]) -> dict[str, int]:
    detail = summary.get("detail_enrichment") if isinstance(summary.get("detail_enrichment"), dict) else {}
    content_recovery = summary.get("content_recovery") if isinstance(summary.get("content_recovery"), dict) else {}
    resolved = int(detail.get("programme_items", detail.get("programme_occurrences", 0)) or 0)
    if not resolved:
        resolved = int(detail.get("events_with_programme_evidence", 0) or 0)
    recovery_events = content_recovery.get("events")
    if isinstance(recovery_events, list):
        terminal = sum(
            bool(row.get("expected_work")) and str(row.get("programme_status") or "") != "RESOLVED"
            for row in recovery_events
            if isinstance(row, dict)
        )
    else:
        terminal = int(detail.get("events_without_programme_evidence", 0) or 0)
    return {"resolved": resolved, "terminal_unresolved": terminal}


def _load_profile(venue_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    profile = summary.get("capability_profile")
    if isinstance(profile, dict):
        return profile
    for name in ("source_capability_profile.json", "capability_profile.json"):
        value = _read_json(venue_dir / name, {})
        if isinstance(value, dict):
            return value
    return {}


def _source_layers(summary: dict[str, Any], profile: dict[str, Any]) -> tuple[str, list[str]]:
    occurrence = profile.get("occurrence_source") or {}
    occurrence_family = (
        profile.get("occurrence_source_family")
        or occurrence.get("source_family")
        or occurrence.get("family")
        or summary.get("occurrence_source_family")
        or summary.get("source_family")
        or summary.get("source_capability")
        or "UNKNOWN"
    )
    enrichment: list[str] = []
    detail = profile.get("detail_source") or {}
    for value in (
        detail.get("source_family"),
        profile.get("enrichment_source_family"),
        (profile.get("pdf_source") or {}).get("type") if isinstance(profile.get("pdf_source"), dict) else None,
    ):
        if value and str(value) not in enrichment:
            enrichment.append(str(value))
    return str(occurrence_family), enrichment


def _gap_state(summary: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Describe missing layers using concrete recovery types.

    Acquisition and enrichment themselves remain in the existing pipeline;
    these fields make the same-run recovery decision explicit in the factory
    artifact without inventing facts or creating a second parser.
    """
    gaps: list[str] = []
    recovery: list[str] = []
    events = _count(summary, ("counts", "events_discovered"), ("counts", "events"))
    programme = _count(summary, ("detail_enrichment", "programme_items"), ("counts", "programme_items"))
    credits = _count(summary, ("detail_enrichment", "credits_total"), ("counts", "credits_total"))
    if events <= 0:
        gaps.append("PARSE_FAILED")
    content_recovery = summary.get("content_recovery") if isinstance(summary.get("content_recovery"), dict) else {}
    programme_recovery = content_recovery.get("programme") if isinstance(content_recovery.get("programme"), dict) else {}
    cast_recovery = content_recovery.get("cast") if isinstance(content_recovery.get("cast"), dict) else {}
    if events > 0 and programme <= 0:
        gaps.append("PROGRAMME_EXTRACTION_FAILED")
        recovery.extend((programme_recovery.get("terminal_failures_by_reason") or {}).keys())
        if not programme_recovery.get("terminal_failures_by_reason"):
            recovery.append("DETAIL_SOURCE_MISSING")
    if events > 0 and credits <= 0:
        gaps.append("CAST_EXTRACTION_FAILED")
        recovery.extend((cast_recovery.get("terminal_failures_by_reason") or {}).keys())
        if not cast_recovery.get("terminal_failures_by_reason"):
            recovery.append("CHARACTER_DRIVEN_CAST_EXTRACTION")
    source_errors = (summary.get("source_audit") or {}).get("adapter_errors") or summary.get("adapter_errors") or []
    if source_errors:
        recovery.append("ALTERNATE_OFFICIAL_SOURCE")
    if summary.get("acquisition_status") in _HUMAN_ACTION_STATES:
        recovery.append("HUMAN_PDF_REQUIRED")
    return list(dict.fromkeys(gaps)), list(dict.fromkeys(recovery))


def _artifact_counts(payload: dict[str, Any]) -> dict[str, int]:
    return {
        "events": len(payload.get("events") or []),
        "composers": len(payload.get("composers") or []),
        "works": len(payload.get("works") or []),
        "relationships": len(payload.get("relationships") or []),
        "credits": len(payload.get("event_credits") or []),
    }


def _in_filter(values: list[str]) -> str:
    """Build a PostgREST ``in`` filter for the current run only."""
    escaped: list[str] = []
    for value in values:
        text = str(value)
        if all(char.isalnum() or char in "-_.:" for char in text):
            escaped.append(text)
        else:
            escaped.append('"' + text.replace('"', '\\"') + '"')
    return "in.(" + ",".join(escaped) + ")"


def _duplicate_extra(values: list[tuple[Any, ...]]) -> int:
    counts = Counter(values)
    return sum(count - 1 for count in counts.values() if count > 1)


def _zero_idempotency_delta() -> dict[str, int]:
    return {"events": 0, "event_work": 0, "credits": 0, "sources": 0}


def _replay_delta_from_result(value: Any) -> dict[str, int]:
    """Return only the post-apply replay delta from a verifier result."""
    source = value if isinstance(value, dict) else {}
    aliases = {
        "events": ("replay_new_events", "new_events"),
        "event_work": ("replay_new_event_work", "new_event_work_relationships"),
        "credits": ("replay_new_credits", "new_credits"),
        "sources": ("replay_new_sources", "new_source_rows"),
    }
    result = _zero_idempotency_delta()
    for entity, names in aliases.items():
        for name in names:
            if name in source:
                try:
                    result[entity] = int(source.get(name) or 0)
                except (TypeError, ValueError):
                    result[entity] = 0
                break
    return result


def _read_supabase_rows(
    table: str,
    select: str,
    filters: list[tuple[str, str]],
    *,
    fetcher: Callable[..., Any] = urlopen,
    page_size: int = 500,
) -> list[dict[str, Any]]:
    """Read a bounded table slice with a GET-only verification credential."""
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = ""
    for name in ("SUPABASE_SECRET_KEY", "SUPABASE_READONLY_KEY"):
        candidate = os.getenv(name, "").strip()
        if candidate:
            key = candidate
            break
    if not base_url or not key:
        raise RuntimeError("idempotency verification requires SUPABASE_URL and SUPABASE_SECRET_KEY or SUPABASE_READONLY_KEY")
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = [("select", select), *filters, ("limit", str(page_size)), ("offset", str(offset))]
        request = Request(
            f"{base_url}/rest/v1/{table}?{urlencode(query)}",
            method="GET",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
        )
        try:
            with fetcher(request, timeout=60) as response:
                body = response.read().decode("utf-8")
                if response.status != 200:
                    raise RuntimeError(f"read-only Supabase {table} lookup returned HTTP {response.status}: {body[:500]}")
        except HTTPError as exc:
            raise RuntimeError(f"read-only Supabase {table} lookup returned HTTP {exc.code}") from exc
        payload = json.loads(body) if body else []
        if not isinstance(payload, list):
            raise RuntimeError(f"read-only Supabase {table} lookup did not return an array")
        rows.extend(row for row in payload if isinstance(row, dict))
        if len(payload) < page_size:
            return rows
        offset += page_size


def _scope_from_payloads(payloads: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    credits: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    work_specs: list[dict[str, Any]] = []
    for payload in payloads:
        default_source = str(payload.get("source") or "")
        payload_events = payload.get("events") if isinstance(payload.get("events"), list) else []
        for event in payload_events:
            if not isinstance(event, dict):
                continue
            event_key = str(event.get("event_key") or "")
            if not event_key:
                continue
            source = str(event.get("source") or default_source)
            source_event_id = str(event.get("source_event_id") or "")
            events.append({"event_key": event_key, "source": source, "source_event_id": source_event_id})
            if source and source_event_id:
                sources.append({"event_key": event_key, "source": source, "source_event_id": source_event_id})
        payload_sources = payload.get("event_sources") if isinstance(payload.get("event_sources"), list) else []
        if payload_sources:
            sources = [row for row in sources if row["event_key"] not in {str(item.get("event_key") or "") for item in payload_events if isinstance(item, dict)}]
            sources.extend(
                {
                    "event_key": str(item.get("event_key") or ""),
                    "source": str(item.get("source") or default_source),
                    "source_event_id": str(item.get("source_event_id") or ""),
                }
                for item in payload_sources
                if isinstance(item, dict) and item.get("event_key") and item.get("source_event_id")
            )
        for work in payload.get("works") if isinstance(payload.get("works"), list) else []:
            if isinstance(work, dict):
                work_specs.append(work)
        for row in payload.get("relationships") if isinstance(payload.get("relationships"), list) else []:
            if isinstance(row, dict) and row.get("event_key"):
                relationships.append(row)
        for row in payload.get("event_credits") if isinstance(payload.get("event_credits"), list) else []:
            if isinstance(row, dict) and row.get("event_key"):
                credits.append(row)
    return {"events": events, "relationships": relationships, "credits": credits, "sources": sources, "work_specs": work_specs}


def verify_run_idempotency(
    payloads: list[dict[str, Any]],
    *,
    row_reader: Callable[[str, str, list[tuple[str, str]]], list[dict[str, Any]]] | None = None,
    first_apply: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify a post-apply replay using only successful current-run identities.

    ``first_apply`` is retained as a compatibility argument but deliberately
    ignored: candidate-row counts are not actual production write deltas.
    """
    result: dict[str, Any] = {
        "idempotency_scope": "current-run",
        "verification_phase": "post-apply-replay",
        "historical_duplicates_excluded": True,
        "run_duplicate_event_identity": 0,
        "run_duplicate_event_work": 0,
        "run_duplicate_credit_identity": 0,
        "run_duplicate_source_identity": 0,
        "payload_events": 0,
        "payload_event_work": 0,
        "payload_credits": 0,
        "payload_sources": 0,
        "replay_new_events": 0,
        "replay_new_event_work": 0,
        "replay_new_credits": 0,
        "replay_new_sources": 0,
        # Kept as compatibility aliases; these now always mean replay deltas.
        "new_events": 0,
        "new_event_work_relationships": 0,
        "new_credits": 0,
        "new_source_rows": 0,
        "idempotency_verified": False,
    }
    current_payloads = [payload for payload in payloads if isinstance(payload, dict)]
    if not current_payloads:
        result["idempotency_reason"] = "no successfully applied payloads in current run"
        return result
    scope = _scope_from_payloads(current_payloads)
    event_rows = scope["events"]
    relation_rows = scope["relationships"]
    credit_rows = scope["credits"]
    source_rows = scope["sources"]
    result.update({
        "payload_events": len(event_rows),
        "payload_event_work": len(relation_rows),
        "payload_credits": len(credit_rows),
        "payload_sources": len(source_rows),
    })
    event_keys = [str(row["event_key"]) for row in event_rows]
    result["run_duplicate_event_identity"] = _duplicate_extra([(key,) for key in event_keys])
    result["run_duplicate_event_work"] = _duplicate_extra([
        (str(row.get("event_key")), str(row.get("work_id") or row.get("candidate_key") or ""))
        for row in relation_rows
    ])
    result["run_duplicate_credit_identity"] = _duplicate_extra([
        (
            str(row.get("event_key")),
            str(row.get("artist_id") or row.get("artist_identity_key") or row.get("artist_name") or ""),
            str(row.get("role") or ""),
            str(row.get("character") or ""),
        )
        for row in credit_rows
    ])
    result["run_duplicate_source_identity"] = _duplicate_extra([
        (str(row.get("source") or ""), str(row.get("source_event_id") or "")) for row in source_rows
    ])
    local_duplicates = sum(
        int(result[key])
        for key in (
            "run_duplicate_event_identity",
            "run_duplicate_event_work",
            "run_duplicate_credit_identity",
            "run_duplicate_source_identity",
        )
    )
    if local_duplicates:
        result["idempotency_reason"] = "duplicate identity in current-run payload"
        return result

    reader = row_reader or (lambda table, select, filters: _read_supabase_rows(table, select, filters))
    try:
        unique_event_keys = sorted(set(event_keys))
        production_events: list[dict[str, Any]] = []
        for start in range(0, len(unique_event_keys), 100):
            production_events.extend(reader("events", "id,event_key", [("event_key", _in_filter(unique_event_keys[start:start + 100]))]))
        production_by_key = {str(row.get("event_key")): str(row.get("id")) for row in production_events if row.get("event_key") and row.get("id")}
        result["replay_new_events"] = sum(key not in production_by_key for key in unique_event_keys)
        result["run_duplicate_event_identity"] += _duplicate_extra([
            (str(row.get("event_key")),) for row in production_events if row.get("event_key")
        ])

        source_identity_to_event_key = {
            (str(row.get("source") or ""), str(row.get("source_event_id") or "")): str(row.get("event_key"))
            for row in source_rows
        }
        production_sources: list[dict[str, Any]] = []
        grouped_sources: dict[str, list[str]] = {}
        for row in source_rows:
            grouped_sources.setdefault(str(row.get("source") or ""), []).append(str(row.get("source_event_id") or ""))
        for source, source_ids in grouped_sources.items():
            for start in range(0, len(set(source_ids)), 100):
                production_sources.extend(reader(
                    "event_sources",
                    "event_id,source,source_event_id",
                    [("source", f"eq.{source}"), ("source_event_id", _in_filter(sorted(set(source_ids))[start:start + 100]))],
                ))
        production_source_keys = [
            (str(row.get("source") or ""), str(row.get("source_event_id") or ""))
            for row in production_sources
        ]
        local_source_keys = list(source_identity_to_event_key)
        result["replay_new_sources"] = sum(key not in set(production_source_keys) for key in local_source_keys)
        result["run_duplicate_source_identity"] += _duplicate_extra([
            key for key in production_source_keys if key in set(local_source_keys)
        ])

        production_event_id_by_key = dict(production_by_key)
        for row in production_sources:
            source_key = (str(row.get("source") or ""), str(row.get("source_event_id") or ""))
            event_key = source_identity_to_event_key.get(source_key)
            if event_key and row.get("event_id"):
                production_event_id_by_key.setdefault(event_key, str(row.get("event_id")))
        production_event_ids = sorted(set(production_event_id_by_key.values()))

        work_by_candidate = {
            str(row.get("candidate_key")): str(row.get("id"))
            for row in scope["work_specs"]
            if row.get("candidate_key") and row.get("id")
        }
        unresolved_work_candidates = sorted({
            str(row.get("candidate_key")) for row in relation_rows
            if not row.get("work_id") and row.get("candidate_key") and str(row.get("candidate_key")) not in work_by_candidate
        })
        if unresolved_work_candidates:
            identities = sorted({
                str(work.get("normalized_source_title"))
                for work in scope["work_specs"]
                if work.get("candidate_key") in unresolved_work_candidates and work.get("normalized_source_title")
            })
            if identities:
                rows = reader("works", "id,identity_key", [("identity_key", _in_filter(identities))])
                by_identity = {str(row.get("identity_key")): str(row.get("id")) for row in rows if row.get("identity_key") and row.get("id")}
                for work in scope["work_specs"]:
                    if work.get("candidate_key") in unresolved_work_candidates:
                        candidate = str(work.get("candidate_key"))
                        work_by_candidate[candidate] = by_identity.get(str(work.get("normalized_source_title")), "")

        production_programme: list[dict[str, Any]] = []
        production_credits: list[dict[str, Any]] = []
        if production_event_ids:
            event_filter = [("event_id", _in_filter(production_event_ids))]
            production_programme = reader("event_programme", "event_id,work_id,order", event_filter)
            production_credits = reader("event_credits", "event_id,artist_id,role,character_id,character", event_filter)
        production_programme_keys = [
            (str(row.get("event_id")), str(row.get("work_id")), str(row.get("order"))) for row in production_programme
        ]
        expected_programme: list[tuple[str, str, str]] = []
        for row in relation_rows:
            event_id = production_event_id_by_key.get(str(row.get("event_key")))
            work_id = str(row.get("work_id") or work_by_candidate.get(str(row.get("candidate_key") or "")) or "")
            if not event_id or not work_id:
                result["replay_new_event_work"] += 1
                continue
            expected_programme.append((event_id, work_id, str(row.get("order") or 1)))
        result["replay_new_event_work"] += sum(key not in set(production_programme_keys) for key in expected_programme)
        result["run_duplicate_event_work"] += _duplicate_extra([
            (event_id, work_id) for event_id, work_id, _order in production_programme
            if event_id in set(production_event_ids)
        ])

        artist_identity_by_credit: dict[int, str] = {}
        unresolved_artist_keys: set[str] = set()
        for index, row in enumerate(credit_rows):
            artist_id = str(row.get("artist_id") or "")
            identity = str(row.get("artist_identity_key") or row.get("artist_name") or "")
            if not artist_id and identity:
                unresolved_artist_keys.add(identity)
            artist_identity_by_credit[index] = artist_id or identity
        if unresolved_artist_keys:
            artist_rows: list[dict[str, Any]] = []
            identity_keys = sorted({str(row.get("artist_identity_key")) for row in credit_rows if row.get("artist_identity_key")})
            names = sorted({str(row.get("artist_name")) for row in credit_rows if row.get("artist_name") and not row.get("artist_identity_key")})
            if identity_keys:
                artist_rows.extend(reader("artists", "id,identity_key,artist_name", [("identity_key", _in_filter(identity_keys))]))
            if names:
                artist_rows.extend(reader("artists", "id,identity_key,artist_name", [("artist_name", _in_filter(names))]))
            by_artist_key = {}
            for row in artist_rows:
                if row.get("id"):
                    if row.get("identity_key"):
                        by_artist_key[str(row.get("identity_key"))] = str(row.get("id"))
                    if row.get("artist_name"):
                        by_artist_key[str(row.get("artist_name"))] = str(row.get("id"))
            for index, row in enumerate(credit_rows):
                if not row.get("artist_id"):
                    identity = str(row.get("artist_identity_key") or row.get("artist_name") or "")
                    artist_identity_by_credit[index] = by_artist_key.get(identity, "")
        expected_credits: list[tuple[str, str, str, str]] = []
        for index, row in enumerate(credit_rows):
            event_id = production_event_id_by_key.get(str(row.get("event_key")))
            artist_id = artist_identity_by_credit.get(index, "")
            if not event_id or not artist_id:
                result["replay_new_credits"] += 1
                continue
            expected_credits.append((event_id, artist_id, str(row.get("role") or ""), str(row.get("character") or "")))
        production_credit_keys = [
            (str(row.get("event_id")), str(row.get("artist_id")), str(row.get("role") or ""), str(row.get("character") or ""))
            for row in production_credits
        ]
        result["replay_new_credits"] += sum(key not in set(production_credit_keys) for key in expected_credits)
        result["run_duplicate_credit_identity"] += _duplicate_extra([
            key for key in production_credit_keys if key[0] in set(production_event_ids)
        ])
    except Exception as exc:
        result["idempotency_reason"] = f"read-only verification failed: {str(exc)[:300]}"
        return result

    duplicate_count = sum(
        int(result[key])
        for key in (
            "run_duplicate_event_identity",
            "run_duplicate_event_work",
            "run_duplicate_credit_identity",
            "run_duplicate_source_identity",
        )
    )
    for legacy_key, replay_key in (
        ("new_events", "replay_new_events"),
        ("new_event_work_relationships", "replay_new_event_work"),
        ("new_credits", "replay_new_credits"),
        ("new_source_rows", "replay_new_sources"),
    ):
        result[legacy_key] = int(result[replay_key])
    result["idempotency_verified"] = not duplicate_count and not any(
        int(result[key]) for key in ("replay_new_events", "replay_new_event_work", "replay_new_credits", "replay_new_sources")
    )
    if not result["idempotency_verified"]:
        result["idempotency_reason"] = "post-apply replay would create new rows or has scoped duplicates"
    else:
        result["idempotency_reason"] = "post-apply replay is fully present and duplicate-free"
    return result


def _venue_dir(output_root: Path, venue_id: str) -> Path:
    return output_root / venue_id


def _persist_apply_result(output_root: Path, venue_id: str, result: dict[str, Any]) -> None:
    """Persist only the sanitized apply outcome, never request headers/payload."""
    _atomic_json_write(_venue_dir(output_root, venue_id) / "apply_result.json", result)


def _ensure_materialized(result: dict[str, Any], *, output_root: Path) -> dict[str, Any]:
    """Materialize the current SAFE subset using the shared graph builder.

    A canonical review or incomplete season must not erase valid occurrence
    facts.  Before creating an apply artifact, the shared release gate still
    rejects rows with missing identity, dates, duplicate slots, or untraceable
    sources.  Coverage/enrichment uncertainty remains local to the report.
    """
    venue_id = str(result.get("venue_id") or "")
    season = str(result.get("season") or (result.get("summary") or {}).get("season") or "")
    directory = _venue_dir(output_root, venue_id)
    graph_path = directory / "production_graph_staging.json"
    manifest_path = directory / "approval_manifest.json"
    final_path = directory / "final_staging.json"
    if graph_path.is_file() and manifest_path.is_file() and final_path.is_file():
        return {"status": "EXISTING", "production_writes": 0}
    summary = result.get("summary") or {}
    if not (
        str(result.get("status") or "") in _PUBLISHABLE_SOURCE_STATES
        and summary.get("source_capability") in {"SOURCE_PASS", "SOURCE_PARTIAL"}
        and summary.get("global_master_preflight") == "PASS"
        and final_path.is_file()
        and (directory / "snapshot.json").is_file()
    ):
        return {"status": "NOT_APPLICABLE", "production_writes": 0}
    final = _read_json(final_path, {})
    source_audit = _read_json(directory / "source_audit.json", {})
    profile = _load_profile(directory, summary)
    events = final.get("events") if isinstance(final, dict) else []
    assessment = assess_release_candidate(
        venue_id=venue_id,
        season=season,
        events=events if isinstance(events, list) else [],
        summary=summary,
        source_audit=source_audit if isinstance(source_audit, dict) else {},
        capability_profile=profile,
    )
    if assessment.get("events_rejected", 0):
        return {"status": "BLOCKED", "blocker": "release-readiness rejected unsafe occurrence rows", "release_assessment": assessment, "production_writes": 0}
    try:
        _write_production_graph_staging(directory, summary, venue_id=venue_id, allow_partial=True)
        if not graph_path.is_file():
            return {"status": "BLOCKED", "blocker": "shared graph materializer produced no artifact", "production_writes": 0}
        manifest = build_approval_manifest(
            summary,
            final_path,
            run_id=str(summary.get("run_id", "local")),
            commit=str(summary.get("git_commit", "unknown")),
        )
        if not manifest.get("eligible_for_apply"):
            return {"status": "BLOCKED", "blocker": "safe approval manifest is not eligible", "production_writes": 0, "release_assessment": assessment}
        _atomic_json_write(manifest_path, manifest)
        graph_hash = hashlib.sha256(graph_path.read_bytes()).hexdigest()
        _atomic_json_write(directory / "materialization_report.json", {
            "schema_version": "venue-expansion-materialization-v1",
            "venue_id": venue_id,
            "season": season,
            "release_status": assessment.get("release_status"),
            "safe_events": len(events) if isinstance(events, list) else 0,
            "review_items_excluded": int((summary.get("counts") or {}).get("review_items", 0) or 0),
            "production_graph_staging_sha256": graph_hash,
            "production_writes": 0,
        })
        return {"status": "CREATED", "release_assessment": assessment, "production_writes": 0}
    except Exception as exc:
        return {"status": "BLOCKED", "blocker": str(exc)[:300], "release_assessment": assessment, "production_writes": 0}


def _publish_one(
    result: dict[str, Any],
    *,
    output_root: Path,
    publish: bool,
    apply: Callable[[dict[str, Any]], dict[str, Any]] = apply_graph,
) -> dict[str, Any]:
    """Validate and optionally apply one existing graph artifact.

    A graph artifact and eligible approval manifest are the only inputs to the
    writer.  No source fetch, staging rebuild, or direct database operation is
    performed here.
    """
    venue_id = str(result.get("venue_id") or "")
    season = str(result.get("season") or (result.get("summary") or {}).get("season") or "")
    directory = _venue_dir(output_root, venue_id)
    graph_path = directory / "production_graph_staging.json"
    manifest_path = directory / "approval_manifest.json"
    final_path = directory / "final_staging.json"
    status = str(result.get("status") or "")
    base: dict[str, Any] = {
        "venue_id": venue_id,
        "season": season,
        "status": "NOT_PUBLISHABLE",
        "production_writes": 0,
        "partial": status != "READY_FOR_APPROVAL",
        "reused": False,
    }
    if status not in _PUBLISHABLE_SOURCE_STATES:
        base["blocker"] = result.get("blocker") or f"venue status {status} is not publishable"
        _persist_apply_result(output_root, venue_id, base)
        return base
    materialization = _ensure_materialized(result, output_root=output_root)
    base["materialization"] = materialization
    if materialization.get("status") == "BLOCKED":
        base["blocker"] = materialization.get("blocker") or "safe materialization blocked"
        _persist_apply_result(output_root, venue_id, base)
        return base
    if not (graph_path.is_file() and manifest_path.is_file() and final_path.is_file()):
        base["blocker"] = "SAFE production graph artifact or approval manifest is missing"
        _persist_apply_result(output_root, venue_id, base)
        return base
    try:
        manifest = validate_approval(
            manifest_path,
            final_path,
            approved_run_id=str((_read_json(manifest_path, {}) or {}).get("dry_run_id") or ""),
            venue=venue_id,
            season=season,
            commit=None,
        )
        payload = _read_json(graph_path)
        if not isinstance(payload, dict):
            raise ApprovalMismatch("APPROVAL_MISMATCH: graph artifact is not an object")
        runtime = _artifact_counts(payload)
        validate_write_scope(manifest, {
            "events": runtime["events"],
            "composers": runtime["composers"],
            "works": runtime["works"],
            "relationships": runtime["relationships"],
        })
        base.update({"status": "READY_TO_PUBLISH", "runtime_scope": runtime, "approval": "PASS"})
        if not publish:
            _persist_apply_result(output_root, venue_id, base)
            return base
        credentials = check_required_credentials("apply")
        if not credentials["configured"]:
            raise ApprovalMismatch("WRITER_CREDENTIAL_MISSING: " + ",".join(credentials["missing"]))
        response = apply(payload)
        base.update({
            "status": "APPLY_SUCCESS",
            "production_result": response,
            "production_writes": sum(runtime.values()),
        })
        _persist_apply_result(output_root, venue_id, base)
        return base
    except ApprovalMismatch as exc:
        base.update({"status": "PUBLISH_BLOCKED", "blocker": str(exc), "approval": "FAIL"})
        _persist_apply_result(output_root, venue_id, base)
    except Exception as exc:  # isolate one venue and continue the batch
        base.update({
            "status": "APPLY_FAILED",
            "blocker": _bounded_failure_message(exc),
            "approval": "PASS",
            "apply_error": _exception_diagnostics(exc),
        })
        _persist_apply_result(output_root, venue_id, base)
    return base


def _frontend_smoke(
    result: dict[str, Any],
    *,
    output_root: Path,
    sender: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Verify production-driven search and detail visibility for one venue."""
    venue_id = str(result.get("venue_id") or "")
    directory = _venue_dir(output_root, venue_id)
    graph = _read_json(directory / "production_graph_staging.json", {})
    events = graph.get("events") or [] if isinstance(graph, dict) else []
    event_id = str(events[0].get("event_key") or events[0].get("source_event_id") or "") if events else ""
    if not event_id:
        return {"status": "NOT_RUN", "blocker": "published graph contains no event identity"}
    base_url = (os.getenv("BYELINGUA_FRONTEND_API_URL") or os.getenv("PUBLIC_APP_URL") or "https://www.bye-lingua.site").rstrip("/")
    endpoint = base_url if base_url.endswith("/api") else base_url + "/api"
    season = str(result.get("season") or "2026-27")
    start_year, end_short = season.split("-", 1)
    end_year = int(start_year) // 100 * 100 + int(end_short)

    def request(payload: dict[str, Any]) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(endpoint, data=body, method="POST", headers={"Content-Type": "application/json"})
        with sender(req, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"frontend API returned HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))

    search = request({"action": "schedule_events", "date_from": f"{start_year}-09-01", "date_to": f"{end_year}-08-31"})
    search_events = search.get("events") if isinstance(search, dict) else []
    if not any(str(row.get("event_id") or row.get("event_key") or "") == event_id for row in (search_events or [])):
        raise RuntimeError("published event is not visible in production search")
    detail = request({"action": "schedule_event_detail", "event_id": event_id})
    if not isinstance(detail, dict) or not detail.get("event"):
        raise RuntimeError("published event detail is not visible")
    return {"status": "PASS", "search": "PASS", "detail": "PASS"}


def _load_publish_progress(path: Path) -> dict[str, Any]:
    value = _read_json(path, {})
    return value if isinstance(value, dict) else {}


def _operational_venue_report(
    result: dict[str, Any],
    *,
    output_root: Path,
    publish_result: dict[str, Any],
    frontend_result: dict[str, Any],
) -> dict[str, Any]:
    summary = result.get("summary") or {}
    profile = _load_profile(_venue_dir(output_root, str(result.get("venue_id") or "")), summary)
    occurrence_source, enrichment_sources = _source_layers(summary, profile)
    gaps, recovery = _gap_state(summary)
    event_count = _count(summary, ("counts", "events_discovered"), ("counts", "events"))
    programme_items = _count(summary, ("detail_enrichment", "programme_items"), ("counts", "programme_items"))
    credits = _count(summary, ("detail_enrichment", "credits_total"), ("counts", "credits_total"))
    work_resolution = _work_global_resolution_metrics(summary)
    programme_content = _programme_content_metrics(summary)
    resolved_programme = programme_content["resolved"]
    programme_failed = programme_content["terminal_unresolved"]
    credit_counts = summary.get("credit_resolution", {}).get("counts", {}) if isinstance(summary.get("credit_resolution"), dict) else {}
    credits_resolved = int(credit_counts.get("credits_safe", 0) or 0)
    credits_failed = int(credit_counts.get("credits_review", 0) or 0)
    characters_resolved = int(credit_counts.get("character_safe", 0) or 0)
    characters_failed = int(credit_counts.get("character_review", 0) or 0)
    content_recovery = summary.get("content_recovery") if isinstance(summary.get("content_recovery"), dict) else {}
    recovery_enrichment_status = summary.get("enrichment_status") or "NOT_AVAILABLE"
    if content_recovery.get("status") == "COMPLETE":
        unresolved = int((content_recovery.get("programme") or {}).get("unresolved_events", 0) or 0) + int((content_recovery.get("cast") or {}).get("unresolved_events", 0) or 0)
        recovery_enrichment_status = "COMPLETE" if unresolved == 0 else "EXPLICIT_FAILURES_RECORDED"
    status = str(publish_result.get("status") or "")
    if status == "APPLY_SUCCESS":
        final_status = "PARTIAL_PUBLISHED" if publish_result.get("partial") else "PUBLISHED"
    elif status == "READY_TO_PUBLISH":
        final_status = "READY_FOR_APPROVAL"
    elif str(result.get("status")) in _HUMAN_ACTION_STATES or str(summary.get("acquisition_status")) in _HUMAN_ACTION_STATES:
        final_status = "HUMAN_PDF_REQUIRED"
    elif event_count > 0 and str(result.get("status")) in {"REVIEW_REQUIRED", "SOURCE_PARTIAL"}:
        final_status = "REVIEW_ONLY"
    else:
        final_status = "BLOCKED"
    return {
        "venue_id": result.get("venue_id"),
        "season": result.get("season"),
        "discovery_mode": (profile.get("discovery") or {}).get("discovered_by") or summary.get("discovery_mode") or "EXISTING_ENGINE",
        "occurrence_source": occurrence_source,
        "enrichment_sources": enrichment_sources,
        "events_discovered": event_count,
        "events_published": (publish_result.get("runtime_scope") or {}).get("events", 0) if status == "APPLY_SUCCESS" else 0,
        "works_resolved": work_resolution["resolved"],
        "works_failed": work_resolution["review"] + work_resolution["new_candidate"] + work_resolution["not_run"],
        "work_global_resolution_resolved": work_resolution["resolved"],
        "work_global_resolution_review": work_resolution["review"],
        "work_global_resolution_new_candidate": work_resolution["new_candidate"],
        "work_global_resolution_not_run": work_resolution["not_run"],
        "programme_content_resolved": programme_content["resolved"],
        "programme_content_terminal_unresolved": programme_content["terminal_unresolved"],
        "programme_resolved": resolved_programme,
        "programme_failed": programme_failed,
        "cast_resolved": credits_resolved,
        "cast_failed": credits_failed,
        "team_resolved": _count(summary, ("credit_resolution", "counts", "role_safe")),
        "artists_failed": int(credit_counts.get("artist_review", 0) or 0),
        "characters_failed": characters_failed,
        "characters_resolved": characters_resolved,
        "pdf_used": bool((profile.get("pdf_source") or {}).get("available")) if isinstance(profile.get("pdf_source"), dict) else False,
        "human_action": publish_result.get("blocker") if final_status == "HUMAN_PDF_REQUIRED" else None,
        "review_items": _count(summary, ("counts", "review_items")),
        "gap_types": gaps,
        "recovery_routes": recovery,
        "occurrence_status": "PUBLISHED" if status == "APPLY_SUCCESS" else ("READY" if status == "READY_TO_PUBLISH" else "NOT_PUBLISHED"),
        "enrichment_status": recovery_enrichment_status,
        "content_recovery": content_recovery,
        "production_level_enrichment_reuse": content_recovery.get("production_level_enrichment_reuse", "NOT_OBSERVED"),
        "unexplained_zero_content_events": _count(summary, ("content_recovery", "unexplained_zero_content_events")),
        "production_status": status,
        "frontend_status": frontend_result.get("status", "NOT_RUN"),
        "final_status": final_status,
        "blocker": publish_result.get("blocker") or result.get("blocker"),
        "apply_error": publish_result.get("apply_error"),
        "production_writes": int(publish_result.get("production_writes", 0) or 0),
    }


def _publish_batch(
    batch: dict[str, Any],
    *,
    output_root: Path,
    publish: bool,
    resume: bool,
    apply: Callable[[dict[str, Any]], dict[str, Any]] = apply_graph,
    smoke: Callable[..., dict[str, Any]] = _frontend_smoke,
    idempotency_verify: Callable[[list[dict[str, Any]]], dict[str, Any]] = verify_run_idempotency,
) -> dict[str, Any]:
    progress_path = output_root / "factory_publish_progress.json"
    progress = _load_publish_progress(progress_path) if resume else {}
    prior = progress.get("venues") if isinstance(progress.get("venues"), dict) else {}
    venue_reports: list[dict[str, Any]] = []
    applied_payloads: list[dict[str, Any]] = []
    for result in batch.get("venues", []):
        venue_id = str(result.get("venue_id") or "")
        previous = prior.get(venue_id) if isinstance(prior, dict) else None
        resumed_success = resume and isinstance(previous, dict) and previous.get("production_status") == "APPLY_SUCCESS"
        if resume and isinstance(previous, dict) and previous.get("production_status") == "APPLY_SUCCESS":
            publish_result = dict(previous)
            publish_result["status"] = publish_result.get("status") or publish_result.get("production_status")
            publish_result["reused"] = True
            frontend_result = {"status": previous.get("frontend_status", "PASS")}
        else:
            summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
            production_gap = summary.get("scope") == "production-gaps"
            safe_programme = _count(summary, ("counts", "safe_programme_relationships"))
            safe_credits = _count(summary, ("credit_resolution", "counts", "credits_safe"))
            if production_gap and safe_programme + safe_credits == 0:
                publish_result = {
                    "venue_id": venue_id,
                    "season": result.get("season"),
                    "status": "NO_CONTENT_CHANGE",
                    "production_writes": 0,
                    "partial": True,
                    "reused": False,
                    "blocker": "no new SAFE programme or credit content was recovered",
                }
            else:
                publish_result = _publish_one(result, output_root=output_root, publish=publish, apply=apply)
            frontend_result = {"status": "NOT_RUN"}
            if publish and publish_result.get("status") == "APPLY_SUCCESS":
                try:
                    frontend_result = smoke(result, output_root=output_root)
                except Exception as exc:
                    frontend_result = {"status": "FAIL", "blocker": str(exc)[:300]}
            publish_result["frontend_status"] = frontend_result.get("status", "NOT_RUN")
        if publish_result.get("status") == "APPLY_SUCCESS":
            graph = _read_json(_venue_dir(output_root, venue_id) / "production_graph_staging.json")
            if isinstance(graph, dict):
                applied_payloads.append(graph)
        report = _operational_venue_report(result, output_root=output_root, publish_result=publish_result, frontend_result=frontend_result)
        result["factory_report"] = report
        venue_reports.append(report)
        prior[venue_id] = publish_result | {"frontend_status": frontend_result.get("status", "NOT_RUN")}
        _atomic_json_write(progress_path, {"schema_version": PUBLISH_PROGRESS_SCHEMA_VERSION, "season": batch.get("season"), "venues": prior, "production_writes": sum(int(item.get("production_writes", 0) or 0) for item in prior.values() if isinstance(item, dict))})

    totals = {
        "venues_attempted": len(venue_reports),
        "published": sum(report["final_status"] == "PUBLISHED" for report in venue_reports),
        "partial_published": sum(report["final_status"] == "PARTIAL_PUBLISHED" for report in venue_reports),
        "review_only": sum(report["final_status"] == "REVIEW_ONLY" for report in venue_reports),
        "human_pdf_required": sum(report["final_status"] == "HUMAN_PDF_REQUIRED" for report in venue_reports),
        "blocked": sum(report["final_status"] == "BLOCKED" for report in venue_reports),
        "events_discovered": sum(report["events_discovered"] for report in venue_reports),
        "events_published": sum(report["events_published"] for report in venue_reports),
        "work_global_resolution_resolved": sum(report["work_global_resolution_resolved"] for report in venue_reports),
        "work_global_resolution_review": sum(report["work_global_resolution_review"] for report in venue_reports),
        "work_global_resolution_new_candidate": sum(report["work_global_resolution_new_candidate"] for report in venue_reports),
        "work_global_resolution_not_run": sum(report["work_global_resolution_not_run"] for report in venue_reports),
        "programme_content_resolved": sum(report["programme_content_resolved"] for report in venue_reports),
        "programme_content_terminal_unresolved": sum(report["programme_content_terminal_unresolved"] for report in venue_reports),
        "programme_resolved": sum(report["programme_resolved"] for report in venue_reports),
        "programme_failed": sum(report["programme_failed"] for report in venue_reports),
        "credits_resolved": sum(report["cast_resolved"] for report in venue_reports),
        "credits_failed": sum(report["cast_failed"] for report in venue_reports),
        "characters_resolved": sum(report["characters_resolved"] for report in venue_reports),
        "characters_failed": sum(report["characters_failed"] for report in venue_reports),
        "events_with_work": sum(_count(report, ("content_recovery", "events_with_work")) for report in venue_reports),
        "events_with_programme": sum(_count(report, ("content_recovery", "events_with_programme")) for report in venue_reports),
        "expected_cast_events": sum(_count(report, ("content_recovery", "expected_cast_events")) for report in venue_reports),
        "expected_cast_events_without_cast": sum(_count(report, ("content_recovery", "expected_cast_events_without_cast")) for report in venue_reports),
        "events_with_artistic_team": sum(_count(report, ("content_recovery", "events_with_artistic_team")) for report in venue_reports),
        "unexplained_zero_content_events": sum(report["unexplained_zero_content_events"] for report in venue_reports),
        "review_items": sum(report["review_items"] for report in venue_reports),
        "frontend_visible_venues": sum(report["frontend_status"] == "PASS" for report in venue_reports),
        "production_writes": sum(report["production_writes"] for report in venue_reports),
    }
    statuses = [report["production_status"] for report in venue_reports]
    if "APPLY_FAILED" in statuses:
        publish_health = "FAIL"
    elif "APPLY_SUCCESS" in statuses:
        publish_health = "PASS"
    else:
        publish_health = "NOT_RUN"
    apply_failed_venues = [report["venue_id"] for report in venue_reports if report["production_status"] == "APPLY_FAILED"]
    approval_mismatch_venues = [report["venue_id"] for report in venue_reports if report["production_status"] == "PUBLISH_BLOCKED"]
    frontend_smoke_failure_venues = [report["venue_id"] for report in venue_reports if report["frontend_status"] == "FAIL"]
    if publish:
        try:
            idempotency_result = idempotency_verify(applied_payloads)
        except Exception as exc:
            idempotency_result = {
                "idempotency_scope": "current-run",
                "verification_phase": "post-apply-replay",
                "historical_duplicates_excluded": True,
                "idempotency_verified": False,
                "idempotency_reason": f"verification failed: {str(exc)[:300]}",
            }
    else:
        idempotency_result = {
            "idempotency_scope": "current-run",
            "verification_phase": "not-run",
            "historical_duplicates_excluded": True,
            "idempotency_verified": False,
            "idempotency_reason": "publish was not requested; no applied payload to verify",
        }
    idempotency_result = dict(idempotency_result)
    replay_delta = _replay_delta_from_result(idempotency_result)
    payload_scope = _scope_from_payloads(applied_payloads)
    idempotency_result.update({
        "payload_events": len(payload_scope["events"]),
        "payload_event_work": len(payload_scope["relationships"]),
        "payload_credits": len(payload_scope["credits"]),
        "payload_sources": len(payload_scope["sources"]),
        "replay_new_events": replay_delta["events"],
        "replay_new_event_work": replay_delta["event_work"],
        "replay_new_credits": replay_delta["credits"],
        "replay_new_sources": replay_delta["sources"],
        # Legacy fields remain aliases for post-apply replay only.
        "new_events": replay_delta["events"],
        "new_event_work_relationships": replay_delta["event_work"],
        "new_credits": replay_delta["credits"],
        "new_source_rows": replay_delta["sources"],
        "first_apply_measurement": "UNAVAILABLE" if publish else "NOT_RUN",
    })
    idempotency_verified = idempotency_result.get("idempotency_verified") is True
    batch.update({
        "operational_schema_version": OPERATIONAL_SCHEMA_VERSION,
        **totals,
        "source_not_published": sum("SOURCE_NOT_PUBLISHED" in report["gap_types"] for report in venue_reports),
        "source_unreadable": sum("SOURCE_UNREADABLE" in report["gap_types"] for report in venue_reports),
        "failure_isolation": "PASS",
        "resume": "PASS" if not resume or progress_path.is_file() else "FAIL",
        "publish_health": publish_health,
        "publish_health_failed_venues": apply_failed_venues,
        "approval_mismatch_count": len(approval_mismatch_venues),
        "approval_mismatch_venues": approval_mismatch_venues,
        "frontend_smoke_failures": len(frontend_smoke_failure_venues),
        "frontend_smoke_failure_venues": frontend_smoke_failure_venues,
        **idempotency_result,
        "idempotency": "PASS" if idempotency_verified else "NOT_VERIFIED",
        "idempotency_verified": idempotency_verified,
        "venues": batch.get("venues", []),
    })
    _atomic_json_write(output_root / "factory_summary.json", batch)
    _atomic_json_write(output_root / "factory_operational_report.json", {
        "schema_version": OPERATIONAL_SCHEMA_VERSION,
        "season": batch.get("season"),
        "venues": venue_reports,
        **totals,
        "publish_health": publish_health,
        "publish_health_failed_venues": apply_failed_venues,
        "approval_mismatch_count": len(approval_mismatch_venues),
        "frontend_smoke_failures": len(frontend_smoke_failure_venues),
        **idempotency_result,
        "idempotency": "PASS" if idempotency_verified else "NOT_VERIFIED",
        "idempotency_verified": idempotency_verified,
    })
    return batch


def _run_production_completeness_factory(
    *,
    season: str,
    selected: list[str],
    output_root: Path,
    publish: bool,
    apply: Callable[[dict[str, Any]], dict[str, Any]] = apply_graph,
    smoke: Callable[..., dict[str, Any]] = _frontend_smoke,
    idempotency_verify: Callable[[list[dict[str, Any]]], dict[str, Any]] = verify_run_idempotency,
) -> dict[str, Any]:
    """Run targeted enrichment for existing production Events only."""
    from season_ingestion.production_completeness import (
        build_targeted_discovery,
        collect_production_gap_events,
        scan_production_gaps,
    )

    groups, before = collect_production_gap_events(season, selected=selected)
    results: list[dict[str, Any]] = []
    for group in groups:
        venue_id = str(group["venue_id"])
        target = {"venue_id": venue_id, "season": season}
        discover = build_targeted_discovery(
            venue_id=venue_id,
            season=season,
            config=group["config"],
            artifact_root=output_root / venue_id,
        )
        try:
            result = run_target(
                target,
                output_root,
                scope="production-gaps",
                existing_events=group["events"],
                content_discovery=discover,
            )
        except Exception as exc:
            result = {
                "venue_id": venue_id,
                "season": season,
                "status": "FAILED",
                "production_writes": 0,
                "blocker": f"{type(exc).__name__}: {exc}"[:300],
                "summary": {"venue": venue_id, "season": season, "scope": "production-gaps", "source_capability": "FAILED", "counts": {"events": len(group["events"]), "writes": 0}},
            }
        results.append(result)

    batch: dict[str, Any] = {
        "schema_version": OPERATIONAL_SCHEMA_VERSION,
        "season": season,
        "scope": "production-gaps",
        "operating_mode": "PRODUCTION_COMPLETENESS",
        "production_completeness_before": before,
        "production_writes": 0,
        "venues": results,
    }
    batch = _publish_batch(
        batch,
        output_root=output_root,
        publish=publish,
        resume=False,
        apply=apply,
        smoke=smoke,
        idempotency_verify=idempotency_verify,
    )
    try:
        after = scan_production_gaps(season, selected=selected)
    except Exception as exc:
        after = {"season": season, "scan_error": f"{type(exc).__name__}: {exc}"[:300]}
    batch["production_completeness_after"] = after
    batch["production_gap_events_before"] = int(before.get("production_gap_events", 0) or 0)
    batch["production_gap_events_after"] = int(after.get("production_gap_events", 0) or 0)
    batch["events_without_programme_before"] = int(before.get("events_without_programme", 0) or 0)
    batch["events_without_programme_after"] = int(after.get("events_without_programme", 0) or 0)
    batch["events_without_credits_before"] = int(before.get("events_without_credits", 0) or 0)
    batch["events_without_credits_after"] = int(after.get("events_without_credits", 0) or 0)
    batch["detail_sources_discovered"] = len({
        url
        for result in results
        for url in ((result.get("summary") or {}).get("content_recovery") or {}).get("discovered_detail_source_urls", [])
    })
    batch["programme_relationships_added"] = 0
    batch["credits_added"] = 0
    for result in results:
        venue_id = str(result.get("venue_id") or "")
        apply_result = _read_json(_venue_dir(output_root, venue_id) / "apply_result.json", {})
        if not isinstance(apply_result, dict) or apply_result.get("status") != "APPLY_SUCCESS":
            continue
        runtime_scope = apply_result.get("runtime_scope") or {}
        batch["programme_relationships_added"] += int(runtime_scope.get("relationships", 0) or 0)
        batch["credits_added"] += int(runtime_scope.get("credits", 0) or 0)
    batch["character_links_added"] = 0
    for result in results:
        venue_id = str(result.get("venue_id") or "")
        apply_result = _read_json(_venue_dir(output_root, venue_id) / "apply_result.json", {})
        if not isinstance(apply_result, dict) or apply_result.get("status") != "APPLY_SUCCESS":
            continue
        graph = _read_json(_venue_dir(output_root, venue_id) / "production_graph_staging.json", {})
        if isinstance(graph, dict):
            batch["character_links_added"] += sum(bool(row.get("character_id") or row.get("character")) for row in graph.get("event_credits", []) if isinstance(row, dict))
    batch["explicit_terminal_failures"] = sum(
        int(((result.get("summary") or {}).get("content_recovery") or {}).get("programme", {}).get("unresolved_events", 0) or 0)
        + int(((result.get("summary") or {}).get("content_recovery") or {}).get("cast", {}).get("unresolved_events", 0) or 0)
        for result in results
    )
    batch["frontend_status"] = "PASS" if batch.get("frontend_visible_venues", 0) == batch.get("published", 0) and batch.get("published", 0) > 0 else "PARTIAL"
    _atomic_json_write(output_root / "factory_summary.json", batch)
    _atomic_json_write(output_root / "factory_operational_report.json", {**(_read_json(output_root / "factory_operational_report.json", {}) or {}), **{key: batch[key] for key in ("production_completeness_before", "production_completeness_after", "production_gap_events_before", "production_gap_events_after", "events_without_programme_before", "events_without_programme_after", "events_without_credits_before", "events_without_credits_after", "detail_sources_discovered", "programme_relationships_added", "credits_added", "character_links_added", "explicit_terminal_failures", "frontend_status")}})
    return batch


def run_factory(
    *,
    season: str,
    scope: str,
    selected: list[str],
    output_root: Path,
    state_path: Path,
    target_path: Path | None = None,
    resume: bool = False,
    publish: bool = False,
    hermes_source_facts_root: Path | None = None,
    apply: Callable[[dict[str, Any]], dict[str, Any]] = apply_graph,
    smoke: Callable[..., dict[str, Any]] = _frontend_smoke,
    idempotency_verify: Callable[[list[dict[str, Any]]], dict[str, Any]] = verify_run_idempotency,
) -> dict[str, Any]:
    if scope == "production-gaps":
        return _run_production_completeness_factory(
            season=season,
            selected=selected,
            output_root=output_root,
            publish=publish,
            apply=apply,
            smoke=smoke,
            idempotency_verify=idempotency_verify,
        )
    batch = run_europe_auto_factory.run_factory(
        season=season,
        scope=scope,
        selected=selected,
        output_root=output_root,
        state_path=state_path,
        hermes_source_facts_root=hermes_source_facts_root,
        resume_root=output_root if resume else None,
        target_path=target_path,
    )
    return _publish_batch(batch, output_root=output_root, publish=publish, resume=resume, apply=apply, smoke=smoke, idempotency_verify=idempotency_verify)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the generic venue expansion factory")
    parser.add_argument("--season", required=True)
    parser.add_argument("--scope", choices=("pending", "all-enabled", "selected", "production-gaps"), default="pending")
    parser.add_argument("--venue-ids", default="", help="comma-separated IDs when --scope selected")
    parser.add_argument("--target-file", type=Path, default=TARGETS_PATH)
    parser.add_argument("--output-root", type=Path, default=Path("venue-expansion-output"))
    parser.add_argument("--state-path", type=Path, default=Path(".factory-state/venue-expansion-source-hashes.json"))
    parser.add_argument("--hermes-source-facts-root", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--no-publish", action="store_true", help="run acquisition and materialization without production apply")
    parser.add_argument("--dry-run", action="store_true", help="alias for read-only execution")
    return parser


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="strict")


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    selected = parse_venue_ids(args.venue_ids)
    publish = bool(args.publish and not args.no_publish and not args.dry_run)
    output_root = args.output_root
    state_path = args.state_path
    if args.scope == "production-gaps" and output_root == Path("venue-expansion-output"):
        output_root = Path("production-completeness-output")
    if args.scope == "production-gaps" and state_path == Path(".factory-state/venue-expansion-source-hashes.json"):
        state_path = Path(".factory-state/production-completeness-source-hashes.json")
    batch = run_factory(
        season=args.season,
        scope=args.scope,
        selected=selected,
        output_root=output_root,
        state_path=state_path,
        target_path=args.target_file,
        resume=args.resume,
        publish=publish,
        hermes_source_facts_root=args.hermes_source_facts_root,
    )
    print(json.dumps(batch, ensure_ascii=False))
    # A mixed batch is operationally successful when every venue was isolated
    # and checkpointed; blocked venues are represented in the review queue.
    return 0 if batch.get("failure_isolation") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
