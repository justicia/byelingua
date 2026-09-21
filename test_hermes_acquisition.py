from __future__ import annotations

import json
import pytest
from jobs import hermes_acquire_worker as worker
from season_ingestion import hermes_acquisition as acquisition
from season_ingestion import pipeline
from season_ingestion.schema import CanonicalEvent
from season_ingestion.adapters.europe_venue import _programme


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


def test_source_facts_reclassify_generic_cast_orchestra_without_changing_evidence():
    facts = _facts()
    facts["events"][0]["credits"][0].update({"source_role": "orchestra", "function": "orchestra", "credit_kind": "cast"})
    config = {"source_id": "berlin", "organization": "Org", "venue": "Venue", "city": "City", "country": "Country", "timezone": "Europe/Berlin"}
    credit = acquisition.facts_to_events(facts, venue="berlin", config=config)[0].credits[0]
    assert credit["credit_kind"] == "ensemble"
    assert credit["source_role"] == "orchestra"


def test_build_request_preserves_listing_source_and_enables_pdf_fallback():
    config = {
        "official_source": "https://official.example/season",
        "listing_source": "https://official.example/calendar",
        "official_pdf_sources": ["https://official.example/season.pdf"],
        "source_id": "venue",
    }

    request = acquisition.build_request(
        venue="venue",
        season="2026-27",
        config=config,
        reason="deterministic_source_failure",
    )

    assert request["official_source_url"] == config["official_source"]
    assert request["listing_source_url"] == config["listing_source"]
    assert request["official_pdf_sources"] == config["official_pdf_sources"]
    assert request["official_pdf_fallback"]["enabled"] is True
    assert request["official_pdf_fallback"]["do_not_invent_dates"] is True


def test_build_request_falls_back_listing_url_when_no_separate_listing_exists():
    config = {"official_source": "https://official.example/season"}

    request = acquisition.build_request(
        venue="venue",
        season="2026-27",
        config=config,
        reason="deterministic_source_failure",
    )

    assert request["official_source_url"] == config["official_source"]
    assert request["listing_source_url"] == config["official_source"]


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


def test_valid_json_succeeds_on_first_attempt(monkeypatch, tmp_path):
    calls = []

    class FakeProcess:
        returncode = 0

        def communicate(self, input_text=None, timeout=None):
            calls.append(json.loads(input_text))
            return json.dumps(_facts(), ensure_ascii=False), ""

    monkeypatch.setattr(acquisition.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    metadata = {}
    result = acquisition.acquire_source_facts(
        {"venue_id": "lauditori_barcelona", "season": "2026-27"},
        command="python jobs/hermes_acquire_worker.py",
        artifact_dir=tmp_path,
        metadata=metadata,
    )

    assert result == _facts()
    assert len(calls) == 1
    assert metadata == {"attempts": 1, "raw_output_saved": "NO"}


def test_bridge_normalizes_missing_envelope_before_validation_without_retry(monkeypatch):
    facts = _facts()
    for field in ("venue_id", "source_id", "official_source_url", "source_contract"):
        facts.pop(field)
    calls = []

    class FakeProcess:
        returncode = 0

        def communicate(self, input_text=None, timeout=None):
            calls.append(json.loads(input_text))
            return json.dumps(facts, ensure_ascii=False), ""

    monkeypatch.setattr(acquisition.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    request = {
        "venue_id": "lauditori_barcelona",
        "season": "2026-27",
        "source_id": "lauditori_barcelona",
        "official_source_url": "https://www.auditori.cat/en/lauditori-season-2026-2027/",
    }

    result = acquisition.acquire_source_facts(request, command="python jobs/hermes_acquire_worker.py")

    assert len(calls) == 1
    assert result["venue_id"] == request["venue_id"]
    assert result["source_id"] == request["source_id"]
    assert result["official_source_url"] == request["official_source_url"]
    assert result["source_contract"] == {"schema_version": worker.SOURCE_FACTS_SCHEMA_VERSION}


def test_bridge_still_rejects_missing_factual_fields_after_envelope_normalization(monkeypatch):
    facts = _facts()
    facts["events"][0].pop("title")
    for field in ("venue_id", "source_id", "official_source_url", "source_contract"):
        facts.pop(field)

    class FakeProcess:
        returncode = 0

        def communicate(self, input_text=None, timeout=None):
            return json.dumps(facts, ensure_ascii=False), ""

    monkeypatch.setattr(acquisition.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    with pytest.raises(acquisition.HermesAcquisitionError) as caught:
        acquisition.acquire_source_facts(
            {
                "venue_id": "lauditori_barcelona",
                "season": "2026-27",
                "source_id": "lauditori_barcelona",
                "official_source_url": "https://www.auditori.cat/en/lauditori-season-2026-2027/",
            },
            command="python jobs/hermes_acquire_worker.py",
        )

    assert "events[0] missing required fields: title" in str(caught.value)


def test_fenced_json_is_recovered_without_rewriting_values(monkeypatch):
    class FakeProcess:
        returncode = 0

        def communicate(self, input_text=None, timeout=None):
            return f"```json\n{json.dumps(_facts(), ensure_ascii=False)}\n```", ""

    monkeypatch.setattr(acquisition.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    result = acquisition.acquire_source_facts(
        {"venue_id": "berlin"},
        command="python jobs/hermes_acquire_worker.py",
    )

    assert result["events"][0]["title"] == "Die Zauberflöte"


def test_malformed_first_attempt_retries_once_and_saves_raw_output(monkeypatch, tmp_path):
    responses = ["not-json", json.dumps(_facts(), ensure_ascii=False)]
    requests = []

    class FakeProcess:
        returncode = 0

        def communicate(self, input_text=None, timeout=None):
            requests.append(json.loads(input_text))
            return responses.pop(0), "first-attempt diagnostic" if len(requests) == 1 else ""

    monkeypatch.setattr(acquisition.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    metadata = {}
    result = acquisition.acquire_source_facts(
        {
            "venue_id": "lauditori_barcelona",
            "season": "2026-27",
            "official_source_url": "https://official.example/lauditori",
        },
        command="python jobs/hermes_acquire_worker.py",
        artifact_dir=tmp_path / "venue-artifact",
        metadata=metadata,
    )

    assert result["events"][0]["title"] == "Die Zauberflöte"
    assert len(requests) == 2
    assert requests[1]["_hermes_retry"] is True
    assert requests[1]["official_source_url"] == requests[0]["official_source_url"]
    raw_artifact = tmp_path / "venue-artifact" / "hermes-attempt-1.json"
    assert json.loads(raw_artifact.read_text(encoding="utf-8"))["raw_stdout"] == "not-json"
    assert metadata == {"attempts": 2, "raw_output_saved": "YES"}


def test_worker_malformed_error_on_stderr_also_retries(monkeypatch, tmp_path):
    responses = [
        (1, "", "hermes_worker_error: Hermes returned malformed JSON: Expecting value"),
        (0, json.dumps(_facts(), ensure_ascii=False), ""),
    ]
    calls = []

    class FakeProcess:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

        def communicate(self, input_text=None, timeout=None):
            calls.append(json.loads(input_text))
            return self.stdout, self.stderr

    def fake_popen(*args, **kwargs):
        return FakeProcess(*responses.pop(0))

    monkeypatch.setattr(acquisition.subprocess, "Popen", fake_popen)
    result = acquisition.acquire_source_facts(
        {"venue_id": "lauditori_barcelona", "season": "2026-27"},
        command="python jobs/hermes_acquire_worker.py",
        artifact_dir=tmp_path,
    )

    assert result["events"]
    assert len(calls) == 2
    assert calls[1]["_hermes_retry"] is True
    assert json.loads((tmp_path / "hermes-attempt-1.json").read_text(encoding="utf-8"))["raw_stderr"].startswith("hermes_worker_error")


def test_malformed_both_attempts_are_classified_and_preserved(monkeypatch, tmp_path):
    class FakeProcess:
        returncode = 0

        def communicate(self, input_text=None, timeout=None):
            return "truncated {", "worker diagnostic"

    monkeypatch.setattr(acquisition.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    with pytest.raises(acquisition.HermesAcquisitionError) as caught:
        acquisition.acquire_source_facts(
            {"venue_id": "tonhalle_zurich", "season": "2026-27"},
            command="python jobs/hermes_acquire_worker.py",
            artifact_dir=tmp_path / "venue-artifact",
        )

    error = caught.value
    assert error.status == acquisition.HERMES_MALFORMED_OUTPUT
    assert error.attempts == 2
    assert error.raw_output_saved is True
    assert len(error.raw_output_paths) == 2
    for attempt in (1, 2):
        artifact = json.loads((tmp_path / "venue-artifact" / f"hermes-attempt-{attempt}.json").read_text(encoding="utf-8"))
        assert artifact["venue_id"] == "tonhalle_zurich"
        assert artifact["season"] == "2026-27"
        assert artifact["attempt"] == attempt
        assert artifact["raw_stdout"] == "truncated {"
        assert artifact["raw_stderr"] == "worker diagnostic"


def test_structurally_invalid_source_facts_still_fail_validation_without_recovery(monkeypatch, tmp_path):
    invalid = _facts()
    invalid["events"][0]["programme"][0]["provenance"] = "invalid"
    calls = []

    class FakeProcess:
        returncode = 0

        def communicate(self, input_text=None, timeout=None):
            calls.append(True)
            return json.dumps(invalid, ensure_ascii=False), ""

    monkeypatch.setattr(acquisition.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    with pytest.raises(acquisition.HermesAcquisitionError) as caught:
        acquisition.acquire_source_facts(
            {"venue_id": "lauditori_barcelona", "season": "2026-27"},
            command="python jobs/hermes_acquire_worker.py",
            artifact_dir=tmp_path,
        )

    assert caught.value.status == acquisition.HERMES_VALIDATION_FAILED
    assert len(calls) == 1
    assert "programme provenance must be an object" in str(caught.value)


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


def test_production_timeout_defaults_are_browser_scale(monkeypatch):
    for name in ("BYELINGUA_HERMES_TOTAL_TIMEOUT_SECONDS", "BYELINGUA_HERMES_FIRST_ATTEMPT_TIMEOUT_SECONDS", "BYELINGUA_HERMES_PROCESS_MARGIN_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    config = worker.timeout_config_from_env()
    assert config == {"total": 1200, "first_attempt": 900, "margin": 60}


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


def test_jsonld_name_cannot_create_programme():
    assert _programme({"name": "Listing title"}, "Listing title", "https://official.example/event") == []


def test_missing_programme_does_not_block_event():
    facts = _facts()
    facts["events"][0]["programme"] = []
    config = {"source_id": "berlin", "organization": "Org", "venue": "Venue", "city": "Berlin", "country": "Germany", "timezone": "Europe/Berlin"}
    events = acquisition.facts_to_events(facts, venue="berlin", config=config)
    assert len(events) == 1
    assert events[0].programme == []


def test_successful_source_facts_are_persisted_atomically(tmp_path):
    path = acquisition.persist_source_facts(_facts(), root=tmp_path / "facts")
    assert path.name == "berlin-2026-27.json"
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == "hermes-source-facts-v1"
    assert not list(path.parent.glob(".*.tmp"))


def test_failed_source_facts_are_not_persisted(tmp_path):
    facts = _facts()
    facts["events"] = []
    try:
        acquisition.persist_source_facts(facts, root=tmp_path / "facts")
    except (ValueError, acquisition.HermesAcquisitionError):
        pass
    else:
        raise AssertionError("invalid source facts unexpectedly persisted")
    assert not (tmp_path / "facts" / "berlin-2026-27.json").exists()


def test_unsafe_source_facts_path_is_rejected(tmp_path):
    facts = _facts()
    facts["venue_id"] = "../escape"
    try:
        acquisition.persist_source_facts(facts, root=tmp_path / "facts")
    except acquisition.HermesAcquisitionError as exc:
        assert "unsafe artifact path component" in str(exc)
    else:
        raise AssertionError("unsafe source-facts path unexpectedly accepted")


def test_untrusted_programme_source_field_is_removed():
    facts = _facts()
    facts["events"][0]["programme"][0]["provenance"]["source_field"] = "llm.output"
    config = {"source_id": "berlin", "organization": "Org", "venue": "Venue", "city": "Berlin", "country": "Germany", "timezone": "Europe/Berlin"}
    event = pipeline.sanitize_programme_evidence(acquisition.facts_to_events(facts, venue="berlin", config=config))[0]
    assert event.programme == []
