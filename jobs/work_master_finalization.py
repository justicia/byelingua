"""Read-only Work Master V1 audit and runtime staging generator."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from season_ingestion.global_master import load_global_snapshot, normalize_identity


COMPOSITE_KINDS = {"composite_programme", "programme_container", "production_title", "composite"}
COMPOSITE_MARKERS = re.compile(r"\b(and|with|works|selections|highlights|gala|programme|program|concert)\b|[/+]", re.I)


def _has_unicode_issue(value: str) -> bool:
    return any(unicodedata.category(char) == "Cf" or unicodedata.category(char) == "Cc" for char in str(value or ""))


def _groups(rows: list[dict], key):
    groups = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return groups


def audit_work_master(payload: dict) -> tuple[dict, dict]:
    works = list(payload.get("works") or [])
    aliases = list(payload.get("work_aliases") or payload.get("aliases") or [])
    composers = {str(row.get("id")): row for row in payload.get("composers", [])}
    aliases_by_work = defaultdict(list)
    for alias in aliases:
        aliases_by_work[str(alias.get("work_id"))].append(alias)

    composer_title_groups = _groups(
        [row for row in works if row.get("composer_id")],
        lambda row: (str(row.get("composer_id")), normalize_identity(row.get("title"))),
    )
    title_groups = _groups(works, lambda row: normalize_identity(row.get("title")))
    alias_groups = _groups(aliases, lambda row: normalize_identity(row.get("alias")))
    duplicate_ids = {id(row) for group in composer_title_groups.values() if len(group) > 1 for row in group}
    hard_conflict_keys = {key for key, group in title_groups.items() if key and len({str(row.get("composer_id")) for row in group}) > 1}
    alias_collision_keys = {key for key, group in alias_groups.items() if key and len({str(row.get("work_id")) for row in group}) > 1}

    staging = []
    counts = defaultdict(int)
    unicode_issues = 0
    translated_canonical_titles = 0
    for work in works:
        work_id = str(work.get("id"))
        title = str(work.get("title") or "")
        composer_id = work.get("composer_id")
        kind = str(work.get("work_kind") or "work").casefold()
        row_unicode = _has_unicode_issue(title)
        unicode_issues += int(row_unicode)
        key = normalize_identity(title)
        work_aliases = aliases_by_work.get(work_id, [])
        localized_aliases = [alias for alias in work_aliases if alias.get("language") and normalize_identity(alias.get("alias")) != key]
        translated_canonical = bool(work.get("normalization_status") == "translated_canonical" or work.get("canonical_language") not in (None, "original"))
        translated_canonical_titles += int(translated_canonical)

        if kind in COMPOSITE_KINDS or (not composer_id and COMPOSITE_MARKERS.search(title)):
            classification, reason = "REVIEW_COMPOSITE", "programme/composite signal; no automatic Work merge"
        elif not composer_id:
            classification, reason = "REVIEW_COMPOSER", "missing composer_id; no fake Composer assignment"
        elif id(work) in duplicate_ids:
            classification, reason = "SAFE_DEDUP_CANDIDATE", "same Composer plus normalized Work identity appears more than once"
        elif key in hard_conflict_keys:
            classification, reason = "REVIEW_IDENTITY", "same normalized title is used by different Composers"
        elif key in alias_collision_keys:
            classification, reason = "REVIEW_IDENTITY", "alias normalization collides across Work identities"
        elif row_unicode:
            classification, reason = "SAFE_CANONICAL_FIX", "format/control character can be removed without changing lookup identity"
        elif translated_canonical:
            classification, reason = "REVIEW_IDENTITY", "canonical-language metadata indicates a translated title"
        elif localized_aliases:
            classification, reason = "SAFE_EXISTING", "Composer-scoped Work is stable; localized variants remain aliases"
        else:
            classification, reason = "SAFE_EXISTING", "Composer-scoped Work has no detected identity conflict"

        counts[classification] += 1
        staging.append({
            "work_id": work.get("id"),
            "canonical_title": title,
            "composer_id": composer_id,
            "composer_canonical_name": (composers.get(str(composer_id)) or {}).get("canonical_name"),
            "identity_key": key,
            "work_kind": kind,
            "aliases": work_aliases,
            "classification": classification,
            "reason": reason,
            "production_write": False,
        })

    summary = {
        "works_total": len(works),
        "works_with_composer": sum(bool(row.get("composer_id")) for row in works),
        "works_missing_composer": sum(not row.get("composer_id") for row in works),
        "safe_existing": counts["SAFE_EXISTING"],
        "safe_canonical_fix": counts["SAFE_CANONICAL_FIX"],
        "safe_alias_add": counts["SAFE_ALIAS_ADD"],
        "safe_composer_link": counts["SAFE_COMPOSER_LINK"],
        "duplicate_candidates": len(duplicate_ids),
        "review_identity": counts["REVIEW_IDENTITY"],
        "review_composer": counts["REVIEW_COMPOSER"],
        "review_composite": counts["REVIEW_COMPOSITE"],
        "legacy_backlog": sum(counts[name] for name in ("REVIEW_IDENTITY", "REVIEW_COMPOSER", "REVIEW_COMPOSITE", "SAFE_DEDUP_CANDIDATE")),
        "unicode_issues": unicode_issues,
        "translated_canonical_titles": translated_canonical_titles,
        "hard_conflicts": len(hard_conflict_keys) + len(alias_collision_keys),
        "database_writes": 0,
        "migrations": 0,
        "vercel": 0,
    }
    return summary, {"schema_version": "work-master-final-staging-v1", "database_writes": 0, "works": staging}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="runtime read-only Work Master input JSON")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/work-master-v1"))
    args = parser.parse_args()
    if args.input:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    else:
        snapshot = load_global_snapshot()
        payload = {
            "works": snapshot.entities.get("work", []),
            "work_aliases": snapshot.work_aliases,
            "composers": snapshot.entities.get("composer", []),
            "composer_aliases": snapshot.composer_aliases,
        }
    summary, staging = audit_work_master(payload)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "work_master_final_staging.json").write_text(json.dumps(staging, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "work_master_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
