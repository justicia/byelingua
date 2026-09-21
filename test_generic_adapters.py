from __future__ import annotations

import json
from pathlib import Path

from season_ingestion.generic_adapters import (
    build_capability_profile,
    classify_acquisition_status,
    classify_canonical_status,
    classify_enrichment_status,
    expand_multi_date_occurrences,
    select_generic_adapter,
    write_capability_profile,
)
from season_ingestion.registry import load_registry


def test_all_source_families_route_to_shared_adapter_families():
    assert select_generic_adapter("STRUCTURED_API") == "structured_api_adapter"
    assert select_generic_adapter("STRUCTURED_HTML") == "html_event_card_adapter"
    assert select_generic_adapter("PAGINATED_CALENDAR") == "paginated_calendar_adapter"
    assert select_generic_adapter("PRODUCTION_PLUS_OCCURRENCES") == "production_occurrence_adapter"
    assert select_generic_adapter("JS_RENDERED_DISCOVERY") == "discovery_then_deterministic"
    assert select_generic_adapter("PDF_FULL") == "pdf_adapter"
    assert select_generic_adapter("PDF_ENRICHMENT") == "pdf_adapter"
    assert select_generic_adapter("HYBRID") == "multi_source_merge"


def test_representative_registry_profiles_use_shared_source_families():
    venues = load_registry()["venues"]
    expected = {
        "deutsche_oper_berlin": "STRUCTURED_API",
        "tonhalle_zurich": "PAGINATED_CALENDAR",
        "lauditori_barcelona": "STRUCTURED_HTML",
        "komische_oper_berlin": "PDF_FULL",
        "barbican_centre": "STRUCTURED_HTML",
        "southbank_centre": "STRUCTURED_HTML",
    }
    assert {
        venue: build_capability_profile(venue_id=venue, season="2026-27", config=venues[venue])["source_family"]
        for venue in expected
    } == expected


def test_capability_profile_contains_discovery_occurrence_detail_pdf_and_fallback():
    profile = build_capability_profile(
        venue_id="test_venue",
        season="2026-27",
        config={
            "official_source": "https://official.example/season",
            "listing_source": "https://official.example/calendar",
            "official_pdf_sources": ["https://official.example/season.pdf"],
            "detail_path_prefixes": ["/event/"],
            "source_family": "STRUCTURED_API",
            "capabilities": ["PRODUCTION_PLUS_OCCURRENCES", "PDF_ENRICHMENT"],
        },
        discovery={
            "source_discovery": "PASS",
            "discovered_mode": "API",
            "discovered_endpoint": "https://official.example/api?page=1",
        },
        observations={"events": 3},
    )
    assert profile["occurrence_source"]["family"] == "STRUCTURED_API"
    assert profile["discovery"]["status"] == "PASS"
    assert profile["occurrence_source"]["events_observed"] == 3
    assert profile["pdf_source"]["fallback_only"] is True
    assert "PDF_ENRICHMENT" in profile["capabilities"]["families"]
    assert profile["strategy"]["adapter"] == "structured_api_adapter"


def test_profile_separates_occurrence_and_enrichment_source_families():
    profile = build_capability_profile(
        venue_id="barbican_centre",
        season="2026-27",
        config={
            "official_source": "https://official.example/listing",
            "source_family": "HYBRID",
            "occurrence_source_family": "STRUCTURED_HTML",
            "enrichment_source_families": ["PDF_ENRICHMENT"],
            "official_pdf_sources": ["https://official.example/season.pdf"],
            "detail_path_prefixes": ["/event/"],
        },
    )
    assert profile["occurrence_source_family"] == "STRUCTURED_HTML"
    assert profile["enrichment_source_families"] == ["PDF_ENRICHMENT"]
    assert profile["overall_source_family"] == "HYBRID"
    assert profile["occurrence_source"]["requires_browser"] is False
    assert profile["pdf_source"]["available"] is True
    assert profile["strategy"]["occurrence_adapter"] == "html_event_card_adapter"
    assert profile["strategy"]["enrichment_adapters"] == ["pdf_adapter"]


def test_profile_serializes_required_capability_flags():
    profile = build_capability_profile(
        venue_id="venue",
        season="2026-27",
        config={"official_source": "https://official.example", "detail_path_prefixes": ["/event/"]},
    )
    assert profile["capabilities"] == {
        "families": ["STRUCTURED_HTML"],
        "explicit_dates": True,
        "explicit_times": True,
        "programme": True,
        "credits": True,
        "room": False,
        "detail_links": True,
    }


def test_capability_profile_is_written_as_a_run_artifact(tmp_path: Path):
    profile = build_capability_profile(venue_id="venue", season="2026-27", config={"official_source": "https://official.example"})
    path = write_capability_profile(tmp_path, profile)
    assert path.name == "source_capability_profile.json"
    assert json.loads(path.read_text(encoding="utf-8"))["venue_id"] == "venue"


def test_multi_date_expansion_is_explicit_and_does_not_expand_ranges():
    assert [row["date"] for row in expand_multi_date_occurrences("October 2 and 4, 2026")] == ["2026-10-02", "2026-10-04"]
    assert [row["date"] for row in expand_multi_date_occurrences("November 6, 7 and 8, 2026")] == ["2026-11-06", "2026-11-07", "2026-11-08"]
    assert [row["date"] for row in expand_multi_date_occurrences("March 6 and 7, May 8 and 9, 2027")] == ["2027-03-06", "2027-03-07", "2027-05-08", "2027-05-09"]
    assert expand_multi_date_occurrences("October 2-4, 2026") == []


def test_optional_enrichment_does_not_change_occurrence_acquisition_state():
    assert classify_acquisition_status(events=5, source_capability="SOURCE_PASS") == "SOURCE_READY"
    assert classify_enrichment_status(programme=0, credits=0) == "NOT_AVAILABLE"
    assert classify_enrichment_status(programme=3, credits=0) == "PARTIAL"
    assert classify_enrichment_status(programme=3, credits=4) == "COMPLETE"


def test_discovered_source_without_parser_is_adapter_required_not_human_pdf():
    assert classify_acquisition_status(
        events=0,
        source_discovered=True,
        deterministic_attempted=True,
        useful_occurrence_source=True,
        pdf_known=True,
        pdf_download_failed=True,
    ) == "ADAPTER_REQUIRED"
    assert classify_acquisition_status(
        events=0,
        pdf_known=True,
        pdf_download_failed=True,
        useful_occurrence_source=False,
    ) == "HUMAN_PDF_REQUIRED"


def test_canonical_review_is_independent_from_acquisition():
    assert classify_acquisition_status(events=4, source_capability="SOURCE_PASS") == "SOURCE_READY"
    assert classify_canonical_status(global_master="PASS", review_items=1, passed=False) == "REVIEW_REQUIRED"
    assert classify_canonical_status(global_master="PASS", review_items=0, passed=True) == "SAFE"
