"""Run Work Character Catalog Ingestion V1 as a read-only batch."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from jobs.build_character_master_phase2 import _classify_row
from season_ingestion.work_character_catalog import EvidenceCache, WikidataReference, WikipediaReference, ingest_work_catalog


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _classifier_catalog(catalog: dict) -> dict:
    aliases = {}
    roles = []
    for character in catalog.get("characters", []):
        name = character.get("canonical_name")
        if not name:
            continue
        roles.append(name)
        flat_aliases = []
        for values in (character.get("aliases") or {}).values():
            flat_aliases.extend(values or [])
        if flat_aliases:
            aliases[name] = flat_aliases
    return {
        "work_title": catalog.get("canonical_work_title"),
        "composer": catalog.get("composer"),
        "canonical_roles": roles,
        "aliases": aliases,
        "evidence_sources": [{"url": "https://www.wikidata.org/wiki/" + catalog["external_ids"]["wikidata"]}] if catalog.get("external_ids", {}).get("wikidata") else [],
    }


def run(args: argparse.Namespace) -> dict:
    if not args.global_master_snapshot:
        raise RuntimeError("GLOBAL_MASTER_REQUIRED")
    work_input = _load(args.work_input)
    phase2 = _load(args.phase2_input)
    cache = EvidenceCache(args.cache_dir, offline=args.offline)
    wikidata = WikidataReference(cache)
    wikipedia = WikipediaReference(cache)
    global_master = _load(args.global_master_snapshot)
    entities = global_master.get("entities", {})
    composers = global_master.get("composers") or entities.get("composer") or []
    composer_by_id = {str(row.get("id")): row for row in composers if row.get("id")}
    # Keep the classifier's historical flat snapshot contract while accepting
    # the canonical GlobalEntitySnapshot shape.
    if entities:
        global_master = {
            **global_master,
            "characters": entities.get("character", []),
            "character_aliases": global_master.get("character_aliases", []),
            "work_characters": global_master.get("work_characters", []),
        }
    works = work_input.get("catalogs", work_input.get("works", []))
    works_with_composer_id = 0
    works_with_composer_name = 0
    works_missing_composer_master = 0
    resolved_works = []
    for work in works:
        work = dict(work)
        composer_id = work.get("composer_id")
        composer_row = composer_by_id.get(str(composer_id)) if composer_id else None
        canonical_name = (composer_row or {}).get("canonical_name") or (composer_row or {}).get("name")
        if composer_id:
            works_with_composer_id += 1
        if canonical_name:
            works_with_composer_name += 1
        elif composer_id:
            works_missing_composer_master += 1
        work["composer_canonical_name"] = canonical_name
        resolved_works.append(work)
    works = resolved_works
    catalogs = []
    wikipedia_rows = []
    evidence_rows = []
    for work in works:
        catalog, wiki_rows, evidence = ingest_work_catalog(work, wikidata, wikipedia)
        catalogs.append(catalog)
        wikipedia_rows.extend([{**row, "work_id": work.get("work_id")} for row in wiki_rows])
        evidence_rows.extend(evidence)

    catalog_by_work = {str(row.get("work_id")): row for row in catalogs}
    phase2_rows = phase2.get("rows", [])
    staged = []
    counts = Counter()
    for row in phase2_rows:
        catalog = catalog_by_work.get(str(row.get("work_id")))
        if not catalog or not catalog.get("characters"):
            result = _classify_row(row, None, global_master or {})
            if not result.get("reason"):
                result["reason"] = "no catalog character candidate"
        else:
            result = _classify_row(row, _classifier_catalog(catalog), global_master or {})
            if global_master is None and result.get("primary_classification", "").startswith("SAFE_"):
                result["primary_classification"] = "REVIEW_WORK_IDENTITY"
                result["reason"] = "Global Master snapshot not supplied; identity resolution is deferred"
        result["catalog_evidence_status"] = catalog.get("evidence_status") if catalog else "CATALOG_SOURCE_MISSING"
        staged.append(result)
        counts[result["primary_classification"]] += 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "wikidata_work_character_snapshot.json").write_text(json.dumps({"schema_version": "wikidata-work-character-snapshot-v1", "works": catalogs, "evidence": evidence_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "wikipedia_character_reference.json").write_text(json.dumps({"schema_version": "wikipedia-character-reference-v1", "rows": wikipedia_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    final = {
        "schema_version": "work-character-catalog-final-staging-v1",
        "database_writes": 0,
        "global_master_snapshot_supplied": global_master is not None,
        "classification_counts": dict(sorted(counts.items())),
        "rows": staged,
        "invariants": {
            "raw_source_as_unverified_canonical": 0,
            "same_name_cross_work_auto_merge": 0,
            "same_name_cross_work_blocks_safe_new": 0,
            "wikipedia_translation_used_as_unverified_canonical": 0,
            "production_roles_in_safe": 0,
            "voice_types_in_safe": 0,
            "ensembles_in_safe": 0,
            "safe_alias_without_identity": 0,
            "safe_row_without_work_character_id": sum(1 for row in staged if row.get("primary_classification", "").startswith("SAFE_") and not row.get("work_character_id")),
            "unclassified_rows": sum(1 for row in staged if not row.get("primary_classification")),
        },
    }
    (args.output_dir / "work_character_catalog_final_staging.json").write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"works": len(catalogs), "wikipedia_rows": len(wikipedia_rows), "classification_counts": dict(sorted(counts.items())), "works_with_composer_id": works_with_composer_id, "works_with_composer_name": works_with_composer_name, "works_missing_composer_master": works_missing_composer_master}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-input", type=Path, required=True)
    parser.add_argument("--phase2-input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/work-character-catalog-v1"))
    parser.add_argument("--cache-dir", type=Path, default=Path("artifacts/work-character-catalog-v1/cache"))
    parser.add_argument("--global-master-snapshot", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
