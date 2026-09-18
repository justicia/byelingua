"""Small, reusable guards for the PDF-first data freeze.

The guards are intentionally independent of Supabase and of any particular
PDF parser.  They validate the boundary around the existing canonical writer:
target scope, append-only enrichment, deterministic PDF accounting, and the
frontend freeze.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

from .global_master import normalize_identity


ALLOWED_FACT_STATUSES = frozenset({"ALREADY_EXISTS", "WRITTEN", "RESOLUTION_FAILED", "UNMATCHED_EVENT"})
FROZEN_FRONTEND_COMMIT = "1d7591dba2df428152b35ccb4a0b98e65c934efa"


class HardFreezeViolation(RuntimeError):
    """Raised when a batch attempts an unsafe mutation."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_batch_manifest(
    *,
    run_id: str,
    pdf_files: Iterable[str],
    pdf_hashes: Mapping[str, str],
    target_venues: Iterable[str],
    target_event_ids: Iterable[str],
    insert_programme: int = 0,
    insert_credits: int = 0,
    insert_characters: int = 0,
    duplicate_pdfs_skipped: int = 0,
) -> dict[str, Any]:
    """Build the auditable pre-apply manifest required by the hard freeze."""
    return {
        "schema_version": "pdf-bulk-hard-freeze-v1",
        "run_id": _text(run_id),
        "pdf_files": sorted({_text(value) for value in pdf_files if _text(value)}),
        "pdf_hashes": {str(key): str(value) for key, value in sorted(pdf_hashes.items())},
        "target_venues": sorted({_text(value) for value in target_venues if _text(value)}),
        "target_event_ids": sorted({_text(value) for value in target_event_ids if _text(value)}),
        "insert_programme": int(insert_programme),
        "insert_credits": int(insert_credits),
        "insert_characters": int(insert_characters),
        "update_existing_accepted_facts": 0,
        "delete_existing_accepted_facts": 0,
        "out_of_scope_mutations": 0,
        "duplicate_pdfs_skipped": int(duplicate_pdfs_skipped),
    }


def validate_batch_manifest(manifest: Mapping[str, Any]) -> None:
    required = (
        "run_id", "pdf_files", "pdf_hashes", "target_venues", "target_event_ids",
        "insert_programme", "insert_credits", "insert_characters",
        "update_existing_accepted_facts", "delete_existing_accepted_facts",
        "out_of_scope_mutations",
    )
    missing = [key for key in required if key not in manifest]
    if missing:
        raise HardFreezeViolation(f"manifest missing required fields: {', '.join(missing)}")
    if not _text(manifest.get("run_id")):
        raise HardFreezeViolation("run_id is required")
    for key in ("update_existing_accepted_facts", "delete_existing_accepted_facts", "out_of_scope_mutations"):
        if int(manifest.get(key, 0) or 0) != 0:
            raise HardFreezeViolation(f"{key} must remain 0")
    for key in ("insert_programme", "insert_credits", "insert_characters"):
        if int(manifest.get(key, 0) or 0) < 0:
            raise HardFreezeViolation(f"{key} cannot be negative")
    if not isinstance(manifest.get("target_venues"), list) or not isinstance(manifest.get("target_event_ids"), list):
        raise HardFreezeViolation("target scope must be explicit lists")


def validate_mutation_scope(
    mutations: Iterable[Mapping[str, Any]],
    *,
    target_venues: Iterable[str],
    target_event_ids: Iterable[str],
) -> int:
    """Return out-of-scope mutation count and raise on the first violation."""
    venues = {_text(value) for value in target_venues}
    event_ids = {_text(value) for value in target_event_ids}
    out_of_scope = 0
    for row in mutations:
        venue = _text(row.get("venue_id") or row.get("venue") or row.get("venue_slug"))
        event_id = _text(row.get("event_id") or row.get("event_key"))
        # Every mutation must carry at least one explicit scope key.  A row
        # with neither key is not safely attributable to the requested batch.
        if not venue and not event_id:
            out_of_scope += 1
            continue
        if (venue and (not venues or venue not in venues)) or (event_id and (not event_ids or event_id not in event_ids)):
            out_of_scope += 1
    if out_of_scope:
        raise HardFreezeViolation(f"OUT_OF_SCOPE_MUTATIONS={out_of_scope}")
    return out_of_scope


def fact_identity(row: Mapping[str, Any], *, kind: str) -> tuple[str, ...]:
    """Stable relationship identity used for append-only de-duplication."""
    event = _text(row.get("event_id") or row.get("event_key"))
    if kind == "programme":
        work_id = _text(row.get("work_id") or row.get("canonical_work_id") or row.get("candidate_key"))
        title = normalize_identity(row.get("canonical_work_title") or row.get("title"))
        composer = normalize_identity(row.get("composer") or row.get("composer_name"))
        return (event, work_id or title, composer if not work_id else "")
    if kind == "credit":
        # Import lazily to keep the freeze helpers usable in small bootstrap
        # contexts while still making role aliases part of relationship
        # identity whenever the resolver is available.
        from .credit_resolution import canonical_instrument, canonical_role, canonical_voice_type
        raw_role = row.get("role") or row.get("function")
        role = canonical_role(raw_role) or normalize_identity(raw_role)
        instrument = canonical_instrument(row.get("instrument") or row.get("source_instrument")) or normalize_identity(row.get("instrument") or row.get("source_instrument"))
        voice_type = canonical_voice_type(row.get("voice_type") or raw_role) or normalize_identity(row.get("voice_type"))
        return (
            event,
            normalize_identity(row.get("artist_id") or row.get("artist_identity_key") or row.get("artist_name") or row.get("artist")),
            role,
            normalize_identity(row.get("character_id") or row.get("character")),
            instrument,
            voice_type,
        )
    if kind == "character":
        return (event, _text(row.get("artist_id") or row.get("artist_identity_key") or row.get("artist_name")), _text(row.get("character_id") or row.get("character")))
    raise ValueError(f"unknown fact kind: {kind}")


def _material_signature(row: Mapping[str, Any], *, kind: str) -> tuple[Any, ...]:
    """Fields whose disagreement is a CONFLICT, not an overwrite."""
    if kind == "programme":
        return (
            normalize_identity(row.get("work_id") or row.get("canonical_work_id")),
            normalize_identity(row.get("canonical_work_title") or row.get("title")),
            normalize_identity(row.get("composer") or row.get("composer_name")),
        )
    if kind == "credit":
        return (
            normalize_identity(row.get("artist_id") or row.get("artist_identity_key") or row.get("artist_name") or row.get("artist")),
            fact_identity(row, kind=kind)[2:],
        )
    if kind == "character":
        return (normalize_identity(row.get("character_id") or row.get("character")),)
    raise ValueError(f"unknown fact kind: {kind}")


def append_only_plan(existing: Iterable[Mapping[str, Any]], incoming: Iterable[Mapping[str, Any]], *, kind: str) -> dict[str, list[dict[str, Any]]]:
    """Plan append-only enrichment and surface same-identity disagreements."""
    existing_rows = [dict(row) for row in existing]
    by_identity: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in existing_rows:
        by_identity.setdefault(fact_identity(row, kind=kind), row)
    to_add: list[dict[str, Any]] = []
    already_exists: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for raw in incoming:
        row = dict(raw)
        identity = fact_identity(row, kind=kind)
        previous = by_identity.get(identity)
        if previous is None:
            by_identity[identity] = row
            to_add.append(row)
        elif _material_signature(previous, kind=kind) == _material_signature(row, kind=kind):
            already_exists.append(row)
        else:
            conflicts.append({"identity": identity, "existing": previous, "incoming": row, "status": "CONFLICT"})
    return {"to_add": to_add, "already_exists": already_exists, "conflicts": conflicts}


def append_only_missing(existing: Iterable[Mapping[str, Any]], incoming: Iterable[Mapping[str, Any]], *, kind: str) -> list[dict[str, Any]]:
    """Return only facts not already accepted; never updates or deletes."""
    return append_only_plan(existing, incoming, kind=kind)["to_add"]


def semantic_programme_identity(row: Mapping[str, Any]) -> tuple[str, ...]:
    return fact_identity(row, kind="programme")


def semantic_credit_identity(row: Mapping[str, Any]) -> tuple[str, ...]:
    return fact_identity(row, kind="credit")


def frontend_matches_frozen_commit(repo: Path, paths: Iterable[str], *, commit: str = FROZEN_FRONTEND_COMMIT) -> dict[str, str]:
    """Verify the checked-out renderer bytes still equal the accepted commit."""
    result: dict[str, str] = {}

    def normalized_bytes(value: bytes) -> bytes:
        # Git checkout settings may change CRLF/LF without changing the
        # renderer.  Freeze the semantic file content, while the before/after
        # snapshot below still detects any mutation during the batch.
        return value.replace(b"\r\n", b"\n")

    for relative in paths:
        path = repo / relative
        if not path.is_file():
            raise HardFreezeViolation(f"frozen frontend file missing: {relative}")
        try:
            rel = path.relative_to(repo).as_posix()
            completed = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=repo, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise HardFreezeViolation(f"cannot verify frozen frontend commit for {relative}") from exc
        expected = hashlib.sha256(normalized_bytes(completed.stdout)).hexdigest()
        actual = hashlib.sha256(normalized_bytes(path.read_bytes())).hexdigest()
        if actual != expected:
            raise HardFreezeViolation(f"frontend file differs from frozen commit: {relative}")
        result[relative.replace("\\", "/")] = actual
    return result
    output: list[dict[str, Any]] = []
    for row in incoming:
        identity = fact_identity(row, kind=kind)
        if identity in seen:
            continue
        seen.add(identity)
        output.append(dict(row))
    return output


def validate_credit_semantics(programme: Iterable[Mapping[str, Any]], credits: Iterable[Mapping[str, Any]]) -> None:
    """Reject the specific semantic pollutions the freeze is meant to stop."""
    composer_names = {
        _text(row.get("composer") or row.get("composer_name")).casefold()
        for row in programme
        if _text(row.get("composer") or row.get("composer_name"))
    }
    cast_roles = {"performer", "singer", "soloist", "actor"}
    team_roles = {"conductor", "director", "stage_director", "set_designer", "costume_designer", "lighting_designer", "dramaturg", "choreographer", "chorus_master"}
    for row in credits:
        artist = _text(row.get("artist_name") or row.get("artist") or row.get("artist_identity_key")).casefold()
        role = _text(row.get("role") or row.get("function")).casefold()
        if artist and artist in composer_names:
            raise HardFreezeViolation("composer metadata cannot become a credit")
        if _text(row.get("character")) and role not in cast_roles:
            raise HardFreezeViolation("character credit must remain in the staged cast roles")
        if _text(row.get("character")) and role in team_roles:
            raise HardFreezeViolation("artistic-team credits cannot carry a character")
        if row.get("source_instrument") and not row.get("instrument"):
            raise HardFreezeViolation("soloist instrument was dropped")


def frontend_snapshot(repo: Path, paths: Iterable[str]) -> dict[str, str]:
    """Hash frontend files for a before/after freeze comparison."""
    snapshot: dict[str, str] = {}
    for relative in paths:
        path = repo / relative
        if path.exists():
            snapshot[relative.replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def assert_frontend_unchanged(before: Mapping[str, str], after: Mapping[str, str]) -> None:
    if dict(before) != dict(after):
        raise HardFreezeViolation("frontend files changed during data ingestion")


def _status_count(section: Mapping[str, Any]) -> int:
    return sum(int(section.get(status, 0) or 0) for status in ALLOWED_FACT_STATUSES if status in section)


def full_ingestion_pass(audit: Mapping[str, Any]) -> bool:
    """PASS means fully accounted for, not that every fact resolved."""
    if int(audit.get("dated_blocks_processed", 0) or 0) != int(audit.get("dated_blocks_found", 0) or 0):
        return False
    sections = (
        ("programme_status", "programme_items_in_pdf", "unaccounted_programme_items"),
        ("credit_status", "credits_in_pdf", "unaccounted_credits"),
        ("character_status", "characters_in_pdf", "unaccounted_characters"),
    )
    for status_key, total_key, unaccounted_key in sections:
        status = audit.get(status_key) or {}
        if any(key not in ALLOWED_FACT_STATUSES for key in status):
            return False
        if _status_count(status) + int(audit.get(unaccounted_key, 0) or 0) != int(audit.get(total_key, 0) or 0):
            return False
        if int(audit.get(unaccounted_key, 0) or 0) != 0:
            return False
    return True
