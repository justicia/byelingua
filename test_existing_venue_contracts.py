import unittest

from season_ingestion.adapters.existing_venue_contracts import AuditorioNacionalAdapter, page_url
from season_ingestion.adapters.detail_linked_listing import DetailLinkedListingAdapter
from season_ingestion.registry import load_registry
from season_ingestion.venue_targets import load_targets


class ExistingVenueSourceContractTests(unittest.TestCase):
    def test_all_six_existing_venues_are_registered_and_enabled(self):
        registry = load_registry()["venues"]
        targets = {target["venue_id"] for target in load_targets()}
        expected = {
            "teatro_real", "operadeparis", "philharmonie_paris",
            "auditorio_nacional", "teatro_alla_scala", "opera_roma",
        }
        self.assertEqual(targets, expected)
        for venue_id in ("operadeparis", "philharmonie_paris", "auditorio_nacional"):
            self.assertEqual(registry[venue_id]["source_contract"]["schema_version"], "official-source-contract-v2")
            self.assertFalse(registry[venue_id]["source_contract"]["writes"])

    def test_paris_and_philharmonie_use_jsonld_occurrence_identity(self):
        registry = load_registry()["venues"]
        cases = (
            ("operadeparis", "/en/season-26-27/opera/idomeneo"),
            ("philharmonie_paris", "/fr/activite/concert-symphonique/29615-demo"),
        )
        for venue_id, detail_path in cases:
            config = registry[venue_id]
            detail_url = ("https://www.operadeparis.fr" if venue_id == "operadeparis" else "https://philharmoniedeparis.fr") + detail_path
            detail = """
            <html><head><title>Season 26/27</title></head><body>
              <h1>Example production</h1><p>Music by Wolfgang Amadeus Mozart</p>
              <script type="application/ld+json">[
                {"@type":"Event","name":"Example production","startDate":"2027-05-01T19:30:00+02:00"},
                {"@type":"Event","name":"Example production","startDate":"2027-05-03T19:30:00+02:00"}
              ]</script>
            </body></html>
            """
            pages = {
                config["listing_source"]: f'<a href="{detail_url}">Example production</a>',
                detail_url: detail,
            }
            events = DetailLinkedListingAdapter(config, fetch=pages.__getitem__).ingest("2026-27")
            self.assertEqual([(event.date, event.start_time) for event in events], [
                ("2027-05-01", "19:30"), ("2027-05-03", "19:30")
            ])
            self.assertEqual(len({event.event_key for event in events}), 2)

    def test_auditorio_pagination_and_detail_rows_become_canonical_events(self):
        config = load_registry()["venues"]["auditorio_nacional"]
        listing_url = config["discovery_source"]
        detail_url = listing_url + "/demo"
        listing = f"""
        <article class="eventitem">
          <h3 class="eventitem__title"><a href="{detail_url}">OCNE. Demo</a></h3>
          <div class="event-date"><span class="weekday">2027-01-15T20:00:00+01:00</span></div>
          <div class="eventitem__text"><div class="location"><span>Sala Sinfónica</span></div></div>
        </article>
        """
        detail = """
        <div id="portal-content"><article id="content">
          <h1>OCNE. Demo</h1>
          <div class="rightColumn__item"><span class="rightColumn__item__label">Sala</span>
            <span class="rightColumn__item__text">Sala Sinfónica</span></div>
          <div class="content"><h4>Kent Nagano, director</h4><h4>Gustav Mahler, Sinfonía n.º 2</h4></div>
        </article></div>
        """
        pages = {page_url(0, listing_url): listing, detail_url: detail}
        events = AuditorioNacionalAdapter(config, fetch=pages.__getitem__).ingest("2026-27")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].date, "2027-01-15")
        self.assertEqual(events[0].start_time, "20:00")
        self.assertEqual(events[0].room, "Sala Sinfónica")
        self.assertEqual(events[0].source_url, detail_url)
        self.assertEqual(events[0].raw["listing_source_url"], page_url(0, listing_url))


if __name__ == "__main__":
    unittest.main()
