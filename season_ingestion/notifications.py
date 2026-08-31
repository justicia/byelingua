"""Operational Cloud Run status surfaces; deliberately separate from user digests."""
from __future__ import annotations

import hashlib
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


TERMINAL_STATUSES = {"DRY_RUN_SUCCESS", "DRY_RUN_PARTIAL", "DRY_RUN_BLOCKED", "DRY_RUN_FAILED", "APPLY_SUCCESS", "APPLY_ROLLED_BACK", "APPLY_FAILED"}


def final_staging_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def systemic_blockers(summary: dict) -> list[str]:
    blockers = []
    if summary.get("source_capability") in {"SOURCE_BLOCKED", "SOURCE_PARTIAL", "SOURCE_UNSUPPORTED"}:
        blockers.append(str(summary["source_capability"]))
    if summary.get("global_master_preflight") != "PASS":
        blockers.append("GLOBAL_MASTER_UNAVAILABLE")
    gates = summary.get("gates") or {}
    for name in ("duplicate_event_identity", "untraceable", "source_order_missing"):
        if gates.get(name) is False:
            blockers.append(name.upper())
    if summary.get("scope") == "existing-production" and gates.get("existing_event_match") is False:
        blockers.append("EXISTING_EVENT_MATCH_FAILED")
    if summary.get("scope") == "existing-production" and gates.get("credit_extraction") is False:
        blockers.append("CREDIT_EXTRACTION_EMPTY")
    if (summary.get("counts") or {}).get("writes", 0) != 0:
        blockers.append("PRODUCTION_WRITES_NONZERO")
    return list(dict.fromkeys(blockers))


def classify_dry_run(summary: dict) -> tuple[str, bool, list[str]]:
    blockers = systemic_blockers(summary)
    if summary.get("source_capability") in {"SOURCE_BLOCKED", "SOURCE_UNSUPPORTED"}:
        return "DRY_RUN_BLOCKED", False, blockers
    if summary.get("global_master_preflight") != "PASS":
        return "DRY_RUN_BLOCKED", False, blockers
    if blockers:
        return "DRY_RUN_PARTIAL", False, blockers
    return "DRY_RUN_SUCCESS", True, []


def build_approval_manifest(summary: dict, staging_path: Path, *, run_id: str, commit: str, created_at: str | None = None) -> dict:
    status, eligible, blockers = classify_dry_run(summary)
    return {
        "schema_version": "1",
        "venue": summary["venue"], "season": summary["season"], "dry_run_id": str(run_id),
        "git_commit": commit, "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "final_staging_hash": final_staging_hash(staging_path),
        "safe_event_count": (summary.get("counts") or {}).get("events_discovered", 0) if eligible else 0,
        "safe_composer_count": sum((summary.get("detail_enrichment") or {}).get("composer_resolution", {}).get(k, 0) for k in ("exact", "alias", "normalized")),
        "safe_work_count": sum((summary.get("detail_enrichment") or {}).get("work_resolution", {}).get(k, 0) for k in ("existing_exact", "existing_alias", "existing_normalized")),
        "safe_relationship_count": max(0, (summary.get("detail_enrichment") or {}).get("programme_items", 0) - (summary.get("detail_enrichment") or {}).get("work_resolution", {}).get("review", 0)),
        "review_count": (summary.get("counts") or {}).get("review_items", 0),
        "systemic_blockers": blockers, "eligible_for_apply": eligible,
        "status": "READY_FOR_APPROVAL" if eligible else status,
    }


def notification_summary(summary: dict, *, status: str, notification_status: str = "NOT_SENT", sent_at: str | None = None, run_id: str | None = None) -> dict:
    return {
        "run_id": run_id or os.getenv("GITHUB_RUN_ID", "local"),
        "mode": summary.get("mode"),
        "status": status,
        "notification_status": notification_status,
        "delivery_channel": "github_actions_summary",
        "recipient_configured": bool(os.getenv("INGESTION_NOTIFICATION_EMAIL")),
        "sent_at": sent_at,
    }


def _counts(summary: dict) -> tuple[int, int, int, int]:
    c = summary.get("counts") or {}; d = summary.get("detail_enrichment") or {}
    return c.get("events_discovered", 0), c.get("events_discovered", 0), d.get("composer_resolution", {}).get("review", 0), d.get("work_resolution", {}).get("review", 0)


def _safe_failure_reason(value: object) -> str:
    text = str(value or "").strip()
    for name in ("SUPABASE_SECRET_KEY", "SUPABASE_READONLY_KEY", "RESEND_API_KEY"):
        secret = os.getenv(name, "")
        if secret:
            text = text.replace(secret, "[redacted]")
    return text[:300]


def render_github_summary(summary: dict, *, status: str, manifest: dict | None = None, run_url: str = "", failure_reason: object = None) -> str:
    counts = summary.get("counts") or {}
    venue = summary.get("venue", "unknown")
    season = summary.get("season", "unknown")
    mode = summary.get("mode", "unknown")
    scope = summary.get("scope", "full-season")
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    production_writes = counts.get("writes", 0)
    approval_status = manifest.get("status") if manifest else ("BLOCKED" if status.startswith("DRY_RUN_") else "N/A")
    lines = [
        "# Cloud Season Ingestion Pipeline V1",
        "",
        f"- **Venue:** {venue}",
        f"- **Season:** {season}",
        f"- **Mode:** {mode}",
        f"- **Scope:** {scope}",
        f"- **Run ID:** {run_id}",
        f"- **Status:** {status}",
        f"- **Source capability:** {summary.get('source_capability', 'UNKNOWN')}",
        f"- **Global Master preflight:** {summary.get('global_master_preflight', 'UNKNOWN')}",
        f"- **Events discovered:** {counts.get('events_discovered', 0)}",
        f"- **Review items:** {counts.get('review_items', 0)}",
        f"- **Production writes:** {production_writes}",
        f"- **Approval status:** {approval_status}",
    ]
    if run_url:
        lines.append(f"- **Run URL:** {run_url}")
    if manifest:
        lines.extend([
            f"- **Approved dry-run ID:** {manifest.get('dry_run_id', '')}",
            f"- **Staging hash:** `{manifest.get('final_staging_hash', '')}`",
        ])
    safe_reason = _safe_failure_reason(failure_reason)
    if safe_reason:
        lines.append(f"- **Failure reason:** {safe_reason}")
    blockers = systemic_blockers(summary)
    if blockers:
        lines.append(f"- **Systemic blockers:** {', '.join(blockers)}")
    return "\n".join(lines) + "\n"


def write_github_step_summary(markdown: str) -> bool:
    target = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if not target:
        return False
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(markdown)
    return True


def render_email(summary: dict, *, status: str, manifest: dict | None = None, run_url: str = "") -> tuple[str, str, str]:
    """Legacy optional email renderer retained for backward compatibility."""
    venue, season = summary.get("venue", ""), summary.get("season", "")
    events, safe_events, composer_review, work_review = _counts(summary)
    source = summary.get("source_capability", "UNKNOWN")
    blockers = ", ".join(systemic_blockers(summary)) or "none"
    eligible = manifest.get("eligible_for_apply") if manifest else False
    subject = f"[Byelingua] {venue} {season} ingestion — {('Ready for approval' if status == 'READY_FOR_APPROVAL' else status.replace('_', ' ').title())}"
    lines = [f"Venue: {venue}", f"Season: {season}", f"Mode: {summary.get('mode', 'dry-run')}", f"Status: {status}", f"Cloud run: {run_url or 'not available'}", f"Source: {source}", f"Events: discovered={events} safe={safe_events} review={summary.get('counts', {}).get('review_items', 0)}", f"Composer review: {composer_review}", f"Work review: {work_review}", f"Systemic blockers: {blockers}", f"Production writes: {summary.get('counts', {}).get('writes', 0)}", f"Apply eligibility: {'READY_FOR_APPROVAL' if eligible else 'BLOCKED'}"]
    if manifest:
        lines += ["", "Approval handoff:", f"dry_run_id={manifest['dry_run_id']}", f"commit={manifest['git_commit']}", f"staging_hash={manifest['final_staging_hash']}"]
    text = "\n".join(lines)
    body = "<html><body><pre style='font-family:Arial,sans-serif;white-space:pre-wrap'>" + html.escape(text) + "</pre></body></html>"
    return subject, body, text


def send_resend(subject: str, html_body: str, text_body: str, *, sender=urlopen) -> None:
    """Legacy optional email sender; Cloud Run Status V1 does not require it."""
    api_key = os.getenv("RESEND_API_KEY")
    recipient = os.getenv("INGESTION_NOTIFICATION_EMAIL")
    from_address = os.getenv("RESEND_FROM_EMAIL")
    if not api_key or not recipient or not from_address:
        raise RuntimeError("notification requires RESEND_API_KEY, INGESTION_NOTIFICATION_EMAIL, and RESEND_FROM_EMAIL")
    payload = json.dumps({"from": from_address, "to": [recipient], "subject": subject, "html": html_body, "text": text_body}).encode()
    req = Request("https://api.resend.com/emails", data=payload, method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    with sender(req, timeout=30) as response:
        if response.status not in (200, 201):
            raise RuntimeError(f"Resend returned HTTP {response.status}")


def github_run_url() -> str:
    server, repo, run_id = os.getenv("GITHUB_SERVER_URL"), os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_RUN_ID")
    return f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else ""
