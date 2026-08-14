from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urldefrag

from ingestion.adapters.teatro_real import parse_calendar_html, parse_detail_html


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and parse Teatro Real production detail pages")
    parser.add_argument("--calendar-html", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    discovery = parse_calendar_html(args.calendar_html.read_text(encoding="utf-8"))
    urls = sorted({urldefrag(event["source_url"])[0] for event in discovery})
    details = {}
    errors = []
    for url in urls:
        try:
            request = Request(url, headers={"User-Agent": "Byelingua Teatro Real ingestion"})
            with urlopen(request, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")
            details[url] = parse_detail_html(html)
        except Exception as exc:  # keep the discovery report auditable
            errors.append({"url": url, "error": str(exc)})
    report = {
        "source": "teatro_real",
        "official_calendar": "https://www.teatroreal.es/en/calendario",
        "detail_page_count": len(urls),
        "parsed_detail_count": len(details),
        "errors": errors,
        "details": details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("detail_page_count", "parsed_detail_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
