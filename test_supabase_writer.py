from season_ingestion.reconciliation import ExistingRecord
from season_ingestion.supabase import apply_events, build_event_updates


def test_386_identity_matches_plan_only_existing_event_updates():
    existing = [ExistingRecord(f"db-event-{i}", "wiener_staatsoper", f"source-{i}", f"https://example/{i}", f"db-key-{i}", "Old", "2027-01-01") for i in range(386)]
    staging = [{"source": "wiener_staatsoper", "source_event_id": f"source-{i}", "source_url": f"https://example/{i}", "event_key": f"staging-key-{i}", "title": "New", "date": "2027-01-02"} for i in range(386)]
    updates = build_event_updates(staging, existing)
    assert len(updates) == 386
    assert {update["event_id"] for update in updates} == {f"db-event-{i}" for i in range(386)}
    assert all(update["event_patch"]["title"] == "New" for update in updates)
    assert all("event_key" not in update["event_patch"] for update in updates)
    assert all("source_event_id" not in update["event_patch"] for update in updates)
    assert all(not {"credits", "programme", "artists"}.intersection(update["event_patch"]) for update in updates)


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


def test_unchanged_record_sends_no_patch(monkeypatch):
    requests = []

    def sender(request, timeout):
        requests.append(request)
        return Response()

    existing = [ExistingRecord("db-event-1", "wiener_staatsoper", "source-1", "https://example/1", "db-key-1", "Old title", "2027-01-01")]
    staging = [{"source": "wiener_staatsoper", "source_event_id": "source-1", "source_url": "https://example/1", "event_key": "staging-key", "title": "Old title", "date": "2027-01-01"}]
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "unit-test-placeholder")
    assert apply_events(staging, existing, sender=sender) == 0
    assert requests == []
