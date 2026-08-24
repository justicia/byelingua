from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def probe(url: str, season: str) -> dict:
    request = Request(url, headers={
        "User-Agent": "ByelinguaSeasonIngestion/1.0 (+https://github.com/justicia/byelingua)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en;q=0.9",
    })
    with urlopen(request, timeout=60) as response:
        status = response.status
        html = response.read().decode("utf-8")
    event_urls = sorted(set(re.findall(r"https://www\.opernhaus\.ch/(?:en/)?spielplan/calendar/[^\"' ]+/2026-2027/?", html)))
    if not event_urls:
        event_urls = sorted(set("https://www.opernhaus.ch" + path for path in re.findall(r"/(?:en/)?spielplan/calendar/[^\"' ]+/2026-2027/?", html)))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "venue": "opernhaus_zurich",
        "official_source": url,
        "season": season,
        "http_status": status,
        "season_marker_found": season.replace("-", "/") in html or "26/27" in html,
        "event_url_count": len(event_urls),
        "event_url_samples": event_urls[:10],
        "source_capability": "SOURCE_PASS" if status == 200 and event_urls else "SOURCE_UNSUPPORTED",
        "production_writes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("source-probe-summary.json"))
    args = parser.parse_args()
    result = probe("https://www.opernhaus.ch/en/spielplan/oper-2627/", "2026-27")
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["source_capability"] == "SOURCE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
