from __future__ import annotations

import io
import json
import sys
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
        "events": [],
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
