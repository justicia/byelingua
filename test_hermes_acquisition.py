from __future__ import annotations

import json

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

    class Completed:
        returncode = 0
        stdout = json.dumps(facts, ensure_ascii=False)
        stderr = ""

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["input"] = json.loads(kwargs["input"])
        return Completed()

    monkeypatch.setattr(acquisition.subprocess, "run", fake_run)
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
