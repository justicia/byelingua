import json
from pathlib import Path
import unittest

from season_ingestion.adapters.detail_linked_listing import DetailLinkedListingAdapter
from season_ingestion.contracts import GlobalEntitySnapshot
from season_ingestion.global_master import resolve_entity, resolve_work


FIXTURES = Path(__file__).parent / "season_ingestion" / "fixtures" / "detail_linked_listing"


def settings(venue_id, prefix, organization, venue, city, country, timezone):
    return {
        "source_id": venue_id, "listing_source": f"https://official.example/{venue_id}/listing",
        "official_source": f"https://official.example/{venue_id}/season", "detail_path_prefixes": [prefix],
        "organization": organization, "venue": venue, "city": city, "country": country, "timezone": timezone,
        "season_start_month": 8, "season_end_month": 7,
    }


def adapter_for(venue_id, fixture_name, config):
    listing = (FIXTURES / f"{fixture_name}_listing.html").read_text(encoding="utf-8")
    detail = (FIXTURES / f"{fixture_name}_detail.html").read_text(encoding="utf-8")
    pages = {config["listing_source"]: listing}
    detail_url = "https://official.example" + {"teatro_alla_scala": "/en/season/2026-2027/opera/la-boheme.html", "opera_roma": "/spettacoli/tosca/", "theater_basel": "/de/spielplan/hamlet"}[venue_id]
    pages[detail_url] = detail
    return DetailLinkedListingAdapter(config, fetch=pages.__getitem__)


class DetailLinkedListingAdapterTests(unittest.TestCase):
    def test_rome_pairs_each_occurrence_row_and_does_not_cross_product_times(self):
        config = settings("opera_roma", "/spettacoli/", "Teatro dell'Opera di Roma", "Teatro dell'Opera di Roma", "Rome", "Italy", "Europe/Rome")
        config.update({"performance_container_selector": "#date-2", "performance_date_selector": ".datelist li", "performance_time_selector": ".turno", "page_season_selector": "body", "page_season_pattern": r"Stagione\s+(20\d{2}\s*[/\-]\s*20\d{2})"})
        detail = "<body>Stagione 2026/2027<h1>Il trovatore</h1><p>Musica di Giuseppe Verdi</p><section id=date-2>" + "".join(f"<div class=datelist><li>{d}<span class=turno>{t}</span></li></div>" for d, t in [("22 Giu", "ORE 20:00"), ("23 Giu", "ORE 20:00"), ("25 Giu", "ORE 20:00"), ("26 Giu", "ORE 18:00"), ("27 Giu", "ORE 16:30"), ("30 Giu", "ORE 20:00"), ("01 Lug", "ORE 20:00")]) + "</section></body>"
        pages = {config["listing_source"]: '<a href="https://official.example/spettacoli/trovatore/">Il trovatore</a>', "https://official.example/spettacoli/trovatore/": detail}
        events = DetailLinkedListingAdapter(config, fetch=pages.__getitem__).ingest("2026-27")
        self.assertEqual([(event.date, event.start_time) for event in events], [("2027-06-22", "20:00"), ("2027-06-23", "20:00"), ("2027-06-25", "20:00"), ("2027-06-26", "18:00"), ("2027-06-27", "16:30"), ("2027-06-30", "20:00"), ("2027-07-01", "20:00")])

    def test_rome_production_date_context_resolves_late_year(self):
        config = settings("opera_roma", "/spettacoli/", "Teatro dell'Opera di Roma", "Teatro dell'Opera di Roma", "Rome", "Italy", "Europe/Rome")
        config.update({"performance_container_selector": "#date-2", "performance_date_selector": ".datelist li", "performance_time_selector": ".turno", "page_season_selector": "body", "page_season_pattern": r"Stagione\s+(20\d{2}\s*[/\-]\s*20\d{2})", "season_bounds": {"2026-27": {"season_start": "2026-08-01", "season_end": "2027-12-31"}}})
        detail = "<body>Stagione 2026/2027<h1>La rondine</h1><section id=date-2><div class=datelist><li>18 Settembre<span class=turno>ORE 20:00</span></li></div></section><p>La rondine</p><p>Dal 18 Settembre al 26 Settembre 2027</p></body>"
        pages = {config["listing_source"]: '<a href="https://official.example/spettacoli/rondine/">La rondine</a>', "https://official.example/spettacoli/rondine/": detail}
        events = DetailLinkedListingAdapter(config, fetch=pages.__getitem__).ingest("2026-27")
        self.assertEqual([(event.date, event.start_time) for event in events], [("2027-09-18", "20:00")])
    def test_milan_listing_detail_multiple_performances_and_traceability(self):
        config = settings("teatro_alla_scala", "/en/season/2026-2027/", "Teatro alla Scala", "Teatro alla Scala", "Milan", "Italy", "Europe/Rome")
        adapter = adapter_for("teatro_alla_scala", "teatro_alla_scala", config)
        events = adapter.ingest("2026-27")
        self.assertEqual(len(events), 2)
        self.assertEqual({event.date for event in events}, {"2026-11-02", "2026-11-04"})
        self.assertTrue(all(event.source_url.startswith("https://official.example/") for event in events))
        self.assertEqual(len({event.event_key for event in events}), 2)

    def test_rome_extracts_composer_and_expands_dates(self):
        config = settings("opera_roma", "/spettacoli/", "Teatro dell'Opera di Roma", "Teatro dell'Opera di Roma", "Rome", "Italy", "Europe/Rome")
        adapter = adapter_for("opera_roma", "opera_roma", config)
        events = adapter.ingest("2026-27")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].programme[0]["composer"], "Giacomo Puccini")
        self.assertEqual(events[0].programme[0]["provenance"]["source_url"], events[0].source_url)

    def test_basel_uses_same_engine(self):
        config = settings("theater_basel", "/de/", "Theater Basel", "Theater Basel", "Basel", "Switzerland", "Europe/Zurich")
        adapter = adapter_for("theater_basel", "theater_basel", config)
        events = adapter.ingest("2026-27")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].programme[0]["composer"], "Example Composer")

    def test_detail_failure_is_source_partial_and_successful_events_remain(self):
        config = settings("opera_roma", "/spettacoli/", "Teatro dell'Opera di Roma", "Teatro dell'Opera di Roma", "Rome", "Italy", "Europe/Rome")
        listing = '<a href="https://official.example/spettacoli/tosca/">Tosca</a><a href="https://official.example/spettacoli/missing/">Missing</a>'
        pages = {
            config["listing_source"]: listing,
            "https://official.example/spettacoli/tosca/": (FIXTURES / "opera_roma_detail.html").read_text(encoding="utf-8"),
        }
        adapter = DetailLinkedListingAdapter(config, fetch=pages.__getitem__)
        events = adapter.ingest("2026-27")
        self.assertGreater(len(events), 0)
        self.assertEqual(len(adapter.failed_months), 1)
        self.assertEqual(len(adapter.successful_months), 2)

    def test_operational_work_resolver_receives_adapter_programme(self):
        config = settings("opera_roma", "/spettacoli/", "Teatro dell'Opera di Roma", "Teatro dell'Opera di Roma", "Rome", "Italy", "Europe/Rome")
        events = adapter_for("opera_roma", "opera_roma", config).ingest("2026-27")
        snapshot = GlobalEntitySnapshot(generated_at="2026-08-25", source="test", freshness_seconds=0, entities={"composer": [{"id": "c1", "canonical_name": "Giacomo Puccini"}], "work": [{"id": "w1", "title": "Tosca", "composer_id": "c1", "normalization_status": "verified", "work_kind": "work"}], "artist": [], "character": []}, work_aliases=[], health={"global_master_loaded": True})
        composer = resolve_entity("composer", events[0].programme[0]["composer"], snapshot)
        work = resolve_work(events[0].programme[0]["source_title"], composer, snapshot)
        self.assertEqual(work["status"], "existing")


if __name__ == "__main__":
    unittest.main()
