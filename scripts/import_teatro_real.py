from __future__ import annotations

import argparse
import json
from pathlib import Path

from ingestion.adapters.teatro_real import build_preview


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local Teatro Real 2026-27 normalized-event preview")
    parser.add_argument("--calendar-html", required=True, type=Path)
    parser.add_argument("--season-pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    preview = build_preview(args.calendar_html.read_text(encoding="utf-8"), args.season_pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(preview["audit"], ensure_ascii=False))


if __name__ == "__main__":
    main()

