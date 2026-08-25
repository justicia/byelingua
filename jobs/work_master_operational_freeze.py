"""Generate the read-only operational Work Master freeze manifest."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from jobs.work_master_finalization import COMPOSITE_KINDS, COMPOSITE_MARKERS
from season_ingestion.global_master import normalize_identity


def build_freeze(payload: dict, title_overrides: dict | None = None) -> tuple[dict, dict]:
    title_overrides = title_overrides or {}
    works = list(payload.get("works") or [])
    groups = defaultdict(list)
    title_groups = defaultdict(list)
    for row in works:
        key = (str(row.get("composer_id")), normalize_identity(row.get("title")))
        if row.get("composer_id") and key[1]:
            groups[key].append(row)
        title_groups[normalize_identity(row.get("title"))].append(row)
    duplicate_ids = {str(row.get("id")) for group in groups.values() if len(group) > 1 for row in group}
    hard_keys = {key for key, rows in title_groups.items() if key and len({str(row.get("composer_id")) for row in rows}) > 1}

    manifest = []
    counts = defaultdict(int)
    special_11 = 0
    for row in works:
        work_id = str(row.get("id"))
        title = str(title_overrides.get(str(row.get("id")), row.get("title")) or "")
        status = str(row.get("normalization_status") or "")
        kind = str(row.get("work_kind") or "work").casefold()
        key = normalize_identity(title)
        if not row.get("composer_id"):
            special_11 += int(status != "review_required")
            if kind in COMPOSITE_KINDS:
                exclusion = "REVIEW_PROGRAMME_CONTAINER"
            elif re.search(r"\b(gala|programme|program|production)\b|[/+]", title, re.I):
                exclusion = "REVIEW_PRODUCTION_TITLE"
            else:
                exclusion = "REVIEW_MISSING_COMPOSER"
            eligible = False
        elif status == "review_required":
            exclusion = "LEGACY_REVIEW_CANDIDATE"
            eligible = False
        elif kind in COMPOSITE_KINDS or COMPOSITE_MARKERS.search(title):
            exclusion = "REVIEW_COMPOSITE_WORK"
            eligible = False
        elif work_id in duplicate_ids:
            exclusion = "REVIEW_DUPLICATE_WORK"
            eligible = False
        elif key in hard_keys:
            exclusion = "REVIEW_HARD_IDENTITY_CONFLICT"
            eligible = False
        elif status not in {"verified", "resolved", "canonical"}:
            exclusion = "REVIEW_NORMALIZATION_STATUS"
            eligible = False
        else:
            exclusion = None
            eligible = True
        counts["auto_match_eligible"] += int(eligible)
        if exclusion:
            counts[exclusion] += 1
        manifest.append({"work_id": row.get("id"), "composer_id": row.get("composer_id"), "canonical_title": title, "normalization_status": status, "auto_match_eligible": eligible, "exclusion_reason": exclusion})
    summary = {
        "works_total": len(works),
        "auto_match_eligible": counts["auto_match_eligible"],
        "legacy_review_backlog": sum(1 for row in works if str(row.get("normalization_status") or "") == "review_required"),
        "missing_composer_backlog": sum(1 for row in works if not row.get("composer_id")),
        "duplicate_backlog": len(duplicate_ids),
        "hard_conflict_backlog": len(hard_keys),
        "special_11_backlog": special_11,
        "production_writes": 0,
        "migrations": 0,
        "vercel": 0,
    }
    return summary, {"schema_version": "work-master-operational-freeze-v1", "production_writes": 0, "works": manifest}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--title-overrides", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/work-master-v1"))
    args = parser.parse_args()
    overrides = json.loads(args.title_overrides.read_text(encoding="utf-8")) if args.title_overrides else {}
    summary, manifest = build_freeze(json.loads(args.input.read_text(encoding="utf-8")), overrides)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "work_master_operational_freeze.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
