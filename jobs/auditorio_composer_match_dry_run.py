"""Phase 3 Auditorio composer-identity matcher dry-run.

This job consumes only validated Phase 2 composer inputs.  It never writes to
Supabase and intentionally does not inspect works or attempt Work matching.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from season_ingestion.auditorio_structure import (
    cast_line,
    ensemble_signal,
    has_role_suffix,
    is_role,
    work_signal,
)


LIFESPAN_RE = re.compile(
    r"\s*\((?:\*|ca\.\s*)?\d{3,4}(?:\s*[–—-]\s*(?:\*|ca\.\s*)?\d{2,4})?\)\s*$",
    re.I,
)
MALFORMED_MARKERS = ("universo",)
FUZZY_REVIEW_THRESHOLD = 0.86


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def lookup_normalize(value: str) -> str:
    value = normalize_space(LIFESPAN_RE.sub("", value))
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return normalize_space(value)


def exact_normalize(value: str) -> str:
    return normalize_space(LIFESPAN_RE.sub("", value)).casefold()


def lifespan_evidence(value: str) -> str | None:
    match = LIFESPAN_RE.search(value)
    return match.group(0).strip() if match else None


def split_components(raw: str) -> list[str]:
    return [part.strip() for part in raw.split("/") if part.strip()] or [raw]


def load_master_snapshot(path: str) -> dict[str, Any]:
    """Load read-only canonical/alias evidence from the existing matcher output.

    The repository has no checked-in Composer table export. The existing Paris
    matcher dry-run contains canonical IDs and the alias matches it read from
    the production Composer Master; it is used here as an offline snapshot.
    """
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    composers: dict[str, dict[str, Any]] = {}
    aliases: list[dict[str, Any]] = []
    for page in document.get("verified", []) + document.get("review", []):
        for match in page.get("composer_matches", []):
            composer_id = match.get("composer_id")
            canonical_name = match.get("canonical_name")
            raw_name = match.get("raw_name")
            if not composer_id or not canonical_name:
                continue
            composers[composer_id] = {"id": composer_id, "canonical_name": canonical_name}
            if raw_name and raw_name != canonical_name:
                aliases.append({"composer_id": composer_id, "alias": raw_name})
    return {"composers": list(composers.values()), "composer_aliases": aliases}


def build_indexes(master: dict[str, Any]) -> dict[str, Any]:
    composers = {row["id"]: row for row in master.get("composers", []) if row.get("id")}
    by_exact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_normalized: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in composers.values():
        record = {"composer_id": row["id"], "canonical_name": row.get("canonical_name"), "match_method": "canonical_name"}
        by_exact[exact_normalize(row["canonical_name"])].append(record)
        by_normalized[lookup_normalize(row["canonical_name"])].append(record)
    for row in master.get("composer_aliases", []):
        composer = composers.get(row.get("composer_id"))
        alias = row.get("alias")
        if not composer or not alias:
            continue
        record = {"composer_id": composer["id"], "canonical_name": composer["canonical_name"], "matched_alias": alias, "match_method": "composer_alias"}
        by_exact[exact_normalize(alias)].append(record)
        by_normalized[lookup_normalize(alias)].append(record)
    return {"composers": composers, "by_exact": by_exact, "by_normalized": by_normalized}


def candidate_matches(raw: str, indexes: dict[str, Any]) -> list[dict[str, Any]]:
    target = lookup_normalize(raw)
    scored: list[dict[str, Any]] = []
    for key, rows in indexes["by_normalized"].items():
        score = difflib.SequenceMatcher(None, target, key).ratio()
        if score >= FUZZY_REVIEW_THRESHOLD:
            for row in rows:
                scored.append({"composer_id": row["composer_id"], "canonical_name": row["canonical_name"], "score": round(score, 4)})
    unique = {row["composer_id"]: row for row in scored}
    return sorted(unique.values(), key=lambda row: row["score"], reverse=True)[:5]


def false_positive_reason(raw: str, classification: str) -> str | None:
    if classification not in {"composer_candidate", "inline_composer_work", "composer_attribution"}:
        return "unapproved_classification"
    if not raw.strip():
        return "empty_composer_input"
    if ensemble_signal(raw):
        return "ensemble_input"
    if cast_line(raw) or has_role_suffix(raw) or is_role(raw):
        return "performer_role_or_cast_input"
    if work_signal(raw) or raw.casefold().startswith("obras de"):
        return "work_or_programme_text"
    if raw.casefold().startswith("tradicional de "):
        return "non_person_traditional_attribution"
    return None


def resolve_component(raw: str, indexes: dict[str, Any]) -> dict[str, Any]:
    raw = raw.strip()
    result: dict[str, Any] = {
        "raw_component_text": raw,
        "lookup_normalized": lookup_normalize(raw),
        "match_status": "unmatched",
        "canonical_composer_id": None,
        "canonical_composer_name": None,
        "match_method": None,
        "matched_alias": None,
        "candidate_matches": [],
        "confidence": None,
        "evidence": [],
        "review_reason": None,
    }
    life = lifespan_evidence(raw)
    if life:
        result["evidence"].append({"type": "lifespan", "value": life})
    if any(marker in lookup_normalize(raw).split() for marker in MALFORMED_MARKERS):
        result["review_reason"] = "malformed_source_identity_not_repaired"
        result["candidate_matches"] = candidate_matches(raw, indexes)
        return result

    exact = indexes["by_exact"].get(exact_normalize(raw), [])
    normalized = indexes["by_normalized"].get(lookup_normalize(raw), [])
    for method, matches in (("exact", exact), ("normalized_exact", normalized)):
        unique = {row["composer_id"]: row for row in matches}
        if len(unique) == 1:
            row = next(iter(unique.values()))
            if len(lookup_normalize(raw).split()) == 1 and len(lookup_normalize(row["canonical_name"]).split()) > 1 and not row.get("matched_alias"):
                result["match_status"] = "ambiguous"
                result["candidate_matches"] = list(unique.values())
                result["review_reason"] = "surname_only_collision_guard"
                return result
            result.update({
                "match_status": "alias" if row.get("matched_alias") and method == "exact" else "normalized_alias" if row.get("matched_alias") else method,
                "canonical_composer_id": row["composer_id"],
                "canonical_composer_name": row["canonical_name"],
                "match_method": method,
                "matched_alias": row.get("matched_alias"),
                "confidence": "high",
            })
            if life:
                result["evidence"].append({"type": "lifespan_assisted_lookup", "value": life})
            return result
        if len(unique) > 1:
            result["match_status"] = "ambiguous"
            result["candidate_matches"] = list(unique.values())
            result["review_reason"] = "multiple_canonical_composer_ids_for_lookup"
            return result

    result["candidate_matches"] = candidate_matches(raw, indexes)
    if result["candidate_matches"]:
        result["review_reason"] = "fuzzy_candidates_review_only"
    else:
        result["review_reason"] = "no_exact_or_alias_match"
    return result


def collect_inputs(classification_path: str) -> list[dict[str, Any]]:
    document = json.loads(Path(classification_path).read_text(encoding="utf-8"))
    inputs = []
    for page in document.get("pages", []):
        for line in page.get("classified_lines", []):
            classification = line.get("classification")
            components: list[tuple[str, str, dict[str, Any]]] = []
            if classification == "composer_candidate":
                components = [(part, line.get("raw_text", ""), {}) for part in split_components(line.get("raw_text", ""))]
            elif classification == "work_candidate" and line.get("inline_composer_work", {}).get("raw_composer_fragment"):
                fragment = line["inline_composer_work"]["raw_composer_fragment"]
                components = [(part, line.get("raw_text", ""), {"fragment_provenance": "inline_composer_work", "input_classification": "inline_composer_work"}) for part in split_components(fragment)]
            elif classification == "composer_attribution":
                components = [(part, line.get("raw_text", ""), {"fragment_provenance": "raw_named_composer_fragments"}) for part in line.get("raw_named_composer_fragments", [])]
            for raw_component, raw_composer_text, provenance in components:
                inputs.append({
                    "source_url": page.get("source_url"),
                    "raw_title": page.get("raw_title"),
                    "raw_composer_text": raw_composer_text,
                    "raw_component_text": raw_component,
                    "classification_source": provenance.pop("input_classification", classification),
                    "block_order": line.get("block_order"),
                    "line_order": line.get("line_order"),
                    **provenance,
                })
    return inputs


def match_inputs(inputs: list[dict[str, Any]], indexes: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results = []
    alias_gaps = []
    for occurrence_id, item in enumerate(inputs, start=1):
        raw = item["raw_component_text"]
        gate = false_positive_reason(raw, item["classification_source"])
        match = resolve_component(raw, indexes) if not gate else {
            "raw_component_text": raw,
            "lookup_normalized": lookup_normalize(raw),
            "match_status": "false_positive_input",
            "canonical_composer_id": None,
            "canonical_composer_name": None,
            "match_method": None,
            "matched_alias": None,
            "candidate_matches": [],
            "confidence": None,
            "evidence": [],
            "review_reason": gate,
        }
        result = {"occurrence_id": occurrence_id, **item, **match}
        results.append(result)
        if match["match_status"] == "unmatched" and match["candidate_matches"] and not gate:
            top = match["candidate_matches"][0]
            alias_gaps.append({
                "raw_alias": raw,
                "suggested_composer_id": top["composer_id"],
                "canonical_name": top["canonical_name"],
                "evidence": "high similarity review evidence; no automatic match",
                "confidence": top["score"],
                "source_examples": [{"source_url": item["source_url"], "raw_title": item["raw_title"], "raw_composer_text": item["raw_composer_text"]}],
            })
    return results, alias_gaps


def summarize(results: list[dict[str, Any]], alias_gaps: list[dict[str, Any]], master_source: str) -> dict[str, Any]:
    statuses = Counter(row["match_status"] for row in results)
    matched = sum(statuses[s] for s in ("exact", "alias", "normalized_exact", "normalized_alias", "high_confidence"))
    canonical_ids = {row["canonical_composer_id"] for row in results if row["canonical_composer_id"]}
    multi = sum("/" in row["raw_composer_text"] for row in results)
    occurrences = {
        (row["source_url"], row.get("block_order"), row.get("line_order"), row["raw_composer_text"], row["classification_source"])
        for row in results
    }
    return {
        "source": "auditorio_nacional",
        "input_artifact": "artifacts/auditorio-nacional/auditorio-structure-classification.json",
        "master_source": master_source,
        "schema_audit": {
            "canonical_table": "composers",
            "primary_key": "id",
            "canonical_name_field": "canonical_name",
            "identity_key_field": "identity_key",
            "birth_death_fields": None,
            "alias_table": "composer_aliases",
            "alias_primary_relationship": "composer_aliases.composer_id -> composers.id",
            "production_matcher": "jobs/match_paris_opera_programmes.py",
            "normalization_helper": "norm",
        },
        "total_composer_occurrences": len(occurrences),
        "total_composer_components": len(results),
        "unique_raw_composer_strings": len({row["raw_composer_text"] for row in results}),
        "unique_normalized_composer_strings": len({row["lookup_normalized"] for row in results}),
        "exact_count": statuses["exact"],
        "alias_count": statuses["alias"],
        "normalized_exact_count": statuses["normalized_exact"],
        "normalized_alias_count": statuses["normalized_alias"],
        "high_confidence_count": statuses["high_confidence"],
        "ambiguous_count": statuses["ambiguous"],
        "unmatched_count": statuses["unmatched"],
        "false_positive_input_count": statuses["false_positive_input"],
        "unique_canonical_composers_matched": len(canonical_ids),
        "multi_composer_occurrence_count": multi,
        "lifespan_assisted_match_count": sum(any(e.get("type") == "lifespan_assisted_lookup" for e in row["evidence"]) for row in results),
        "alias_gap_count": len(alias_gaps),
        "collision_count": sum(row["match_status"] == "ambiguous" for row in results),
        "malformed_source_count": sum("malformed_source" in (row.get("review_reason") or "") for row in results),
        "matched_percentage": round(100 * matched / len(results), 2) if results else 0,
        "ambiguous_percentage": round(100 * statuses["ambiguous"] / len(results), 2) if results else 0,
        "unmatched_percentage": round(100 * statuses["unmatched"] / len(results), 2) if results else 0,
        "database_writes": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="artifacts/auditorio-nacional/auditorio-structure-classification.json")
    parser.add_argument("--master-snapshot", default="paris-opera-programme-match-dry-run.json")
    parser.add_argument("--output-dir", default="artifacts/auditorio-nacional")
    args = parser.parse_args()
    master = load_master_snapshot(args.master_snapshot)
    indexes = build_indexes(master)
    inputs = collect_inputs(args.input)
    results, alias_gaps = match_inputs(inputs, indexes)
    summary = summarize(results, alias_gaps, args.master_snapshot)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "auditorio-composer-match.json").write_text(json.dumps({"source": "auditorio_nacional", "matches": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "auditorio-composer-match-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "auditorio-composer-alias-gaps.json").write_text(json.dumps({"source": "auditorio_nacional", "alias_gaps": alias_gaps}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
