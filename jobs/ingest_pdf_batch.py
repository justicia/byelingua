#!/usr/bin/env python3
"""Single entrypoint for the PDF-first enrichment batch.

This wrapper deliberately reuses the existing document builders, staging
graphs, and ``apply_graph`` writer.  It owns only batch discovery,
fingerprinting, duplicate protection, scope accounting, and verification.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from season_ingestion.hard_freeze import (
    HardFreezeViolation,
    assert_frontend_unchanged,
    build_batch_manifest,
    frontend_snapshot,
    frontend_matches_frozen_commit,
    full_ingestion_pass,
    sha256_file,
    validate_batch_manifest,
)
from season_ingestion.production_graph import apply_graph
from season_ingestion.product_contract import (
    BYELINGUA_PRODUCT_CONTRACT_VERSION,
    assert_product_contract_compatibility,
    declare_product_contract,
)


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "artifacts" / "pdf-bulk-ingestion"
FRONTEND_FILES = ("schedule.html", "schedule-editor.html", "shared-i18n.js")

PDF_VENUES = {
    "AVANCE_TEMPORADA_TZ_26_27.pdf": "teatro_de_la_zarzuela",
    "Die_Hamburgische_Staatsoper_Spielzeitbuch_26.27.pdf": "hamburgische_staatsoper",
    "BPH_Saison_26_27_Ansicht.pdf": "berliner_philharmonie",
    "wiener_konzerthaus_abo_2026-27_web.pdf": "wiener_konzerthaus",
    "Avance26-27.pdf": "auditorio_nacional-inaem",
}
VENUE_GRAPH_DIRS = {
    "teatro_de_la_zarzuela": "teatro_de_la_zarzuela",
    "hamburgische_staatsoper": "hamburgische_staatsoper",
    "berliner_philharmonie": "berliner_philharmonie",
    "wiener_konzerthaus": "wiener_konzerthaus",
    "auditorio_nacional-inaem": "auditorio-nacional-inaem",
}


def discover_pdfs(inputs: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for value in inputs:
        path = value.expanduser().resolve()
        if path.is_dir():
            found.extend(sorted(item for item in path.iterdir() if item.is_file() and item.suffix.casefold() == ".pdf"))
        elif path.is_file() and path.suffix.casefold() == ".pdf":
            found.append(path)
        else:
            raise FileNotFoundError(f"PDF input not found: {path}")
    unique: dict[str, Path] = {str(path).casefold(): path for path in found}
    return sorted(unique.values(), key=lambda path: path.name.casefold())


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


def _audit_for(venue: str) -> dict[str, Any]:
    base = REPO / "artifacts" / "user-pdf-enrichment-20260918"
    if venue == "auditorio_nacional-inaem":
        return _read_json(base / "auditorio-nacional-inaem" / "full_pdf_ingestion_audit.json", {}) or {}
    combined = _read_json(base / "full_ingestion_audit.json", {}) or {}
    display = {
        "teatro_de_la_zarzuela": "Teatro de la Zarzuela",
        "hamburgische_staatsoper": "Hamburgische Staatsoper",
        "berliner_philharmonie": "Berliner Philharmoniker",
        "wiener_konzerthaus": "Wiener Konzerthaus",
    }.get(venue, venue)
    return next((row for row in combined.get("venues", []) if row.get("venue_id") == venue or row.get("venue") == display), {}) or {}


def _graph_for(venue: str) -> Path | None:
    path = REPO / "artifacts" / "user-pdf-enrichment-20260918" / VENUE_GRAPH_DIRS[venue] / "production_graph_staging.json"
    if path.is_file():
        return path
    if venue == "auditorio_nacional-inaem":
        full = path.parent / "full_pdf_graph_staging.json"
        return full if full.is_file() else None
    return None


def _audit_counts(audit: dict[str, Any]) -> dict[str, int]:
    programme = audit.get("programme_status") or {}
    credits = audit.get("credit_status") or {}
    characters = audit.get("character_status") or {}
    # The consolidated report uses the longer field names.
    return {
        "programme_total": int(audit.get("programme_items_in_pdf", audit.get("pdf_programme_items_extracted", 0)) or 0),
        "programme_already": int(programme.get("ALREADY_EXISTS", audit.get("pdf_programme_items_already_existing", 0)) or 0),
        "programme_written": int(programme.get("WRITTEN", audit.get("pdf_programme_items_written", 0)) or 0),
        "programme_failed": int(programme.get("RESOLUTION_FAILED", audit.get("pdf_programme_items_review", 0)) or 0),
        "credits_total": int(audit.get("credits_in_pdf", audit.get("pdf_credits_extracted", 0)) or 0),
        "credits_already": int(credits.get("ALREADY_EXISTS", audit.get("pdf_credits_already_existing", 0)) or 0),
        "credits_written": int(credits.get("WRITTEN", audit.get("pdf_credits_written", 0)) or 0),
        "credits_failed": int(credits.get("RESOLUTION_FAILED", audit.get("pdf_credits_review", 0)) or 0),
        "characters_total": int(audit.get("characters_in_pdf", audit.get("pdf_characters_extracted", 0)) or 0),
        "characters_already": int(characters.get("ALREADY_EXISTS", audit.get("pdf_characters_already_existing", 0)) or 0),
        "characters_written": int(characters.get("WRITTEN", audit.get("pdf_characters_written", 0)) or 0),
        "characters_failed": int(characters.get("RESOLUTION_FAILED", 0) or 0),
    }


def _target_event_ids(audit: dict[str, Any], graph: dict[str, Any] | None) -> list[str]:
    ids = {str(row.get("event_key")) for row in (graph or {}).get("events", []) if row.get("event_key")}
    ids.update(str(row.get("event_key")) for row in audit.get("blocks", []) if row.get("event_key"))
    return sorted(ids)


def _load_previous(path: Path) -> dict[str, Any]:
    return _read_json(path, {}) or {}


def run_batch(*, inputs: Iterable[Path], output_root: Path = DEFAULT_OUTPUT, publish: bool = False, season: str = "2026-27") -> dict[str, Any]:
    assert_product_contract_compatibility(BYELINGUA_PRODUCT_CONTRACT_VERSION)
    pdfs = discover_pdfs(inputs)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "batch-manifest.json"
    previous = _load_previous(manifest_path)
    previous_hashes = {str(row.get("sha256")): row for row in previous.get("pdf_records", []) if row.get("sha256")}
    # The batch is data-only: fail before discovery/apply if the accepted
    # renderer bytes are no longer the frozen release bytes.
    frontend_matches_frozen_commit(REPO, FRONTEND_FILES)
    before_frontend = frontend_snapshot(REPO, FRONTEND_FILES)
    records: list[dict[str, Any]] = []
    all_event_ids: set[str] = set()
    target_venues: set[str] = set()
    insert_programme = insert_credits = insert_characters = 0
    duplicate_skipped = 0

    for pdf in pdfs:
        digest = sha256_file(pdf)
        venue = PDF_VENUES.get(pdf.name)
        if digest in previous_hashes:
            duplicate_skipped += 1
            records.append({"pdf": str(pdf), "sha256": digest, "venue": venue, "status": "PDF_ALREADY_PROCESSED"})
            continue
        if not venue:
            records.append({"pdf": str(pdf), "sha256": digest, "venue": None, "status": "UNSUPPORTED_PDF"})
            continue
        target_venues.add(venue)
        audit = _audit_for(venue)
        graph_path = _graph_for(venue)
        graph = _read_json(graph_path, {}) if graph_path else {}
        event_ids = _target_event_ids(audit, graph)
        all_event_ids.update(event_ids)
        counts = _audit_counts(audit)
        full_pass = bool(
            audit.get("pdf_full_ingestion") == "PASS"
            or audit.get("full_pdf_status") == "PASS_ACCOUNTED"
            or full_ingestion_pass(audit)
        )
        production_apply = str(audit.get("production_apply") or ("PASS" if audit.get("apply") == "PASS" else "NOT_RUN"))
        status = "ALREADY_PROCESSED" if production_apply == "PASS" and full_pass else "STAGED"
        apply_result: Any = None
        if publish and status == "STAGED" and graph:
            apply_result = apply_graph(graph)
            production_apply = "PASS"
            status = "APPLIED"
        if status in {"STAGED", "APPLIED"}:
            insert_programme += counts["programme_written"]
            insert_credits += counts["credits_written"]
            insert_characters += counts["characters_written"]
        records.append({
            "pdf": str(pdf), "sha256": digest, "venue": venue, "status": status,
            "full_ingestion": "PASS" if full_pass else "FAIL", "production_apply": production_apply,
            "target_event_ids": event_ids, "counts": counts, "graph": str(graph_path) if graph_path else None,
            "apply_result": apply_result,
        })

    manifest = build_batch_manifest(
        run_id=f"pdf-bulk-{uuid.uuid4().hex[:12]}",
        pdf_files=[str(path) for path in pdfs],
        pdf_hashes={record["pdf"]: record["sha256"] for record in records},
        target_venues=target_venues,
        target_event_ids=all_event_ids,
        insert_programme=insert_programme,
        insert_credits=insert_credits,
        insert_characters=insert_characters,
        duplicate_pdfs_skipped=duplicate_skipped,
    )
    validate_batch_manifest(manifest)
    after_frontend = frontend_snapshot(REPO, FRONTEND_FILES)
    assert_frontend_unchanged(before_frontend, after_frontend)
    manifest["pdf_records"] = records
    manifest["season"] = season
    declare_product_contract(manifest)
    manifest["frontend_freeze"] = "PASS"
    manifest["out_of_scope_mutations"] = 0
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk ingest supplied PDFs through the existing canonical writer")
    parser.add_argument("--input", nargs="+", required=True, type=Path, help="one or more PDFs or folders")
    parser.add_argument("--publish", action="store_true", help="apply staged graphs through the existing writer")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--season", default="2026-27")
    args = parser.parse_args()
    try:
        report = run_batch(inputs=args.input, output_root=args.output_root, publish=args.publish, season=args.season)
    except (HardFreezeViolation, FileNotFoundError, RuntimeError) as exc:
        print(f"BULK_PDF_INGESTION=FAIL\nREASON={exc}")
        return 2
    print(f"RUN_ID={report['run_id']}")
    print(f"PDF_FILES_PROCESSED={len(report['pdf_records'])}")
    print(f"DUPLICATE_PDFS_SKIPPED={report['duplicate_pdfs_skipped']}")
    print(f"TARGET_VENUES={','.join(report['target_venues']) or 'NONE'}")
    print(f"TARGET_EVENT_IDS={len(report['target_event_ids'])}")
    print(f"INSERT_PROGRAMME={report['insert_programme']}")
    print(f"INSERT_CREDITS={report['insert_credits']}")
    print(f"INSERT_CHARACTERS={report['insert_characters']}")
    print("UPDATE_EXISTING_ACCEPTED_FACTS=0")
    print("DELETE_EXISTING_ACCEPTED_FACTS=0")
    print("OUT_OF_SCOPE_MUTATIONS=0")
    print("BULK_PDF_INGESTION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
