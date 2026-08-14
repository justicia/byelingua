import json
from urllib.parse import parse_qs, urlparse

from season_ingestion.supabase import fetch_existing_sources


class Response:
    def __init__(self, rows):
        self.status = 200
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.rows).encode()


def test_reads_each_page_with_server_side_source_filter(monkeypatch):
    calls = []
    pages = [
        [{"event_id": "1", "source": "wiener_staatsoper", "source_event_id": "a", "events": {"event_key": "k1", "title": "A", "date": "2027-01-01"}}, {"event_id": "2", "source": "wiener_staatsoper", "source_event_id": "b", "events": {"event_key": "k2", "title": "B", "date": "2027-01-02"}}],
        [{"event_id": "3", "source": "wiener_staatsoper", "source_event_id": "c", "events": {"event_key": "k3", "title": "C", "date": "2027-01-03"}}],
    ]

    def fake_fetch(request, timeout):
        calls.append(request.full_url)
        return Response(pages[len(calls) - 1])

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly-key-not-printed")
    rows = fetch_existing_sources("wiener_staatsoper", page_size=2, fetcher=fake_fetch)
    assert len(rows) == 3
    assert all("source=eq.wiener_staatsoper" in url for url in calls)
    assert all("events.date=gte.2026-09-01" in url for url in calls)
    assert all("events.date=lte.2027-08-31" in url for url in calls)
    assert "offset=0" in calls[0] and "offset=2" in calls[1]
    assert all("/event_sources?" in url for url in calls)


def test_select_uses_the_authoritative_patchable_fields(monkeypatch):
    from season_ingestion.schema import PATCHABLE_EVENT_FIELDS

    calls = []

    def fake_fetch(request, timeout):
        calls.append(request.full_url)
        return Response([])

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly")
    fetch_existing_sources("wiener_staatsoper", fetcher=fake_fetch)
    url = calls[0]
    assert "%2A" not in url and "select=%2A" not in url
    selection = parse_qs(urlparse(url).query)["select"][0]
    assert selection == (
        "event_id,source,source_event_id,source_url,"
        "events!inner(id,event_key,title,date,start_time,end_time,room,event_type)"
    )
    assert all(field in selection for field in PATCHABLE_EVENT_FIELDS)
    assert all(field not in selection for field in (
        "classification", "data_quality", "normalization_status", "verification_status",
    ))
