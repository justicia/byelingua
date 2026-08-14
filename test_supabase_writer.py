from season_ingestion.reconciliation import ExistingRecord
from season_ingestion.supabase import apply_events, build_event_updates


def test_386_identity_matches_plan_only_existing_event_updates():
    existing = [ExistingRecord(f"db-event-{i}", "wiener_staatsoper", f"source-{i}", f"https://example/{i}", f"db-key-{i}", "Old", "2027-01-01") for i in range(386)]
    staging = [{"source": "wiener_staatsoper", "source_event_id": f"source-{i}", "source_url": f"https://example/{i}", "event_key": f"staging-key-{i}", "title": "New", "date": "2027-01-02"} for i in range(386)]
    updates = build_event_updates(staging, existing)
    assert len(updates) == 386
    assert {event_id for event_id, _ in updates} == {f"db-event-{i}" for i in range(386)}
    assert all(payload["title"] == "New" for _, payload in updates)
    assert all("event_key" not in payload for _, payload in updates)
    assert all("source_event_id" not in payload for _, payload in updates)


class Response:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_apply_writer_sends_only_existing_event_patches(monkeypatch):
    existing = [ExistingRecord(f"db-event-{i}", "wiener_staatsoper", f"source-{i}", f"https://example/{i}", f"db-key-{i}", "Old", "2027-01-01") for i in range(386)]
    staging = [{"source": "wiener_staatsoper", "source_event_id": f"source-{i}", "source_url": f"https://example/{i}", "event_key": f"staging-key-{i}", "title": "New", "date": "2027-01-02"} for i in range(386)]
    requests = []

    def sender(request, timeout):
        requests.append(request)
        return Response()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "unit-test-placeholder")
    assert apply_events(staging, existing, sender=sender) == 386
    assert len(requests) == 386
    assert all(request.method == "PATCH" for request in requests)
    assert all("/rest/v1/events?id=eq.db-event-" in request.full_url for request in requests)
