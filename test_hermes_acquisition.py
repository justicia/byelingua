from __future__ import annotations

import json
from jobs import hermes_acquire_worker as worker
from season_ingestion import hermes_acquisition as acquisition
from season_ingestion import pipeline
from season_ingestion.schema import CanonicalEvent


def _facts() -> dict:
    source_url = "https://official.example/event/1"
    return {
        "schema_version": "hermes-source-facts-v1",
        "venue_id": "berlin",
        "season": "2026-27",
        "source_id": "berlin",
        "source_type": "html",
        "official_source_url": "https://official.example/season",
        "source_contract": {"discovery_url": "https://official.example/season"},
        "events": [{
            "source_event_id": "event-1",
            "source_url": source_url,
            "title": "Die Zauberflöte",
            "date": "2026-10-01",
            "start_time": "19:30",
            "end_time": None,
            "room": "Main Hall",
            "programme": [{
                "source_title": "Die Zauberflöte",
                "composer": "Wolfgang Amadeus Mozart",
                "source_programme_index": 1,
                "original_programme_order": 1,
                "provenance": {"source_url": source_url},
            }],
            "credits": [{
                "artist_name": "Example Artist",
                "source_role": "performer",
                "function": "performer",
                "credit_kind": "cast",
                "source_url": source_url,
                "source_field": "official.cast",
                "provenance": {"source_url": source_url},
            }],
        }],
    }


def test_source_facts_convert_without_canonical_ids():
    config = {
        "source_id": "berlin",
        "organization": "Staatsoper Unter den Linden",
        "venue": "Staatsoper Unter den Linden",
        "city": "Berlin",
        "country": "Germany",
        "timezone": "Europe/Berlin",
    }
    events = acquisition.facts_to_events(_facts(), venue="berlin", config=config)
    assert len(events) == 1
    assert isinstance(events[0], CanonicalEvent)
    assert "work_id" not in events[0].programme[0]
    assert "artist_id" not in events[0].credits[0]


def test_acquisition_subprocess_contract_is_read_only(monkeypatch):
    facts = _facts()
    seen = {}

    class FakeProcess:
        pid = 123
        returncode = 0
        def communicate(self, input_text=None, timeout=None):
            seen["input"] = json.loads(input_text)
            return json.dumps(facts, ensure_ascii=False), ""
        def poll(self):
            return self.returncode

    def fake_popen(command, **kwargs):
        seen["command"] = command
        return FakeProcess()

    monkeypatch.setattr(acquisition.subprocess, "Popen", fake_popen)
    result = acquisition.acquire_source_facts({"venue_id": "berlin"}, command="python jobs/hermes_acquire_worker.py")
    assert result == facts
    assert seen["command"] == ["python", "jobs/hermes_acquire_worker.py"]
    assert seen["input"] == {"venue_id": "berlin"}


def test_pipeline_uses_hermes_fallback_before_shared_normalization(monkeypatch, tmp_path):
    config = {
        "official_source": "https://official.example/season",
        "source_id": "berlin",
        "organization": "Staatsoper Unter den Linden",
        "venue": "Staatsoper Unter den Linden",
        "city": "Berlin",
        "country": "Germany",
        "timezone": "Europe/Berlin",
        "source_contract": {"schema_version": "official-source-contract-v2", "writes": False},
    }

    class Adapter:
        last_errors = []

        def ingest(self, season):
            raise AssertionError("forced Hermes validation must not call deterministic adapter")

    facts = _facts()
    events = acquisition.facts_to_events(facts, venue="berlin", config=config)
    monkeypatch.setattr(pipeline, "load_registry", lambda: {"venues": {"berlin": config}})
    monkeypatch.setattr(pipeline, "load_adapter", lambda venue: Adapter())
    monkeypatch.setattr(pipeline, "acquire_events", lambda **kwargs: (facts, events))
    monkeypatch.setattr(pipeline, "load_global_snapshot", lambda path=None: pipeline.empty_global_snapshot("2026-01-01T00:00:00+00:00"))
    monkeypatch.setenv("BYELINGUA_FORCE_HERMES_FALLBACK", "1")
    monkeypatch.setenv("BYELINGUA_HERMES_ACQUIRE_COMMAND", "python jobs/hermes_acquire_worker.py")

    summary = pipeline.run_pipeline(venue="berlin", season="2026-27", output_dir=tmp_path)
    assert summary["source_capability"] == "SOURCE_PASS"
    assert summary["hermes_fallback"]["status"] == "PASS"
    assert summary["counts"]["events"] == 1
    assert summary["counts"]["writes"] == 0


def test_pipeline_replays_validated_hermes_artifact_without_refetch(monkeypatch, tmp_path):
    config = {
        "official_source": "https://official.example/season",
        "source_id": "berlin",
        "organization": "Staatsoper Unter den Linden",
        "venue": "Staatsoper Unter den Linden",
        "city": "Berlin",
        "country": "Germany",
        "timezone": "Europe/Berlin",
        "source_contract": {"schema_version": "official-source-contract-v2", "writes": False},
    }

    class Adapter:
        last_errors = []

        def ingest(self, season):
            raise AssertionError("validated Hermes artifact replay must not refetch the source")

    artifact = tmp_path / "hermes-source-facts.json"
    artifact.write_text(json.dumps(_facts(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(pipeline, "load_registry", lambda: {"venues": {"berlin": config}})
    monkeypatch.setattr(pipeline, "load_adapter", lambda venue: Adapter())
    monkeypatch.setattr(pipeline, "load_global_snapshot", lambda path=None: pipeline.empty_global_snapshot("2026-01-01T00:00:00+00:00"))

    summary = pipeline.run_pipeline(
        venue="berlin",
        season="2026-27",
        output_dir=tmp_path / "output",
        hermes_source_facts_path=artifact,
    )
    assert summary["source_capability"] == "SOURCE_PASS"
    assert summary["hermes_fallback"]["status"] == "PASS"
    assert summary["hermes_fallback"]["acquisition_mode"] == "validated_source_facts_artifact"
    assert summary["counts"]["events"] == 1
    assert summary["counts"]["writes"] == 0


def test_empty_deterministic_result_without_errors_is_eligible_for_hermes():
    class Adapter:
        last_errors = []

    assert acquisition.eligible_for_fallback(events=[], adapter=Adapter()) is True


def test_nonempty_deterministic_result_is_not_eligible_for_hermes():
    class Adapter:
        last_errors = [{"error": "stale warning"}]

    assert acquisition.eligible_for_fallback(events=[object()], adapter=Adapter()) is False


def test_empty_hermes_facts_are_rejected(monkeypatch):
    facts = _facts()
    facts["events"] = []

    class FakeProcess:
        pid = 123
        returncode = 0
        def communicate(self, input_text=None, timeout=None):
            return json.dumps(facts), ""
        def poll(self):
            return self.returncode

    monkeypatch.setattr(acquisition.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    try:
        acquisition.acquire_source_facts({"venue_id": "berlin"}, command="python jobs/hermes_acquire_worker.py")
    except acquisition.HermesAcquisitionError as exc:
        assert "events must be non-empty" in str(exc)
    else:
        raise AssertionError("empty Hermes facts unexpectedly passed")


def test_invalid_timeout_configuration_fails_preflight(monkeypatch):
    monkeypatch.setenv("BYELINGUA_HERMES_TOTAL_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("BYELINGUA_HERMES_FIRST_ATTEMPT_TIMEOUT_SECONDS", "11")
    try:
        worker.timeout_config_from_env()
    except worker.WorkerError as exc:
        assert "must not exceed total" in str(exc)
    else:
        raise AssertionError("invalid timeout configuration unexpectedly passed")


def test_outer_timeout_uses_worker_budget_plus_margin(monkeypatch):
    seen = {}

    class FakeProcess:
        returncode = 0
        pid = 123
        def communicate(self, input_text=None, timeout=None):
            seen["timeout"] = timeout
            return json.dumps(_facts()), ""
        def poll(self):
            return self.returncode

    monkeypatch.setenv("BYELINGUA_HERMES_TOTAL_TIMEOUT_SECONDS", "100")
    monkeypatch.setenv("BYELINGUA_HERMES_FIRST_ATTEMPT_TIMEOUT_SECONDS", "80")
    monkeypatch.setenv("BYELINGUA_HERMES_PROCESS_MARGIN_SECONDS", "10")
    monkeypatch.setattr(acquisition.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    acquisition.acquire_source_facts({"venue_id": "berlin", "official_source_url": "https://official.example/season"}, command="python jobs/hermes_acquire_worker.py")
    assert seen["timeout"] == 110


def test_invalid_programme_provenance_is_rejected():
    facts = _facts()
    facts["events"][0]["programme"][0]["provenance"] = "invalid"
    try:
        worker.validate_source_facts(facts)
    except ValueError as exc:
        assert str(exc) == "programme provenance must be an object"
    else:
        raise AssertionError("invalid programme provenance unexpectedly passed")
