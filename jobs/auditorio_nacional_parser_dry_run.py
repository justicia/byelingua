"""Generate reproducible raw Auditorio Nacional parser dry-run artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from season_ingestion.adapters.auditorio_nacional import (
    DISCOVERY_URL,
    _fetch_url,
    attach_details,
    discover,
    summarize,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/auditorio-nacional")
    parser.add_argument("--insecure-tls", action="store_true",
                        help="Allow the local TLS inspection certificate for this read-only fetch")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fetch = lambda url: _fetch_url(url, insecure_tls=args.insecure_tls)

    occurrences, pages = discover(fetch)
    enriched, errors = attach_details(occurrences, fetch)
    summary = summarize(enriched, pages, errors)
    summary["official_discovery_url"] = DISCOVERY_URL
    summary["season"] = "2026-27"

    def write(name: str, value: object) -> None:
        (output_dir / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    write("auditorio-discovery-dry-run.json", {
        "source": "auditorio_nacional", "season": "2026-27",
        "pages": pages, "occurrences": occurrences,
    })
    write("auditorio-parser-dry-run.json", {
        "source": "auditorio_nacional", "season": "2026-27",
        "occurrences": enriched,
    })
    write("auditorio-parser-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
