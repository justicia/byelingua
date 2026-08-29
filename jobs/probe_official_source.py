from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def load_venue_config(venue: str) -> dict:
    registry = json.loads((ROOT / "season_ingestion/venue_registry.json").read_text(encoding="utf-8"))
    try:
        config = registry["venues"][venue]
    except KeyError:
        raise SystemExit(f"venue is not registered for cloud probing: {venue}") from None
    if not config.get("enabled", True):
        raise SystemExit(f"venue is disabled for cloud probing: {venue}")
    return config


def _candidate_links(html: str, *, base_url: str, config: dict) -> list[str]:
    prefixes = tuple(config.get("detail_path_prefixes", ()))
    pattern = config.get("detail_link_pattern")
    links: set[str] = set()
    for href in re.findall(r"\b(?:href|data-href)=[\"']([^\"']+)", html, flags=re.I):
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc != urlparse(base_url).netloc:
            continue
        path = parsed.path
        if prefixes and any(path.startswith(prefix) for prefix in prefixes):
            links.add(absolute)
        elif pattern and re.search(pattern, absolute):
            links.add(absolute)
    return sorted(links)


def probe(venue: str, url: str, season: str, config: dict) -> dict:
    request = Request(url, headers={
        "User-Agent": "ByelinguaSeasonIngestion/1.0 (+https://github.com/justicia/byelingua)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en;q=0.9",
    })
    with urlopen(request, timeout=60) as response:
        status = response.status
        html = response.read().decode("utf-8")
    event_urls = _candidate_links(html, base_url=url, config=config)
    start_year, end_year = season.split("-", 1)
    full_end_year = end_year if len(end_year) == 4 else start_year[:2] + end_year
    season_markers = {
        season,
        season.replace("-", "/"),
        f"{start_year}/{full_end_year}",
        f"{start_year[-2:]}/{end_year[-2:]}",
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "venue": venue,
        "official_source": url,
        "season": season,
        "http_status": status,
        "season_marker_found": any(marker in html for marker in season_markers),
        "event_url_count": len(event_urls),
        "event_url_samples": event_urls[:10],
        "source_capability": "SOURCE_PASS" if status == 200 and (event_urls or not config.get("detail_path_prefixes")) else "SOURCE_REACHABLE",
        "production_writes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--venue", required=True)
    parser.add_argument("--season", required=True)
    parser.add_argument("--output", type=Path, default=Path("source-probe-summary.json"))
    args = parser.parse_args()
    config = load_venue_config(args.venue)
    result = probe(args.venue, config["official_source"], args.season, config)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        Path(step_summary).write_text(
            "\n".join([
                "# Official Source Probe",
                "",
                f"Venue: {result['venue']}",
                f"Season: {result['season']}",
                f"HTTP status: {result['http_status']}",
                f"Season marker found: {result['season_marker_found']}",
                f"Candidate detail links: {result['event_url_count']}",
                f"Source capability: {result['source_capability']}",
                "Production writes: 0",
                "",
            ]),
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["http_status"] == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())
