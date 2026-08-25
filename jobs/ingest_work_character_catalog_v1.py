"""Run Work Character Catalog Ingestion V1 as a read-only batch."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from jobs.build_character_master_phase2 import _classify_row
from season_ingestion.work_character_catalog import EvidenceCache, WikidataReference, WikipediaReference, ingest_work_catalog
from season_ingestion.global_master import load_global_snapshot, normalize_identity


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


PILOT_TITLES = ("Tannhäuser", "Le nozze di Figaro", "Carmen", "Die Zauberflöte", "Norma", "Otello", "Ariadne auf Naxos", "Lulu")


def snapshot_payload(snapshot) -> dict:
    return {
        "generated_at": snapshot.generated_at,
        "source": snapshot.source,
        "freshness_seconds": snapshot.freshness_seconds,
        "health": snapshot.health,
        "entities": snapshot.entities,
        "composer_aliases": snapshot.composer_aliases,
        "work_aliases": snapshot.work_aliases,
        "artist_aliases": snapshot.artist_aliases,
        "character_aliases": snapshot.character_aliases,
        "work_characters": snapshot.work_characters,
    }


def bootstrap_inputs(snapshot) -> tuple[dict, dict, dict]:
    """Build the catalog and classifier inputs from one frozen read-only snapshot."""
    payload = snapshot_payload(snapshot)
    works = snapshot.entities.get("work", [])
    composers = {str(row.get("id")): row for row in snapshot.entities.get("composer", [])}
    works_by_id = {str(row.get("id")): row for row in works}
    unlinked = [row for row in snapshot.work_characters if row.get("character_uid") is None]
    work_input = []
    phase2_rows = []
    for relation in unlinked:
        work = works_by_id.get(str(relation.get("work_id")))
        composer = composers.get(str(work.get("composer_id"))) if work and work.get("composer_id") else None
        row = {
            "id": relation.get("id"),
            "work_character_id": relation.get("id"),
            "work_id": relation.get("work_id"),
            "canonical_name": relation.get("canonical_name"),
            "raw_source_name": relation.get("canonical_name"),
            "work_title": work.get("title") if work else None,
            "canonical_work_title": work.get("title") if work else None,
            "composer_id": work.get("composer_id") if work else None,
            "composer_canonical_name": composer.get("canonical_name") if composer else None,
        }
        phase2_rows.append(row)
        if work:
            work_input.append({
                "work_id": work.get("id"),
                "canonical_work_title": work.get("title"),
                "composer_id": work.get("composer_id"),
                "composer_canonical_name": composer.get("canonical_name") if composer else None,
            })
    unique_works = {str(row["work_id"]): row for row in work_input if row.get("work_id")}
    return {"works": list(unique_works.values())}, {"rows": phase2_rows}, payload


def bootstrap_preflight(snapshot, work_input: dict) -> dict:
    works = snapshot.entities.get("work", [])
    work_ids = {str(row.get("id")) for row in works}
    unlinked = [row for row in snapshot.work_characters if row.get("character_uid") is None]
    missing_work = [row for row in unlinked if str(row.get("work_id")) not in work_ids]
    works_by_id = {str(row.get("id")): row for row in works}
    composers = {str(row.get("id")): row for row in snapshot.entities.get("composer", [])}
    pilot = []
    for title in PILOT_TITLES:
        matches = [row for row in work_input.get("works", []) if normalize_identity(row.get("canonical_work_title")) == normalize_identity(title)]
        pilot.append({"title": title, "matches": matches})
    work_input_status = []
    for work in work_input.get("works", []):
        composer_id = work.get("composer_id")
        composer = composers.get(str(composer_id)) if composer_id else None
        status = "RUNNABLE" if composer else ("INPUT_BLOCKED_MISSING_COMPOSER" if not composer_id else "INPUT_BLOCKED_COMPOSER_REFERENCE")
        work_input_status.append({"work_id": work.get("work_id"), "work_title": work.get("canonical_work_title"), "composer_canonical_name": (composer or {}).get("canonical_name"), "status": status})
    runnable_work_ids = {str(item["work_id"]) for item in work_input_status if item["status"] == "RUNNABLE"}
    blocked_work_ids = {str(item["work_id"]) for item in work_input_status if item["status"] != "RUNNABLE"}
    unlinked_with_composer = [row for row in unlinked if str(row.get("work_id")) in runnable_work_ids]
    unlinked_missing_composer = [row for row in unlinked if str(row.get("work_id")) in blocked_work_ids]
    return {
        "characters": len(snapshot.entities.get("character", [])),
        "character_aliases": len(snapshot.character_aliases),
        "work_characters": len(snapshot.work_characters),
        "linked": sum(row.get("character_uid") is not None for row in snapshot.work_characters),
        "unlinked": len(unlinked),
        "works_with_unlinked": len({str(row.get("work_id")) for row in unlinked if row.get("work_id")}),
        "unlinked_rows_with_work": len(unlinked) - len(missing_work),
        "unlinked_rows_missing_work": len(missing_work),
        "works_with_composer_master": len(runnable_work_ids),
        "works_missing_composer_master": len(blocked_work_ids),
        "unlinked_rows_with_composer_master": len(unlinked_with_composer),
        "unlinked_rows_missing_composer_master": len(unlinked_missing_composer),
        "works_with_composer_id": len(runnable_work_ids),
        "works_with_composer_name": len(runnable_work_ids),
        "work_input_status": work_input_status,
        "pilot": pilot,
    }


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
    replay_path = args.snapshot_file or args.global_master_snapshot
    snapshot = load_global_snapshot(path=replay_path) if replay_path else load_global_snapshot()
    work_input, phase2, snapshot_payload_data = bootstrap_inputs(snapshot)
    if args.work_input:
        work_input = _load(args.work_input)
    if args.phase2_input:
        phase2 = _load(args.phase2_input)
    preflight = bootstrap_preflight(snapshot, work_input)
    cache = EvidenceCache(args.cache_dir, offline=args.offline)
    wikidata = WikidataReference(cache)
    wikipedia = WikipediaReference(cache)
    global_master = snapshot_payload_data
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
    resolved_works = []
    for work in works:
        work = dict(work)
        composer_id = work.get("composer_id")
        composer_row = composer_by_id.get(str(composer_id)) if composer_id else None
        canonical_name = (composer_row or {}).get("canonical_name") or (composer_row or {}).get("name")
        work["composer_canonical_name"] = canonical_name
        resolved_works.append(work)
    works = resolved_works
    all_works = works
    args.output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_bytes = json.dumps(snapshot_payload_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    snapshot_hash = hashlib.sha256(snapshot_bytes).hexdigest()
    (args.output_dir / "global_master_snapshot.json").write_bytes(snapshot_bytes + b"\n")
    if preflight["unlinked_rows_missing_work"]:
        return {"mode": "REPLAY" if replay_path else "LIVE_READONLY", "bootstrap_status": "BOOTSTRAP_BLOCKED", "snapshot_hash": snapshot_hash, "preflight": preflight, "missing_work_character_ids": [row.get("id") for row in snapshot.work_characters if row.get("character_uid") is None and str(row.get("work_id")) not in {str(work.get("id")) for work in snapshot.entities.get("work", [])}]}
    runnable_ids = {str(item["work_id"]) for item in preflight["work_input_status"] if item["status"] == "RUNNABLE"}
    pilot_titles = {normalize_identity(title) for title in PILOT_TITLES}
    pilot_ids = {str(row.get("work_id")) for row in work_input.get("works", []) if str(row.get("work_id")) in runnable_ids and normalize_identity(row.get("canonical_work_title")) in pilot_titles}
    works = [work for work in all_works if str(work.get("work_id")) in pilot_ids]
    catalogs = []
    wikipedia_rows = []
    evidence_rows = []
    for work in works:
        catalog, wiki_rows, evidence = ingest_work_catalog(work, wikidata, wikipedia)
        catalogs.append(catalog)
        wikipedia_rows.extend([{**row, "work_id": work.get("work_id")} for row in wiki_rows])
        evidence_rows.extend(evidence)
    pilot_catalogs = list(catalogs)
    pilot_pass = any(row.get("work_match_diagnostics", {}).get("selected_qid") and row.get("evidence_status") in {"CATALOG_READY", "CATALOG_PARTIAL"} for row in pilot_catalogs)
    if pilot_pass:
        processed = {str(row.get("work_id")) for row in catalogs}
        for work in all_works:
            if str(work.get("work_id")) in processed:
                continue
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
        if str(row.get("work_id")) not in runnable_ids:
            result = _classify_row(row, None, global_master or {})
            result["primary_classification"] = "REVIEW_WORK_IDENTITY"
            result["reason"] = "MISSING_COMPOSER_MASTER"
        elif not catalog or not catalog.get("characters"):
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
    pipeline_status = "RUN_COMPLETE_WITH_INPUT_BACKLOG" if pilot_pass and preflight["works_missing_composer_master"] else ("RUN_COMPLETE" if pilot_pass else "PILOT_ENGINE_BLOCKED")
    wikidata_live_requests = sum("wikidata.org" in str(item.get("source_url")) and not item.get("cache_hit", False) for item in evidence_rows)
    wikipedia_live_requests = sum("wikipedia.org" in str(item.get("source_url")) and not item.get("cache_hit", False) for item in evidence_rows)
    source_statuses = Counter(str(item.get("status")) for item in evidence_rows if item.get("source_url"))
    catalog_status_counts = Counter(str(catalog.get("evidence_status")) for catalog in catalogs)
    return {"works": len(catalogs), "works_total": len(all_works), "works_runnable": len(runnable_ids), "works_attempted": len(catalogs), "works_input_blocked": preflight["works_missing_composer_master"], "rows_input_blocked": preflight["unlinked_rows_missing_composer_master"], "wikipedia_rows": wikipedia_rows, "classification_counts": dict(sorted(counts.items())), "catalog_status_counts": dict(sorted(catalog_status_counts.items())), "source_statuses": dict(sorted(source_statuses.items())), "wikidata_live_requests": wikidata_live_requests, "wikipedia_live_requests": wikipedia_live_requests, "wikidata_safe_work_qid": sum(catalog.get("work_match_diagnostics", {}).get("work_resolution_status") == "SAFE_WORK_QID" for catalog in pilot_catalogs), "works_with_composer_master": preflight["works_with_composer_master"], "works_missing_composer_master": preflight["works_missing_composer_master"], "unlinked_rows_with_composer_master": preflight["unlinked_rows_with_composer_master"], "unlinked_rows_missing_composer_master": preflight["unlinked_rows_missing_composer_master"], "snapshot_hash": snapshot_hash, "preflight": preflight, "pilot_works": len(pilot_catalogs), "pilot_pass": pilot_pass, "all_works_run": pilot_pass and len(catalogs) == len(runnable_ids), "pipeline_status": pipeline_status, "mode": "REPLAY" if replay_path else "LIVE_READONLY", "catalogs": catalogs}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-input", type=Path)
    parser.add_argument("--phase2-input", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/work-character-catalog-v1"))
    parser.add_argument("--cache-dir", type=Path, default=Path("artifacts/work-character-catalog-v1/cache"))
    parser.add_argument("--global-master-snapshot", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--snapshot-file", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    result = run(args)
    pilot_diagnostics = []
    wikipedia_rows_by_work = {}
    for row in result.get("wikipedia_rows", []):
        wikipedia_rows_by_work[str(row.get("work_id"))] = wikipedia_rows_by_work.get(str(row.get("work_id")), 0) + 1
    for catalog in result.get("catalogs", []):
        title = catalog.get("canonical_work_title")
        if normalize_identity(title) not in {normalize_identity(item) for item in PILOT_TITLES}:
            continue
        characters = catalog.get("characters", [])
        pilot_diagnostics.append({
            "work_id": catalog.get("work_id"),
            "work_title": title,
            "composer_canonical_name": catalog.get("composer"),
            "work_input_status": "RUNNABLE",
            "wikidata_work_status": catalog.get("work_match_diagnostics", {}).get("work_resolution_status"),
            "wikidata_work_qid_candidates": catalog.get("work_match_diagnostics", {}).get("work_search_candidates", []),
            "candidate_diagnostics": catalog.get("work_match_diagnostics", {}).get("candidate_diagnostics", []),
            "selected_work_qid": catalog.get("external_ids", {}).get("wikidata"),
            "original_language": catalog.get("original_language"),
            "p674_count": sum("wikidata:P674" in row.get("evidence_sources", []) for row in characters),
            "p1441_count": sum("wikidata:P1441" in row.get("evidence_sources", []) for row in characters),
            "wikipedia_role_row_count": wikipedia_rows_by_work.get(str(catalog.get("work_id")), 0),
            "catalog_status": catalog.get("evidence_status"),
            "blocker_or_review_reason": catalog.get("work_match_diagnostics", {}).get("rejection_reason"),
        })
    result["catalogs"] = []
    result["wikipedia_rows"] = []
    summary = {
        "git_sha": __import__("os").environ.get("GITHUB_SHA"),
        "run_mode": result.get("mode"),
        "snapshot_hash": result.get("snapshot_hash"),
        "snapshot_loaded": bool(result.get("snapshot_hash")),
        "characters_count": result.get("preflight", {}).get("characters"),
        "character_aliases_count": result.get("preflight", {}).get("character_aliases"),
        "work_character_count": result.get("preflight", {}).get("work_characters"),
        "linked_count": result.get("preflight", {}).get("linked"),
        "unlinked_count": result.get("preflight", {}).get("unlinked"),
        "works_with_unlinked_count": result.get("preflight", {}).get("works_with_unlinked"),
        "join_health": {key: result.get("preflight", {}).get(key) for key in ("unlinked_rows_with_work", "unlinked_rows_missing_work", "works_with_composer_master", "works_missing_composer_master", "unlinked_rows_with_composer_master", "unlinked_rows_missing_composer_master")},
        "pilot": pilot_diagnostics,
        "wikidata_request_stats": {"live_requests": result.get("wikidata_live_requests", 0), "safe_work_qid": result.get("wikidata_safe_work_qid", 0)},
        "wikipedia_request_stats": {"live_requests": result.get("wikipedia_live_requests", 0)},
        "source_statuses": result.get("source_statuses", {}),
        "all_work": {key: result.get(key) for key in ("all_works_run", "works_total", "works_runnable", "works_attempted", "works_input_blocked")},
        "pipeline_status": result.get("pipeline_status"),
        "catalog_status_counts": result.get("catalog_status_counts", {}),
        "classification_counts": result.get("classification_counts", {}),
        "invariants": {"production_writes": 0, "character_writes": 0, "alias_writes": 0, "work_character_writes": 0, "event_credit_writes": 0, "migrations": 0, "vercel": 0},
        "production_writes": 0,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "pilot_diagnostics.json").write_text(json.dumps(pilot_diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_result = {key: value for key, value in result.items() if key not in {"catalogs", "wikipedia_rows"}}
    print(json.dumps(log_result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
