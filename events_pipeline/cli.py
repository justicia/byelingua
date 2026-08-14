from __future__ import annotations

import argparse
import json
from pathlib import Path
from .adapters import extract_fixture
from .report import IngestionReport

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "venue-ingestion-batch" / "adapters"
RAW = ROOT / "venue-ingestion-batch" / "raw"
REPORTS = ROOT / "reports" / "ingestion"


def manifests():
    for path in sorted(MANIFESTS.glob("*.json")):
        yield path.stem, json.loads(path.read_text(encoding="utf-8"))


def selected(args):
    all_items = list(manifests())
    if args.source:
        return [(slug, item) for slug, item in all_items if slug == args.source]
    if args.city:
        return [(slug, item) for slug, item in all_items if str(item.get("city", "")).casefold() == args.city.casefold()]
    return all_items if args.all else []


def run(args):
    chosen = selected(args)
    if not chosen:
        raise SystemExit("select exactly one of --source, --city, or --all")
    for slug, manifest in chosen:
        report = IngestionReport.start(slug, manifest.get("adapter", "unknown"))
        raw_path = RAW / f"{slug}.html"
        if not raw_path.exists():
            report.records_failed = 1
            report.error_summary = [f"raw fixture not found: {raw_path}"]
            report.finish("FAILED")
            print(report.write(REPORTS))
            continue
        events, quarantine = extract_fixture(manifest, raw_path)
        report.records_fetched = len(events) + len(quarantine)
        report.records_valid = len(events)
        report.records_quarantined = len(quarantine)
        # Production writing is intentionally a separate implementation gate.
        # This command currently proves extraction/validation only; it never
        # writes Supabase until a source-specific upsert adapter is approved.
        report.error_summary = ["production upsert adapter not enabled; dry-run only"]
        report.finish("PARTIAL" if quarantine or not events else "READY_FOR_IMPORT")
        out = report.write(REPORTS)
        print(json.dumps({"source": slug, "status": report.status, "events": len(events), "quarantined": len(quarantine), "report": str(out)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(prog="python -m events_pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest")
    group = ingest.add_mutually_exclusive_group(required=True)
    group.add_argument("--source")
    group.add_argument("--city")
    group.add_argument("--all", action="store_true")
    ingest.add_argument("--write-production", action="store_true", help="reserved; refuses until source upsert adapter is enabled")
    ingest.set_defaults(func=run)
    args = parser.parse_args()
    if getattr(args, "write_production", False):
        raise SystemExit("production upsert is not enabled yet; review the generated report first")
    args.func(args)
