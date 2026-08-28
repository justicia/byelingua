from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from season_ingestion.adapters.opernhaus_zurich import (
    OpernhausZurichAdapter,
    _detail_urls,
    parse_detail,
)
from season_ingestion.credit_resolution import canonical_role
from season_ingestion.registry import load_registry
from season_ingestion.season import resolve_season_bounds


def _fetch_pages(urls: list[str], *, workers: int) -> tuple[dict[str, str], list[dict[str, str]]]:
    pages: dict[str, str] = {}
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {executor.submit(OpernhausZurichAdapter._fetch_url, url): url for url in urls}
        for future in as_completed(pending):
            url = pending[future]
            try:
                pages[url] = future.result()
            except Exception as exc:  # the error is preserved as review evidence
                errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
    return pages, sorted(errors, key=lambda row: row["url"])


def stage(*, season: str, output_dir: Path, workers: int = 4) -> dict:
    settings = load_registry()["venues"]["opernhaus_zurich"]
    season_start, season_end = resolve_season_bounds(season, settings)
    season_html = OpernhausZurichAdapter._fetch_url(settings["official_source"])
    detail_urls = _detail_urls(season_html)
    pages, errors = _fetch_pages(detail_urls, workers=workers)

    events = []
    parse_errors = list(errors)
    for url in detail_urls:
        html = pages.get(url)
        if html is None:
            continue
        try:
            events.extend(parse_detail(html, url, settings, season_start=season_start, season_end=season_end))
        except Exception as exc:
            parse_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
    events = sorted({event.event_key: event for event in events}.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))

    normalized_events = []
    role_counts: dict[str, int] = {}
    for event in events:
        credits = []
        for raw in event.credits:
            source_role = str(raw.get("source_role") or "").strip()
            canonical = canonical_role(source_role)
            row = {
                "artist_name": str(raw.get("artist_name") or "").strip(),
                "source_role": source_role,
                "canonical_role": canonical or ("performer" if raw.get("credit_kind") == "cast" and raw.get("character") else None),
                "credit_kind": raw.get("credit_kind"),
                "raw_character": raw.get("character"),
                "source_url": raw.get("source_url"),
                "source_field": raw.get("source_field"),
            }
            key = row["canonical_role"] or "REVIEW_ROLE_UNKNOWN"
            role_counts[key] = role_counts.get(key, 0) + 1
            credits.append(row)
        normalized_events.append({
            "event_key": event.event_key,
            "source_event_id": event.source_event_id,
            "source_url": event.source_url,
            "title": event.title,
            "date": event.date,
            "start_time": event.start_time,
            "programme": [{
                "source_title": item.get("source_title"),
                "composer": item.get("composer"),
                "source_programme_index": item.get("source_programme_index"),
                "source_url": (item.get("provenance") or {}).get("source_url"),
            } for item in event.programme],
            "credits": credits,
        })

    staging = {
        "schema_version": "opernhaus-zurich-credit-enrichment-staging-v1",
        "source": "opernhaus_zurich",
        "season": season,
        "official_source": settings["official_source"],
        "events": normalized_events,
        "production_writes": 0,
    }
    summary = {
        "schema_version": "opernhaus-zurich-credit-enrichment-summary-v1",
        "season": season,
        "official_pages_discovered": len(detail_urls),
        "official_pages_checked": len(pages),
        "source_failures": len(parse_errors),
        "events_total": len(events),
        "events_with_credits": sum(bool(event["credits"]) for event in normalized_events),
        "credits_total": sum(len(event["credits"]) for event in normalized_events),
        "programme_evidence_events": sum(bool(event["programme"]) for event in normalized_events),
        "role_counts": dict(sorted(role_counts.items())),
        "errors": parse_errors,
        "production_writes": 0,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "zurich_official_credit_staging.json").write_text(json.dumps(staging, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "zurich_credit_enrichment_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Opernhaus Zürich official credit staging")
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(stage(season=args.season, output_dir=args.output_dir, workers=max(1, min(args.workers, 6))), ensure_ascii=False))


if __name__ == "__main__":
    main()
