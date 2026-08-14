#!/usr/bin/env python3
"""Unattended official-source discovery/staging batch.

This batch is deliberately staging-only: it never calls Supabase and never
changes the production schema. Each venue has its own adapter manifest and a
raw HTML sample; generic extraction is conservative and leaves programme
normalisation for review when a detail endpoint is not yet mapped.
"""
from __future__ import annotations

import json
import re
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OUT = Path("venue-ingestion-batch")
CTX = ssl._create_unverified_context()
VENUES = [
    ("theatre_champs_elysees", "Théâtre des Champs-Élysées", "Paris", "France", "https://www.theatrechampselysees.fr/"),
    ("maison_radio_france", "Maison de la Radio et de la Musique / Auditorium de Radio France", "Paris", "France", "https://billetterie.maisondelaradioetdelamusique.fr/list/events?lang=fr"),
    ("salle_gaveau", "Salle Gaveau", "Paris", "France", "https://sallegaveau.com/"),
    ("opera_royal_versailles", "Château de Versailles Spectacles / Opéra Royal de Versailles", "Versailles", "France", "https://www.chateauversailles-spectacles.fr/"),
    ("la_seine_musicale", "La Seine Musicale", "Boulogne-Billancourt", "France", "https://www.laseinemusicale.com/programmation/"),
    ("salle_cortot", "Salle Cortot", "Paris", "France", "https://sallecortot.com/"),
    ("wiener_musikverein", "Wiener Musikverein", "Vienna", "Austria", "https://musikverein.at/2026-27"),
    ("wiener_konzerthaus", "Wiener Konzerthaus", "Vienna", "Austria", "https://konzerthaus.at/de"),
    ("theater_an_der_wien", "Theater an der Wien", "Vienna", "Austria", "https://www.theater-wien.at/de/spielplan"),
    ("grafenegg", "Grafenegg", "Grafenegg", "Austria", "https://www.grafenegg.com/de/programm-karten"),
    ("muth", "MuTh", "Vienna", "Austria", "https://muth.at/en/calendar/?date=10"),
    ("festspielhaus_st_poelten", "Festspielhaus St. Pölten", "St. Pölten", "Austria", "https://www.festspielhaus.at/"),
    ("teatro_de_la_zarzuela", "Teatro de la Zarzuela", "Madrid", "Spain", "https://teatrodelazarzuela.inaem.gob.es/es/"),
    ("fundacion_juan_march", "Fundación Juan March", "Madrid", "Spain", "https://www2.march.es/musica/"),
    ("teatro_monumental_rtve", "Teatro Monumental / RTVE Orquesta y Coro", "Madrid", "Spain", "https://www.teatromonumental.es/"),
    ("teatro_auditorio_el_escorial", "Teatro Auditorio San Lorenzo de El Escorial", "San Lorenzo de El Escorial", "Spain", "https://www.teatroauditorioescorial.es/"),
]


def fetch(url: str) -> tuple[int, bytes, str]:
    req = Request(url, headers={"User-Agent": "Byelingua-venue-staging/1.0", "Accept-Language": "en-US,en;q=0.8"})
    with urlopen(req, timeout=30, context=CTX) as response:
        return response.status, response.read(), response.headers.get_content_type()


def inspect_html(raw: bytes) -> dict:
    text = raw.decode("utf-8", "ignore")
    dates = re.findall(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", text)
    iso = re.findall(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}", text)
    titles = []
    for match in re.findall(r"<(?:h2|h3|h4)[^>]*>(.*?)</(?:h2|h3|h4)>", text, flags=re.S | re.I):
        title = re.sub(r"<[^>]+>", " ", match)
        title = re.sub(r"\s+", " ", title).strip()
        if title and title not in titles and len(title) < 180:
            titles.append(title)
    return {"date_tokens": len(set(dates)), "iso_datetime_tokens": len(set(iso)), "title_samples": titles[:12], "html_bytes": len(raw)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    adapters = OUT / "adapters"
    raw_dir = OUT / "raw"
    adapters.mkdir(exist_ok=True)
    raw_dir.mkdir(exist_ok=True)
    results = []
    for slug, venue, city, country, url in VENUES:
        adapter = {"adapter": f"{slug}_adapter", "source": url, "venue": venue, "city": city, "country": country, "canonical_event_schema": "baseline-v1", "writes_production": False}
        (adapters / f"{slug}.json").write_text(json.dumps(adapter, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        row = {"slug": slug, "venue": venue, "official_url": url, "attempted_at": datetime.now(timezone.utc).isoformat(), "events_extracted": 0, "events_normalized": 0, "duplicates_removed": 0, "programme_review": 0, "artist_review": 0, "errors": [], "status": "FAILED"}
        try:
            status, raw, content_type = fetch(url)
            (raw_dir / f"{slug}.html").write_bytes(raw)
            row["http_status"] = status
            row["content_type"] = content_type
            row["inspection"] = inspect_html(raw)
            # A conservative generic listing inspection is staging evidence,
            # not a canonical event import.
            row["status"] = "PARTIAL" if row["inspection"]["title_samples"] else "FAILED"
            row["events_extracted"] = row["inspection"]["iso_datetime_tokens"] or row["inspection"]["date_tokens"]
            row["programme_review"] = row["events_extracted"]
            row["errors"] = ["detail endpoint / JSON-LD mapping still required before READY FOR IMPORT"]
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            row["errors"] = [f"{type(exc).__name__}: {exc}"]
        results.append(row)
        time.sleep(0.25)
    now = datetime.now(timezone.utc).isoformat()
    report = {"generated_at": now, "production_database_modified": False, "venues_attempted": len(results), "success": sum(r["status"] == "SUCCESS" for r in results), "partial": sum(r["status"] == "PARTIAL" for r in results), "failed": sum(r["status"] == "FAILED" for r in results), "venues": results, "ready_for_import": [], "needs_review": [r["venue"] for r in results]}
    (OUT / "venue_ingestion_batch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Venue ingestion batch report", "", f"Generated: {now}", "", "## Summary", "", f"- TOTAL venues attempted: {len(results)}", f"- SUCCESS: {report['success']}", f"- PARTIAL: {report['partial']}", f"- FAILED: {report['failed']}", "- Production database modified: no", "", "## Venue results", "", "| Venue | Status | HTTP | Extracted | Programme review | Errors |", "|---|---:|---:|---:|---:|---|"]
    for r in results:
        lines.append(f"| {r['venue']} | {r['status']} | {r.get('http_status', '')} | {r['events_extracted']} | {r['programme_review']} | {'; '.join(r['errors'])} |")
    lines += ["", "## READY FOR IMPORT", "", "None. Generic extraction is intentionally staging-only until detail/API adapters and work normalization are reviewed.", "", "## NOT READY / NEEDS REVIEW", ""] + [f"- {name}" for name in report["needs_review"]]
    (OUT / "venue_ingestion_batch_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
