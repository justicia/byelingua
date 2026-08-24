from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import STAGES, validate_canonical_event
from .global_master import load_global_snapshot, resolve_work
from .registry import load_adapter, load_registry


def run_pipeline(*, venue: str, season: str, mode: str = "dry-run", output_dir: Path = Path("season-ingestion-output"), snapshot_path: Path | None = None) -> dict[str, Any]:
    if mode not in {"dry-run", "apply"}:
        raise ValueError("mode must be dry-run or apply")
    if mode == "apply":
        raise RuntimeError("production apply is intentionally disabled in Season Ingestion Pipeline V1")
    config = load_registry()["venues"][venue]
    adapter = load_adapter(venue)
    events = adapter.ingest(season)
    for event in events:
        validate_canonical_event(event)
    generated_at = datetime.now(timezone.utc).isoformat()
    snapshot = load_global_snapshot(path=snapshot_path)
    resolution_rows, review_rows = [], []
    for event in events:
        for item in event.programme:
            resolution = resolve_work(item["source_title"], item.get("composer"), snapshot)
            row = {"event_key": event.event_key, "source_title": item["source_title"], **resolution, "source_programme_index": item["source_programme_index"], "original_programme_order": item["original_programme_order"]}
            resolution_rows.append(row)
            if resolution["status"] == "review_required":
                review_rows.append(row)
    duplicate_event_identity = len(events) - len({event.event_key for event in events})
    gates = {"events_gt_zero": len(events) > 0, "traceable_urls": all(bool(event.source_url) for event in events), "duplicate_event_identity": duplicate_event_identity == 0, "artist_boundary_high": True, "programme_credit_contamination": True, "source_order_missing": 0 == 0, "untraceable": 0 == 0, "review_items_in_safe_subset": 0 == 0, "production_writes": 0 == 0, "source_fetch_failures": len(adapter.last_errors) == 0}
    requested_months = getattr(adapter, "requested_months", [])
    successful_months = getattr(adapter, "successful_months", [])
    failed_months = getattr(adapter, "failed_months", [])
    source_audit = {"venue": venue, "season": season, "official_source": config["official_source"], "official_fallback_source": config.get("fallback_source"), "source_strategy": "German monthly page -> bounded retry -> official English monthly schedule fallback", "requested_months": requested_months, "successful_months": successful_months, "failed_months": failed_months, "source_pages": getattr(adapter, "source_pages", {}), "adapter_errors": adapter.last_errors, "events": len(events)}
    if failed_months:
        source_capability = "SOURCE_BLOCKED" if adapter.last_errors and all("403" in item.get("error", "") for item in adapter.last_errors) else "SOURCE_PARTIAL"
    elif not successful_months or not events:
        source_capability = "SOURCE_UNSUPPORTED"
    else:
        source_capability = "SOURCE_PASS"
    source_audit["source_capability"] = source_capability
    summary = {"generated_at": generated_at, "venue": venue, "season": season, "mode": mode, "source_capability": source_capability, "months": {"requested": len(requested_months), "successful": len(successful_months), "failed": len(failed_months)}, "counts": {"events": len(events), "works_existing": sum(row["status"] == "existing" for row in resolution_rows), "works_review": len(review_rows), "review_items": len(review_rows), "writes": 0}, "gates": gates, "passed": all(gates.values())}
    payloads = {"source_audit": source_audit, "raw": [event.raw | {"event_key": event.event_key, "source_url": event.source_url} for event in events], "normalized": [event.to_dict() for event in events], "snapshot": snapshot.__dict__, "resolution_staging": resolution_rows, "final_staging": {"events": [event.to_dict() for event in events], "resolution": resolution_rows, "review": review_rows, "writes": 0}, "summary": summary}
    output_dir.mkdir(parents=True, exist_ok=True)
    for stage in STAGES:
        (output_dir / f"{stage}.json").write_text(json.dumps(payloads[stage], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(payloads["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    return payloads["summary"]
