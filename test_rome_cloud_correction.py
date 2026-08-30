import unittest

from bs4 import BeautifulSoup

from season_ingestion.adapters.detail_linked_listing import DetailLinkedListingAdapter, _rome_credits
from season_ingestion.pipeline import match_existing_events
from season_ingestion.reconciliation import ExistingRecord
from season_ingestion.schema import CanonicalEvent


ROME_URL = "https://www.operaroma.it/spettacoli/example/"


def _rome_detail() -> BeautifulSoup:
    return BeautifulSoup(
        """
        <div class="ruoli">
          <h4>direttore</h4><span class="persone">Conductor Example</span><br/>
          <h4>regia</h4><span class="persone">Director Example</span><br/>
          <p>
            <p>Maestro del Coro <strong>Chorus Master Example</strong></p>
            <p>Scene <strong>Set Designer Example</strong></p>
            <p>Costumi <strong>Costume Designer Example</strong></p>
            <p>Luci <strong>Lighting Designer Example</strong></p>
            <p>Movimenti coreografici <strong>Choreographer Example</strong></p>
            <p>Drammaturgia <strong>Dramaturg Example</strong></p>
            <p>PERSONAGGI E INTEPRETI</p>
            <p>Character Twenty-Two <strong>Cast Twenty-Two</strong> 22, 25</p>
            <p>Character Twenty-Three <strong>Cast Twenty-Three</strong> 23, 26</p>
            <p>Ferrando <strong>Cast Every Date</strong></p>
            <p><strong>Orchestra e Coro del teatro dell’Opera di Roma</strong></p>
          </p>
        </div>
        """,
        "html.parser",
    )


class RomeCreditExtractionTests(unittest.TestCase):
    def test_ruoli_extracts_team_cast_and_both_collective_functions(self):
        rows = _rome_credits(_rome_detail(), ROME_URL, "2027-06-22")
        functions = {row["function"] for row in rows}
        self.assertTrue({
            "conductor", "stage_director", "chorus_master", "set_designer",
            "costume_designer", "lighting_designer", "choreographer", "dramaturg",
            "performer", "orchestra", "choir",
        } <= functions)
        self.assertIn("Character Twenty-Two", {row.get("character") for row in rows})
        self.assertNotIn("Character Twenty-Three", {row.get("character") for row in rows})
        self.assertEqual(sum(row["function"] == "performer" for row in rows), 2)

    def test_ruoli_trailing_day_annotations_change_by_occurrence(self):
        rows = _rome_credits(_rome_detail(), ROME_URL, "2027-06-23")
        characters = {row.get("character") for row in rows if row["credit_kind"] == "cast"}
        self.assertEqual(characters, {"Character Twenty-Three", "Ferrando"})

    def test_existing_scope_filters_detail_urls_without_touching_other_pages(self):
        config = {
            "source_id": "opera_roma",
            "listing_source": "https://official.example/listing",
            "official_source": "https://official.example/season",
            "detail_path_prefixes": ["/spettacoli/"],
            "detail_link_pattern": r"official\.example/spettacoli/",
            "organization": "Teatro dell'Opera di Roma",
            "venue": "Teatro dell'Opera di Roma",
            "city": "Rome",
            "country": "Italy",
            "timezone": "Europe/Rome",
            "season_start_month": 8,
            "season_end_month": 7,
            "season_bounds": {"2026-27": {"season_start": "2026-08-01", "season_end": "2027-12-31"}},
            "page_season_selector": "body",
            "page_season_pattern": r"Stagione\s+(20\d{2}\s*[/\-]\s*20\d{2})",
            "performance_container_selector": "#date-2",
            "performance_date_selector": ".datelist li",
            "performance_time_selector": ".turno",
            "detail_profile": "teatro_dell_opera_di_roma",
        }
        selected = "https://official.example/spettacoli/selected/"
        ignored = "https://official.example/spettacoli/ignored/"
        detail = "<body>Stagione 2026/2027<h1>Tosca</h1><p>Musica di Giacomo Puccini</p><section id=date-2><div class=datelist><li>22 Giu<span class=turno>ORE 20:00</span></li></div></section></body>"
        pages = {config["listing_source"]: f'<a href="{selected}">Selected</a><a href="{ignored}">Ignored</a>', selected: detail}
        adapter = DetailLinkedListingAdapter(config, fetch=pages.__getitem__)
        adapter.allowed_detail_urls = {selected}
        events = adapter.ingest("2026-27")
        self.assertEqual(len(events), 1)
        self.assertEqual(adapter.productions_discovered_before_scope, 2)
        self.assertEqual(adapter.detail_scope_filtered, 1)
        self.assertEqual(adapter.detail_pages_requested, [selected])

    def test_existing_event_match_is_one_to_one_and_read_only(self):
        def event(day: int) -> CanonicalEvent:
            return CanonicalEvent(
                source="opera_roma", source_event_id=f"new-{day}", source_url=ROME_URL,
                organization="Teatro dell'Opera di Roma", venue="Teatro dell'Opera di Roma",
                city="Rome", country="Italy", timezone="Europe/Rome", title="Example",
                date=f"2027-06-{day:02d}", start_time="20:00", end_time=None, room=None,
                event_type="performance", programme=[], credits=[],
            )

        staged = [event(22), event(23)]
        existing = [
            ExistingRecord(f"db-{day}", "opera_roma", f"old-{day}", ROME_URL, f"key-{day}", "Example", f"2027-06-{day:02d}", {"start_time": "20:00"}, frozenset({"start_time"}))
            for day in (22, 23)
        ]
        result = match_existing_events(staged, existing)
        self.assertEqual(result["matched_count"], 2)
        self.assertEqual(result["unmatched_existing"], [])
        self.assertEqual(result["unmatched_staged"], [])
        self.assertEqual([record.event_id for record in result["matched_records"]], ["db-22", "db-23"])


if __name__ == "__main__":
    unittest.main()
