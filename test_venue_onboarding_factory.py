import json

import pytest

from season_ingestion.factory import build_batch_approval_manifest, build_batch_summary, classify_summary
from season_ingestion.generic_adapters import select_generic_adapter
from season_ingestion.venue_targets import load_targets, matrix_targets


def test_target_queue_contains_existing_venues_and_wave_one_targets():
    targets = load_targets()
    ids = {target["venue_id"] for target in targets}
    assert {"wiener_staatsoper", "bayerische_staatsoper", "opernhaus_zurich"} <= ids
    assert {
        "wiener_musikverein", "wiener_konzerthaus", "theater_an_der_wien",
        "theatre_champs_elysees", "maison_radio_france", "teatro_de_la_zarzuela",
        "berliner_philharmonie", "staatsoper_unter_den_linden", "deutsche_oper_berlin",
        "komische_oper_berlin", "elbphilharmonie", "hamburgische_staatsoper",
        "tonhalle_zurich", "accademia_nazionale_santa_cecilia", "gran_teatre_del_liceu",
        "palau_de_la_musica_catalana", "lauditori_barcelona", "concertgebouw",
        "dutch_national_opera", "royal_opera_house", "barbican_centre",
        "southbank_centre", "wigmore_hall", "la_monnaie_de_munt", "bozar",
    } <= ids
    assert len(ids) >= 25
    assert "munich_bayerische_staatsoper" not in ids
    assert len(matrix_targets(targets)) == len(ids)


def test_duplicate_canonical_target_is_rejected(tmp_path):
    path = tmp_path / "targets.yml"
    path.write_text("schema_version: venue-onboarding-targets-v1\ntargets:\n  - venue_id: x\n    enabled: true\n  - venue_id: x\n    enabled: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_targets(path)


def test_generic_adapter_selection():
    assert select_generic_adapter("JSON_LD") == "generic_jsonld"
    assert select_generic_adapter("ICS") == "generic_ics"
    assert select_generic_adapter("UNKNOWN") is None


def test_munich_source_blocked_is_terminal_without_writes():
    summary = {"source_capability": "SOURCE_BLOCKED", "global_master_preflight": "FAIL", "counts": {"writes": 0}, "passed": False}
    assert classify_summary(summary) == "SOURCE_BLOCKED"


def test_zurich_ready_for_approval_is_idempotent_classification():
    summary = {"source_capability": "SOURCE_PASS", "global_master_preflight": "PASS", "counts": {"writes": 0}, "passed": True}
    assert classify_summary(summary) == "READY_FOR_APPROVAL"
    assert classify_summary(summary) == "READY_FOR_APPROVAL"


def test_mixed_batch_isolated_and_manifest_deterministic():
    results = [
        {"venue_id": "opernhaus_zurich", "status": "READY_FOR_APPROVAL", "production_writes": 0, "summary": {"source_capability": "SOURCE_PASS", "counts": {"events_discovered": 196, "writes": 0}}},
        {"venue_id": "bayerische_staatsoper", "status": "SOURCE_BLOCKED", "production_writes": 0, "summary": {"source_capability": "SOURCE_BLOCKED", "counts": {"events_discovered": 0, "writes": 0}}},
    ]
    summary = build_batch_summary(results, season="2026-27", batch_run_id="42", git_commit="abc")
    assert summary["batch_status"] == "COMPLETED_WITH_BLOCKED_TARGETS"
    assert summary["ready_for_approval"] == 1 and summary["source_blocked"] == 1
    manifest_a = build_batch_approval_manifest(summary)
    manifest_b = build_batch_approval_manifest(summary)
    assert json.dumps(manifest_a, sort_keys=True) == json.dumps(manifest_b, sort_keys=True)
