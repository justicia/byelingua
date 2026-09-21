import json

from season_ingestion.adapters.europe_venue import EuropeVenueAdapter, _season_month_urls


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


def test_official_paginated_event_overview_api_produces_explicit_occurrences():
    first = {
        "Pager": {"LastIndex": 2},
        "EventOverview": [{
            "IdEventDate": 1,
            "Slug": "/event/one",
            "Title": "Opera One",
            "DateFrom": "2026-09-02 19:30:00",
            "DateTo": "2026-09-02 22:00:00",
            "Location": "Main Hall",
        }],
    }
    second = {
        "Pager": {"LastIndex": 2},
        "EventOverview": [{
            "IdEventDate": 2,
            "Slug": "/event/two",
            "Title": "Opera Two",
            "DateFrom": "2026-09-03 20:00:00",
            "Location": "Studio",
        }],
    }
    pages = {
        "https://official.example/event.json?p=1": json.dumps(first),
        "https://official.example/event.json?p=2": json.dumps(second),
        "https://official.example/event/one": "{}",
        "https://official.example/event/two": "{}",
    }
    adapter = EuropeVenueAdapter({**SETTINGS, "listing_source": "https://official.example/event.json?p=1"}, fetch=pages.__getitem__)
    events = adapter.ingest("2026-27")
    assert [(event.title, event.date, event.start_time, event.room) for event in events] == [
        ("Opera One", "2026-09-02", "19:30", "Main Hall"),
        ("Opera Two", "2026-09-03", "20:00", "Studio"),
    ]
    assert adapter.listing_pages_successful[-1].endswith("p=2")


def test_observed_season_month_template_expands_only_requested_season():
    urls = _season_month_urls("https://official.example/calendar?month=YYYY-MM", "2026-27")
    assert len(urls) == 12
    assert urls[0].endswith("month=2026-09")
    assert urls[-1].endswith("month=2027-08")
    assert len(set(urls)) == 12


def test_generic_embedded_payload_joins_production_title_to_explicit_sessions():
    payload = {
        "productions": {
            "42": {
                "id": 42,
                "title": {"en": "La Vestale"},
                "url": "/production/la-vestale",
                "composer": {"name": "Gaspare Spontini"},
            }
        },
        "sessions": {
            "101": {"id": 101, "production": 42, "start_date": {"value": "2026-11-01 19:30"}},
            "102": {"id": 102, "production": 42, "start_date": {"value": "2026-11-03 19:30"}},
        },
    }
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: json.dumps(payload))
    events = adapter.ingest("2026-27")
    assert [(event.title, event.date, event.start_time) for event in events] == [
        ("La Vestale", "2026-11-01", "19:30"),
        ("La Vestale", "2026-11-03", "19:30"),
    ]
    assert events[0].programme[0]["composer"] == "Gaspare Spontini"


def test_generic_json_byte_array_transport_is_decoded_without_factual_rewrite():
    payload = {"events": [{"id": "e1", "title": "Zürich Concert", "date": "2027-02-04T20:00:00+01:00"}]}
    encoded = json.dumps(payload).encode("utf-8")
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: json.dumps(list(encoded)))
    events = adapter.ingest("2026-27")
    assert len(events) == 1
    assert events[0].title == "Zürich Concert"


def test_rbo_json_api_uses_official_tags_for_type_and_tour_exclusion():
    payload = {
        "data": [
            {
                "type": "event", "id": "manon",
                "attributes": {"title": "Manon", "productionPageUrl": "/production/manon-kenneth-macmillan", "performances": [{"date": "2026-10-13T19:30:00+01:00", "performanceType": "standard"}]},
                "relationships": {"tags": {"data": [{"type": "tags", "id": "ballet"}]}},
            },
            {
                "type": "event", "id": "tour",
                "attributes": {"title": "Architecture Tour", "performances": [{"date": "2026-10-14T12:00:00+01:00", "performanceType": "guided-tour"}]},
                "relationships": {"tags": {"data": [{"type": "tags", "id": "tour"}]}},
            },
        ],
        "included": [
            {"type": "tags", "id": "ballet", "attributes": {"title": "Ballet and dance"}},
            {"type": "tags", "id": "tour", "attributes": {"title": "Tours"}},
        ],
    }
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: json.dumps(payload))
    events = adapter.ingest("2026-27")
    assert [(event.title, event.event_type) for event in events] == [("Manon", "ballet"), ("Architecture Tour", "visitor_activity")]
    assert events[0].source_url.endswith("/production/manon-kenneth-macmillan")
    assert events[0].raw["official_tags"] == ["Ballet and dance"]


def test_rbo_live_podcast_is_not_left_as_an_unclassified_performance():
    payload = {
        "data": [{
            "type": "event", "id": "dish",
            "attributes": {"title": "Dish from Waitrose", "productionPageUrl": "/production/dish-from-waitrose", "performances": [{"date": "2026-11-01T16:00:00+00:00"}]},
            "relationships": {"tags": {"data": []}},
        }],
        "included": [],
    }
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: json.dumps(payload))
    events = adapter.ingest("2026-27")
    assert events[0].event_type == "other"


def test_rbo_participatory_tea_dance_is_not_misclassified_as_ballet():
    payload = {
        "data": [{
            "type": "event", "id": "tea-dance",
            "attributes": {"title": "Tea Dance", "performances": [{"date": "2026-11-02T12:30:00+00:00"}]},
            "relationships": {"tags": {"data": []}},
        }],
        "included": [],
    }
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: json.dumps(payload))
    events = adapter.ingest("2026-27")
    assert events[0].event_type == "other"


def test_semantic_slot_dedup_prefers_detail_page_over_listing_source_id():
    listing = '''<a href="/production/manon">Manon</a>
    <script type="application/ld+json">{
      "@type":"Event", "@id":"listing-id", "name":"Manon",
      "startDate":"2026-10-13T19:30:00+01:00", "url":"https://official.example/season"
    }</script>'''
    detail = '''<script type="application/ld+json">{
      "@type":"Event", "@id":"detail-id", "name":"Manon",
      "startDate":"2026-10-13T19:30:00+01:00", "url":"https://official.example/production/manon",
      "location":{"name":"Main Stage"}
    }</script>'''
    pages = {"https://official.example/season": listing, "https://official.example/production/manon": detail}
    settings = {**SETTINGS, "detail_path_prefixes": ["/production/"]}
    adapter = EuropeVenueAdapter(settings, fetch=pages.__getitem__)
    events = adapter.ingest("2026-27")
    assert len(events) == 1
    assert events[0].source_url == "https://official.example/production/manon"
    assert events[0].room == "Main Stage"
    assert adapter.duplicate_performance_slot == 0
    assert adapter.source_duplicates_collapsed == 1


def test_semantic_slot_dedup_keeps_listing_category_with_detail_cast():
    listing_payload = {
        "data": [{
            "type": "event", "id": "friends-rehearsal",
            "attributes": {"title": "Friends Rehearsals", "productionPageUrl": "/production/friends-rehearsals", "performances": [{"date": "2026-09-08T19:45:00+02:00"}]},
            "relationships": {"tags": {"data": [{"type": "tags", "id": "rehearsal"}, {"type": "tags", "id": "ballet"}]}},
        }],
        "included": [
            {"type": "tags", "id": "rehearsal", "attributes": {"title": "Rehearsals"}},
            {"type": "tags", "id": "ballet", "attributes": {"title": "Ballet and dance"}},
        ],
    }
    detail_state = {"queries": [{"state": {"data": {"data": {"stage": {
        "title": "Friends Rehearsals",
        "activities": [{"id": "74463", "attributes": {
            "date": "2026-09-08T19:45:00+02:00",
            "tags": [],
            "prioritisedCast": [{"name": "Example Artist", "role": "Example Role"}],
        }}],
    }}}}}]}
    detail_page = f'<script>window.__REACT_QUERY_DEHYDRATED_STATE__ = {json.dumps(detail_state)};</script>'
    pages = {
        "https://official.example/season": json.dumps(listing_payload),
        "https://official.example/production/friends-rehearsals": detail_page,
    }
    settings = {**SETTINGS, "detail_path_prefixes": ["/production/"]}
    adapter = EuropeVenueAdapter(settings, fetch=pages.__getitem__)
    events = adapter.ingest("2026-27")
    assert len(events) == 1
    assert events[0].event_type == "rehearsal"
    assert events[0].raw["official_tags"] == ["Rehearsals", "Ballet and dance"]
    assert events[0].credits[0]["artist_name"] == "Example Artist"


def test_rbo_detail_state_preserves_per_performance_cast_and_local_timezone():
    state = {
        "queries": [{"state": {"data": {"data": {"stage": {
            "title": "Manon",
            "activities": [{
                "id": "74500",
                "attributes": {
                    "date": "2026-10-13T20:30:00+02:00",
                    "castListUrl": "/cast-sheet/manon/74500",
                    "tags": [{"tags": {"title": "Ballet and dance"}}],
                    "locations": [{"locations": {"title": "Main Stage"}}],
                    "prioritisedCast": [
                        {"name": "Koen Kessels", "role": "Conductor"},
                        {"name": "Francesca Hayward", "role": "Manon"},
                        {"name": "Marcelino Sambé", "role": "Des Grieux"},
                        {"name": "Orchestra of the Royal Opera House", "role": "Orchestra"},
                    ],
                },
            }],
        }}}}}],
    }
    page = f'<script>window.__REACT_QUERY_DEHYDRATED_STATE__ = {json.dumps(state)};</script>'
    pages = {
        "https://official.example/season": '<a href="/production/manon">Manon</a>',
        "https://official.example/production/manon": page,
    }
    settings = {**SETTINGS, "timezone": "Europe/London", "detail_path_prefixes": ["/production/"]}
    adapter = EuropeVenueAdapter(settings, fetch=pages.__getitem__)
    events = adapter.ingest("2026-27")
    assert len(events) == 1
    event = events[0]
    assert (event.date, event.start_time, event.event_type, event.room) == ("2026-10-13", "19:30", "ballet", "Main Stage")
    assert [(row["artist_name"], row["source_role"], row["credit_kind"]) for row in event.credits] == [
        ("Koen Kessels", "Conductor", "artistic_team"),
        ("Francesca Hayward", "Manon", "cast"),
        ("Marcelino Sambé", "Des Grieux", "cast"),
        ("Orchestra of the Royal Opera House", "Orchestra", "ensemble"),
    ]


def test_generic_html_calendar_card_preserves_explicit_day_and_title():
    page = """
    <div data-day="2026-10-12"><ul class="events-list">
      <li class="event-entry"><div data-href="/events/one">
        <h3 class="event-title">Ariadne auf Naxos</h3><span>20:00</span>
      </div></li>
    </ul></div>
    """
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: page)
    events = adapter.ingest("2026-27")
    assert len(events) == 1
    assert events[0].title == "Ariadne auf Naxos"
    assert events[0].date == "2026-10-12"
    assert events[0].start_time == "20:00"


def test_generic_rendered_payload_uses_literal_date_and_nearby_source_name():
    page = '<script>window.__NUXT__=(function(){return {date_start:"2026-09-17T18:30:00+02:00",name:"VOCES8"}})()</script>'
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: page)
    events = adapter.ingest("2026-27")
    assert len(events) == 1
    assert events[0].title == "VOCES8"
    assert events[0].date == "2026-09-17"
    assert events[0].start_time == "18:30"


def test_generic_event_card_supports_localized_explicit_date_text():
    page = """
    <div class="event-card"><a href="/en/calendar/example">
      <h3>Palestine, a Song of the Land</h3>
      <p>14 Sept.'26 - 20:00</p>
    </a></div>
    """
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: page)
    events = adapter.ingest("2026-27")
    assert len(events) == 1
    assert events[0].title == "Palestine, a Song of the Land"
    assert events[0].date == "2026-09-14"
    assert events[0].start_time == "20:00"


def test_generic_calendar_link_supports_explicit_spanish_date_text():
    page = """
    <div class="calendar-event"><a href="/es/temporada/example">
      <h3>La verbena de la Paloma</h3>
      <p>Miércoles, 23 Septiembre 2026</p>
    </a></div>
    """
    adapter = EuropeVenueAdapter(SETTINGS, fetch=lambda _: page)
    events = adapter.ingest("2026-27")
    assert len(events) == 1
    assert events[0].title == "La verbena de la Paloma"
    assert events[0].date == "2026-09-23"
