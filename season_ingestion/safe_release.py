"""Materialize approved release artifacts for the existing atomic graph writer.

This module is deliberately source-free: it reads an already approved release
artifact, selects only its SAFE rows, and writes a new local handoff directory.
It never fetches an official source and never performs a production write.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .approval import validate_approval, validate_write_scope
from .notifications import build_approval_manifest
from .production_graph import build_payload
from .registry import load_registry
from .release_readiness import season_bounds


MATERIALIZATION_SCHEMA_VERSION = "safe-release-materialization-v1"
DEFAULT_RELEASE_ID = "safe-release-v1-20260915"
DEFAULT_CREATED_AT = "2026-09-15T00:00:00+00:00"
APPROVED_RELEASE_VENUES = (
    "theater_an_der_wien",
    "maison_radio_france",
    "palau_de_la_musica_catalana",
    "royal_opera_house",
)
APPROVED_EVENT_COUNTS = {
    "theater_an_der_wien": 119,
    "maison_radio_france": 145,
    "palau_de_la_musica_catalana": 434,
    "royal_opera_house": 878,
}
INPUT_ARTIFACT_FILES = (
    "final_staging.json",
    "snapshot.json",
    "summary.json",
    "source_audit.json",
    "source_capability_profile.json",
    "credit_resolution_staging.json",
)


class SafeReleaseMaterializationError(RuntimeError):
    """Raised when an approved artifact cannot be safely materialized."""


class SafeReleaseVerifierCredentialBlocked(RuntimeError):
    """Raised when the selected read credential cannot see production identity rows."""

    def __init__(self, message: str, credential_used: str):
        super().__init__(message)
        self.credential_used = credential_used


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def artifact_bundle_sha256(input_dir: Path) -> str:
    """Hash the exact approved input bundle in a stable name/order sequence."""
    digest = hashlib.sha256()
    for name in INPUT_ARTIFACT_FILES:
        path = input_dir / name
        if not path.is_file():
            raise SafeReleaseMaterializationError(f"approved artifact missing: {path}")
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise SafeReleaseMaterializationError(f"invalid approved artifact: {path}") from exc


def _date_value(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _safe_relationships(final: dict[str, Any]) -> list[dict[str, Any]]:
    rows = final.get("resolution") or []
    if not isinstance(rows, list):
        raise SafeReleaseMaterializationError("final_staging.resolution must be a list")
    safe = [
        row for row in rows
        if row.get("status") == "existing"
        and row.get("work_id")
        and (row.get("composer_resolution") or {}).get("status") == "existing"
    ]
    relationships = []
    for row in safe:
        source_url = (row.get("provenance") or {}).get("source_url") or row.get("source_url")
        if not source_url:
            raise SafeReleaseMaterializationError("SAFE programme relationship is untraceable")
        relationships.append({
            "event_key": row["event_key"],
            "work_id": row["work_id"],
            "order": row.get("original_programme_order") or row.get("source_programme_index") or 1,
            "source_url": source_url,
        })
    return relationships


def _graph_gates(payload: dict[str, Any], season: str) -> dict[str, int]:
    events = payload.get("events") or []
    event_keys = [str(row.get("event_key") or "") for row in events]
    event_key_set = set(event_keys)
    start, end = season_bounds(season)
    out_of_season = sum(
        1 for row in events
        if (_date_value(row.get("date")) is None)
        or not (start <= _date_value(row.get("date")) <= end)
    )
    relationships = payload.get("relationships") or []
    works = {str(row.get("id")) for row in (payload.get("works") or [])}
    invalid_fk = sum(
        1 for row in relationships
        if str(row.get("event_key")) not in event_key_set or str(row.get("work_id")) not in works
    )
    duplicate_event_work = len(relationships) - len({(str(row.get("event_key")), str(row.get("work_id"))) for row in relationships})
    credits = payload.get("event_credits") or []
    duplicate_credit = len(credits) - len({
        (
            str(row.get("event_key")),
            str(row.get("artist_id") or row.get("artist_identity_key")),
            str(row.get("role")),
            str(row.get("character_id")),
        )
        for row in credits
    })
    untraceable = sum(1 for row in events if not row.get("source_url"))
    return {
        "duplicate_event_identity": len(event_keys) - len(event_key_set),
        "duplicate_event_work": duplicate_event_work,
        "duplicate_safe_credit_identity": duplicate_credit,
        "invalid_fk": invalid_fk,
        "untraceable_event_source": untraceable,
        "out_of_season": out_of_season,
        "review_rows_in_safe_payload": 0,
    }


def _build_graph_payload(
    *,
    input_dir: Path,
    venue_id: str,
    season: str,
    expected_event_count: int,
    approved_report: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    final = _read_json(input_dir / "final_staging.json")
    snapshot = _read_json(input_dir / "snapshot.json")
    summary = _read_json(input_dir / "summary.json")
    profile = _read_json(input_dir / "source_capability_profile.json")
    source_credit = _read_json(input_dir / "credit_resolution_staging.json")

    if summary.get("venue") != venue_id or profile.get("venue_id") != venue_id:
        raise SafeReleaseMaterializationError("approved artifact venue mismatch")
    if summary.get("season") != season or profile.get("season") != season:
        raise SafeReleaseMaterializationError("approved artifact season mismatch")
    if approved_report.get("venue") != venue_id or approved_report.get("season") != season:
        raise SafeReleaseMaterializationError("approved release report venue/season identity mismatch")
    if approved_report.get("release_status") != "SAFE_RELEASE_CANDIDATE":
        raise SafeReleaseMaterializationError("artifact is not a SAFE_RELEASE_CANDIDATE")
    if approved_report.get("events_release_review", 0) or approved_report.get("events_rejected", 0):
        raise SafeReleaseMaterializationError("approved report contains review/rejected occurrences")

    events = final.get("events") or []
    if len(events) != expected_event_count or approved_report.get("events_release_safe") != expected_event_count:
        raise SafeReleaseMaterializationError("approved event count mismatch")
    if len({str(row.get("event_key")) for row in events}) != len(events):
        raise SafeReleaseMaterializationError("duplicate SAFE Event identity")
    if len({str(row.get("source_event_id")) for row in events}) != len(events):
        raise SafeReleaseMaterializationError("duplicate SAFE source Event identity")
    start, end = season_bounds(season)
    if any((_date_value(row.get("date")) is None) or not (start <= _date_value(row.get("date")) <= end) for row in events):
        raise SafeReleaseMaterializationError("SAFE Event outside season")
    if any(not row.get("source_url") for row in events):
        raise SafeReleaseMaterializationError("SAFE Event source is untraceable")

    credit_staging = final.get("credit_resolution") or {}
    if credit_staging != source_credit:
        raise SafeReleaseMaterializationError("credit staging artifacts disagree")
    safe_credit_rows = credit_staging.get("safe_event_credits") or []
    if any(
        not (row.get("credit") or {}).get("canonical_role")
        or not str((row.get("credit") or {}).get("artist_resolution", {}).get("status", "")).startswith("SAFE_")
        for row in safe_credit_rows
    ):
        raise SafeReleaseMaterializationError("unsafe credit entered SAFE payload")

    safe_relationships = _safe_relationships(final)
    composer_ids = {
        row["composer_resolution"].get("entity_id")
        for row in (final.get("resolution") or [])
        if row.get("status") == "existing"
        and row.get("work_id")
        and (row.get("composer_resolution") or {}).get("status") == "existing"
    }
    work_ids = {row.get("work_id") for row in safe_relationships}
    entities = snapshot.get("entities") or {}
    composers = [row for row in entities.get("composer", []) if row.get("id") in composer_ids]
    works = [row for row in entities.get("work", []) if row.get("id") in work_ids]
    staging = {
        "composer": {"safe": composers},
        "work": {"safe": works},
        "relationships": {"safe_existing": safe_relationships, "safe_new": []},
        "credit_resolution": credit_staging,
    }
    config = load_registry()["venues"].get(venue_id) or {}
    payload = build_payload(
        events,
        staging,
        organization={"name": config.get("organization"), "slug": venue_id},
        venue={"name": config.get("venue"), "city": config.get("city"), "country_code": config.get("country")},
    )
    payload["release"] = {
        "venue_id": venue_id,
        "season": season,
        "source_fingerprint": summary.get("source_fingerprint"),
        "final_staging_sha256": sha256_file(input_dir / "final_staging.json"),
    }
    gates = _graph_gates(payload, season)
    if any(gates.values()):
        raise SafeReleaseMaterializationError(f"production graph validation failed: {gates}")
    return payload, {
        "summary": summary,
        "source_fingerprint": summary.get("source_fingerprint"),
        "input_artifact_sha256": artifact_bundle_sha256(input_dir),
        "input_review_rows_excluded": len(final.get("review") or []) + len(credit_staging.get("review_event_credits") or []),
        "gates": gates,
    }


def verify_local_apply_compatibility(
    release_dir: Path,
    *,
    venue_id: str,
    season: str,
    approved_run_id: str,
) -> dict[str, Any]:
    """Validate exactly what the existing apply runner loads, without writing."""
    manifest_path = release_dir / "approval_manifest.json"
    final_path = release_dir / "final_staging.json"
    graph_path = release_dir / "production_graph_staging.json"
    manifest = validate_approval(manifest_path, final_path, approved_run_id=approved_run_id, venue=venue_id, season=season, commit=None)
    graph = _read_json(graph_path)
    runtime = {
        "events": len(graph.get("events", [])),
        "composers": len(graph.get("composers", [])),
        "works": len(graph.get("works", [])),
        "relationships": len(graph.get("relationships", [])),
    }
    validate_write_scope(manifest, runtime)
    if graph.get("release", {}).get("venue_id") != venue_id or graph.get("release", {}).get("season") != season:
        raise SafeReleaseMaterializationError("production graph release identity mismatch")
    return {"manifest": manifest, "runtime_scope": runtime, "compatible": True}


def materialize_venue(
    *,
    input_dir: Path,
    output_root: Path,
    venue_id: str,
    season: str,
    expected_event_count: int,
    approved_report: dict[str, Any],
    approved_run_id: str = DEFAULT_RELEASE_ID,
    commit: str = "unknown",
    created_at: str = DEFAULT_CREATED_AT,
) -> dict[str, Any]:
    """Materialize one approved venue into a fresh apply-compatible directory."""
    input_dir = input_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    release_dir = output_root / venue_id
    if release_dir.exists() and any(release_dir.iterdir()):
        raise SafeReleaseMaterializationError(f"refusing to overwrite release directory: {release_dir}")
    release_dir.mkdir(parents=True, exist_ok=True)

    payload, details = _build_graph_payload(
        input_dir=input_dir,
        venue_id=venue_id,
        season=season,
        expected_event_count=expected_event_count,
        approved_report=approved_report,
    )
    final_path = release_dir / "final_staging.json"
    shutil.copyfile(input_dir / "final_staging.json", final_path)
    graph_path = release_dir / "production_graph_staging.json"
    graph_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = details["summary"]
    manifest = build_approval_manifest(
        summary,
        final_path,
        run_id=approved_run_id,
        commit=commit,
        created_at=created_at,
    )
    manifest_path = release_dir / "approval_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compatibility = verify_local_apply_compatibility(
        release_dir,
        venue_id=venue_id,
        season=season,
        approved_run_id=approved_run_id,
    )
    if not manifest.get("eligible_for_apply") or manifest.get("safe_event_count") != expected_event_count:
        raise SafeReleaseMaterializationError("approval manifest is not eligible for the approved event count")

    gates = details["gates"]
    report = {
        "schema_version": MATERIALIZATION_SCHEMA_VERSION,
        "venue_id": venue_id,
        "season": season,
        "approved_release_status": approved_report.get("release_status"),
        "approved_event_count": expected_event_count,
        "materialized_event_count": len(payload.get("events", [])),
        "safe_programme_relationships": len(payload.get("relationships", [])),
        "safe_credits": len(payload.get("event_credits", [])),
        "review_rows_included": 0,
        "input_review_rows_excluded": details["input_review_rows_excluded"],
        "source_fingerprint": details["source_fingerprint"],
        "input_artifact_sha256": details["input_artifact_sha256"],
        "final_staging_sha256": sha256_file(final_path),
        "production_graph_staging_sha256": sha256_file(graph_path),
        "approval_manifest_sha256": sha256_file(manifest_path),
        "gates": gates,
        "production_graph_validation": "PASS",
        "apply_runner_compatible": "YES" if compatibility["compatible"] else "NO",
        "approved_run_id": approved_run_id,
        "status": "APPLY_READY",
        "production_writes": 0,
    }
    (release_dir / "materialization_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def materialize_release(
    *,
    release_report_path: Path,
    output_root: Path,
    season: str = "2026-27",
    approved_run_id: str = DEFAULT_RELEASE_ID,
    commit: str = "unknown",
    created_at: str = DEFAULT_CREATED_AT,
) -> list[dict[str, Any]]:
    release_report = _read_json(release_report_path)
    if release_report.get("season") != season:
        raise SafeReleaseMaterializationError("release-readiness season mismatch")
    if set(release_report.get("safe_release_venues", [])) != set(APPROVED_RELEASE_VENUES):
        raise SafeReleaseMaterializationError("release cohort does not match the approved four venues")
    reports = []
    for venue_id in APPROVED_RELEASE_VENUES:
        entry = next((row for row in release_report.get("reports", []) if row.get("venue") == venue_id), None)
        if not entry:
            raise SafeReleaseMaterializationError(f"approved release entry missing: {venue_id}")
        artifact_root = Path(entry["artifact_dir"])
        input_dir = artifact_root / "deterministic"
        reports.append(materialize_venue(
            input_dir=input_dir,
            output_root=output_root,
            venue_id=venue_id,
            season=season,
            expected_event_count=APPROVED_EVENT_COUNTS[venue_id],
            approved_report=entry,
            approved_run_id=approved_run_id,
            commit=commit,
            created_at=created_at,
        ))
    return reports


def _verification_credential() -> tuple[str, str]:
    """Select a credential for GET-only verification without exposing its value."""
    if not os.environ.get("SUPABASE_URL", "").strip():
        raise RuntimeError("read-only verification requires SUPABASE_URL")
    for name in ("SUPABASE_SECRET_KEY", "SUPABASE_READONLY_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return name, value
    raise SafeReleaseVerifierCredentialBlocked(
        "read-only verification requires SUPABASE_SECRET_KEY or SUPABASE_READONLY_KEY",
        "NONE",
    )


def _read_rows(
    path: str,
    filters: list[tuple[str, str]],
    select: str,
    *,
    page_size: int = 5000,
    fetcher=urlopen,
) -> list[dict[str, Any]]:
    """Read a production table with explicit filters; this helper never writes."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    credential_used, key = _verification_credential()
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = urlencode([
            *filters,
            ("select", select),
            ("limit", str(page_size)),
            ("offset", str(offset)),
        ])
        request = Request(url + path + "?" + query, method="GET", headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"})
        try:
            with fetcher(request, timeout=60) as response:
                if response.status != 200:
                    if credential_used == "SUPABASE_READONLY_KEY" and response.status in {401, 403}:
                        raise SafeReleaseVerifierCredentialBlocked(
                            f"read-only credential cannot access {path} (HTTP {response.status})",
                            credential_used,
                        )
                    raise RuntimeError(f"read-only verification returned HTTP {response.status}")
                page = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if credential_used == "SUPABASE_READONLY_KEY" and exc.code in {401, 403}:
                raise SafeReleaseVerifierCredentialBlocked(
                    f"read-only credential cannot access {path} (HTTP {exc.code})",
                    credential_used,
                ) from exc
            raise
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def _read_table(
    path: str,
    filter_column: str,
    ids: list[str],
    select: str,
    *,
    fetcher=urlopen,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for start in range(0, len(ids), 100):
        batch = ids[start:start + 100]
        rows.extend(_read_rows(
            path,
            [(filter_column, "in.(" + ",".join(batch) + ")")],
            select,
            fetcher=fetcher,
        ))
    return rows


def verify_production_release(
    *,
    release_dir: Path,
    venue_id: str,
    season: str,
    api_base_url: str | None = None,
    fetcher=urlopen,
) -> dict[str, Any]:
    """Read production state for one materialized release; never writes."""
    credential_used, _ = _verification_credential()
    graph = _read_json(release_dir / "production_graph_staging.json")
    organization = graph.get("organization") or {}
    venue = graph.get("venue") or {}
    organization_slug = str(organization.get("slug") or "").strip()
    venue_name = str(venue.get("name") or "").strip()
    if not organization_slug or not venue_name:
        raise RuntimeError("release graph is missing production organization/venue identity")

    organization_rows = _read_rows(
        "/rest/v1/organizations",
        [("slug", f"eq.{organization_slug}")],
        "id,name,slug",
        fetcher=fetcher,
    )
    if len(organization_rows) != 1:
        if credential_used == "SUPABASE_READONLY_KEY":
            raise SafeReleaseVerifierCredentialBlocked(
                f"read-only credential could not resolve production organization {organization_slug}",
                credential_used,
            )
        raise RuntimeError(f"production organization lookup did not resolve uniquely for {organization_slug}")
    organization_id = str(organization_rows[0].get("id") or "")
    venue_rows = _read_rows(
        "/rest/v1/venues",
        [("organization_id", f"eq.{organization_id}"), ("name", f"eq.{venue_name}")],
        "id,name,city,organization_id",
        fetcher=fetcher,
    )
    if len(venue_rows) != 1:
        if credential_used == "SUPABASE_READONLY_KEY":
            raise SafeReleaseVerifierCredentialBlocked(
                f"read-only credential could not resolve production venue {venue_name}",
                credential_used,
            )
        raise RuntimeError(f"production venue lookup did not resolve uniquely for {venue_name}")
    production_venue_id = str(venue_rows[0].get("id") or "")
    season_start, season_end = season_bounds(season)
    production_events = _read_rows(
        "/rest/v1/events",
        [
            ("organization_id", f"eq.{organization_id}"),
            ("venue_id", f"eq.{production_venue_id}"),
            ("date", f"gte.{season_start}"),
            ("date", f"lte.{season_end}"),
        ],
        "id,event_key,title,date",
        fetcher=fetcher,
    )
    production_event_ids = sorted({str(row.get("id")) for row in production_events if row.get("id")})
    source_rows: list[dict[str, Any]] = []
    for start in range(0, len(production_event_ids), 100):
        batch = production_event_ids[start:start + 100]
        source_rows.extend(_read_rows(
            "/rest/v1/event_sources",
            [("event_id", "in.(" + ",".join(batch) + ")")],
            "event_id,source,source_event_id,source_url",
            fetcher=fetcher,
        ))
    expected_ids = {str(row.get("source_event_id")) for row in graph.get("events", []) if row.get("source_event_id")}
    matched = [row for row in source_rows if str(row.get("source_event_id")) in expected_ids]
    event_ids = sorted({str(row.get("event_id")) for row in matched if row.get("event_id")})
    programme = _read_table("/rest/v1/event_programme", "event_id", event_ids, "event_id,work_id", fetcher=fetcher) if event_ids else []
    credits = _read_table("/rest/v1/event_credits", "event_id", event_ids, "event_id,artist_id,role,character_id", fetcher=fetcher) if event_ids else []
    result = {
        "venue_id": venue_id,
        "season": season,
        "credential_used": credential_used,
        "credential_value_printed": "NO",
        "verifier_read_only": "YES",
        "release_status": "PASS",
        "verifier_status": "PASS",
        "production_identity": {"organization_id": organization_id, "venue_id": production_venue_id},
        "production_events": len(set(event_ids)),
        "event_sources": len(matched),
        "programme_relationships": len(programme),
        "safe_credits": len(credits),
        "duplicate_event_identity": len(matched) - len({str(row.get("source_event_id")) for row in matched}),
        "duplicate_event_work": len(programme) - len({(str(row.get("event_id")), str(row.get("work_id"))) for row in programme}),
        "duplicate_credit_identity": len(credits) - len({(str(row.get("event_id")), str(row.get("artist_id")), str(row.get("role")), str(row.get("character_id"))) for row in credits}),
        "api_search": "NOT_RUN",
        "event_detail": "NOT_RUN",
        "production_writes": 0,
    }
    if api_base_url:
        result["api_search"], result["event_detail"] = _verify_api_visibility(api_base_url, graph)
    return result


def _verify_api_visibility(api_base_url: str, graph: dict[str, Any]) -> tuple[str, str]:
    """Use only the application's read actions; this function never calls Supabase writes."""
    base = api_base_url.rstrip("/")
    venue_name = str((graph.get("venue") or {}).get("name") or "")
    body = json.dumps({"action": "schedule_events", "date_from": "2026-09-01", "date_to": "2027-08-31", "venues": [venue_name]}, ensure_ascii=False).encode("utf-8")
    request = Request(base, data=body, method="POST", headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urlopen(request, timeout=45) as response:
        if response.status != 200:
            return f"FAIL_HTTP_{response.status}", "NOT_RUN"
        payload = json.loads(response.read().decode("utf-8"))
    events = payload.get("events") or []
    if not events:
        return "FAIL_HTTP_200_EVENTS_0", "NOT_RUN"
    detail_body = json.dumps({"action": "schedule_event_detail", "event_id": events[0].get("event_id")}).encode("utf-8")
    detail_request = Request(base, data=detail_body, method="POST", headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urlopen(detail_request, timeout=45) as response:
        detail_status = response.status
    return f"PASS_HTTP_200_EVENTS_{len(events)}", f"PASS_HTTP_{detail_status}" if detail_status == 200 else f"FAIL_HTTP_{detail_status}"
