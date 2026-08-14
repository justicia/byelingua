import re
from urllib.parse import urlparse

from season_ingestion.adapters.wiener_staatsoper import WienerStaatsoperAdapter, parse_calendar

SETTINGS = {
    "organization": "Wiener Staatsoper", "venue": "Wiener Staatsoper", "city": "Vienna",
    "country": "Austria", "timezone": "Europe/Vienna",
    "calendar_url": "https://www.wiener-staatsoper.at/en/calendar/{year}/{month}/",
}

HTML = '''
<div class="sticky-date" data-event="event-7"><span class="production-time">19:00 - 22:15</span></div>
<article id="event-7" class="event-list-item">
 <a class="event-title" href="/calendar/detail/die-zauberfloete/2026-09-12/">Die Zauberflöte</a>
 <div class="event-lead">Wolfgang Amadeus Mozart</div><div class="event-genre">Oper</div>
 <div class="event-room">Großes Haus</div>
 <div class="production-cast">
  <div class="d-flex justify-content-between"><p>Musikalische Leitung</p><div class="text-end"><a>A. Conductor</a></div></div>
  <div class="d-flex justify-content-between"><p>Regie, Bühne, Kostüme</p><div class="text-end"><a>A. Director</a></div></div>
  <div class="d-flex justify-content-between"><p>Tamino</p><div class="text-end"><span class="text-primary">A. Singer</span></div></div>
 </div>
</article>'''


def test_calendar_parses_source_identity_time_programme_and_cast():
    event = parse_calendar(HTML, "https://example/calendar", SETTINGS)[0]
    assert event.source_event_id == "die-zauberfloete:2026-09-12"
    assert (event.start_time, event.end_time) == ("19:00", "22:15")
    assert event.programme[0]["status"] == "source_verified"
    assert event.credits[0]["artistic_function"] == "conductor"
    assert event.credits[1]["artistic_function"] == "stage_director"
    assert event.credits[2] == {"person": "A. Singer", "raw_role_label": "Tamino", "role": "performer", "character": "Tamino"}


def test_season_fetches_each_month_once_and_keeps_partial_results():
    calls = []
    def fetch(url):
        calls.append(url)
        if "october" in url: raise RuntimeError("temporary failure")
        return HTML if "september" in url else "<html></html>"
    adapter = WienerStaatsoperAdapter(SETTINGS, fetch=fetch)
    events = adapter.ingest("2026-27")
    assert len(calls) == 12 and len(set(calls)) == 12
    assert len(events) == 1
    assert adapter.last_errors[0]["url"].endswith("/2026/october/")


def test_event_key_is_stable_when_mutable_content_changes():
    first = parse_calendar(HTML, "https://example/calendar", SETTINGS)[0]
    changed = parse_calendar(HTML.replace("19:00", "20:00"), "https://example/calendar", SETTINGS)[0]
    assert first.event_key == changed.event_key


def test_unknown_music_is_review_required_and_missing_fields_have_reasons():
    html = HTML.replace(
        '<span class="production-time">19:00 - 22:15</span>',
        '<span class="production-time"></span>',
    ).replace('<div class="event-lead">Wolfgang Amadeus Mozart</div>', '')
    html = html.replace('<div class="production-cast">', '<div class="not-production-cast">')
    event = parse_calendar(html, "https://example/calendar", SETTINGS)[0]
    assert event.start_time is None
    assert event.data_quality["start_time"]["reason"] == "calendar_sticky_time_not_provided"
    assert event.data_quality["credits"]["status"] == "incomplete_source_data"
    assert event.programme[0]["normalization_status"] == "review_required"
    assert event.programme[0]["source_title"] == "Die Zauberflöte"


def test_composer_whitespace_is_cleaned_and_multiple_names_are_structured():
    html = HTML.replace(
        "Wolfgang Amadeus Mozart",
        "  Wolfgang  Amadeus Mozart,\n Johann   Strauss  ",
    )
    event = parse_calendar(html, "https://example/calendar", SETTINGS)[0]
    assert [item["composer"] for item in event.programme] == [
        "Wolfgang Amadeus Mozart", "Johann Strauss"
    ]
    assert all(not re.search(r"\n|\s{2,}", item["composer"]) for item in event.programme)


def test_identity_dates_and_source_urls_are_valid_and_unique():
    events = parse_calendar(HTML + HTML.replace("2026-09-12", "2026-09-13"),
                            "https://example/calendar", SETTINGS)
    assert len({event.event_key for event in events}) == len(events)
    assert len({event.source_event_id for event in events}) == len(events)
    for event in events:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", event.date)
        parsed = urlparse(event.source_url)
        assert parsed.scheme == "https" and parsed.netloc
