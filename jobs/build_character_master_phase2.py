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
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from normalization.characters import normalize_key, parse_source_label


OFFICIAL_CATALOGS = {
    "Tannhäuser": {
        "original_language": "de",
        "evidence_status": "CATALOG_READY",
        "evidence_sources": [
            {
                "url": "https://www.staatsoper.de/stuecke/tannhaeuser",
                "publisher": "Bayerische Staatsoper",
                "type": "official_production_cast",
            }
        ],
        "canonical_roles": [
            "Hermann, Landgraf von Thüringen",
            "Tannhäuser",
            "Wolfram von Eschenbach",
            "Walther von der Vogelweide",
            "Biterolf",
            "Heinrich der Schreiber",
            "Reinmar von Zweter",
            "Elisabeth, Nichte des Landgrafen",
            "Venus",
            "Ein junger Hirt",
        ],
        "aliases": {
            "Ein junger Hirt": ["Un Joven Pastor"],
            "Walther von der Vogelweide": ["Walter von der Vogelweide"],
            "Wolfram von Eschenbach": ["Wolfram Von Eschenbach"],
            "Heinrich der Schreiber": ["Heinrich Der Schreiber"],
        },
    },
    "Le nozze di Figaro": {
        "original_language": "it",
        "evidence_status": "CATALOG_READY",
        "evidence_sources": [
            {
                "url": "https://www.metopera.org/globalassets/discover/education/educator-guides/figaro/figaro.pdf",
                "publisher": "The Metropolitan Opera",
                "type": "official_character_guide",
            }
        ],
        "canonical_roles": [
            "Il Conte Almaviva",
            "La Contessa Almaviva",
            "Figaro",
            "Susanna",
            "Cherubino",
            "Marcellina",
            "Bartolo",
            "Basilio",
            "Don Curzio",
            "Barbarina",
            "Antonio",
        ],
        "aliases": {
            "Il Conte Almaviva": ["Count Almaviva", "Graf Almaviva"],
            "La Contessa Almaviva": ["Countess Almaviva", "Gräfin Almaviva"],
        },
    },
}


def _git_json(revision: str, path: str) -> dict:
    git_executable = os.environ.get(
        "CHARACTER_MASTER_GIT_EXE",
        r"C:\Users\cheng\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe",
    )
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


def _classify_row(row: dict, catalog: dict | None) -> dict:
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
    base.update(
        canonical_character_name=canonical,
        candidate_key=_identity_key(catalog.get("composer", ""), catalog.get("work_title", ""), canonical),
        match_method=match["match_method"],
        evidence=catalog.get("evidence_sources", []),
    )
    if match["match_method"] == "canonical_exact":
        base["primary_classification"] = "REVIEW_CROSS_WORK_IDENTITY"
        base["reason"] = "canonical catalog match; existing global collision not locally verifiable"
    else:
        base["primary_classification"] = "REVIEW_LOCALIZED_ALIAS"
        base["reason"] = "verified source variation; alias requires production review"
    return base


def build(phase1: dict, work_snapshot: dict | None = None) -> tuple[dict, dict]:
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
        evidence = OFFICIAL_CATALOGS.get(title)
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
        "review_character_credits_before": review_before,
        "unlockable_by_existing_character": final_counts["safe_link_existing"],
        "unlockable_by_new_character": final_counts["safe_new_character"],
        "unlockable_by_alias": final_counts["safe_new_alias"],
        "unlockable_by_composite_expansion": final_counts["safe_composite_expansion"],
        "still_character_review": sum(
            value for key, value in final_counts.items() if key.startswith("review_")
        ),
        "simulation_basis": "local row-level staging only; no production credit reads or writes",
    }
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
