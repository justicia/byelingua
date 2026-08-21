"""Generate the Phase 2 Auditorio structure-classification artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from season_ingestion.auditorio_structure import classify_artifact, summarize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="artifacts/auditorio-nacional/auditorio-parser-dry-run.json")
    parser.add_argument("--output-dir", default="artifacts/auditorio-nacional")
    args = parser.parse_args()
    pages = classify_artifact(args.input)
    summary = summarize(pages, args.input)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "auditorio-structure-classification.json").write_text(
        json.dumps({"source": "auditorio_nacional", "pages": pages}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "auditorio-structure-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    qa_pages = []
    for page in pages:
        composer_lines = [line for line in page["classified_lines"] if line["classification"] == "composer_candidate"]
        if composer_lines:
            qa_pages.append({
                "source_url": page["source_url"],
                "raw_title": page["raw_title"],
                "structure_class": page["structure_class"],
                "composer_candidate_lines": composer_lines,
            })
    (out / "auditorio-structure-qa.json").write_text(
        json.dumps({"source": "auditorio_nacional", "pages": qa_pages}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
