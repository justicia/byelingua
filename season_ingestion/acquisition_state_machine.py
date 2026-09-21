"""Three-level official source acquisition state machine.

The state machine owns orchestration and classification only.  It reuses the
existing Hermes source-facts contract and deterministic PDF framework; it
does not add fields to that contract or perform production writes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import requests

from jobs.hermes_acquire_worker import _normalize_programme_order, validate_source_facts
from season_ingestion.hermes_acquisition import (
    HERMES_MALFORMED_OUTPUT,
    HERMES_SOURCE_BLOCKED,
    HERMES_TIMEOUT,
    HERMES_VALIDATION_FAILED,
    HermesAcquisitionError,
    acquire_source_facts,
    acquire_source_discovery,
    build_request,
)
from season_ingestion.pdf_acquisition import PdfAcquisitionError, _pdf_page_count, extract_pdf_pages
from season_ingestion.pdf_batch import PDF_URLS, run_pdf_batch_venue
from season_ingestion.pipeline import run_pipeline
from season_ingestion.tonhalle_acquisition import acquire_source_facts as acquire_tonhalle_source_facts
from season_ingestion.generic_adapters import (
    build_capability_profile,
    classify_acquisition_status,
    classify_canonical_status,
    classify_enrichment_status,
    write_capability_profile,
)


HERMES_PASS = "HERMES_PASS"
HERMES_PARTIAL = "HERMES_PARTIAL"
# Backward-compatible alias for callers that used the old generic status.
HERMES_BLOCKED = HERMES_SOURCE_BLOCKED

PDF_FULL_SOURCE = "PDF_FULL_SOURCE"
PDF_ENRICHMENT_SOURCE = "PDF_ENRICHMENT_SOURCE"
PDF_FAILED = "PDF_FAILED"

SOURCE_READY = "SOURCE_READY"
SOURCE_PARTIAL = "SOURCE_PARTIAL"
ADAPTER_REQUIRED = "ADAPTER_REQUIRED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
HUMAN_PDF_REQUIRED = "HUMAN_PDF_REQUIRED"
NO_OFFICIAL_PDF = "NO_OFFICIAL_PDF"
BLOCKED = "BLOCKED"

DEFAULT_MANUAL_ROOT = Path("manual_sources")
DEFAULT_DISCOVERY_TIMEOUT_SECONDS = 30


class AcquisitionStateError(RuntimeError):
    """A state-machine orchestration failure."""


def _event_count(facts: dict[str, Any] | None) -> int:
    return len(facts.get("events", [])) if isinstance(facts, dict) and isinstance(facts.get("events"), list) else 0


def _programme_count(facts: dict[str, Any] | None) -> int:
    if not isinstance(facts, dict):
        return 0
    return sum(len(event.get("programme", [])) for event in facts.get("events", []) if isinstance(event, dict))


def _credit_count(facts: dict[str, Any] | None) -> int:
    if not isinstance(facts, dict):
        return 0
    return sum(len(event.get("credits", [])) for event in facts.get("events", []) if isinstance(event, dict))


def _set_report_dimensions(
    report: dict[str, Any],
    *,
    source_capability: str | None = None,
    source_discovered: bool = False,
    deterministic_attempted: bool = False,
    useful_occurrence_source: bool = True,
    pdf_known: bool = False,
    pdf_download_failed: bool = False,
    canonical_passed: bool = False,
    review_items: int = 0,
) -> None:
    report["acquisition_status"] = classify_acquisition_status(
        events=int(report.get("merged_events", 0) or 0),
        source_capability=source_capability,
        source_discovered=source_discovered,
        deterministic_attempted=deterministic_attempted,
        useful_occurrence_source=useful_occurrence_source,
        pdf_known=pdf_known,
        pdf_download_failed=pdf_download_failed,
    )
    report["enrichment_status"] = classify_enrichment_status(
        programme=int(report.get("merged_programme", 0) or 0),
        credits=int(report.get("merged_credits", 0) or 0),
    )
    report["canonical_status"] = classify_canonical_status(
        global_master=str(report.get("global_master") or "NOT_RUN"),
        review_items=review_items,
        passed=canonical_passed,
    )


def assess_hermes_quality(
    facts: dict[str, Any] | None,
    *,
    error: str | None = None,
    status: str | None = None,
) -> tuple[str, str | None]:
    """Classify Hermes using contract validity plus explicit coverage signals."""
    if status in {
        HERMES_SOURCE_BLOCKED,
        HERMES_TIMEOUT,
        HERMES_MALFORMED_OUTPUT,
        HERMES_VALIDATION_FAILED,
    }:
        return status, error
    if error:
        return HERMES_BLOCKED, error
    if not isinstance(facts, dict):
        return HERMES_BLOCKED, "Hermes returned no source facts"
    try:
        validate_source_facts(facts)
    except Exception as exc:
        return HERMES_BLOCKED, f"invalid source-facts: {exc}"
    events = facts.get("events") or []
    if not events:
        return HERMES_BLOCKED, "events=0"

    contract = facts.get("source_contract") or {}
    quality = contract.get("coverage_quality") if isinstance(contract, dict) else None
    quality = quality if isinstance(quality, dict) else {}
    status = str(quality.get("status") or quality.get("classification") or "").casefold()
    if status in {"partial", "incomplete", "blocked", "review", "unknown"}:
        return HERMES_PARTIAL, f"coverage_quality={status}"
    if quality.get("complete") is False or quality.get("season_complete") is False:
        return HERMES_PARTIAL, "coverage marked incomplete"
    for key in ("coverage_ratio", "season_coverage_ratio"):
        value = quality.get(key)
        if isinstance(value, (int, float)) and value < 0.8:
            return HERMES_PARTIAL, f"{key}={value}"
    expected = quality.get("expected_occurrence_count")
    if isinstance(expected, int) and expected > 0 and len(events) < max(1, int(expected * 0.8)):
        return HERMES_PARTIAL, f"events={len(events)} below expected coverage={expected}"

    # The contract itself guarantees explicit date/title/source URL for every
    # event.  Without a negative coverage signal, this is a credible automatic
    # result; venue-specific coverage evidence can still downgrade it above.
    return HERMES_PASS, None


def _known_pdf_records(config: dict[str, Any], venue_id: str, season: str) -> list[dict[str, Any]]:
    records = []
    for value in config.get("official_pdf_sources", []) or []:
        if not isinstance(value, str) or not value.strip():
            continue
        records.append({
            "venue_id": venue_id,
            "pdf_url": value.strip(),
            "document_title": None,
            "season": season,
            "document_type": "official_pdf_candidate",
            "coverage": "undetermined",
            "download_status": "KNOWN",
            "discovery": "registry",
        })
    return records


def _is_pdf_candidate(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.casefold()
    return path.endswith(".pdf") or "/pdf" in path or "download" in path or "brochure" in path or "programme" in path


def discover_official_pdf_sources(
    config: dict[str, Any],
    *,
    venue_id: str,
    season: str,
    session: Any = requests,
    timeout_seconds: int = DEFAULT_DISCOVERY_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Discover registry and directly linked official PDF candidates."""
    records = _known_pdf_records(config, venue_id, season)
    known_urls = {record["pdf_url"] for record in records}
    page_urls = [config.get("official_source"), config.get("listing_source")]
    official_hosts = {
        urlparse(str(url)).netloc.casefold()
        for url in page_urls
        if isinstance(url, str) and url.strip()
    }
    for page_url in page_urls:
        if not isinstance(page_url, str) or not page_url.strip():
            continue
        try:
            response = session.get(
                page_url,
                timeout=timeout_seconds,
                headers={"User-Agent": "Byelingua official PDF discovery/1.0", "Accept": "text/html,application/xhtml+xml"},
            )
            response.raise_for_status()
            html = response.text
        except Exception:
            continue
        hrefs = re.findall(r"(?:href|src)=[\"']([^\"']+)[\"']", html, flags=re.I)
        for href in hrefs:
            absolute = urljoin(page_url, href.strip())
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"} or not _is_pdf_candidate(absolute):
                continue
            # A candidate found on an official page is an officially linked
            # asset even when its CDN hostname differs from the venue host.
            if absolute in known_urls:
                continue
            if parsed.netloc.casefold() not in official_hosts and not href.casefold().endswith(".pdf"):
                continue
            known_urls.add(absolute)
            records.append({
                "venue_id": venue_id,
                "pdf_url": absolute,
                "document_title": None,
                "season": season,
                "document_type": "official_linked_pdf_candidate",
                "coverage": "undetermined",
                "download_status": "DISCOVERED",
                "discovery": "official_page",
            })
    return records


def manual_pdf_path(*, manual_root: Path, venue_id: str, season: str) -> Path:
    return manual_root / venue_id / season / "source.pdf"


def _manual_pdf_artifact(path: Path, *, source_url: str) -> dict[str, Any]:
    payload = path.read_bytes()
    if not payload.startswith(b"%PDF-"):
        raise PdfAcquisitionError("manual PDF is missing the %PDF- header")
    sha256 = hashlib.sha256(payload).hexdigest()
    return {
        "source_url": source_url,
        "path": str(path),
        "sha256": sha256,
        "byte_size": len(payload),
        "page_count": _pdf_page_count(path),
    }


def _fact_key(event: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(event.get("date") or ""),
        str(event.get("start_time") or ""),
        " ".join(str(event.get("title") or "").casefold().split()),
        " ".join(str(event.get("room") or "").casefold().split()),
    )


def _row_key(row: dict[str, Any], kind: str) -> tuple[str, ...]:
    provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    if kind == "programme":
        return (
            " ".join(str(row.get("source_title") or "").casefold().split()),
            " ".join(str(row.get("composer") or "").casefold().split()),
            str(provenance.get("source_url") or row.get("source_url") or ""),
            str(provenance.get("pdf_page") or ""),
            str(provenance.get("source_field") or ""),
        )
    return (
        " ".join(str(row.get("artist_name") or "").casefold().split()),
        " ".join(str(row.get("source_role") or "").casefold().split()),
        " ".join(str(row.get("function") or "").casefold().split()),
        str(provenance.get("source_url") or row.get("source_url") or ""),
        str(provenance.get("pdf_page") or ""),
    )


def _append_source_record(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    target_provenance = target.setdefault("provenance", {})
    incoming_provenance = incoming.get("provenance") if isinstance(incoming.get("provenance"), dict) else {}
    source_record = {
        key: incoming_provenance.get(key)
        for key in ("source_url", "pdf_page", "pdf_sha256", "source_field")
        if incoming_provenance.get(key) is not None
    }
    if not source_record:
        source_record = {"source_url": incoming.get("source_url")}
    records = target_provenance.setdefault("source_records", [])
    if source_record not in records:
        records.append(source_record)


def merge_official_source_facts(
    source_facts: list[tuple[str, dict[str, Any]]],
    *,
    request: dict[str, Any],
) -> dict[str, Any]:
    """Merge Hermes/HTML/PDF facts while preserving per-fact provenance."""
    usable = []
    for label, facts in source_facts:
        validate_source_facts(facts)
        usable.append((label, facts))
    if not usable:
        raise AcquisitionStateError("no validated source facts to merge")
    base_facts = next((facts for _, facts in usable if _event_count(facts)), usable[0][1])
    merged = copy.deepcopy(base_facts)
    merged["venue_id"] = request["venue_id"]
    merged["season"] = request["season"]
    merged["source_id"] = request.get("source_id", request["venue_id"])
    merged["official_source_url"] = request["official_source_url"]
    merged.setdefault("source_contract", {})
    merged["source_contract"]["acquisition_sources"] = []
    event_index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    merged["events"] = []
    for label, facts in usable:
        merged["source_contract"]["acquisition_sources"].append({
            "label": label,
            "source_type": facts.get("source_type"),
            "official_source_url": facts.get("official_source_url"),
            "events": _event_count(facts),
        })
        for raw_event in facts.get("events", []):
            event = copy.deepcopy(raw_event)
            key = _fact_key(event)
            existing = event_index.get(key)
            if existing is None:
                event_index[key] = event
                merged["events"].append(event)
                continue
            _append_source_record(existing, event)
            for collection, kind in (("programme", "programme"), ("credits", "credit")):
                rows = existing.setdefault(collection, [])
                seen = {_row_key(row, kind) for row in rows}
                for row in event.get(collection, []):
                    if _row_key(row, kind) not in seen:
                        rows.append(copy.deepcopy(row))
                        seen.add(_row_key(row, kind))
    _normalize_programme_order(merged)
    validate_source_facts(merged)
    return merged


def _default_hermes_runner(request: dict[str, Any], *, artifact_dir: Path | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    try:
        return {"facts": acquire_source_facts(request, artifact_dir=artifact_dir, metadata=metadata), **metadata}
    except Exception as exc:
        result = {"error": str(exc), **metadata}
        if isinstance(exc, HermesAcquisitionError):
            result.update({
                "status": exc.status,
                "attempts": exc.attempts,
                "raw_output_saved": "YES" if exc.raw_output_saved else "NO",
                "raw_output_paths": exc.raw_output_paths,
            })
        return result


def _default_discovery_runner(request: dict[str, Any], *, artifact_dir: Path | None = None) -> dict[str, Any]:
    """Use Hermes only to locate an official deterministic source."""
    metadata: dict[str, Any] = {}
    try:
        discovery = acquire_source_discovery(
            {**request, "hermes_mode": "source_discovery"},
            artifact_dir=(artifact_dir / "discovery") if artifact_dir is not None else None,
            metadata=metadata,
        )
        return {
            "source_discovery": "PASS",
            "discovered_mode": discovery.get("discovered_mode"),
            "discovered_endpoint": discovery.get("discovered_endpoint"),
            "discovery": discovery,
            **metadata,
        }
    except Exception as exc:
        result = {"error": str(exc), "source_discovery": "FAIL", **metadata}
        if isinstance(exc, HermesAcquisitionError):
            result.update({
                "status": exc.status,
                "attempts": exc.attempts,
                "raw_output_saved": "YES" if exc.raw_output_saved else "NO",
                "raw_output_paths": exc.raw_output_paths,
            })
        return result


def _default_deterministic_runner(
    *, venue_id: str, season: str, config: dict[str, Any], discovery: dict[str, Any], output_dir: Path,
) -> dict[str, Any]:
    """Run the existing canonical adapter against a discovered official endpoint."""
    endpoint = str(discovery.get("discovered_endpoint") or "").strip()
    if not endpoint:
        raise AcquisitionStateError("source discovery returned no endpoint")
    season_start = f"{str(season).split('-', 1)[0]}-09-01"
    endpoint = endpoint.replace("{YYYY-MM-DD}", season_start).replace("YYYY-MM-DD", season_start)
    endpoint = endpoint.replace("{value}", "alle")
    endpoint = endpoint.replace("{page}", "1").replace("p=N", "p=1")
    overrides = {
        "official_source": endpoint,
        "listing_source": endpoint,
        "discovered_mode": discovery.get("discovered_mode"),
        "discovered_endpoint": endpoint,
    }
    if str(discovery.get("discovered_mode") or "").upper() == "API":
        # The observed API is the complete occurrence source.  Keep optional
        # detail enrichment bounded; it must not turn a full calendar into an
        # unbounded serial crawl.
        overrides["max_detail_pages"] = 0
    summary = run_pipeline(
        venue=venue_id,
        season=season,
        mode="dry-run",
        scope="full-season",
        output_dir=output_dir,
        config_override=overrides,
        allow_hermes_fallback=False,
    )
    counts = summary.get("counts") or {}
    detail = summary.get("detail_enrichment") or {}
    events = int(counts.get("events", 0) or 0)
    return {
        "events": events,
        "programme": int(detail.get("programme_items", 0) or 0),
        "credits": int(detail.get("credits_total", 0) or 0),
        "global_master": summary.get("global_master_preflight", "NOT_RUN"),
        "source_capability": summary.get("source_capability", "FAILED"),
        "source_family": summary.get("source_family"),
        "acquisition_status": summary.get("acquisition_status"),
        "enrichment_status": summary.get("enrichment_status"),
        "canonical_status": summary.get("canonical_status"),
        "capability_profile": summary.get("source_capability_profile"),
        "review_items": int((summary.get("counts") or {}).get("review_items", 0) or 0),
        # A preflight can pass with an empty adapter result.  Source readiness
        # always requires at least one explicit occurrence.
        "passed": bool(summary.get("passed")) and events > 0,
    }


def _default_tonhalle_runner(request: dict[str, Any], *, artifact_dir: Path | None = None) -> dict[str, Any]:
    """Use Hermes for compact endpoint discovery, then fetch Tonhalle deterministically."""
    metadata: dict[str, Any] = {}
    discovery_request = dict(request)
    discovery_request["hermes_mode"] = "source_discovery"
    try:
        discovery = acquire_source_discovery(
            discovery_request,
            artifact_dir=(artifact_dir / "discovery") if artifact_dir is not None else None,
            metadata=metadata,
        )
    except Exception as exc:
        result = {"error": str(exc), "source_discovery": "FAIL", **metadata}
        if isinstance(exc, HermesAcquisitionError):
            result.update({
                "status": exc.status,
                "attempts": exc.attempts,
                "raw_output_saved": "YES" if exc.raw_output_saved else "NO",
                "raw_output_paths": exc.raw_output_paths,
            })
        return result

    result: dict[str, Any] = {
        "source_discovery": "PASS",
        "discovered_mode": discovery.get("discovered_mode"),
        "discovered_endpoint": discovery.get("discovered_endpoint"),
        "discovery": discovery,
        **metadata,
    }
    try:
        tonhalle_config = dict(request)
        tonhalle_config["official_source"] = request["official_source_url"]
        tonhalle_config["listing_source"] = request.get("listing_source_url") or request["official_source_url"]
        tonhalle_config["venue_id"] = request["venue_id"]
        tonhalle_config["source_id"] = request.get("source_id", request["venue_id"])
        facts, deterministic_metadata = acquire_tonhalle_source_facts(
            config=tonhalle_config,
            season=str(request["season"]),
            discovery=discovery,
        )
    except Exception as exc:
        result.update({"error": f"Tonhalle deterministic acquisition failed: {exc}"})
        return result
    result.update({"facts": facts, **deterministic_metadata, "status": HERMES_PASS})
    return result


def _default_pdf_runner(
    *,
    venue_id: str,
    season: str,
    config: dict[str, Any],
    candidate: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    # Reuse the same deterministic venue adapter used by the PDF batch.  A
    # candidate override lets discovery and human-provided files use the same
    # code path; no venue-specific manual workflow is introduced here.  The
    # adapter also accepts official URLs discovered at runtime, so new venues
    # do not need a second hard-coded PDF registry.
    return run_pdf_batch_venue(
        venue_id=venue_id,
        config=config,
        season=season,
        output_dir=output_dir,
        pdf_url=candidate.get("pdf_url"),
        manual_pdf_path_value=candidate.get("manual_path"),
        include_facts=True,
    )


def run_acquisition_state_machine(
    *,
    venue_id: str,
    season: str,
    config: dict[str, Any],
    output_dir: Path,
    manual_root: Path = DEFAULT_MANUAL_ROOT,
    hermes_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    pdf_runner: Callable[..., dict[str, Any]] | None = None,
    pdf_discoverer: Callable[..., list[dict[str, Any]]] = discover_official_pdf_sources,
    deterministic_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run Level 1 Hermes, Level 2 automatic PDF, then Level 3 human PDF."""
    output_dir.mkdir(parents=True, exist_ok=True)
    request = build_request(venue=venue_id, season=season, config=config, reason="acquisition_state_machine")
    hermes_runner = hermes_runner or _default_hermes_runner
    pdf_runner = pdf_runner or _default_pdf_runner
    deterministic_runner = deterministic_runner or _default_deterministic_runner
    if hermes_runner is _default_hermes_runner:
        if venue_id == "tonhalle_zurich":
            hermes_result = _default_tonhalle_runner(request, artifact_dir=output_dir / "hermes") or {}
        else:
            hermes_result = _default_discovery_runner(request, artifact_dir=output_dir / "hermes") or {}
    else:
        hermes_result = hermes_runner(request) or {}
    hermes_facts = hermes_result.get("facts") if isinstance(hermes_result, dict) else None
    hermes_status, hermes_reason = assess_hermes_quality(
        hermes_facts,
        error=hermes_result.get("error") if isinstance(hermes_result, dict) else "Hermes runner returned no result",
        status=hermes_result.get("status") if isinstance(hermes_result, dict) else None,
    )
    hermes_valid_facts = None
    if isinstance(hermes_facts, dict):
        try:
            validate_source_facts(hermes_facts)
            hermes_valid_facts = hermes_facts
        except Exception:
            hermes_valid_facts = None
    discovery_only = bool(
        isinstance(hermes_result, dict)
        and hermes_result.get("source_discovery") == "PASS"
        and hermes_valid_facts is None
    )
    if discovery_only:
        hermes_status, hermes_reason = HERMES_PASS, None
    initial_profile = build_capability_profile(venue_id=venue_id, season=season, config=config)
    report: dict[str, Any] = {
        "venue": venue_id,
        "season": season,
        "hermes_status": hermes_status,
        "hermes_attempts": hermes_result.get("attempts", 0) if isinstance(hermes_result, dict) else 0,
        "raw_output_saved": hermes_result.get("raw_output_saved", "NO") if isinstance(hermes_result, dict) else "NO",
        "hermes_events": _event_count(hermes_facts),
        "source_discovery": hermes_result.get("source_discovery", "NOT_ATTEMPTED") if isinstance(hermes_result, dict) else "NOT_ATTEMPTED",
        "discovered_mode": hermes_result.get("discovered_mode") if isinstance(hermes_result, dict) else None,
        "discovered_endpoint": hermes_result.get("discovered_endpoint") if isinstance(hermes_result, dict) else None,
        "acquisition_mode": None,
        "source_family": initial_profile["occurrence_source"]["family"],
        "occurrence_source_family": initial_profile.get("occurrence_source_family", initial_profile["occurrence_source"]["family"]),
        "enrichment_source_families": initial_profile.get("enrichment_source_families", []),
        "source_capability_profile": initial_profile,
        "acquisition_status": "SOURCE_BLOCKED",
        "enrichment_status": "NOT_AVAILABLE",
        "canonical_status": "REVIEW_REQUIRED",
        "pdf_discovered": "NO",
        "pdf_download": "NOT_ATTEMPTED" if hermes_status == HERMES_PASS else "NOT_ATTEMPTED",
        "pdf_type": "NONE",
        "pdf_events": 0,
        "pdf_programme": 0,
        "pdf_credits": 0,
        "merged_events": 0,
        "merged_programme": 0,
        "merged_credits": 0,
        "global_master": "NOT_RUN",
        "final_status": SOURCE_READY if hermes_status == HERMES_PASS and hermes_valid_facts else BLOCKED,
        "human_action": "NONE",
        "production_writes": 0,
        "hermes_error": hermes_reason,
        "blocker": hermes_status if hermes_status in {
            HERMES_SOURCE_BLOCKED,
            HERMES_TIMEOUT,
            HERMES_MALFORMED_OUTPUT,
            HERMES_VALIDATION_FAILED,
        } else hermes_reason,
    }
    write_capability_profile(output_dir, report["source_capability_profile"])
    if discovery_only:
        report["acquisition_mode"] = report["discovered_mode"]
        try:
            deterministic = deterministic_runner(
                venue_id=venue_id,
                season=season,
                config=config,
                discovery=hermes_result.get("discovery") or hermes_result,
                output_dir=output_dir / "deterministic",
            ) or {}
            report.update({
                "merged_events": int(deterministic.get("events", 0) or 0),
                "merged_programme": int(deterministic.get("programme", 0) or 0),
                "merged_credits": int(deterministic.get("credits", 0) or 0),
                "global_master": deterministic.get("global_master", "NOT_RUN"),
            })
            if deterministic.get("source_family"):
                report["source_family"] = deterministic["source_family"]
            if deterministic.get("capability_profile"):
                report["source_capability_profile"] = deterministic["capability_profile"]
                report["source_family"] = report["source_capability_profile"].get("occurrence_source_family", report["source_family"])
                report["occurrence_source_family"] = report["source_capability_profile"].get("occurrence_source_family", report["source_family"])
                report["enrichment_source_families"] = report["source_capability_profile"].get("enrichment_source_families", [])
                write_capability_profile(output_dir, report["source_capability_profile"])
            _set_report_dimensions(
                report,
                source_capability=deterministic.get("source_capability"),
                source_discovered=True,
                deterministic_attempted=True,
                useful_occurrence_source=True,
                canonical_passed=bool(deterministic.get("passed")),
                review_items=int(deterministic.get("review_items", 0) or 0),
            )
            if report["merged_events"] and deterministic.get("source_capability") == "SOURCE_PASS":
                report.update({"final_status": SOURCE_READY if report["canonical_status"] == "SAFE" else REVIEW_REQUIRED, "blocker": None if report["canonical_status"] == "SAFE" else "canonical review remains", "pdf_reports": []})
                _write_json(output_dir / "state-report.json", report)
                return report
            if report["merged_events"]:
                report["final_status"] = REVIEW_REQUIRED
                report["blocker"] = "deterministic occurrence coverage requires review"
            else:
                # A discovered official source with no parsed occurrences is
                # an adapter gap, never a reason to request a human PDF.
                report["acquisition_status"] = ADAPTER_REQUIRED
                report["final_status"] = BLOCKED
                report["blocker"] = "ADAPTER_REQUIRED: deterministic source produced no explicit occurrences"
            report["pdf_reports"] = []
            _write_json(output_dir / "state-report.json", report)
            return report
        except Exception as exc:
            report["acquisition_status"] = ADAPTER_REQUIRED
            report["final_status"] = BLOCKED
            report["blocker"] = f"ADAPTER_REQUIRED: deterministic {report['discovered_mode'] or 'source'} acquisition failed: {exc}"
            report["pdf_reports"] = []
            _write_json(output_dir / "state-report.json", report)
            return report
    if hermes_status == HERMES_PASS and hermes_valid_facts:
        merged = merge_official_source_facts([("hermes", hermes_valid_facts)], request=request)
        report.update({
            "merged_events": _event_count(merged),
            "merged_programme": _programme_count(merged),
            "merged_credits": _credit_count(merged),
            "blocker": None,
            "acquisition_mode": "HERMES_SOURCE_FACTS",
        })
        _set_report_dimensions(
            report,
            source_capability="SOURCE_PASS",
            source_discovered=True,
            deterministic_attempted=False,
            canonical_passed=False,
        )
        _write_json(output_dir / "merged-source-facts.json", merged)
        report["pdf_reports"] = []
        _write_json(output_dir / "state-report.json", report)
        return report

    candidates = pdf_discoverer(config, venue_id=venue_id, season=season)
    report["pdf_discovered"] = "YES" if candidates else "NO"
    manual_path = manual_pdf_path(manual_root=manual_root, venue_id=venue_id, season=season)
    pdf_inputs: list[tuple[str, dict[str, Any]]] = []
    pdf_reports: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        result = pdf_runner(
            venue_id=venue_id,
            season=season,
            config=config,
            candidate=candidate,
            output_dir=output_dir / f"pdf-{index + 1}",
        ) or {}
        pdf_reports.append(result)
        if result.get("global_master") == "PASS":
            report["global_master"] = "PASS"
        elif report["global_master"] == "NOT_RUN" and result.get("global_master"):
            report["global_master"] = result["global_master"]
        facts = result.get("facts")
        if isinstance(facts, dict):
            validate_source_facts(facts)
            pdf_inputs.append((f"pdf:{candidate.get('pdf_url')}", facts))
        report["pdf_events"] += _event_count(facts)
        report["pdf_programme"] += _programme_count(facts)
        report["pdf_credits"] += _credit_count(facts)

    auto_pdf_pass = any(result.get("pdf_download") == "PASS" for result in pdf_reports)
    if auto_pdf_pass:
        report["pdf_download"] = "PASS"
    elif candidates:
        report["pdf_download"] = "FAIL"
    if any(result.get("source_type") == "FULL_SOURCE" for result in pdf_reports):
        report["pdf_type"] = PDF_FULL_SOURCE
    elif any(result.get("source_type") == "ENRICHMENT_SOURCE" for result in pdf_reports):
        report["pdf_type"] = PDF_ENRICHMENT_SOURCE
    elif candidates:
        report["pdf_type"] = PDF_FAILED

    manual_pdf_loaded = False
    if not pdf_inputs and manual_path.exists():
        manual_candidate = {
            "pdf_url": (candidates[0].get("pdf_url") if candidates else config.get("official_source")),
            "manual_path": str(manual_path),
        }
        result = pdf_runner(
            venue_id=venue_id,
            season=season,
            config=config,
            candidate=manual_candidate,
            output_dir=output_dir / "manual-pdf",
        ) or {}
        pdf_reports.append(result)
        if result.get("global_master") == "PASS":
            report["global_master"] = "PASS"
        elif report["global_master"] == "NOT_RUN" and result.get("global_master"):
            report["global_master"] = result["global_master"]
        facts = result.get("facts")
        if isinstance(facts, dict):
            validate_source_facts(facts)
            pdf_inputs.append((f"manual_pdf:{manual_path}", facts))
            report["pdf_events"] += _event_count(facts)
            report["pdf_programme"] += _programme_count(facts)
            report["pdf_credits"] += _credit_count(facts)
            report["pdf_download"] = "PASS"
            manual_pdf_loaded = True

    human_pdf_required = bool(candidates and not auto_pdf_pass and not manual_pdf_loaded)

    if pdf_inputs or hermes_valid_facts:
        source_inputs = []
        if hermes_valid_facts:
            source_inputs.append(("hermes", hermes_valid_facts))
        source_inputs.extend(pdf_inputs)
        merged = merge_official_source_facts(source_inputs, request=request)
        report.update({
            "merged_events": _event_count(merged),
            "merged_programme": _programme_count(merged),
            "merged_credits": _credit_count(merged),
        })
        pdf_occurrence_source = any(result.get("source_type") == "FULL_SOURCE" for result in pdf_reports)
        _set_report_dimensions(
            report,
            source_capability="SOURCE_PASS" if pdf_occurrence_source or hermes_status == HERMES_PASS else "SOURCE_PARTIAL",
            source_discovered=bool(hermes_valid_facts) or pdf_occurrence_source,
            deterministic_attempted=False,
            useful_occurrence_source=bool(_event_count(merged)),
            pdf_known=bool(candidates),
            pdf_download_failed=bool(candidates and not auto_pdf_pass),
            canonical_passed=bool(report["global_master"] == "PASS" and _event_count(merged)),
        )
        _write_json(output_dir / "merged-source-facts.json", merged)
        if report["merged_events"] and not human_pdf_required:
            report["final_status"] = SOURCE_READY if report["pdf_type"] == PDF_FULL_SOURCE or hermes_status == HERMES_PASS else REVIEW_REQUIRED
            report["blocker"] = None if report["final_status"] == SOURCE_READY else hermes_reason or "coverage requires review"

    if human_pdf_required:
        report["acquisition_status"] = HUMAN_PDF_REQUIRED
        report["final_status"] = HUMAN_PDF_REQUIRED
        report["human_action"] = f"Download the official PDF and place it at {manual_path}"
    elif report["final_status"] == BLOCKED:
        if candidates and not auto_pdf_pass:
            report["final_status"] = HUMAN_PDF_REQUIRED
            report["human_action"] = f"Download the official PDF and place it at {manual_path}"
        elif not candidates:
            # PDF absence is only fallback metadata.  Preserve the actual
            # Hermes/acquisition blocker when no source was obtained.
            report["final_status"] = BLOCKED
            report["human_action"] = "NONE"
        elif not report["merged_events"]:
            report["final_status"] = REVIEW_REQUIRED
    if report.get("pdf_type") != "NONE":
        report["source_capability_profile"] = build_capability_profile(
            venue_id=venue_id,
            season=season,
            config=config,
            observations={
                "events": report.get("merged_events", 0),
                "pdf_type": report.get("pdf_type"),
                "source_discovery": report.get("source_discovery"),
                "discovered_mode": report.get("discovered_mode"),
                "endpoint": report.get("discovered_endpoint"),
            },
        )
        report["source_family"] = report["source_capability_profile"]["occurrence_source"]["family"]
        report["occurrence_source_family"] = report["source_capability_profile"].get("occurrence_source_family", report["source_family"])
        report["enrichment_source_families"] = report["source_capability_profile"].get("enrichment_source_families", [])
    write_capability_profile(output_dir, report["source_capability_profile"])
    report["pdf_reports"] = pdf_reports
    _write_json(output_dir / "state-report.json", report)
    return report


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
