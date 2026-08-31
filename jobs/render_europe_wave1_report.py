"""Render the compact Wave 1 launch report from independent venue results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


WAVE1_VENUES = {
    "wiener_musikverein", "wiener_konzerthaus", "theater_an_der_wien",
    "theatre_champs_elysees", "maison_radio_france", "teatro_de_la_zarzuela",
    "berliner_philharmonie", "staatsoper_unter_den_linden", "deutsche_oper_berlin",
    "komische_oper_berlin", "elbphilharmonie", "hamburgische_staatsoper",
    "tonhalle_zurich", "accademia_nazionale_santa_cecilia", "gran_teatre_del_liceu",
    "palau_de_la_musica_catalana", "lauditori_barcelona", "concertgebouw",
    "dutch_national_opera", "royal_opera_house", "barbican_centre",
    "southbank_centre", "wigmore_hall", "la_monnaie_de_munt", "bozar",
}


def _classification(item: dict) -> str:
    summary = item.get("summary") or {}
    source = summary.get("source_capability")
    counts = summary.get("counts") or {}
    events = int(counts.get("events", counts.get("events_discovered", 0)) or 0)
    if item.get("status") == "FAILED" or source in {"SOURCE_BLOCKED", "SOURCE_UNSUPPORTED", "ADAPTER_REQUIRED", "FAILED"} or events <= 0:
        return "BLOCKED"
    if item.get("status") == "READY_FOR_APPROVAL" and source == "SOURCE_PASS":
        return "PASS"
    return "PARTIAL"


def build_report(summary: dict, *, existing_production_venues: int = 9) -> dict:
    venues = summary.get("venues") or []
    classifications = [{"venue": item.get("venue_id"), "status": _classification(item)} for item in venues]
    accepted = [item for item in venues if _classification(item) in {"PASS", "PARTIAL"}]
    blocked = [item for item in venues if _classification(item) == "BLOCKED"]
    new_ready = sum(item.get("venue_id") in WAVE1_VENUES for item in accepted)
    events = programme = credits = 0
    for item in accepted:
        counts = (item.get("summary") or {}).get("counts") or {}
        events += int(counts.get("events", counts.get("events_discovered", 0)) or 0)
        programme += int(counts.get("safe_programme_relationships", 0) or 0)
        credits += int(counts.get("credits_safe", 0) or 0)
    return {
        "VENUES_ATTEMPTED": len(venues),
        "VENUES_PRODUCTION_READY": len(accepted),
        "VENUES_BLOCKED": len(blocked),
        "TOTAL_PRODUCTION_VENUES": existing_production_venues + new_ready,
        "TOTAL_EVENTS": events,
        "TOTAL_PROGRAMME_RELATIONSHIPS": programme,
        "TOTAL_CREDITS": credits,
        "classifications": classifications,
        "blocked": [{"venue": item.get("venue_id"), "blocker": item.get("blocker") or (item.get("summary") or {}).get("failure_reason"), "next technical fix": item.get("next_technical_fix") or "Rerun the isolated venue after the blocker is fixed"} for item in blocked],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(json.loads(args.summary.read_text(encoding="utf-8")))
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
