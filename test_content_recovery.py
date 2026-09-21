from __future__ import annotations

from season_ingestion.content_recovery import _expected_layers, extract_detail_content, recover_missing_content
from season_ingestion.pipeline import sanitize_programme_evidence
from season_ingestion.schema import CanonicalEvent


DETAIL_URL = "https://official.example/productions/la-calisto"
CONFIG = {
    "official_source": "https://official.example/season",
    "listing_source": "https://official.example/calendar",
    "organization": "Official Theatre",
}


def _event(*, programme=None, credits=None, source_url=DETAIL_URL, source_event_id="event-1", title="La Calisto", event_type="opera", raw=None) -> CanonicalEvent:
    return CanonicalEvent(
        source="test",
        source_event_id=source_event_id,
        source_url=source_url,
        organization="Official Theatre",
        venue="Official Theatre",
        city="Paris",
        country="France",
        timezone="Europe/Paris",
        title=title,
        date="2026-11-01",
        start_time="19:00",
        end_time=None,
        room=None,
        event_type=event_type,
        programme=programme or [],
        credits=credits or [],
        data_quality={"programme": {"status": "NO_PROGRAMME_EVIDENCE"}},
        raw=raw or {"detail_source_url": source_url},
    )


DETAIL = """
<html><body>
  <h1>La Calisto</h1>
  <p>Music by Francesco Cavalli</p>
  <table><tr><th>Conductor</th><td>Jane Conductor</td></tr></table>
</body></html>
"""


def test_detail_content_recovery_reuses_one_official_detail_fetch():
    calls = []

    class Adapter:
        def _fetch(self, url):
            calls.append(url)
            return DETAIL

    result = recover_missing_content([_event()], adapter=Adapter(), config=CONFIG, season="2026-27")
    recovered = result["events"][0]
    assert calls == [DETAIL_URL]
    assert recovered.programme[0]["source_title"] == "La Calisto"
    assert recovered.programme[0]["composer"] == "Francesco Cavalli"
    assert recovered.programme[0]["provenance"]["source_url"] == DETAIL_URL
    assert recovered.credits[0]["artist_name"] == "Jane Conductor"
    assert result["report"]["programme_recovered"] == 1
    assert result["report"]["credits_recovered"] == 1
    assert result["report"]["unexplained_zero_content_events"] == 0


def test_content_extractor_preserves_explicit_jsonld_work_and_credits():
    page = """
    <script type="application/ld+json">
    {"@type":"Event","name":"La Calisto","startDate":"2026-11-01T19:00:00+01:00",
     "workPerformed":{"@type":"CreativeWork","name":"La Calisto","composer":{"name":"Francesco Cavalli"}},
     "performer":{"@type":"Person","name":"Jane Singer"}}
    </script>
    """
    content = extract_detail_content(page, DETAIL_URL, _event())
    assert content["programme"][0]["source_title"] == "La Calisto"
    assert content["programme"][0]["composer"] == "Francesco Cavalli"
    assert content["credits"][0]["artist_name"] == "Jane Singer"


def test_explicit_work_title_is_kept_when_official_detail_omits_composer():
    page = """
    <script type="application/ld+json">
    {"@type":"Event","name":"The Magic Flute","startDate":"2026-11-01T19:00:00+00:00",
     "workPerformed":{"@type":"CreativeWork","name":"The Magic Flute"}}
    </script>
    """
    content = extract_detail_content(page, DETAIL_URL, _event())
    assert content["programme"][0]["source_title"] == "The Magic Flute"
    assert content["programme"][0]["composer"] is None


def test_missing_detail_evidence_gets_explicit_terminal_cause_without_fabrication():
    result = recover_missing_content(
        [_event(source_url="https://official.example/season")],
        adapter=object(),
        config=CONFIG,
        season="2026-27",
    )
    report_event = result["report"]["events"][0]
    assert report_event["programme_status"] == "PROGRAMME_RESOLUTION_FAILED"
    assert report_event["cast_status"] == "CAST_RESOLUTION_FAILED"
    assert result["report"]["unexplained_zero_content_events"] == 0


def test_expected_layers_do_not_use_theatre_domain_or_guided_tour_title():
    tour = _event(
        title="Guided Tour of the Theatre",
        event_type="theatre",
        source_url="https://official.example/theatre/guided-tour",
    )
    assert _expected_layers(tour) == {"work": False, "programme": False, "cast": False, "artistic_team": False}


def test_expected_layers_preserve_explicit_opera_and_concert_types():
    assert _expected_layers(_event(event_type="opera", title="La Traviata"))["cast"] is True
    assert _expected_layers(_event(event_type="concert", title="Orchestra Concert"))["programme"] is True


def test_404_performance_detail_falls_back_once_and_reuses_production_page():
    production_url = "https://official.example/productions/la-calisto"
    performance_one = "https://official.example/performances/la-calisto-1"
    performance_two = "https://official.example/performances/la-calisto-2"
    calls = []

    class Adapter:
        def _fetch(self, url):
            calls.append(url)
            if url != production_url:
                raise RuntimeError("HTTP 404 Not Found")
            return DETAIL

    events = [
        _event(source_event_id="event-1", source_url=performance_one, raw={"detail_source_url": performance_one, "production_detail_url": production_url}),
        _event(source_event_id="event-2", source_url=performance_two, raw={"detail_source_url": performance_two, "production_detail_url": production_url}),
    ]
    result = recover_missing_content(events, adapter=Adapter(), config=CONFIG, season="2026-27")
    assert calls == [performance_one, production_url, performance_two]
    assert all(event.programme for event in result["events"])
    assert result["report"]["source_pages_reused_across_events"] == 1
    assert result["report"]["events"][0]["failed_source_urls"] == [performance_one]
    assert result["report"]["events"][0]["fallback_source_url"] == production_url


def test_sanitizer_keeps_shared_detail_programme_evidence_but_drops_title_only_rows():
    event = _event(programme=[
        {
            "source_title": "La Calisto",
            "composer": "Francesco Cavalli",
            "source_programme_index": 1,
            "original_programme_order": 1,
            "provenance": {"source_url": DETAIL_URL, "source_field": "detail.composer"},
        },
        {
            "source_title": "La Calisto",
            "composer": None,
            "source_programme_index": 2,
            "original_programme_order": 2,
            "provenance": {"source_url": DETAIL_URL, "source_field": "jsonld.name"},
        },
    ])
    sanitized = sanitize_programme_evidence([event])[0]
    assert len(sanitized.programme) == 1
    assert sanitized.programme[0]["provenance"]["source_field"] == "detail.composer"
