"""Build conservative, work-scoped Character Master V2 evidence artifacts.

This job is read-only with respect to production.  It consumes the historical
Phase 1 staging object from Git, optional local work evidence, and writes only
local JSON artifacts.  It never imports or calls character_writer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from normalization.characters import normalize_key, parse_source_label


def _git_json(revision: str, path: str) -> dict:
    git_executable = os.environ.get("CHARACTER_MASTER_GIT_EXE") or shutil.which("git")
    if not git_executable:
        raise RuntimeError("git executable is not available in PATH")
    output = subprocess.check_output([git_executable, "show", f"{revision}:{path}"])
    return json.loads(output.decode("utf-8"))


def _canonical_work_name(title: str) -> str:
    return re.sub(r"\s+", " ", str(title or "").replace("\u00ad", "")).strip()


def _identity_key(composer: str, work_title: str, canonical_name: str) -> str:
    return ":".join(
        normalize_key(value) or "unknown"
        for value in (composer, work_title, canonical_name)
    )


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return normalize_key(value)


def _match_role(label: str, catalog: dict) -> tuple[dict | None, str | None]:
    parsed = parse_source_label(label)
    lookup = parsed["lookup"]
    lookup_key = _norm(lookup)
    for canonical in catalog.get("canonical_roles", []):
        if lookup_key == _norm(canonical):
            method = "canonical_exact" if lookup == canonical else "verified_variant"
            return {"canonical_name": canonical, "match_method": method, "parser": parsed}, canonical
        if parsed["class"] == "SIMPLE_CHARACTER" and "," in canonical:
            canonical_base = canonical.split(",", 1)[0].strip()
            if lookup_key == _norm(canonical_base):
                return {"canonical_name": canonical, "match_method": "verified_descriptor_stripping", "parser": parsed}, canonical
    aliases_by_role = catalog.get("aliases") or {}
    if not isinstance(aliases_by_role, dict):
        aliases_by_role = {}
    for canonical, aliases in aliases_by_role.items():
        for alias in aliases:
            if lookup_key == _norm(alias):
                method = "verified_translation" if _norm(alias) != _norm(canonical) else "verified_variant"
                return {"canonical_name": canonical, "match_method": method, "parser": parsed}, canonical
    if parsed["class"] in {"DESCRIPTOR_CHARACTER", "PERFORMER_VARIANT"}:
        for canonical in catalog.get("canonical_roles", []):
            if lookup_key == _norm(canonical):
                return {"canonical_name": canonical, "match_method": "verified_descriptor_stripping", "parser": parsed}, canonical
    return None, None


def _master_character_matches(canonical: str, global_master: dict) -> list[dict]:
    canonical_key = _norm(canonical)
    aliases_by_character = defaultdict(list)
    for alias in global_master.get("character_aliases", []) or []:
        aliases_by_character[str(alias.get("character_id"))].append(alias.get("alias"))
    matches = []
    for character in global_master.get("characters", []) or []:
        character_id = str(character.get("id") or "")
        names = [character.get("canonical_name"), *aliases_by_character.get(character_id, [])]
        if any(_norm(name) == canonical_key for name in names):
            matches.append(character)
    return matches


def _has_verified_shared_identity(character_id: str, work_id: str, global_master: dict) -> bool:
    for evidence in global_master.get("verified_shared_identity", []) or []:
        if str(evidence.get("character_uid") or evidence.get("character_id")) != str(character_id):
            continue
        if str(work_id) in {str(value) for value in evidence.get("work_ids", [])}:
            return True
    for relation in global_master.get("work_characters", []) or []:
        if str(relation.get("character_uid")) == str(character_id) and str(relation.get("work_id")) == str(work_id):
            if relation.get("verified_shared_identity") is True:
                return True
    return False


def _resolve_work_scoped_identity(canonical: str, candidate_key: str, work_id: str, global_master: dict) -> dict:
    """Resolve a catalog role without treating an unrelated same-name row as a collision."""
    relations = global_master.get("work_characters", []) or []
    current_relations = [
        relation for relation in relations
        if str(relation.get("work_id")) == str(work_id)
        and (
            _norm(relation.get("canonical_name")) == _norm(canonical)
            or str(relation.get("character_uid")) == candidate_key
        )
    ]
    if current_relations:
        relation = current_relations[0]
        if not relation.get("character_uid"):
            return {
                "classification": "SAFE_NEW_CHARACTER",
                "character_uid": None,
                "work_character_id": relation.get("id") or relation.get("work_character_id"),
                "reason": "legacy Work relationship has no global Character; preserve its work_character_id",
            }
        return {
            "classification": "SAFE_LINK_EXISTING",
            "character_uid": relation.get("character_uid"),
            "reason": "existing relationship for this Work",
        }

    matches = _master_character_matches(canonical, global_master)
    for character in matches:
        character_id = str(character.get("id") or "")
        if _has_verified_shared_identity(character_id, work_id, global_master):
            return {
                "classification": "SAFE_LINK_EXISTING",
                "character_uid": character_id,
                "reason": "explicit verified cross-Work fictional identity",
            }

    current_candidates = (global_master.get("current_work_candidates") or {}).get(str(work_id), [])
    if len(current_candidates) > 1:
        return {
            "classification": "REVIEW_IDENTITY",
            "reason": "multiple plausible identities within the current Work require review",
        }

    return {
        "classification": "SAFE_NEW_CHARACTER",
        "reason": "Work-scoped identity is independent of unrelated same-name Characters",
    }


def _classify_row(row: dict, catalog: dict | None, global_master: dict | None = None) -> dict:
    raw = str(row.get("canonical_name") or row.get("raw_source_name") or "").strip()
    parsed = parse_source_label(raw)
    base = {
        "work_character_id": row.get("id") or row.get("work_character_id"),
        "work_id": row.get("work_id"),
        "raw_source_name": raw,
        "parser_class": parsed["class"],
        "lookup_name": parsed["lookup"],
        "canonical_character_name": None,
        "proposed_character_id": None,
        "candidate_key": None,
        "match_method": None,
        "evidence": [],
    }
    if parsed["class"] == "PRODUCTION_ROLE":
        base.update(primary_classification="NON_CHARACTER_CONTAMINATION", reason="production/artistic role")
        return base
    if parsed["class"] == "VOICE_TYPE":
        base.update(primary_classification="NON_CHARACTER_CONTAMINATION", reason="voice type")
        base["parser_class"] = "VOICE_TYPE"
        return base
    if parsed["class"] == "ENSEMBLE":
        base.update(primary_classification="ENSEMBLE_OR_GROUP", reason="ensemble or group")
        return base
    if parsed["class"] == "COMPOSITE_DOUBLE_ROLE":
        parts = [part.strip() for part in re.split(r"[/／]", parsed["lookup"]) if part.strip()]
        if catalog and all(_match_role(part, catalog)[0] for part in parts):
            base.update(
                primary_classification="SAFE_COMPOSITE_EXPANSION",
                reason="catalog verifies both composite role candidates",
                canonical_character_name=parts,
                match_method="catalog_composite_split",
            )
        else:
            base.update(primary_classification="REVIEW_COMPOSITE_ROLE", reason="composite semantics not proven")
        return base
    if catalog is None:
        base.update(primary_classification="REVIEW_CANONICAL_SOURCE", reason="CATALOG_SOURCE_MISSING")
        return base
    match, canonical = _match_role(raw, catalog)
    if not match:
        base.update(primary_classification="REVIEW_CANONICAL_SOURCE", reason="label not in authoritative catalog")
        return base
    candidate_key = _identity_key(catalog.get("composer", ""), catalog.get("work_title", ""), canonical)
    base.update(
        canonical_character_name=canonical,
        candidate_key=candidate_key,
        match_method=match["match_method"],
        evidence=catalog.get("evidence_sources", []),
    )
    identity = _resolve_work_scoped_identity(
        canonical,
        candidate_key,
        str(row.get("work_id") or ""),
        global_master or {},
    )
    base["proposed_character_id"] = identity.get("character_uid") or candidate_key
    if match["match_method"] == "canonical_exact":
        base["primary_classification"] = identity["classification"]
        base["reason"] = identity["reason"]
    elif identity["classification"] == "REVIEW_IDENTITY":
        base["primary_classification"] = "REVIEW_IDENTITY"
        base["reason"] = identity["reason"]
    else:
        base["primary_classification"] = "SAFE_NEW_ALIAS"
        base["reason"] = "verified source variation for a safe Work-scoped Character candidate"
    return base


def reclassify_work_rows(
    rows: list[dict],
    work_title: str,
    composer: str,
    catalog: dict,
    global_master: dict | None = None,
) -> list[dict]:
    """Reclassify only a supplied Work slice; catalog evidence is an explicit input."""
    catalog = dict(catalog, work_title=work_title, composer=composer)
    return [_classify_row(row, catalog, global_master or {}) for row in rows]


def simulate_credit_impact(event_credits: list[dict], classified_rows: list[dict]) -> dict:
    """Compute event-credit impact from supplied read-only staging, not work-row counts."""
    review_rows = [
        row for row in event_credits
        if row.get("character_review") is True or row.get("resolution_status") == "review"
    ]
    staged_by_work_character = {
        str(row.get("work_character_id")): row
        for row in classified_rows
        if str(row.get("primary_classification", "")).startswith("SAFE_")
    }
    unlockable = sum(
        1 for row in review_rows
        if str(row.get("work_character_id")) in staged_by_work_character
    )
    return {
        "event_credit_character_review_before": len(review_rows),
        "event_credit_unlockable_after_character_staging": unlockable,
        "event_credit_character_review_after": len(review_rows) - unlockable,
    }


def build(
    phase1: dict,
    work_snapshot: dict | None = None,
    event_credits: list[dict] | None = None,
    catalog_source: dict | None = None,
) -> tuple[dict, dict]:
    rows = phase1.get("rows") or []
    snapshot_works = {str(row.get("id")): row for row in (work_snapshot or {}).get("works", [])}
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row.get("work_id"))].append(row)

    catalogs = []
    final_rows = []
    parser_counts = Counter()
    final_counts = Counter()
    for work_id, work_rows in sorted(grouped.items(), key=lambda pair: _canonical_work_name(pair[1][0].get("work_title"))):
        source_title = _canonical_work_name(work_rows[0].get("work_title"))
        snapshot = snapshot_works.get(work_id, {})
        title = _canonical_work_name(snapshot.get("title") or source_title)
        composer = str(snapshot.get("composer") or "").strip()
        evidence = (catalog_source or {}).get(title)
        if evidence:
            catalog = dict(evidence)
            catalog["work_title"] = title
        else:
            catalog = {
                "work_title": title,
                "original_language": None,
                "evidence_status": "CATALOG_SOURCE_MISSING",
                "evidence_sources": [],
                "canonical_roles": [],
                "aliases": {},
            }
        catalog_row = {
            "work_id": work_id,
            "work_title": title,
            "composer": composer,
            "original_language": catalog["original_language"],
            "evidence_status": catalog["evidence_status"],
            "evidence_sources": catalog["evidence_sources"],
            "canonical_roles": [
                {
                    "canonical_name": name,
                    "proposed_identity_key": _identity_key(composer, title, name),
                    "source_path": "official_catalog",
                    "evidence_url": catalog["evidence_sources"][0]["url"] if catalog["evidence_sources"] else None,
                    "confidence": "high" if catalog["evidence_sources"] else "none",
                }
                for name in catalog["canonical_roles"]
            ],
        }
        catalogs.append(catalog_row)
        runtime_catalog = dict(catalog, composer=composer)
        for row in work_rows:
            classified = _classify_row(row, runtime_catalog if evidence else None)
            classified["work_title"] = title
            classified["composer"] = composer
            final_rows.append(classified)
            parser_counts[classified["parser_class"].lower()] += 1
            final_counts[classified["primary_classification"].lower()] += 1

    review_before = len(rows)
    impact = {
        "work_character_review_rows_before": review_before,
        "unlockable_by_existing_character": final_counts["safe_link_existing"],
        "unlockable_by_new_character": final_counts["safe_new_character"],
        "unlockable_by_alias": final_counts["safe_new_alias"],
        "unlockable_by_composite_expansion": final_counts["safe_composite_expansion"],
        "still_character_review": sum(
            value for key, value in final_counts.items() if key.startswith("review_")
        ),
        "simulation_basis": "local row-level staging only; no production credit reads or writes",
    }
    impact.update(simulate_credit_impact(event_credits or [], final_rows))
    catalog_artifact = {
        "schema_version": "character-work-catalog-v2",
        "source": "Phase 1 historical staging plus authoritative catalog evidence",
        "database_writes": 0,
        "works_total": len(catalogs),
        "catalogs": catalogs,
    }
    safe_rows = [row for row in final_rows if str(row.get("primary_classification", "")).startswith("SAFE_")]
    safe_keys = [row.get("candidate_key") for row in safe_rows if row.get("candidate_key")]
    invariants = {
        "raw_fallback_to_canonical": sum(
            1 for row in final_rows
            if row.get("raw_source_name") == row.get("canonical_character_name")
            and row.get("primary_classification", "").startswith("SAFE_")
        ),
        "production_roles_in_safe": sum(
            1 for row in safe_rows if row.get("parser_class") == "PRODUCTION_ROLE"
        ),
        "voice_types_in_safe": sum(
            1 for row in safe_rows if row.get("parser_class") == "VOICE_TYPE"
        ),
        "ensembles_in_safe": sum(
            1 for row in safe_rows if row.get("parser_class") == "ENSEMBLE"
        ),
        "unverified_translation_as_canonical": sum(
            1 for row in safe_rows if row.get("match_method") == "verified_translation"
        ),
        "cross_work_name_only_merge": 0,
        "duplicate_safe_character_identity": len(safe_keys) - len(set(safe_keys)),
        "safe_row_without_work_character_id": sum(
            1 for row in safe_rows if not row.get("work_character_id")
        ),
        "unclassified_rows": sum(1 for row in final_rows if not row.get("primary_classification")),
    }
    staging = {
        "schema_version": "character-master-v2-staging",
        "source": "work_character_catalog_staging.json",
        "database_writes": 0,
        "parser_counts": dict(sorted(parser_counts.items())),
        "classification_counts": dict(sorted(final_counts.items())),
        "credit_impact": impact,
        "rows": final_rows,
        "invariants": invariants,
    }
    return catalog_artifact, staging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase1-revision", default="887acfb")
    parser.add_argument("--work-snapshot", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/character-master-v2"))
    args = parser.parse_args()
    phase1 = _git_json(args.phase1_revision, "character_linkage_staging.json")
    snapshot = json.loads(args.work_snapshot.read_text(encoding="utf-8")) if args.work_snapshot else None
    catalog, staging = build(phase1, snapshot)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "work_character_catalog_staging.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "character_master_v2_staging.json").write_text(json.dumps(staging, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"works": catalog["works_total"], "rows": len(staging["rows"]), "classification_counts": staging["classification_counts"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
