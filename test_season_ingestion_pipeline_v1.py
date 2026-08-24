from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from season_ingestion.adapters.munich_bayerische_staatsoper import parse_calendar
from season_ingestion.adapters.opernhaus_zurich import parse_detail
from season_ingestion.adapters.opernhaus_zurich import _detail_urls
from season_ingestion.pipeline import run_pipeline


HTML = '''<html><body><h1>Oktober 2026</h1>
<a href="/productions/semele">2. Oktober 2026.10.26 Freitag Fr.18.00 Uhr | NationaltheaterSEMELE Georg Friedrich Händel Preise</a>
<a href="/productions/ariadne">12. Oktober 2026.10.26 Montag Mo.19.00 Uhr | NationaltheaterARIADNE AUF NAXOS Richard Strauss Preise</a>
</body></html>'''
ENGLISH_HTML = '''<html><body>
<a href="/productions/zauberfloete">3. December 2026.12.26 Thursday Thu 07:00 pm | NationaltheaterDIE ZAUBERFLÖTE Wolfgang Amadeus Mozart Prices</a>
</body></html>'''
ZURICH_DETAIL_HTML = '''<script type="application/ld+json">{"@type":"Event","name":"Rachmaninow – Die drei Opern","startDate":"2026-11-01T18:00","endDate":"2026-11-01T21:20","url":"https://www.opernhaus.ch/en/spielplan/calendar/rachmaninov-die-drei-opern/2026-2027/","location":{"name":"Main Stage"}}</script>'''


class SeasonIngestionPipelineV1Tests(unittest.TestCase):
    def test_munich_parser_preserves_event_and_programme_provenance(self):
        settings = {"organization": "Bayerische Staatsoper", "venue": "Nationaltheater", "city": "Munich", "country": "Germany", "timezone": "Europe/Berlin"}
        events = parse_calendar(HTML, "https://www.staatsoper.de/spielplan/2026-10", settings, season_start="2026-09-01", season_end="2027-08-31")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].programme[0]["original_programme_order"], 1)
        self.assertTrue(events[0].source_url.startswith("https://www.staatsoper.de/"))

    def test_official_english_fallback_format_is_supported(self):
        settings = {"organization": "Bayerische Staatsoper", "venue": "Nationaltheater", "city": "Munich", "country": "Germany", "timezone": "Europe/Berlin"}
        events = parse_calendar(ENGLISH_HTML, "https://www.staatsoper.de/en/schedule/2026-12", settings, season_start="2026-09-01", season_end="2027-08-31")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].start_time, "19:00")

    def test_zurich_detail_jsonld_preserves_order_and_provenance(self):
        settings = {"organization": "Opernhaus Zürich", "venue": "Opernhaus Zürich", "city": "Zürich", "country": "Switzerland", "timezone": "Europe/Zurich", "official_source": "https://www.opernhaus.ch/en/spielplan/oper-2627/"}
        events = parse_detail(ZURICH_DETAIL_HTML, "https://www.opernhaus.ch/en/spielplan/calendar/rachmaninov-die-drei-opern/2026-2027/", settings, season_start="2026-09-01", season_end="2027-08-31")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].programme[0]["original_programme_order"], 1)
        self.assertEqual(events[0].venue, "Main Stage")
        self.assertEqual(events[0].data_quality["character"]["status"], "unavailable")

    def test_zurich_season_page_relative_detail_urls_are_discoverable(self):
        urls = _detail_urls('<a href="/en/spielplan/calendar/rachmaninov-die-drei-opern/2026-2027/">Rachmaninow</a>')
        self.assertEqual(urls, ["https://www.opernhaus.ch/en/spielplan/calendar/rachmaninov-die-drei-opern/2026-2027/"])

    def test_apply_is_blocked(self):
        with self.assertRaises(RuntimeError):
            run_pipeline(venue="munich_bayerische_staatsoper", season="2026-27", mode="apply")

    def test_output_contract_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = {"organization": "Bayerische Staatsoper", "venue": "Nationaltheater", "city": "Munich", "country": "Germany", "timezone": "Europe/Berlin"}
            class FakeAdapter:
                last_errors = []
                def ingest(self, season):
                    return parse_calendar(HTML, "https://www.staatsoper.de/spielplan/2026-10", settings, season_start="2026-09-01", season_end="2027-08-31")
            with patch("season_ingestion.pipeline.load_adapter", return_value=FakeAdapter()):
                result = run_pipeline(venue="munich_bayerische_staatsoper", season="2026-27", output_dir=Path(tmp))
            self.assertEqual(result["counts"]["writes"], 0)
            self.assertTrue(result["gates"]["production_writes"])
            self.assertTrue((Path(tmp) / "final_staging.json").exists())
            self.assertEqual(set(json.loads((Path(tmp) / "summary.json").read_text())["gates"]), set(result["gates"]))


if __name__ == "__main__":
    unittest.main()
