"""Read-only release admission gates for deterministic venue artifacts.

Release readiness is deliberately separate from acquisition and canonical
status.  In particular, programme/credit resolution review does not reject an
otherwise traceable occurrence set.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

from .contracts import schedule_integrity_report


SAFE_RELEASE_CANDIDATE = "SAFE_RELEASE_CANDIDATE"
REVIEW_RELEASE_CANDIDATE = "REVIEW_RELEASE_CANDIDATE"
REJECT_RELEASE_CANDIDATE = "REJECT_RELEASE_CANDIDATE"

_GENERIC_TITLES = {
    "calendar",
    "event",
    "events",
    "official event",
    "programme",
    "program",
    "season",
}


def season_bounds(season: str) -> tuple[date, date]:
    start_year, end_short = (int(part) for part in str(season).split("-", 1))
    end_year = start_year // 100 * 100 + end_short
    return date(start_year, 9, 1), date(end_year, 8, 31)


def _date_value(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _count(value: Any) -> int:
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _event_identity(row: dict[str, Any]) -> str:
    return str(row.get("event_key") or row.get("source_event_id") or "")


def _slot(row: dict[str, Any]) -> tuple[str, str, str, str, Any]:
    # Keep this identical to contracts.schedule_integrity_report.
    return (
        str(row.get("organization") or ""),
        str(row.get("venue") or ""),
        str(row.get("title") or row.get("production_title") or ""),
        str(row.get("date") or ""),
        row.get("start_time"),
    )


def _day_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("organization") or ""),
        str(row.get("venue") or ""),
        str(row.get("title") or row.get("production_title") or ""),
        str(row.get("date") or ""),
    )


def _coverage_assessment(
    *,
    events: list[dict[str, Any]],
    season: str,
    source_audit: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Assess coverage only from current source-native artifact evidence."""
    occurrence = profile.get("occurrence_source") or {}
    family = str(
        profile.get("occurrence_source_family")
        or occurrence.get("family")
        or profile.get("source_family")
        or ""
    )
    mode = str(occurrence.get("mode") or "").upper()
    pagination = str(occurrence.get("pagination_mode") or "none").casefold()
    source_url = str(occurrence.get("url") or "")
    errors = source_audit.get("adapter_errors") or []
    failed = source_audit.get("failed_months") or []
    requested = source_audit.get("requested_months") or []
    successful = source_audit.get("successful_months") or []
    detail_requested = source_audit.get("detail_pages_requested") or []
    detail_successful = source_audit.get("detail_pages_successful") or []
    requested_count = _count(requested)
    successful_count = _count(successful)
    failed_count = _count(failed)
    detail_requested_count = _count(detail_requested)
    detail_successful_count = _count(detail_successful)
    discovered = source_audit.get("productions_discovered")
    if not isinstance(discovered, int):
        discovered = 0
    explicit_complete = bool(
        source_audit.get("coverage_complete")
        or source_audit.get("pagination_complete")
    )

    dates = [_date_value(row.get("date")) for row in events]
    dates = [item for item in dates if item is not None]
    first = min(dates) if dates else None
    last = max(dates) if dates else None
    span_days = (last - first).days + 1 if first and last else 0
    season_start, season_end = season_bounds(season)
    evidence: list[str] = []

    if source_audit.get("scope") == "production-gaps":
        verified = int(source_audit.get("existing_events_verified", 0) or 0)
        complete = bool(events) and verified == len(events) and all(
            _date_value(row.get("date")) is not None and str(row.get("source_url") or "").strip()
            for row in events
        )
        evidence.append(f"existing production identities verified={verified}/{len(events)}")
        return {
            "pass": bool(complete),
            "family": family,
            "mode": "EXISTING_PRODUCTION",
            "source_url": source_url,
            "events": len(events),
            "discovered": verified,
            "date_min": first.isoformat() if first else None,
            "date_max": last.isoformat() if last else None,
            "pagination_complete": bool(complete),
            "evidence": evidence,
        }

    complete = False
    if errors or failed_count:
        evidence.append("source fetch failures remain")
    if family == "STRUCTURED_API" or mode == "API":
        complete = (
            not errors
            and not failed_count
            and bool(events)
            and discovered == len(events)
            and first is not None
            and last is not None
            and first >= season_start
            and last <= season_end
            and (span_days >= 180 or explicit_complete)
        )
        evidence.extend(
            [
                f"single API result set rows={len(events)} discovered={discovered}",
                f"date_span={first.isoformat() if first else None}..{last.isoformat() if last else None}",
            ]
        )
    elif pagination == "bounded":
        # A bounded calendar is complete only when the source exposes enough
        # month/page requests for a season and every request succeeded.
        complete = (
            not errors
            and not failed_count
            and requested_count >= 6
            and successful_count >= requested_count
            and first is not None
            and last is not None
            and (span_days >= 180 or explicit_complete)
        )
        evidence.append(f"bounded pages requested={requested_count} successful={successful_count}")
    else:
        # A season-labelled listing or a complete detail-linked listing is
        # credible without imposing an arbitrary event-count threshold.
        season_label = str(season).replace("-", "-") in source_url
        complete_detail_links = bool(detail_requested_count) and detail_successful_count >= detail_requested_count
        complete = (
            not errors
            and not failed
            and first is not None
            and last is not None
            and (span_days >= 180 or explicit_complete)
            and (season_label or complete_detail_links)
        )
        evidence.extend(
            [
                f"season_label={season_label}",
                f"detail_links={detail_successful_count}/{detail_requested_count}",
            ]
        )

    return {
        "pass": bool(complete),
        "family": family,
        "mode": mode,
        "source_url": source_url,
        "events": len(events),
        "discovered": discovered,
        "date_min": first.isoformat() if first else None,
        "date_max": last.isoformat() if last else None,
        "pagination_complete": bool(complete),
        "evidence": evidence,
    }


def _row_rejection_reasons(events: list[dict[str, Any]], season: str) -> dict[int, list[str]]:
    start, end = season_bounds(season)
    reasons: dict[int, list[str]] = {}
    seen_identity: set[str] = set()
    seen_slots: set[tuple[str, str, str, str, Any]] = set()
    days: dict[tuple[str, str, str, str], set[Any]] = {}

    for index, row in enumerate(events):
        row_reasons: list[str] = []
        title = str(row.get("title") or row.get("production_title") or "").strip()
        event_date = _date_value(row.get("date"))
        source_url = str(row.get("source_url") or "").strip()
        if not title or title.casefold() in _GENERIC_TITLES:
            row_reasons.append("missing_or_generic_title")
        if event_date is None:
            row_reasons.append("missing_or_invalid_date")
        elif not (start <= event_date <= end):
            row_reasons.append("out_of_season")
        if not source_url:
            row_reasons.append("untraceable_source")

        identity = _event_identity(row)
        if identity and identity in seen_identity:
            row_reasons.append("duplicate_event_identity")
        if identity:
            seen_identity.add(identity)

        slot = _slot(row)
        if slot in seen_slots:
            row_reasons.append("duplicate_performance_slot")
        seen_slots.add(slot)

        day = _day_key(row)
        times = days.setdefault(day, set())
        if row.get("start_time") is None and any(value is not None for value in times):
            row_reasons.append("null_timed_shadow_duplicate")
        times.add(row.get("start_time"))

        if row_reasons:
            reasons[index] = row_reasons

    # If the null-time row appears after the timed row, the loop above marks
    # it.  If source order is reversed, mark the null-time row in a second
    # deterministic pass.
    timed_days = {
        key for key, times in days.items() if None in times and any(value is not None for value in times)
    }
    for index, row in enumerate(events):
        if row.get("start_time") is None and _day_key(row) in timed_days:
            reasons.setdefault(index, []).append("null_timed_shadow_duplicate")
    return reasons


def assess_release_candidate(
    *,
    venue_id: str,
    season: str,
    events: Iterable[dict[str, Any]],
    summary: dict[str, Any],
    source_audit: dict[str, Any],
    capability_profile: dict[str, Any],
) -> dict[str, Any]:
    """Return a release-only assessment without mutating source artifacts."""
    rows = [dict(row) for row in events]
    rejection_reasons = _row_rejection_reasons(rows, season)
    schedule = schedule_integrity_report(rows)
    coverage = _coverage_assessment(
        events=rows,
        season=season,
        source_audit=source_audit,
        profile=capability_profile,
    )

    season_gate = not any("out_of_season" in reasons or "missing_or_invalid_date" in reasons for reasons in rejection_reasons.values())
    duplicate_gate = schedule["duplicate_event_identity"] == 0
    slot_gate = schedule["duplicate_performance_slot"] == 0 and schedule["null_timed_shadow_duplicates"] == 0
    traceability_gate = schedule["untraceable_source"] == 0
    hard_rejected = set(rejection_reasons)
    remaining = [row for index, row in enumerate(rows) if index not in hard_rejected]
    all_occurrence_gates = season_gate and duplicate_gate and slot_gate and traceability_gate

    if not remaining:
        release_status = REJECT_RELEASE_CANDIDATE
        safe_count = review_count = 0
    elif all_occurrence_gates and coverage["pass"]:
        release_status = SAFE_RELEASE_CANDIDATE
        safe_count, review_count = len(remaining), 0
    else:
        release_status = REVIEW_RELEASE_CANDIDATE
        safe_count, review_count = 0, len(remaining)

    blockers: list[str] = []
    if not season_gate:
        blockers.append("season boundary violations")
    if not duplicate_gate:
        blockers.append("duplicate Event identity")
    if not slot_gate:
        blockers.append("duplicate performance slot or null-time shadow duplicate")
    if not traceability_gate:
        blockers.append("untraceable source URL")
    if not coverage["pass"]:
        blockers.append("source-native occurrence coverage is incomplete or unproven")
    if release_status == REJECT_RELEASE_CANDIDATE and not blockers:
        blockers.append("no valid occurrence rows remain")

    return {
        "venue": venue_id,
        "season": season,
        "acquisition_status": summary.get("acquisition_status") or summary.get("source_capability"),
        "events_discovered": len(rows),
        "events_release_safe": safe_count,
        "events_release_review": review_count,
        "events_rejected": len(hard_rejected),
        "season_gate": "PASS" if season_gate else "FAIL",
        "duplicate_gate": "PASS" if duplicate_gate else "FAIL",
        "slot_gate": "PASS" if slot_gate else "FAIL",
        "coverage_gate": "PASS" if coverage["pass"] else "FAIL",
        "traceability_gate": "PASS" if traceability_gate else "FAIL",
        "programme": int((summary.get("detail_enrichment") or {}).get("programme_items", 0) or 0),
        "credits": int((summary.get("detail_enrichment") or {}).get("credits_total", 0) or 0),
        "global_master": summary.get("global_master_preflight", "NOT_RUN"),
        "release_status": release_status,
        "release_blocker": "; ".join(blockers) if blockers else None,
        "coverage_evidence": coverage,
        "schedule_integrity": schedule,
    }


def audit_artifact_directory(*, venue_id: str, season: str, artifact_dir: Any) -> dict[str, Any]:
    """Load one existing deterministic artifact directory and assess it."""
    from pathlib import Path
    import json

    root = Path(artifact_dir)
    deterministic = root / "deterministic"
    read = lambda name: json.loads((deterministic / name).read_text(encoding="utf-8"))
    return assess_release_candidate(
        venue_id=venue_id,
        season=season,
        events=read("normalized.json"),
        summary=read("summary.json"),
        source_audit=read("source_audit.json"),
        capability_profile=read("source_capability_profile.json"),
    )
