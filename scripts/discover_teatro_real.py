from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ingestion.adapters.teatro_real import parse_calendar_html


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Teatro Real 2026-27 discovery report")
    parser.add_argument("--calendar-html", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    events = parse_calendar_html(args.calendar_html.read_text(encoding="utf-8"))
    report = {
        "source": "teatro_real",
        "official_calendar": "https://www.teatroreal.es/en/calendario",
        "season": "2026-27",
        "performance_count": len(events),
        "production_count": len({event["source_url"] for event in events}),
        "date_min": min((event["date"] for event in events), default=None),
        "date_max": max((event["date"] for event in events), default=None),
        "monthly_counts": dict(sorted(Counter(event["date"][:7] for event in events).items())),
        "events": [
            {
                "date": event["date"],
                "time": event["start_time"],
                "source_title": event["display_title"],
                "source_category": event["source_event_type"],
                "detail_url": event["source_url"],
                "source_event_id": event["source_event_id"],
            }
            for event in events
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("performance_count", "production_count", "date_min", "date_max", "monthly_counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
