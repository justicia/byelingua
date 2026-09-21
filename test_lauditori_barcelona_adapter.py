from __future__ import annotations

import json
from urllib.parse import quote

from season_ingestion.adapters.lauditori_barcelona import (
    LauditoriBarcelonaAdapter,
    expand_event_dates,
    extract_event_cards,
    parse_detail_enrichment,
)


def _listing(cards: list[dict]) -> str:
    payload = quote(json.dumps({"events": cards}, ensure_ascii=False, separators=(",", ":")), safe="")
    return f"<script>window.aPnextevents = JSON.parse(decodeURIComponent('{payload}'))</script>"


def _card(*, dates: str = "October 2 and 4, 2026") -> dict:
    return {
        "id": 10,
        "wp_post": {"post_title": "Beethoven's Seventh"},
        "event_date_text": dates,
        "link": "https://www.auditori.cat/en/events/beethoven-seventh/",
        "hall_obj": {"wp_post": {"post_title": "Sala 1 Pau Casals"}},
        "tax_ecategory_str": "Symphonic",
        "tax_cicles_str": "OBC",
        "interpreters_obj": [{"artist": {"wp_post": {"post_title": "OBC"}}}],
    }


DETAIL = """
<div class="wp-block-auditori-plugin-section">
  <h2>Repertoire</h2>
  <p>Robert Gerhard: Concertino for string orchestra<br/>
     Frédéric Chopin: Concerto for Piano and Orchestra No. 2, Op. 21<br/>
     Ludwig van Beethoven: Symphony No. 7, Op. 92</p>
  <h2>Artistas</h2>
  <p>Barcelona Symphony Orchestra<br/>Ludovic Morlot, conductor<br/>Jan Lisiecki, piano</p>
</div>
"""


def test_event_payload_and_explicit_multi_date_expansion():
    cards = extract_event_cards(_listing([_card()]))
    assert len(cards) == 1
    assert [row["date"] for row in expand_event_dates(cards[0]["event_date_text"], season="2026-27")] == ["2026-10-02", "2026-10-04"]


def test_compact_month_groups_expand_without_inventing_dates():
    rows = expand_event_dates("March 6 and 7, May 8 and 9, 2027 · 7 p.m.", season="2026-27")
    assert [(row["date"], row["start_time"]) for row in rows] == [
        ("2027-03-06", "19:00"),
        ("2027-03-07", "19:00"),
        ("2027-05-08", "19:00"),
        ("2027-05-09", "19:00"),
    ]


def test_explicit_twenty_four_hour_time_is_preserved():
    rows = expand_event_dates("February 13, 2027 · 20.00 h", season="2026-27")
    assert rows == [{"date": "2027-02-13", "start_time": "20:00"}]


def test_detail_repertoire_and_artists_are_source_traceable():
    result = parse_detail_enrichment(DETAIL, "https://www.auditori.cat/en/events/beethoven-seventh/")
    assert [row["source_title"] for row in result["programme"]] == [
        "Concertino for string orchestra",
        "Concerto for Piano and Orchestra No. 2, Op. 21",
        "Symphony No. 7, Op. 92",
    ]
    assert result["programme"][0]["composer"] == "Robert Gerhard"
    assert result["programme"][0]["provenance"]["source_field"] == "official.repertoire"
    assert [row["artist_name"] for row in result["credits"]] == ["Barcelona Symphony Orchestra", "Ludovic Morlot", "Jan Lisiecki"]
    assert result["credits"][1]["function"] == "conductor"


def test_adapter_emits_one_canonical_event_per_explicit_date_and_uses_details():
    listing_url = "https://www.auditori.cat/en/lauditori-season-2026-2027/"
    detail_url = "https://www.auditori.cat/en/events/beethoven-seventh/"
    pages = {listing_url: _listing([_card()]), detail_url: DETAIL}
    settings = {
        "venue_id": "lauditori_barcelona",
        "source_id": "lauditori_barcelona",
        "official_source": listing_url,
        "listing_source": listing_url,
        "organization": "L'Auditori de Barcelona",
        "venue": "L'Auditori",
        "city": "Barcelona",
        "country": "Spain",
        "timezone": "Europe/Madrid",
    }
    adapter = LauditoriBarcelonaAdapter(settings, fetch=pages.__getitem__)
    events = adapter.ingest("2026-27")
    assert adapter.event_cards == 1
    assert len(events) == 2
    assert [event.date for event in events] == ["2026-10-02", "2026-10-04"]
    assert all(event.start_time is None for event in events)
    assert all(len(event.programme) == 3 for event in events)
    assert all(len(event.credits) == 3 for event in events)
    assert all(event.source_url == detail_url for event in events)
    assert adapter.detail_pages_successful == [detail_url]
    assert adapter.source_time_optional is True
