from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from season_ingestion.adapters.munich_bayerische_staatsoper import parse_calendar
from season_ingestion.adapters.opernhaus_zurich import parse_detail
from season_ingestion.adapters.opernhaus_zurich import _detail_urls
from season_ingestion.contracts import GlobalEntitySnapshot
from season_ingestion.global_master import normalize_identity, resolve_entity, resolve_work
from season_ingestion.pipeline import run_pipeline


HTML = '''<html><body><h1>Oktober 2026</h1>
<a href="/productions/semele">2. Oktober 2026.10.26 Freitag Fr.18.00 Uhr | NationaltheaterSEMELE Georg Friedrich Händel Preise</a>
<a href="/productions/ariadne">12. Oktober 2026.10.26 Montag Mo.19.00 Uhr | NationaltheaterARIADNE AUF NAXOS Richard Strauss Preise</a>
</body></html>'''
ENGLISH_HTML = '''<html><body>
<a href="/productions/zauberfloete">3. December 2026.12.26 Thursday Thu 07:00 pm | NationaltheaterDIE ZAUBERFLÖTE Wolfgang Amadeus Mozart Prices</a>
</body></html>'''
ZURICH_DETAIL_HTML = '''<script type="application/ld+json">{"@type":"Event","name":"Rachmaninow – Die drei Opern","startDate":"2026-11-01T18:00","endDate":"2026-11-01T21:20","url":"https://www.opernhaus.ch/en/spielplan/calendar/rachmaninov-die-drei-opern/2026-2027/","description":"Sergei Rachmaninoff\\n\\nThree one-act operas","location":{"name":"Main Stage"},"performer":[{"@type":"Person","name":"Gianandrea Noseda","description":"Musikalische Leitung"},{"@type":"Person","name":"Elena Stikhina","description":"Soprano"}]}</script>'''
ZURICH_NO_PROGRAMME_HTML = '''<script type="application/ld+json">{"@type":"Event","name":"Opernhaus für alle","startDate":"2027-07-02T19:00","endDate":"2027-07-02T21:00","url":"https://www.opernhaus.ch/en/spielplan/calendar/opernhaus-fuer-alle/2026-2027/","description":"","location":{"name":"Main Stage"}}</script>'''
ZURICH_MULTI_WORK_HTML = '''<script type="application/ld+json">{"@type":"Event","name":"Requiem pour Ophélie","startDate":"2027-05-04T19:00","endDate":"2027-05-04T20:40","url":"https://www.opernhaus.ch/en/spielplan/calendar/requiem-pour-ophelie/2026-2027/","description":"Works by Hector Berlioz, Ambroise Thomas and Gabriel Fauré","location":{"name":"Main Stage"},"performer":[{"@type":"Person","name":"Raphaël Pichon","description":"Musikalische Leitung"},{"@type":"MusicGroup","name":"Orchestra of the Zurich Opera House","description":"Orchester"}]}</script>'''
ZURICH_TITLE_AS_COMPOSER_HTML = '''<script type="application/ld+json">{"@type":"Event","name":"Herr der Diebe","startDate":"2027-02-27T14:00","endDate":"2027-02-27T16:00","url":"https://www.opernhaus.ch/en/spielplan/calendar/herr-der-diebe/2026-2027/","description":"Herr der Diebe\\n\\nMusic by three Master’s students of ZHdK: Marlena Kreßin, Joanna Lohmann and Moritz Lieberherr","location":{"name":"Main Stage"}}</script>'''


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
        self.assertEqual(events[0].programme[0]["composer"], "Sergei Rachmaninoff")
        self.assertEqual(events[0].credits[0]["credit_kind"], "artistic_team")
        self.assertEqual(events[0].credits[1]["artist_name"], "Elena Stikhina")
        self.assertEqual(events[0].credits[1]["character"], "Soprano")

    def test_zurich_no_programme_evidence_is_not_a_work_candidate(self):
        settings = {"organization": "Opernhaus Zürich", "venue": "Opernhaus Zürich", "city": "Zürich", "country": "Switzerland", "timezone": "Europe/Zurich", "official_source": "https://www.opernhaus.ch/en/spielplan/oper-2627/"}
        events = parse_detail(ZURICH_NO_PROGRAMME_HTML, "https://www.opernhaus.ch/en/spielplan/calendar/opernhaus-fuer-alle/2026-2027/", settings, season_start="2026-09-01", season_end="2027-08-31")
        self.assertEqual(events[0].programme, [])
        self.assertEqual(events[0].data_quality["programme"]["status"], "NO_PROGRAMME_EVIDENCE")

    def test_zurich_multi_work_description_is_review_not_fake_single_work(self):
        settings = {"organization": "Opernhaus Zürich", "venue": "Opernhaus Zürich", "city": "Zürich", "country": "Switzerland", "timezone": "Europe/Zurich", "official_source": "https://www.opernhaus.ch/en/spielplan/oper-2627/"}
        events = parse_detail(ZURICH_MULTI_WORK_HTML, "https://www.opernhaus.ch/en/spielplan/calendar/requiem-pour-ophelie/2026-2027/", settings, season_start="2026-09-01", season_end="2027-08-31")
        self.assertEqual(events[0].programme, [])
        self.assertEqual(events[0].data_quality["programme"]["status"], "DETAIL_PARSE_REVIEW")
        self.assertEqual(events[0].credits[0]["credit_kind"], "artistic_team")

    def test_zurich_production_heading_is_not_composer(self):
        settings = {"organization": "Opernhaus Zürich", "venue": "Opernhaus Zürich", "city": "Zürich", "country": "Switzerland", "timezone": "Europe/Zurich", "official_source": "https://www.opernhaus.ch/en/spielplan/oper-2627/"}
        events = parse_detail(ZURICH_TITLE_AS_COMPOSER_HTML, "https://www.opernhaus.ch/en/spielplan/calendar/herr-der-diebe/2026-2027/", settings, season_start="2026-09-01", season_end="2027-08-31")
        self.assertIsNone(events[0].programme[0].get("composer") if events[0].programme else None)
        self.assertEqual(events[0].data_quality["programme"]["status"], "NO_PROGRAMME_EVIDENCE")

    def test_zurich_season_page_relative_detail_urls_are_discoverable(self):
        urls = _detail_urls('<a href="/en/spielplan/calendar/rachmaninov-die-drei-opern/2026-2027/">Rachmaninow</a>')
        self.assertEqual(urls, ["https://www.opernhaus.ch/en/spielplan/calendar/rachmaninov-die-drei-opern/2026-2027/"])

    def test_shared_composer_resolver_matches_canonical_and_aliases(self):
        snapshot = GlobalEntitySnapshot(generated_at="now", source="test", freshness_seconds=0, entities={"composer": [{"id": "mozart", "canonical_name": "Wolfgang Amadeus Mozart"}], "work": [{"id": "magic", "title": "Die Zauberflöte", "composer_id": "mozart"}], "artist": [], "character": []}, composer_aliases=[{"composer_id": "mozart", "alias": "Mozart"}])
        self.assertEqual(resolve_entity("composer", "Wolfgang Amadeus Mozart (1756–1791)", snapshot)["match_method"], "exact")
        self.assertEqual(resolve_entity("composer", "Mozart", snapshot)["match_method"], "alias")
        self.assertEqual(resolve_entity("composer", "Unknown Composer", snapshot)["status"], "review_required")
        self.assertEqual(resolve_work("Die Zauberflöte", resolve_entity("composer", "Mozart", snapshot), snapshot)["status"], "existing")

    def test_shared_identity_normalizer_handles_accents_and_punctuation(self):
        self.assertEqual(normalize_identity("Richard Strauß"), normalize_identity("Richard Strauss"))
        self.assertEqual(normalize_identity("Antonín Dvořák"), normalize_identity("Antonin Dvorak"))
        self.assertEqual(normalize_identity("Composer: Wolfgang Amadeus Mozart (1756-1791)"), "wolfgang amadeus mozart")

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
