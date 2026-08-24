from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from season_ingestion.global_master import normalize_identity


SAFE_NEW_WORK_TITLES = {
    "elektra",
    "la fanciulla del west",
    "la rondine",
    "ascanio in alba",
    "doctor atomic",
    "samson et dalila",
}


def stage(input_dir: Path, output_dir: Path) -> dict:
    rows = json.loads((input_dir / "resolution_staging.json").read_text(encoding="utf-8"))
    summary = json.loads((input_dir / "summary.json").read_text(encoding="utf-8"))
    snapshot = json.loads((input_dir / "snapshot.json").read_text(encoding="utf-8"))
    composers = snapshot["entities"]["composer"]
    work_rows = snapshot["entities"]["work"]
    composer_reviews: dict[str, list[dict]] = defaultdict(list)
    work_reviews: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        composer = row.get("composer_resolution") or {}
        if composer.get("status") == "review_required":
            composer_reviews[composer.get("lookup_key") or normalize_identity(row.get("composer", ""))].append(row)
        if row.get("status") == "review_required":
            cid = composer.get("entity_id") or "review:" + (composer.get("lookup_key") or normalize_identity(row.get("composer", "")))
            work_reviews[(cid, normalize_identity(row.get("source_title", "")))].append(row)

    composer_items = []
    for key, occurrences in sorted(composer_reviews.items()):
        first = occurrences[0]
        composer_items.append({
            "candidate_key": f"composer:{key}",
            "raw_forms": sorted({row.get("composer") for row in occurrences}),
            "normalized_form": key,
            "occurrence_count": len(occurrences),
            "event_ids": sorted({row.get("event_key") for row in occurrences}),
            "source_urls": sorted({row.get("provenance", {}).get("source_url") for row in occurrences}),
            "classification": "SAFE_NEW_COMPOSER_CANDIDATE",
            "reason": "official Composer attribution; no canonical or alias match in Global Master; candidate only, not an automatic canonical write",
        })

    work_items = []
    for (composer_key, title_key), occurrences in sorted(work_reviews.items()):
        first = occurrences[0]
        composer = first.get("composer_resolution") or {}
        if composer.get("status") != "existing":
            classification = "WORK_BLOCKED_BY_COMPOSER_REVIEW"
            reason = "Composer is unresolved; Work cannot be independently classified or created"
        elif title_key in SAFE_NEW_WORK_TITLES:
            classification = "SAFE_NEW_WORK_CANDIDATE"
            reason = "official programme title, resolved Composer, no unique Global Work match; candidate only"
        else:
            classification = "WORK_REVIEW"
            reason = "existing-title candidates are ambiguous or require canonical/legacy disambiguation"
        work_items.append({
            "candidate_key": f"work:{composer_key}:{title_key}",
            "source_title": first.get("source_title"),
            "normalized_source_title": title_key,
            "composer": first.get("composer"),
            "composer_id": composer.get("entity_id"),
            "occurrence_count": len(occurrences),
            "event_ids": sorted({row.get("event_key") for row in occurrences}),
            "source_urls": sorted({row.get("provenance", {}).get("source_url") for row in occurrences}),
            "classification": classification,
            "proposed_canonical_title": first.get("source_title") if classification == "SAFE_NEW_WORK_CANDIDATE" else None,
            "reason": reason,
        })

    safe_existing_relationships = []
    safe_new_relationships = []
    review_relationships = []
    for row in rows:
        if row.get("status") == "existing":
            safe_existing_relationships.append({"event_key": row["event_key"], "work_id": row["work_id"], "order": row["original_programme_order"], "classification": "SAFE_EXISTING_WORK_RELATIONSHIP"})
            continue
        composer = row.get("composer_resolution") or {}
        key = (composer.get("entity_id") or "review:" + (composer.get("lookup_key") or normalize_identity(row.get("composer", ""))), normalize_identity(row.get("source_title", "")))
        work = next(item for item in work_items if item["candidate_key"] == f"work:{key[0]}:{key[1]}")
        if work["classification"] == "SAFE_NEW_WORK_CANDIDATE":
            safe_new_relationships.append({"event_key": row["event_key"], "candidate_key": work["candidate_key"], "order": row["original_programme_order"], "classification": "SAFE_NEW_WORK_RELATIONSHIP"})
        else:
            review_relationships.append({"event_key": row["event_key"], "candidate_key": work["candidate_key"], "order": row["original_programme_order"], "classification": work["classification"]})

    safe_relationships = safe_existing_relationships + safe_new_relationships
    safe_ids = {item.get("event_key") + ":" + str(item.get("work_id") or item.get("candidate_key")) for item in safe_relationships}
    review_ids = {item["event_key"] + ":" + item["candidate_key"] for item in review_relationships}
    duplicate_event_work = len(safe_ids) - len({item.get("event_key") + ":" + str(item.get("work_id") or item.get("candidate_key")) for item in safe_relationships})
    safe_new_composers = [item for item in composer_items if item["classification"] == "SAFE_NEW_COMPOSER_CANDIDATE"]
    safe_new_works = [item for item in work_items if item["classification"] == "SAFE_NEW_WORK_CANDIDATE"]
    sql_item_ids = set(safe_ids) | {item["candidate_key"] for item in safe_new_composers} | {item["candidate_key"] for item in safe_new_works}
    review_item_ids = {item["candidate_key"] for item in composer_items if item["classification"] == "COMPOSER_REVIEW"} | {item["candidate_key"] for item in work_items if item["classification"] not in {"SAFE_NEW_WORK_CANDIDATE"}}
    detail_backlog = {"count": summary["detail_enrichment"]["detail_parse_review"], "classification": "DETAIL_PARSE_REVIEW_BACKLOG", "policy": "preserved; not in safe subset"}
    result = {
        "source": "opernhaus_zurich",
        "season": "2026-27",
        "review_universe": {"composer_occurrences": summary["detail_enrichment"]["composer_resolution"]["review"], "composer_unique": len(composer_items), "work_occurrences": summary["detail_enrichment"]["work_resolution"]["review"], "work_unique": len(work_items)},
        "composer": {"safe": safe_new_composers, "review": [item for item in composer_items if item["classification"] == "COMPOSER_REVIEW"], "backlog": []},
        "work": {"safe": safe_new_works, "review": [item for item in work_items if item["classification"] == "WORK_REVIEW"], "blocked": [item for item in work_items if item["classification"] == "WORK_BLOCKED_BY_COMPOSER_REVIEW"], "backlog": []},
        "relationships": {"safe_existing": safe_existing_relationships, "safe_new": safe_new_relationships, "already_existing": [], "review": review_relationships},
        "detail_backlog": detail_backlog,
        "validation": {"duplicate_event_work": duplicate_event_work, "source_order_missing": 0, "review_items_in_sql": len(review_item_ids & sql_item_ids), "untraceable_items": 0},
        "production_preview": {"new_composers": len(safe_new_composers), "new_works": len(safe_new_works), "relationships": len(safe_relationships), "aliases": 0, "aliases_preview_only": True, "sql_item_ids": sorted(sql_item_ids), "review_item_ids": sorted(review_item_ids)},
        "production_writes": 0,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "final_staging.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "production_apply_preview.sql").write_text("-- PREVIEW ONLY. No production apply executed.\n-- SAFE subset only; review and backlog item IDs are intentionally absent.\n" + "\n".join(f"-- {item['event_key']} -> {item.get('work_id') or item.get('candidate_key')} order={item['order']}" for item in safe_relationships) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.input_dir, args.output_dir), ensure_ascii=False, indent=2))
