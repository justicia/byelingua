"""Read-only Hermes bridge for eligible deterministic source failures.

This module owns the subprocess boundary only.  It validates the source-facts
contract exported by the worker, converts source observations into the
existing ``CanonicalEvent`` shape, and leaves all shared identity resolution
to the normal pipeline.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from jobs.hermes_acquire_worker import (
    _normalize_request_contract_fields,
    _terminate_process_tree,
    timeout_config_from_env,
    validate_source_facts,
)
from .credit_resolution import normalized_credit_kind
from .schema import CanonicalEvent


HERMES_SOURCE_BLOCKED = "HERMES_SOURCE_BLOCKED"
HERMES_TIMEOUT = "HERMES_TIMEOUT"
HERMES_MALFORMED_OUTPUT = "HERMES_MALFORMED_OUTPUT"
HERMES_VALIDATION_FAILED = "HERMES_VALIDATION_FAILED"
DEFAULT_HERMES_ARTIFACT_ROOT = Path("artifacts/hermes-acquisition")


class HermesAcquisitionError(RuntimeError):
    """A concrete read-only Hermes bridge failure."""

    def __init__(
        self,
        message: str,
        *,
        status: str = HERMES_SOURCE_BLOCKED,
        attempts: int = 0,
        raw_output_saved: bool = False,
        raw_output_paths: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.attempts = attempts
        self.raw_output_saved = raw_output_saved
        self.raw_output_paths = list(raw_output_paths or [])


def eligible_for_fallback(*, events: list[Any], adapter: Any, force: bool = False) -> bool:
    """Return true when deterministic acquisition produced no usable events."""
    return bool(force or not events)


def build_request(*, venue: str, season: str, config: dict[str, Any], reason: str) -> dict[str, Any]:
    official_url = config.get("official_source") or config.get("listing_source")
    listing_url = config.get("listing_source") or official_url
    if not isinstance(official_url, str) or not official_url.strip():
        raise HermesAcquisitionError(f"{venue}: official source URL is not configured")
    return {
        "venue_id": venue,
        "season": season,
        "official_source_url": official_url,
        "listing_source_url": listing_url,
        "source_id": config.get("source_id", venue),
        "organization": config.get("organization"),
        "venue": config.get("venue"),
        "city": config.get("city"),
        "country": config.get("country"),
        "timezone": config.get("timezone"),
        "source_contract": config.get("source_contract", {}),
        "official_pdf_sources": config.get("official_pdf_sources", []),
        "fallback_reason": reason,
        "official_pdf_fallback": {
            "enabled": True,
            "search_scope": "official-domain-only-or-officially-linked-asset",
            "season": season,
            "allowed_source_modes": ["FULL_SOURCE", "ENRICHMENT_SOURCE", "HYBRID"],
            "required_provenance": ["source_url", "pdf_page", "source_field"],
            "do_not_invent_dates": True,
        },
    }


def _command_tokens(command: str) -> list[str]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        raise HermesAcquisitionError(f"Hermes command is not parseable: {exc}") from exc
    if not tokens:
        raise HermesAcquisitionError("BYELINGUA_HERMES_ACQUIRE_COMMAND is empty")
    return tokens


def _artifact_dir(request: dict[str, Any], artifact_dir: Path | None) -> Path:
    if artifact_dir is not None:
        return Path(artifact_dir)
    venue_id = str(request.get("venue_id") or "unknown")
    season = str(request.get("season") or "unknown")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", venue_id):
        venue_id = "unknown"
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", season):
        season = "unknown"
    return DEFAULT_HERMES_ARTIFACT_ROOT / venue_id / season


def _persist_raw_attempt(
    request: dict[str, Any],
    *,
    artifact_dir: Path,
    attempt: int,
    stdout: str,
    stderr: str,
) -> Path | None:
    payload = {
        "venue_id": request.get("venue_id"),
        "season": request.get("season"),
        "attempt": attempt,
        "raw_stdout": stdout,
        "raw_stderr": stderr,
    }
    path = artifact_dir / f"hermes-attempt-{attempt}.json"
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, TypeError, ValueError):
        return None
    return path


def _json_transport_variants(raw: str) -> list[str]:
    text = raw.strip()
    variants = [text]
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip().casefold() in {"```", "```json"} and lines[-1].strip() == "```":
        variants.append("\n".join(lines[1:-1]).strip())
    elif len(lines) >= 2 and lines[0].strip().casefold() == "json":
        variants.append("\n".join(lines[1:]).strip())
    return list(dict.fromkeys(variants))


def _parse_json_output(raw: str) -> Any:
    errors: list[json.JSONDecodeError] = []
    for candidate in _json_transport_variants(raw):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            errors.append(exc)
    error = errors[-1] if errors else json.JSONDecodeError("Expecting value", raw, 0)
    raise HermesAcquisitionError(
        f"Hermes worker stdout is malformed JSON: {error.msg}",
        status=HERMES_MALFORMED_OUTPUT,
    ) from error


def _worker_error_status(stderr: str) -> str:
    text = (stderr or "").casefold()
    if "timed out" in text or "timeout" in text:
        return HERMES_TIMEOUT
    if "malformed json" in text or "empty stdout" in text or "output must be a json object" in text:
        return HERMES_MALFORMED_OUTPUT
    if "contract validation failed" in text or "validation failed" in text:
        return HERMES_VALIDATION_FAILED
    return HERMES_SOURCE_BLOCKED


def _retry_request(request: dict[str, Any]) -> dict[str, Any]:
    retry = dict(request)
    # This private transport marker is consumed by the worker prompt builder;
    # all official source URLs and source configuration remain unchanged.
    retry["_hermes_retry"] = True
    return retry


def acquire_source_facts(
    request: dict[str, Any],
    *,
    command: str | None = None,
    artifact_dir: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke the configured worker and validate its stdout contract."""
    command = command if command is not None else os.environ.get("BYELINGUA_HERMES_ACQUIRE_COMMAND", "")
    tokens = _command_tokens(command)
    try:
        timeout_config = timeout_config_from_env()
    except Exception as exc:
        raise HermesAcquisitionError(str(exc)) from exc
    timeout_seconds = timeout_config["total"] + timeout_config["margin"]
    deadline = time.monotonic() + timeout_seconds
    output_root = _artifact_dir(request, artifact_dir)
    saved_paths: list[str] = []
    for attempt in (1, 2):
        if metadata is not None:
            metadata.update({"attempts": attempt, "raw_output_saved": "YES" if saved_paths else "NO"})
        remaining = max(1, int(deadline - time.monotonic() + 1))
        attempt_request = request if attempt == 1 else _retry_request(request)
        try:
            process = subprocess.Popen(
                tokens,
                cwd=Path(__file__).resolve().parents[1],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=os.name != "nt",
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            try:
                stdout, stderr = process.communicate(json.dumps(attempt_request, ensure_ascii=False), timeout=remaining)
            except subprocess.TimeoutExpired as exc:
                _terminate_process_tree(process)
                stdout, stderr = process.communicate()
                saved = _persist_raw_attempt(
                    request,
                    artifact_dir=output_root,
                    attempt=attempt,
                    stdout=stdout or "",
                    stderr=stderr or "",
                )
                if saved is not None:
                    saved_paths.append(str(saved))
                error = HermesAcquisitionError(
                    f"Hermes worker timed out after {timeout_seconds}s",
                    status=HERMES_TIMEOUT,
                    attempts=attempt,
                    raw_output_saved=saved is not None,
                    raw_output_paths=saved_paths,
                )
                raise error from exc
        except subprocess.TimeoutExpired as exc:
            raise HermesAcquisitionError(
                f"Hermes worker timed out after {timeout_seconds}s",
                status=HERMES_TIMEOUT,
                attempts=attempt,
                raw_output_saved=bool(saved_paths),
                raw_output_paths=saved_paths,
            ) from exc
        except OSError as exc:
            raise HermesAcquisitionError(
                f"Hermes worker could not start: {exc}",
                status=HERMES_SOURCE_BLOCKED,
                attempts=attempt,
                raw_output_saved=bool(saved_paths),
                raw_output_paths=saved_paths,
            ) from exc

        if process.returncode != 0:
            detail = (stderr or "").strip().splitlines()
            suffix = f": {detail[-1][:300]}" if detail else ""
            status = _worker_error_status(stderr or "")
            saved = _persist_raw_attempt(
                request,
                artifact_dir=output_root,
                attempt=attempt,
                stdout=stdout or "",
                stderr=stderr or "",
            )
            if saved is not None:
                saved_paths.append(str(saved))
            error = HermesAcquisitionError(
                f"Hermes worker exited with code {process.returncode}{suffix}",
                status=status,
                attempts=attempt,
                raw_output_saved=saved is not None,
                raw_output_paths=saved_paths,
            )
            if status == HERMES_MALFORMED_OUTPUT and attempt == 1:
                continue
            raise error

        try:
            facts = _parse_json_output(stdout or "")
        except HermesAcquisitionError as exc:
            saved = _persist_raw_attempt(
                request,
                artifact_dir=output_root,
                attempt=attempt,
                stdout=stdout or "",
                stderr=stderr or "",
            )
            if saved is not None:
                saved_paths.append(str(saved))
            exc.attempts = attempt
            exc.raw_output_saved = saved is not None
            exc.raw_output_paths = saved_paths
            if attempt == 1:
                continue
            raise

        if isinstance(facts, dict):
            _normalize_request_contract_fields(facts, request)
        try:
            validate_source_facts(facts)
        except Exception as exc:
            saved = _persist_raw_attempt(
                request,
                artifact_dir=output_root,
                attempt=attempt,
                stdout=stdout or "",
                stderr=stderr or "",
            )
            if saved is not None:
                saved_paths.append(str(saved))
            raise HermesAcquisitionError(
                f"Hermes source-facts validation failed: {exc}",
                status=HERMES_VALIDATION_FAILED,
                attempts=attempt,
                raw_output_saved=saved is not None,
                raw_output_paths=saved_paths,
            ) from exc
        if not facts["events"]:
            saved = _persist_raw_attempt(
                request,
                artifact_dir=output_root,
                attempt=attempt,
                stdout=stdout or "",
                stderr=stderr or "",
            )
            if saved is not None:
                saved_paths.append(str(saved))
            raise HermesAcquisitionError(
                "Hermes source-facts validation failed: events must be non-empty",
                status=HERMES_VALIDATION_FAILED,
                attempts=attempt,
                raw_output_saved=saved is not None,
                raw_output_paths=saved_paths,
            )
        if metadata is not None:
            metadata.update({"attempts": attempt, "raw_output_saved": "YES" if saved_paths else "NO"})
        return facts

    raise HermesAcquisitionError(
        "Hermes returned malformed output after retry",
        status=HERMES_MALFORMED_OUTPUT,
        attempts=2,
        raw_output_saved=bool(saved_paths),
        raw_output_paths=saved_paths,
    )


def _validate_discovery_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HermesAcquisitionError(
            "Hermes source discovery output must be a JSON object",
            status=HERMES_MALFORMED_OUTPUT,
        )
    mode = str(value.get("discovered_mode") or "").upper()
    endpoint = value.get("discovered_endpoint")
    if mode not in {"API", "HTML"} or not isinstance(endpoint, str) or not endpoint.strip():
        raise HermesAcquisitionError(
            "Hermes source discovery output is incomplete",
            status=HERMES_VALIDATION_FAILED,
        )
    result = dict(value)
    result["status"] = str(result.get("status") or "PASS").upper()
    result["discovered_mode"] = mode
    result["discovered_endpoint"] = endpoint.strip()
    return result


def acquire_source_discovery(
    request: dict[str, Any],
    *,
    command: str | None = None,
    artifact_dir: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke Hermes in compact source-discovery mode, without source-fact extraction."""
    command = command if command is not None else os.environ.get("BYELINGUA_HERMES_ACQUIRE_COMMAND", "")
    tokens = _command_tokens(command)
    try:
        timeout_config = timeout_config_from_env()
    except Exception as exc:
        raise HermesAcquisitionError(str(exc)) from exc
    timeout_seconds = timeout_config["total"] + timeout_config["margin"]
    deadline = time.monotonic() + timeout_seconds
    output_root = _artifact_dir(request, artifact_dir)
    saved_paths: list[str] = []
    discovery_request = dict(request)
    discovery_request["hermes_mode"] = "source_discovery"

    for attempt in (1, 2):
        if metadata is not None:
            metadata.update({"attempts": attempt, "raw_output_saved": "YES" if saved_paths else "NO"})
        remaining = max(1, int(deadline - time.monotonic() + 1))
        attempt_request = discovery_request if attempt == 1 else _retry_request(discovery_request)
        try:
            process = subprocess.Popen(
                tokens,
                cwd=Path(__file__).resolve().parents[1],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=os.name != "nt",
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            try:
                stdout, stderr = process.communicate(json.dumps(attempt_request, ensure_ascii=False), timeout=remaining)
            except subprocess.TimeoutExpired as exc:
                _terminate_process_tree(process)
                stdout, stderr = process.communicate()
                saved = _persist_raw_attempt(request, artifact_dir=output_root, attempt=attempt, stdout=stdout or "", stderr=stderr or "")
                if saved is not None:
                    saved_paths.append(str(saved))
                raise HermesAcquisitionError(
                    f"Hermes worker timed out after {timeout_seconds}s",
                    status=HERMES_TIMEOUT,
                    attempts=attempt,
                    raw_output_saved=saved is not None,
                    raw_output_paths=saved_paths,
                ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HermesAcquisitionError(
                f"Hermes worker timed out after {timeout_seconds}s",
                status=HERMES_TIMEOUT,
                attempts=attempt,
                raw_output_saved=bool(saved_paths),
                raw_output_paths=saved_paths,
            ) from exc
        except OSError as exc:
            raise HermesAcquisitionError(
                f"Hermes worker could not start: {exc}",
                status=HERMES_SOURCE_BLOCKED,
                attempts=attempt,
                raw_output_saved=bool(saved_paths),
                raw_output_paths=saved_paths,
            ) from exc

        if process.returncode != 0:
            detail = (stderr or "").strip().splitlines()
            suffix = f": {detail[-1][:300]}" if detail else ""
            status = _worker_error_status(stderr or "")
            saved = _persist_raw_attempt(request, artifact_dir=output_root, attempt=attempt, stdout=stdout or "", stderr=stderr or "")
            if saved is not None:
                saved_paths.append(str(saved))
            error = HermesAcquisitionError(
                f"Hermes worker exited with code {process.returncode}{suffix}",
                status=status,
                attempts=attempt,
                raw_output_saved=saved is not None,
                raw_output_paths=saved_paths,
            )
            if status == HERMES_MALFORMED_OUTPUT and attempt == 1:
                continue
            raise error

        try:
            value = _parse_json_output(stdout or "")
            discovery = _validate_discovery_result(value)
        except HermesAcquisitionError as exc:
            saved = _persist_raw_attempt(request, artifact_dir=output_root, attempt=attempt, stdout=stdout or "", stderr=stderr or "")
            if saved is not None:
                saved_paths.append(str(saved))
            exc.attempts = attempt
            exc.raw_output_saved = saved is not None
            exc.raw_output_paths = saved_paths
            if attempt == 1:
                continue
            raise
        if metadata is not None:
            metadata.update({"attempts": attempt, "raw_output_saved": "YES" if saved_paths else "NO"})
        return discovery

    raise HermesAcquisitionError(
        "Hermes source discovery returned malformed output after retry",
        status=HERMES_MALFORMED_OUTPUT,
        attempts=2,
        raw_output_saved=bool(saved_paths),
        raw_output_paths=saved_paths,
    )


def persist_source_facts(facts: dict[str, Any], *, root: Path = Path("artifacts/hermes-source-facts")) -> Path:
    """Atomically persist only validated, non-empty source facts."""
    validate_source_facts(facts)
    if not facts["events"]:
        raise HermesAcquisitionError("Hermes source-facts validation failed: events must be non-empty")
    venue_id = str(facts["venue_id"])
    season = str(facts["season"])
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", venue_id) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", season):
        raise HermesAcquisitionError("Hermes source-facts validation failed: unsafe artifact path component")
    path = root / f"{venue_id}-{season}.json"
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=root, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(facts, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
    return path


def facts_to_events(facts: dict[str, Any], *, venue: str, config: dict[str, Any]) -> list[CanonicalEvent]:
    """Convert raw source facts to existing canonical event candidates."""
    validate_source_facts(facts)
    source = str(facts.get("source_id") or config.get("source_id") or venue)
    events: list[CanonicalEvent] = []
    for raw_event in facts["events"]:
        source_url = raw_event["source_url"]
        programme = []
        for row in raw_event["programme"]:
            item = dict(row)
            provenance = dict(item.get("provenance") or {})
            provenance.setdefault("source_url", source_url)
            item["provenance"] = provenance
            programme.append(item)
        credits = []
        for row in raw_event["credits"]:
            item = dict(row)
            item["credit_kind"] = normalized_credit_kind(item)
            item.setdefault("source_url", source_url)
            provenance = dict(item.get("provenance") or {})
            provenance.setdefault("source_url", item["source_url"])
            item["provenance"] = provenance
            credits.append(item)
        quality = dict(raw_event.get("data_quality") or {})
        schedule_quality = dict(quality.get("schedule") or {})
        schedule_quality.setdefault("year_status", "YEAR_EXPLICIT")
        schedule_quality.setdefault("source_field", "hermes.source_facts.date")
        quality["schedule"] = schedule_quality
        programme_quality = dict(quality.get("programme") or {})
        programme_quality.setdefault("status", "PROGRAMME_EVIDENCE_FOUND" if programme else "NO_PROGRAMME_EVIDENCE")
        quality["programme"] = programme_quality
        events.append(
            CanonicalEvent(
                source=source,
                source_event_id=raw_event["source_event_id"],
                source_url=source_url,
                organization=config["organization"],
                venue=config["venue"],
                city=config["city"],
                country=config["country"],
                timezone=config["timezone"],
                title=raw_event["title"],
                date=raw_event["date"],
                start_time=raw_event["start_time"],
                end_time=raw_event.get("end_time"),
                room=raw_event.get("room"),
                event_type=raw_event.get("event_type") or config.get("default_event_type", "performance"),
                classification=raw_event.get("classification") or config.get("default_event_type", "performance"),
                programme=programme,
                credits=credits,
                data_quality=quality,
                raw={
                    "source_facts_schema_version": facts["schema_version"],
                    "source_contract": facts["source_contract"],
                    "source_event": raw_event,
                },
            )
        )
    return events


def acquire_events(*, venue: str, season: str, config: dict[str, Any], reason: str) -> tuple[dict[str, Any], list[CanonicalEvent]]:
    request = build_request(venue=venue, season=season, config=config, reason=reason)
    facts = acquire_source_facts(request)
    return facts, facts_to_events(facts, venue=venue, config=config)
