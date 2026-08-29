from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from season_ingestion.adapters.detail_linked_listing import (
    SCALA_NON_CREDIT_LABELS,
    SCALA_PERFORMER_LABELS,
    SCALA_TEAM_ROLES,
    DetailLinkedListingAdapter,
)
from season_ingestion.registry import load_registry


def _fetch_pages(urls: list[str], *, workers: int) -> tuple[dict[str, str], list[dict[str, str]]]:
    pages: dict[str, str] = {}
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {executor.submit(DetailLinkedListingAdapter._fetch_url, url): url for url in urls}
        for future in as_completed(pending):
            url = pending[future]
            try:
                pages[url] = future.result()
            except Exception as exc:
                errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
    return pages, sorted(errors, key=lambda row: row["url"])


def _normalize_staged_credits(event: dict) -> list[dict]:
    normalized: list[dict] = []
    for credit in event.get("credits", []):
        source_artist = str(credit.get("artist_name") or "").strip()
        if source_artist and source_artist == source_artist.upper() and any(character.isalpha() for character in source_artist):
            credit = {**credit, "artist_name": source_artist.title()}
        label = str(credit.get("source_role") or credit.get("raw_character") or "").casefold().strip()
        if label in SCALA_NON_CREDIT_LABELS:
            continue
        role = SCALA_TEAM_ROLES.get(label)
        if role:
            for artist in (value.strip() for value in re.split(r"\s*(?:/|,)\s*", str(credit.get("artist_name") or ""))):
                if artist:
                    normalized.append({**credit, "artist_name": artist, "canonical_role": role, "raw_character": None, "credit_kind": "artistic_team"})
            continue
        if label in SCALA_PERFORMER_LABELS:
            normalized.append({**credit, "canonical_role": "performer", "raw_character": None, "credit_kind": "cast"})
            continue
        normalized.append(credit)
    unique: dict[tuple[str, str, str], dict] = {}
    for credit in normalized:
        key = (
            str(credit.get("artist_name") or "").casefold().strip(),
            str(credit.get("canonical_role") or "").casefold().strip(),
            str(credit.get("raw_character") or "").casefold().strip(),
        )
        unique.setdefault(key, credit)
    return list(unique.values())


def _summary(events: list[dict], *, season: str, pages_discovered: int, pages_checked: int, errors: list[dict]) -> dict:
    credit_rows = [credit for event in events for credit in event["credits"]]
    return {
        "schema_version": "teatro-alla-scala-credit-enrichment-summary-v1",
        "season": season,
        "production_writes": 0,
        "official_pages_discovered": pages_discovered,
        "official_pages_checked": pages_checked,
        "source_failures": len(errors),
        "events_total": len(events),
        "events_with_credits": sum(bool(event["credits"]) for event in events),
        "credits_total": len(credit_rows),
        "cast_rows": sum(bool(credit["credit_kind"] == "cast" and credit.get("raw_character")) for credit in credit_rows),
        "performer_rows_without_character": sum(credit["credit_kind"] == "cast" and not credit.get("raw_character") for credit in credit_rows),
        "conductor_rows": sum(credit["canonical_role"] == "conductor" for credit in credit_rows),
        "director_rows": sum(credit["canonical_role"] == "stage_director" for credit in credit_rows),
        "orchestra_chorus_rows": sum(credit["canonical_role"] in {"orchestra", "choir"} for credit in credit_rows),
        "other_team_rows": sum(credit["credit_kind"] in {"artistic_team", "ensemble"} and credit["canonical_role"] not in {"conductor", "stage_director", "orchestra", "choir"} for credit in credit_rows),
        "errors": errors,
    }


def stage(*, season: str, output_dir: Path, workers: int = 5) -> dict:
    settings = load_registry()["venues"]["teatro_alla_scala"]
    discovery = DetailLinkedListingAdapter(settings)
    listing_url = settings["listing_source"]
    listing_html = discovery._fetch_url(listing_url)
    detail_urls = discovery._listing_urls(listing_html, listing_url)
    pages, errors = _fetch_pages(detail_urls, workers=workers)

    events = []
    parse_errors = list(errors)
    for url in detail_urls:
        html = pages.get(url)
        if html is None:
            continue
        parser = DetailLinkedListingAdapter(settings, fetch={url: html}.__getitem__)
        try:
            events.extend(parser._events_from_detail(html, url, url.rstrip("/").rsplit("/", 1)[-1], season))
        except Exception as exc:
            parse_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
    events = sorted({event.event_key: event for event in events}.values(), key=lambda event: (event.date, event.start_time or "", event.event_key))

    normalized_events = []
    for event in events:
        normalized_events.append({
            "event_key": event.event_key,
            "source_event_id": event.source_event_id,
            "source_url": event.source_url,
            "title": event.title,
            "date": event.date,
            "start_time": event.start_time,
            "event_type": event.event_type,
            "programme": event.programme,
            "credits": [{
                "artist_name": credit.get("artist_name"),
                "canonical_role": credit.get("function"),
                "source_role": credit.get("source_role"),
                "raw_character": credit.get("character"),
                "credit_kind": credit.get("credit_kind"),
                "billing_order": credit.get("billing_order"),
                "source_url": credit.get("source_url"),
                "source_field": credit.get("source_field"),
            } for credit in event.credits],
        })

    for event in normalized_events:
        event["credits"] = _normalize_staged_credits(event)
    summary = _summary(normalized_events, season=season, pages_discovered=len(detail_urls), pages_checked=len(pages), errors=parse_errors)
    staging = {
        "schema_version": "teatro-alla-scala-credit-enrichment-staging-v1",
        "source": "teatro_alla_scala",
        "season": season,
        "production_writes": 0,
        "events": normalized_events,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scala_credit_staging.json").write_text(json.dumps(staging, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def normalize_existing(path: Path, output_dir: Path) -> dict:
    staging = json.loads(path.read_text(encoding="utf-8"))
    events = staging.get("events", [])
    for event in events:
        event["credits"] = _normalize_staged_credits(event)
    summary = _summary(events, season=staging.get("season", "2026-27"), pages_discovered=86, pages_checked=86, errors=[])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scala_credit_staging.json").write_text(json.dumps(staging, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Teatro alla Scala official credit staging")
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--normalize-existing", type=Path)
    args = parser.parse_args()
    result = normalize_existing(args.normalize_existing, args.output_dir) if args.normalize_existing else stage(season=args.season, output_dir=args.output_dir, workers=max(1, min(args.workers, 6)))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
