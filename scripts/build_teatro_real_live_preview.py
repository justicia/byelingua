from __future__ import annotations

import argparse
import json
from pathlib import Path

from ingestion.adapters.teatro_real import merge_sources, parse_calendar_html, parse_season_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized Teatro Real preview from live discovery/details")
    parser.add_argument("--calendar-html", required=True, type=Path)
    parser.add_argument("--details-json", required=True, type=Path)
    parser.add_argument("--season-pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    events = parse_calendar_html(args.calendar_html.read_text(encoding="utf-8"))
    supplements = parse_season_pdf(args.season_pdf)
    detail_report = json.loads(args.details_json.read_text(encoding="utf-8"))
    for url, detail in detail_report.get("details", {}).items():
        if not (detail.get("programme") or detail.get("cast") or detail.get("artistic_team")):
            continue
        supplements.append({
            "pdf_page": None,
            "title": detail["title"],
            "title_aliases": detail.get("title_aliases", []),
            "programme": detail.get("programme", []),
            "cast": detail.get("cast", []),
            "artistic_team": detail.get("artistic_team", []),
            "performance_kind": "opera" if detail.get("source_event_type") == "Opera" else "dance",
            "source_url": url,
        })
    normalized = merge_sources(events, supplements)
    preview = {
        "source": "teatro_real",
        "season": "2026-27",
        "official_calendar": "https://www.teatroreal.es/en/calendario",
        "events": normalized,
        "audit": {
            "event_count": len(normalized),
            "opera_count": sum(event["event_type"] == "opera" for event in normalized),
            "events_with_programme": sum(bool(event["programme"]) for event in normalized),
            "events_with_cast": sum(bool(event["cast"]) for event in normalized),
            "events_with_artistic_team": sum(bool(event["artistic_team"]) for event in normalized),
            "duplicate_source_event_ids": len(normalized) - len({event["source_event_id"] for event in normalized}),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(preview["audit"], ensure_ascii=False))


if __name__ == "__main__":
    main()
