from __future__ import annotations

import io
import json
import sys
from copy import deepcopy
import jobs.hermes_acquire_worker as worker


def _facts() -> dict:
    return {
        "schema_version": worker.SOURCE_FACTS_SCHEMA_VERSION,
        "venue_id": "berlin",
        "season": "2026-27",
        "source_id": "berlin",
        "source_type": "html",
        "official_source_url": "https://official.example/season",
        "source_contract": {"discovery_url": "https://official.example/season"},
        "events": [{
            "source_event_id": "berlin-1",
            "source_url": "https://official.example/event/1",
            "title": "Example production",
            "date": "2026-09-01",
            "start_time": None,
            "end_time": None,
            "programme": [],
            "credits": [],
        }],
    }


def test_prompt_forbids_non_browser_paths_and_preserves_contract(monkeypatch):
    prompt = worker.build_prompt(
        {"official_source_url": "https://official.example/season", "season": "2026-27"},
        json.dumps(worker.SOURCE_FACTS_SCHEMA, ensure_ascii=False, sort_keys=True),
    )
    assert "Browser Automation" in prompt
    assert "Do not use computer_use" in prompt
    assert "Do not use web search" in prompt
    assert "Do not use Supabase" in prompt
    assert worker.SOURCE_FACTS_SCHEMA_VERSION in prompt


def test_retry_marker_uses_short_json_only_prompt():
    request = {
        "official_source_url": "https://official.example/season",
        "listing_source_url": "https://official.example/calendar",
        "season": "2026-27",
        "_hermes_retry": True,
    }
    schema_text = json.dumps(worker.SOURCE_FACTS_SCHEMA, ensure_ascii=False, sort_keys=True)
    prompt = worker.build_prompt(request, schema_text)

    assert len(prompt) < len(worker.build_prompt({key: value for key, value in request.items() if key != "_hermes_retry"}, schema_text))
    assert "Return ONLY one valid JSON object" in prompt
    assert "No markdown" in prompt
    assert "hermes-source-facts-v1" in prompt
    assert "_hermes_retry" not in prompt
    assert request["official_source_url"] in prompt


def test_prompt_supports_official_pdf_fallback_and_hybrid_sources():
    request = {
        "official_source_url": "https://official.example/season",
        "listing_source_url": "https://official.example/calendar",
        "official_pdf_sources": ["https://official.example/season.pdf"],
        "season": "2026-27",
    }
    prompt = worker.build_prompt(
        request,
        json.dumps(worker.SOURCE_FACTS_SCHEMA, ensure_ascii=False, sort_keys=True),
    )
    normalized_prompt = " ".join(prompt.split())

    assert "<listing_source_url>" in prompt
    assert "official_pdf_sources" in normalized_prompt
    assert "inspect those official or officially linked PDF/brochure URLs first" in normalized_prompt
    assert "Inspect both URLs when they differ" in normalized_prompt
    assert "OFFICIAL PDF FALLBACK IS FIRST-CLASS" in normalized_prompt
    assert "official-domain PDF links or downloadable assets/document viewers linked directly" in normalized_prompt
    assert "pdf_sources" in normalized_prompt
    for field in ("venue_id", "pdf_url", "document_title", "season", "document_type", "coverage", "download_status"):
        assert field in normalized_prompt
    assert "FULL_SOURCE, ENRICHMENT_SOURCE, or HYBRID" in normalized_prompt
    assert "Never manufacture an occurrence from a range or premiere-only statement" in normalized_prompt
    assert "source_url as the exact PDF URL, pdf_page as a 1-based page number, and source_field" in normalized_prompt
    assert 'Top-level source_type remains strictly only "api" or "html"' in normalized_prompt


def test_prompt_requires_grouped_occurrences_to_inherit_source_title():
    prompt = worker.build_prompt(
        {"official_source_url": "https://official.example/season", "season": "2026-27"},
        json.dumps(worker.SOURCE_FACTS_SCHEMA, ensure_ascii=False, sort_keys=True),
    )
    normalized_prompt = " ".join(prompt.split())
    assert "Every emitted event MUST have a non-empty source-supported title" in normalized_prompt
    assert "group several occurrence dates under one production or work heading" in normalized_prompt
    assert "inherit the nearest explicit source-supported production/work title" in normalized_prompt
    assert "follow the official occurrence detail link" in normalized_prompt
    assert "Never invent a title" in normalized_prompt
    assert "do not emit that occurrence" in normalized_prompt


def test_prompt_requires_surviving_operatic_programme_evidence():
    prompt = worker.build_prompt(
        {"official_source_url": "https://official.example/season", "season": "2026-27"},
        json.dumps(worker.SOURCE_FACTS_SCHEMA, ensure_ascii=False, sort_keys=True),
    )
    normalized_prompt = " ".join(prompt.split())
    assert "the official production/work title is valid programme evidence" in normalized_prompt
    assert "follow that detail page for composer/work evidence" in normalized_prompt
    assert "programme.provenance.source_field to exactly \"official.detail.music\"" in normalized_prompt
    assert "use \"official.works\" or \"official.programme\"" in normalized_prompt
    assert "Do not use page-title, event.name, html.title, listing-card.title" in normalized_prompt
    assert "do not use a combined source field such as \"page title and Music by\"" in normalized_prompt


def test_lauditori_envelope_fields_are_restored_from_request_without_changing_facts():
    facts = _facts()
    for field in ("venue_id", "source_id", "official_source_url", "source_contract"):
        facts.pop(field)
    request = {
        "venue_id": "lauditori_barcelona",
        "season": "2026-27",
        "source_id": "lauditori_barcelona",
        "official_source_url": "https://www.auditori.cat/en/lauditori-season-2026-2027/",
        "listing_source_url": "https://www.auditori.cat/en/lauditori-season-2026-2027/",
    }

    normalized = worker._parse_and_validate(
        json.dumps(facts, ensure_ascii=False), worker.validate_source_facts, request=request
    )

    assert normalized["venue_id"] == request["venue_id"]
    assert normalized["source_id"] == request["source_id"]
    assert normalized["official_source_url"] == request["official_source_url"]
    assert normalized["source_contract"] == {"schema_version": worker.SOURCE_FACTS_SCHEMA_VERSION}
    assert normalized["source_type"] == "html"
    assert normalized["events"][0]["title"] == facts["events"][0]["title"]


def test_missing_envelope_metadata_does_not_trigger_hermes_retry(monkeypatch, capsys):
    facts = _facts()
    for field in ("venue_id", "source_id", "official_source_url", "source_contract"):
        facts.pop(field)
    request = {
        "venue_id": "lauditori_barcelona",
        "season": "2026-27",
        "source_id": "lauditori_barcelona",
        "official_source_url": "https://www.auditori.cat/en/lauditori-season-2026-2027/",
        "listing_source_url": "https://www.auditori.cat/en/lauditori-season-2026-2027/",
    }
    prompts = []
    monkeypatch.setattr(worker, "_run_hermes", lambda prompt, timeout_seconds: prompts.append(prompt) or json.dumps(facts))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))

    assert worker.main() == 0
    assert len(prompts) == 1
    normalized = json.loads(capsys.readouterr().out)
    assert normalized["venue_id"] == request["venue_id"]
    assert normalized["source_id"] == request["source_id"]
    assert normalized["official_source_url"] == request["official_source_url"]
    assert normalized["source_contract"] == {"schema_version": worker.SOURCE_FACTS_SCHEMA_VERSION}


def test_missing_factual_fields_remain_rejected_after_envelope_normalization():
    facts = _facts()
    facts["events"][0].pop("title")
    for field in ("venue_id", "source_id", "official_source_url", "source_contract"):
        facts.pop(field)
    request = {
        "venue_id": "lauditori_barcelona",
        "season": "2026-27",
        "source_id": "lauditori_barcelona",
        "official_source_url": "https://www.auditori.cat/en/lauditori-season-2026-2027/",
    }

    try:
        worker._parse_and_validate(json.dumps(facts), worker.validate_source_facts, request=request)
    except worker.WorkerError as exc:
        assert "events[0] missing required fields: title" in str(exc)
    else:
        raise AssertionError("missing factual event title unexpectedly passed")


def test_source_discovery_prompt_is_compact_and_official_only():
    prompt = worker.build_source_discovery_prompt({
        "venue_id": "tonhalle_zurich",
        "season": "2026-27",
        "official_source_url": "https://tonhalle-orchester.ch/en/concerts/saison-2026-27/",
        "listing_source_url": "https://tonhalle-orchester.ch/en/concerts/saison-2026-27/",
    })
    normalized = " ".join(prompt.split())
    assert "source-discovery worker" in normalized
    assert "stable official occurrence-discovery interface" in normalized
    assert "API/JSON/XHR endpoint" in normalized
    assert "pagination or month navigation" in normalized
    assert "detail URL pattern" in normalized
    assert "season filter/query parameters" in normalized
    assert "Do not extract the season and do not return source facts" in normalized
    assert "https://tonhalle-orchester.ch/en/concerts/saison-2026-27/" in prompt


def test_parse_normalizes_programme_order_and_preserves_hermes_raw_values():
    facts = _facts()
    facts["events"][0]["programme"] = [
        {
            "source_title": f"Work {raw_order}",
            "source_programme_index": raw_order,
            "original_programme_order": raw_order,
            "provenance": {},
        }
        for raw_order in (2, 4, 7)
    ]

    normalized = worker._parse_and_validate(json.dumps(facts), worker.validate_source_facts)
    programme = normalized["events"][0]["programme"]

    assert [row["source_programme_index"] for row in programme] == [1, 2, 3]
    assert [row["original_programme_order"] for row in programme] == [1, 2, 3]
    assert [row["source_title"] for row in programme] == ["Work 2", "Work 4", "Work 7"]
    assert [row["provenance"]["hermes_raw_source_programme_index"] for row in programme] == [2, 4, 7]
    assert [row["provenance"]["hermes_raw_original_programme_order"] for row in programme] == [2, 4, 7]


def test_replacement_character_in_source_facts_is_rejected():
    facts = _facts()
    facts["events"][0]["title"] = "Ariadne auf Naxos \ufffd"

    try:
        worker._parse_and_validate(json.dumps(facts, ensure_ascii=False), worker.validate_source_facts)
    except worker.WorkerError as exc:
        assert "replacement character in root.events[0].title" in str(exc)
    else:
        raise AssertionError("U+FFFD source fact was accepted")


def test_valid_european_unicode_passes_unchanged():
    facts = _facts()
    facts["source_contract"].update({
        "venue_name": "Staatsoper Unter den Linden",
        "artist_name": "José",
        "city": "Zürich",
        "theatre": "Théâtre",
    })
    facts["events"][0]["title"] = "Ariadne auf Naxos"
    facts["events"][0]["programme"] = [{
        "source_title": "Götterdämmerung",
        "source_programme_index": 1,
        "original_programme_order": 1,
        "provenance": {},
    }]
    original = deepcopy(facts)

    normalized = worker._parse_and_validate(
        json.dumps(facts, ensure_ascii=False), worker.validate_source_facts
    )

    assert normalized["source_contract"] == original["source_contract"]
    assert normalized["events"][0]["title"] == original["events"][0]["title"]
    assert normalized["events"][0]["programme"][0]["source_title"] == "Götterdämmerung"


def test_worker_configures_utf8_stdio_when_supported(monkeypatch):
    calls = []

    class Stream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(worker.sys, "stdout", Stream())
    monkeypatch.setattr(worker.sys, "stderr", Stream())

    worker._configure_utf8_stdio()

    assert calls == [
        {"encoding": "utf-8", "errors": "strict"},
        {"encoding": "utf-8", "errors": "strict"},
    ]


def test_worker_json_transport_round_trips_unicode_as_ascii(monkeypatch, capsys):
    facts = _facts()
    facts["source_contract"].update({
        "venue_name": "Zürich",
        "theatre": "Théâtre",
    })
    facts["events"][0]["title"] = "Łukasz"
    facts["events"][0]["programme"] = [{
        "source_title": "Götterdämmerung",
        "source_programme_index": 1,
        "original_programme_order": 1,
        "provenance": {},
    }]
    monkeypatch.setattr(
        worker,
        "_run_hermes",
        lambda prompt, timeout_seconds: json.dumps(facts, ensure_ascii=False),
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"official_source_url": "https://official.example", "season": "2026-27"})),
    )

    assert worker.main() == 0
    payload = capsys.readouterr().out.strip()
    assert payload.encode("ascii")
    round_tripped = json.loads(payload)
    assert round_tripped["events"][0]["title"] == "Łukasz"
    assert round_tripped["source_contract"]["venue_name"] == "Zürich"
    assert round_tripped["source_contract"]["theatre"] == "Théâtre"
    assert round_tripped["events"][0]["programme"][0]["source_title"] == "Götterdämmerung"


def test_run_hermes_forces_utf8_and_rejects_invalid_bytes(monkeypatch):
    calls = {}

    class FakeProcess:
        returncode = 0

        def communicate(self, timeout):
            return calls["stdout_bytes"], calls["stderr_bytes"]

    def fake_popen(command, **kwargs):
        calls["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(worker.shutil, "which", lambda name: "hermes")
    monkeypatch.setattr(worker.subprocess, "Popen", fake_popen)

    calls["stdout_bytes"] = "José".encode("utf-8")
    calls["stderr_bytes"] = b""
    assert worker._run_hermes("prompt", timeout_seconds=5) == "José"
    assert calls["kwargs"]["env"]["PYTHONUTF8"] == "1"
    assert calls["kwargs"]["env"]["PYTHONIOENCODING"] == "utf-8"
    assert "errors" not in calls["kwargs"]

    calls["stdout_bytes"] = b"invalid-utf8:\xff"
    try:
        worker._run_hermes("prompt", timeout_seconds=5)
    except worker.WorkerError as exc:
        assert "invalid UTF-8" in str(exc)
    else:
        raise AssertionError("invalid UTF-8 was silently decoded")


def test_replacement_character_retry_requests_refetch_and_exact_unicode(monkeypatch, capsys):
    invalid = _facts()
    invalid["events"][0]["title"] = "Ariadne auf Naxos \ufffd"
    responses = [json.dumps(invalid, ensure_ascii=False), json.dumps(_facts(), ensure_ascii=False)]
    prompts = []
    monkeypatch.setattr(
        worker,
        "_run_hermes",
        lambda prompt, timeout_seconds: prompts.append(prompt) or responses.pop(0),
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"official_source_url": "https://official.example", "season": "2026-27"})),
    )

    assert worker.main() == 0
    assert len(prompts) == 2
    assert "Refetch the affected source text" in prompts[1]
    assert "preserve the exact source Unicode" in prompts[1]
    assert "do not output replacement characters" in prompts[1]
    assert "return valid UTF-8 JSON only" in prompts[1]
    assert "\ufffd" not in capsys.readouterr().out


def test_main_retries_malformed_json_and_stdout_is_one_contract_document(monkeypatch, capsys):
    responses = [
        "not-json",
        json.dumps(_facts()),
    ]
    monkeypatch.setattr(worker, "_run_hermes", lambda prompt, timeout_seconds: responses.pop(0))
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"official_source_url": "https://official.example", "season": "2026-27"})),
    )

    assert worker.main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == _facts()
    assert "not-json" not in captured.out
    assert not responses


def test_main_does_not_emit_stdout_after_two_invalid_responses(monkeypatch, capsys):
    monkeypatch.setattr(worker, "_run_hermes", lambda prompt, timeout_seconds: "not-json")
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"official_source_url": "https://official.example", "season": "2026-27"})),
    )

    assert worker.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "malformed JSON" in captured.err
