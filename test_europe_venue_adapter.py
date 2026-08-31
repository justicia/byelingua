from season_ingestion.adapters.europe_venue import EuropeVenueAdapter


SETTINGS = {
    "venue_id": "wave_test",
    "source_id": "wave_test",
    "official_source": "https://official.example/season",
    "listing_source": "https://official.example/season",
    "organization": "Official Organization",
    "venue": "Official Venue",
    "city": "Paris",
    "country": "France",
    "timezone": "Europe/Paris",
    "season": "2026-27",
    "season_start_month": 9,
}


def test_jsonld_occurrence_is_source_fact_and_preserves_raw_title():
    page = '''
    <script type="application/ld+json">
    {"@type":"Event","@id":"https://official.example/event/1",
     "name":"Symphonie n°4 (35 min)","startDate":"2026-10-02T20:00:00+02:00",
     "composer":{"@type":"Person","name":"Ludwig van Beethoven"},
     "workPerformed":{"@type":"CreativeWork","name":"Symphonie n°4 (35 min)","composer":{"name":"Ludwig van Beethoven"}},
     "performer":{"@type":"Person","name":"Artist Example"}}
    </script>'''
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: page)
    events = adapter.ingest("2026-27")
    assert len(events) == 1
    event = events[0]
    assert event.date == "2026-10-02"
    assert event.start_time == "20:00"
    assert event.title == "Symphonie n°4"
    assert event.programme[0]["raw_title"] == "Symphonie n°4 (35 min)"
    assert event.programme[0]["source_title"] == "Symphonie n°4"
    assert event.raw["source_occurrence"]["startDate"].startswith("2026-10-02")
    assert event.credits[0]["artist_name"] == "Artist Example"


def test_explicit_year_is_required_for_html_time_fallback():
    page = '<h1>Concert</h1><time datetime="10-02T20:00">2 October</time>'
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: page)
    assert adapter.ingest("2026-27") == []
    assert adapter.date_year_unverified == 1


def test_detail_failure_is_isolated_and_recorded():
    listing = '<a href="/event/1">Event</a>'

    def fetch(url):
        if url.endswith("/season"):
            return listing
        raise RuntimeError("detail unavailable")

    adapter = EuropeVenueAdapter({**SETTINGS, "detail_path_prefixes": ["/event/"], "detail_link_pattern": "official\\.example/"}, fetch=fetch)
    assert adapter.ingest("2026-27") == []
    assert len(adapter.detail_pages_failed) == 1
    assert "detail unavailable" in adapter.last_errors[0]["error"]
