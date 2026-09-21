#!/usr/bin/env python3
"""Read-only production audit for publication-policy violations."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.event_policy import classify_performance_type, event_requires_cast, visitor_exclusion_reason
from season_ingestion.production_completeness import _readonly_rows
from season_ingestion.season import resolve_season_bounds


def _production_rows(season: str, *, page_size: int = 1000) -> list[dict]:
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not base_url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    start_date, end_date = resolve_season_bounds(season)
    rows, offset = [], 0
    while True:
        query = urlencode([
            ("select", "event_id,source,source_url,events!inner(id,event_key,title,date,event_type)"),
            ("events.date", f"gte.{start_date}"),
            ("events.date", f"lte.{end_date}"),
            ("order", "event_id"),
            ("limit", page_size),
            ("offset", offset),
        ])
        request = Request(
            f"{base_url}/rest/v1/event_sources?{query}",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
        )
        with urlopen(request, timeout=60) as response:
            page = json.loads(response.read().decode("utf-8"))
        rows.extend(row for row in page if isinstance(row, dict))
        if len(page) < page_size:
            return rows
        offset += page_size


def run(season: str) -> dict:
    source_rows = _production_rows(season)
    by_event: dict[str, dict] = {}
    event_sources: dict[str, set[str]] = defaultdict(set)
    for row in source_rows:
        event_id = str(row.get("event_id") or "")
        event = row.get("events") or {}
        if isinstance(event, list):
            event = event[0] if event else {}
        if not event_id or not isinstance(event, dict):
            continue
        by_event.setdefault(event_id, event)
        if row.get("source"):
            event_sources[event_id].add(str(row["source"]))
    event_ids = sorted(by_event)
    programme = _readonly_rows("event_programme", "event_id,work_id", event_ids, page_size=100, prefer_secret=True)
    credits = _readonly_rows("event_credits", "event_id,artist_id,role,character_id", event_ids, page_size=100, prefer_secret=True)
    programme_by_event = Counter(str(row.get("event_id")) for row in programme if row.get("event_id"))
    credits_by_event = Counter(str(row.get("event_id")) for row in credits if row.get("event_id"))
    grouped: dict[str, list[str]] = defaultdict(list)
    for event_id in event_ids:
        source = sorted(event_sources[event_id])[0] if event_sources[event_id] else "unknown"
        grouped[source].append(event_id)

    venues = []
    for source_id, source_event_ids in grouped.items():
        visitor, unclassified, cast_missing = [], [], []
        current_types, policy_types = Counter(), Counter()
        for event_id in source_event_ids:
            row = by_event[event_id]
            title = str(row.get("title") or "")
            current_type = str(row.get("event_type") or "performance")
            event = SimpleNamespace(title=title, event_type=current_type, raw={"source_event_type": current_type})
            current_types[current_type] += 1
            reason = visitor_exclusion_reason(event)
            if reason:
                visitor.append({"event_id": event_id, "title": title, "date": row.get("date"), "reason": reason})
                continue
            policy_type = classify_performance_type(event)
            policy_types[policy_type] += 1
            if policy_type == "unclassified_performance":
                unclassified.append({"event_id": event_id, "title": title, "date": row.get("date")})
            if event_requires_cast(SimpleNamespace(event_type=policy_type)) and credits_by_event[event_id] == 0:
                cast_missing.append({"event_id": event_id, "title": title, "date": row.get("date"), "event_type": policy_type})
        venues.append({
            "venue_id": source_id,
            "source_id": source_id,
            "events": len(source_event_ids),
            "programme_relationships": sum(programme_by_event[event_id] for event_id in source_event_ids),
            "credits": sum(credits_by_event[event_id] for event_id in source_event_ids),
            "events_without_programme": sum(programme_by_event[event_id] == 0 for event_id in source_event_ids),
            "events_without_credits": sum(credits_by_event[event_id] == 0 for event_id in source_event_ids),
            "visitor_events": len(visitor),
            "unclassified_performances": len(unclassified),
            "required_cast_missing": len(cast_missing),
            "current_event_types": dict(sorted(current_types.items())),
            "policy_event_types": dict(sorted(policy_types.items())),
            "visitor_sample": visitor[:20],
            "unclassified_sample": unclassified[:20],
            "cast_missing_sample": cast_missing[:20],
        })
    venues.sort(key=lambda row: (-(row["visitor_events"] + row["unclassified_performances"] + row["events_without_credits"]), row["venue_id"]))
    total_keys = (
        "events", "programme_relationships", "credits", "events_without_programme",
        "events_without_credits", "visitor_events", "unclassified_performances", "required_cast_missing",
    )
    return {
        "schema_version": "publication-policy-audit-v2",
        "season": season,
        "production_writes": 0,
        "totals": {key: sum(int(row[key]) for row in venues) for key in total_keys},
        "venues": venues,
        "errors": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.season)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["totals"], ensure_ascii=False))
    print(f"VENUES={len(result['venues'])}")
    print("PRODUCTION_WRITES=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
