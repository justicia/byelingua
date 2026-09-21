from __future__ import annotations

from pathlib import Path

from season_ingestion.acquisition_state_machine import (
    BLOCKED,
    HERMES_BLOCKED,
    HERMES_MALFORMED_OUTPUT,
    HERMES_PARTIAL,
    HERMES_PASS,
    HUMAN_PDF_REQUIRED,
    NO_OFFICIAL_PDF,
    PDF_ENRICHMENT_SOURCE,
    PDF_FULL_SOURCE,
    REVIEW_REQUIRED,
    SOURCE_READY,
    assess_hermes_quality,
    merge_official_source_facts,
    run_acquisition_state_machine,
)
from season_ingestion.pdf_batch import (
    ACQUISITION_STATE_MACHINE_VENUES,
    UNRESOLVED_ACQUISITION_STATE_MACHINE_VENUES,
)


OFFICIAL = "https://venue.example/season"
PDF = "https://cdn.venue.example/season.pdf"


def _config() -> dict:
    return {
        "venue_id": "test_venue",
        "source_id": "test_venue",
        "official_source": OFFICIAL,
        "listing_source": OFFICIAL,
        "official_pdf_sources": [PDF],
        "organization": "Test Organization",
        "venue": "Test Venue",
        "city": "Test City",
        "country": "Test Country",
        "timezone": "Europe/Berlin",
        "source_contract": {"schema_version": "official-source-contract-v2", "writes": False},
    }


def _facts(*, source_url: str = OFFICIAL, title: str = "Ariadne auf Naxos", programme: bool = False, coverage: dict | None = None) -> dict:
    event = {
        "source_event_id": "event-1",
        "source_url": source_url,
        "title": title,
        "date": "2026-09-16",
        "start_time": "19:30",
        "end_time": None,
        "room": "Main Hall",
        "event_type": "performance",
        "classification": "performance",
        "programme": [],
        "credits": [],
        "provenance": {"source_url": source_url, "source_field": "official.event"},
    }
    if programme:
        event["programme"] = [{
            "source_title": title,
            "source_programme_index": 1,
            "original_programme_order": 1,
            "provenance": {"source_url": source_url, "source_field": "official.programme", "pdf_page": 4, "pdf_sha256": "b" * 64},
        }]
    contract = {"writes": False}
    if coverage is not None:
        contract["coverage_quality"] = coverage
    return {
        "schema_version": "hermes-source-facts-v1",
        "venue_id": "test_venue",
        "season": "2026-27",
        "source_id": "test_venue",
        "source_type": "html",
        "official_source_url": source_url,
        "source_contract": contract,
        "events": [event],
    }


def test_hermes_status_requires_coverage_quality_pass():
    assert assess_hermes_quality(_facts()) == (HERMES_PASS, None)
    assert assess_hermes_quality(_facts(coverage={"status": "partial"})) == (HERMES_PARTIAL, "coverage_quality=partial")
    assert assess_hermes_quality(None, error="timeout") == (HERMES_BLOCKED, "timeout")
    assert assess_hermes_quality({**_facts(), "events": []}) == (HERMES_BLOCKED, "events=0")


def test_merge_keeps_hybrid_event_and_pdf_row_provenance():
    request = {"venue_id": "test_venue", "season": "2026-27", "source_id": "test_venue", "official_source_url": OFFICIAL}
    merged = merge_official_source_facts(
        [("hermes", _facts()), ("pdf", _facts(source_url=PDF, programme=True))],
        request=request,
    )

    assert len(merged["events"]) == 1
    assert merged["events"][0]["source_url"] == OFFICIAL
    assert merged["events"][0]["programme"][0]["provenance"]["source_url"] == PDF
    assert merged["events"][0]["provenance"]["source_records"][0]["source_url"] == PDF


def test_state_machine_stops_after_hermes_pass(tmp_path: Path):
    called = []

    def discover(*args, **kwargs):
        called.append(True)
        return []

    report = run_acquisition_state_machine(
        venue_id="test_venue",
        season="2026-27",
        config=_config(),
        output_dir=tmp_path,
        hermes_runner=lambda request: {"facts": _facts()},
        pdf_discoverer=discover,
    )

    assert report["hermes_status"] == HERMES_PASS
    assert report["final_status"] == SOURCE_READY
    assert report["merged_events"] == 1
    assert called == []
    assert report["production_writes"] == 0


def test_discovery_runs_shared_deterministic_path_before_pdf_fallback(tmp_path: Path):
    report = run_acquisition_state_machine(
        venue_id="test_venue",
        season="2026-27",
        config=_config(),
        output_dir=tmp_path,
        hermes_runner=lambda request: {"source_discovery": "PASS", "discovered_mode": "HTML", "discovered_endpoint": OFFICIAL},
        deterministic_runner=lambda **kwargs: {"events": 2, "programme": 3, "credits": 4, "global_master": "PASS", "source_capability": "SOURCE_PASS", "passed": True},
        pdf_discoverer=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("PDF fallback should not run")),
    )
    assert report["hermes_status"] == HERMES_PASS
    assert report["acquisition_mode"] == "HTML"
    assert report["merged_events"] == 2
    assert report["global_master"] == "PASS"
    assert report["final_status"] == SOURCE_READY


def test_discovery_without_occurrences_never_inherits_source_ready(tmp_path: Path):
    report = run_acquisition_state_machine(
        venue_id="test_venue",
        season="2026-27",
        config=_config(),
        output_dir=tmp_path,
        hermes_runner=lambda request: {"source_discovery": "PASS", "discovered_mode": "API", "discovered_endpoint": "https://venue.example/events?date={YYYY-MM-DD}&p={page}"},
        deterministic_runner=lambda **kwargs: {"events": 0, "programme": 0, "credits": 0, "global_master": "PASS", "source_capability": "SOURCE_PASS", "passed": False},
        pdf_discoverer=lambda *args, **kwargs: [],
    )
    assert report["final_status"] == BLOCKED
    assert report["acquisition_status"] == "ADAPTER_REQUIRED"
    assert report["merged_events"] == 0
    assert report["pdf_discovered"] == "NO"


def test_state_machine_writes_capability_profile_for_every_run(tmp_path: Path):
    report = run_acquisition_state_machine(
        venue_id="test_venue",
        season="2026-27",
        config=_config(),
        output_dir=tmp_path,
        hermes_runner=lambda request: {"facts": _facts()},
    )
    profile_path = tmp_path / "source_capability_profile.json"
    assert report["source_family"] == "STRUCTURED_HTML"
    assert profile_path.exists()


def test_discovery_endpoint_template_is_rendered_for_deterministic_api(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_pipeline(**kwargs):
        captured.update(kwargs)
        return {"counts": {"events": 1}, "detail_enrichment": {}, "global_master_preflight": "PASS", "source_capability": "SOURCE_PASS", "passed": True}

    monkeypatch.setattr("season_ingestion.acquisition_state_machine.run_pipeline", fake_pipeline)
    from season_ingestion.acquisition_state_machine import _default_deterministic_runner

    result = _default_deterministic_runner(
        venue_id="test_venue",
        season="2026-27",
        config=_config(),
        discovery={"discovered_mode": "API", "discovered_endpoint": "https://venue.example/api?date={YYYY-MM-DD}&p=N&category={value}"},
        output_dir=tmp_path,
    )
    assert captured["config_override"]["listing_source"] == "https://venue.example/api?date=2026-09-01&p=1&category=alle"
    assert result["events"] == 1


def test_partial_hermes_plus_full_pdf_becomes_source_ready(tmp_path: Path):
    def pdf_runner(**kwargs):
        return {"pdf_download": "PASS", "source_type": "FULL_SOURCE", "facts": _facts(source_url=PDF, programme=True)}

    report = run_acquisition_state_machine(
        venue_id="test_venue",
        season="2026-27",
        config=_config(),
        output_dir=tmp_path,
        hermes_runner=lambda request: {"facts": _facts(coverage={"status": "partial"})},
        pdf_runner=pdf_runner,
        pdf_discoverer=lambda *args, **kwargs: [{"pdf_url": PDF}],
    )

    assert report["hermes_status"] == HERMES_PARTIAL
    assert report["pdf_type"] == PDF_FULL_SOURCE
    assert report["final_status"] == SOURCE_READY
    assert report["merged_events"] == 1
    assert report["merged_programme"] == 1


def test_enrichment_pdf_does_not_upgrade_partial_hermes_without_review(tmp_path: Path):
    def pdf_runner(**kwargs):
        return {"pdf_download": "PASS", "source_type": "ENRICHMENT_SOURCE", "facts": _facts(source_url=PDF, programme=True)}

    report = run_acquisition_state_machine(
        venue_id="test_venue",
        season="2026-27",
        config=_config(),
        output_dir=tmp_path,
        hermes_runner=lambda request: {"facts": _facts(coverage={"status": "partial"})},
        pdf_runner=pdf_runner,
        pdf_discoverer=lambda *args, **kwargs: [{"pdf_url": PDF}],
    )

    assert report["pdf_type"] == PDF_ENRICHMENT_SOURCE
    assert report["final_status"] == REVIEW_REQUIRED
    assert report["production_writes"] == 0


def test_known_pdf_failure_requests_human_pdf_at_standard_path(tmp_path: Path):
    report = run_acquisition_state_machine(
        venue_id="test_venue",
        season="2026-27",
        config=_config(),
        output_dir=tmp_path,
        manual_root=tmp_path / "manual_sources",
        hermes_runner=lambda request: {"error": "HTTP 403"},
        pdf_runner=lambda **kwargs: {"pdf_download": "FAIL", "error": "missing %PDF-"},
        pdf_discoverer=lambda *args, **kwargs: [{"pdf_url": PDF}],
    )

    assert report["hermes_status"] == HERMES_BLOCKED
    assert report["final_status"] == HUMAN_PDF_REQUIRED
    assert str(tmp_path / "manual_sources" / "test_venue" / "2026-27" / "source.pdf") in report["human_action"]
    assert report["production_writes"] == 0


def test_partial_hermes_still_requests_human_pdf_when_known_auto_download_fails(tmp_path: Path):
    report = run_acquisition_state_machine(
        venue_id="test_venue",
        season="2026-27",
        config=_config(),
        output_dir=tmp_path,
        manual_root=tmp_path / "manual_sources",
        hermes_runner=lambda request: {"facts": _facts(coverage={"status": "partial"})},
        pdf_runner=lambda **kwargs: {"pdf_download": "FAIL", "error": "timeout"},
        pdf_discoverer=lambda *args, **kwargs: [{"pdf_url": PDF}],
    )

    assert report["final_status"] == HUMAN_PDF_REQUIRED
    assert "source.pdf" in report["human_action"]


def test_no_known_or_discovered_pdf_is_a_distinct_final_state(tmp_path: Path):
    report = run_acquisition_state_machine(
        venue_id="test_venue",
        season="2026-27",
        config={**_config(), "official_pdf_sources": []},
        output_dir=tmp_path,
        hermes_runner=lambda request: {"error": "timeout"},
        pdf_discoverer=lambda *args, **kwargs: [],
    )

    assert report["final_status"] == BLOCKED
    assert report["pdf_discovered"] == "NO"
    assert report["production_writes"] == 0


def test_malformed_hermes_output_is_preserved_when_pdf_fallback_is_unavailable(tmp_path: Path):
    report = run_acquisition_state_machine(
        venue_id="lauditori_barcelona",
        season="2026-27",
        config={**_config(), "official_pdf_sources": []},
        output_dir=tmp_path,
        hermes_runner=lambda request: {
            "status": HERMES_MALFORMED_OUTPUT,
            "error": "Hermes returned malformed JSON: Expecting value",
            "attempts": 2,
            "raw_output_saved": "YES",
        },
        pdf_discoverer=lambda *args, **kwargs: [],
    )

    assert report["hermes_status"] == HERMES_MALFORMED_OUTPUT
    assert report["hermes_attempts"] == 2
    assert report["raw_output_saved"] == "YES"
    assert report["final_status"] == BLOCKED
    assert report["blocker"] == HERMES_MALFORMED_OUTPUT


def test_state_machine_venue_selection_has_one_shared_source_of_truth():
    assert ACQUISITION_STATE_MACHINE_VENUES == (
        "deutsche_oper_berlin",
        "dutch_national_opera",
        "komische_oper_berlin",
        "theatre_champs_elysees",
        "southbank_centre",
        "tonhalle_zurich",
        "lauditori_barcelona",
    )
    assert UNRESOLVED_ACQUISITION_STATE_MACHINE_VENUES == (
        "deutsche_oper_berlin",
        "dutch_national_opera",
        "theatre_champs_elysees",
        "southbank_centre",
    )
    assert "barbican_centre" not in ACQUISITION_STATE_MACHINE_VENUES
    assert "elbphilharmonie" not in ACQUISITION_STATE_MACHINE_VENUES
