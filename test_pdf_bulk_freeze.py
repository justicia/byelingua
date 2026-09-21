from pathlib import Path

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - keeps the smoke runnable in the bundled runtime
    from contextlib import contextmanager

    class _PytestFallback:
        @staticmethod
        @contextmanager
        def raises(expected):
            try:
                yield
            except expected:
                return
            raise AssertionError(f"expected {expected.__name__}")

    pytest = _PytestFallback()

from season_ingestion.hard_freeze import (
    HardFreezeViolation,
    append_only_missing,
    assert_frontend_unchanged,
    build_batch_manifest,
    full_ingestion_pass,
    validate_batch_manifest,
    validate_credit_semantics,
    validate_mutation_scope,
)


def test_duplicate_pdf_manifest_is_stable_and_scoped():
    manifest = build_batch_manifest(
        run_id="run-1",
        pdf_files=["a.pdf"],
        pdf_hashes={"a.pdf": "a" * 64},
        target_venues=["venue-a"],
        target_event_ids=["event-a"],
        duplicate_pdfs_skipped=1,
    )
    validate_batch_manifest(manifest)
    assert manifest["duplicate_pdfs_skipped"] == 1
    assert manifest["update_existing_accepted_facts"] == 0
    assert manifest["delete_existing_accepted_facts"] == 0


def test_cross_pdf_programme_and_credit_deduplication_is_append_only():
    existing_programme = [{"event_key": "e", "work_id": "w"}]
    incoming_programme = [{"event_key": "e", "work_id": "w"}, {"event_key": "e", "work_id": "w2"}]
    assert append_only_missing(existing_programme, incoming_programme, kind="programme") == [{"event_key": "e", "work_id": "w2"}]
    existing_credit = [{"event_key": "e", "artist_id": "a", "role": "singer", "character": "X", "instrument": ""}]
    incoming_credit = existing_credit + [{"event_key": "e", "artist_id": "a", "role": "singer", "character": "Y", "instrument": ""}]
    assert len(append_only_missing(existing_credit, incoming_credit, kind="credit")) == 1


def test_composer_metadata_cannot_become_cast():
    with pytest.raises(HardFreezeViolation):
        validate_credit_semantics([{"composer": "Richard Wagner", "title": "Tristan"}], [{"artist_name": "Richard Wagner", "role": "singer"}])


def test_opera_character_and_artistic_team_are_separate():
    validate_credit_semantics(
        [{"composer": "Giuseppe Verdi", "title": "Falstaff"}],
        [
            {"artist_name": "Artist", "role": "singer", "character": "Falstaff"},
            {"artist_name": "Conductor", "role": "conductor"},
        ],
    )
    with pytest.raises(HardFreezeViolation):
        validate_credit_semantics([], [{"artist_name": "Director", "role": "director", "character": "Falstaff"}])


def test_concerto_instrument_is_preserved():
    validate_credit_semantics([], [{"artist_name": "Soloist", "role": "soloist", "source_instrument": "violin", "instrument": "violin"}])
    with pytest.raises(HardFreezeViolation):
        validate_credit_semantics([], [{"artist_name": "Soloist", "role": "soloist", "source_instrument": "violin"}])


def test_cross_venue_scope_is_hard_fail():
    with pytest.raises(HardFreezeViolation):
        validate_mutation_scope([{"venue_id": "other", "event_id": "e2"}], target_venues=["target"], target_event_ids=["e1"])


def test_accepted_data_cannot_be_overwritten_or_deleted():
    manifest = build_batch_manifest(run_id="run", pdf_files=[], pdf_hashes={}, target_venues=["v"], target_event_ids=["e"])
    manifest["update_existing_accepted_facts"] = 1
    with pytest.raises(HardFreezeViolation):
        validate_batch_manifest(manifest)


def test_frontend_guard_detects_ingestion_changes():
    before = {"schedule.html": "old"}
    assert_frontend_unchanged(before, {"schedule.html": "old"})
    with pytest.raises(HardFreezeViolation):
        assert_frontend_unchanged(before, {"schedule.html": "new"})


def test_full_ingestion_pass_allows_legitimate_resolution_failures():
    audit = {
        "dated_blocks_found": 2,
        "dated_blocks_processed": 2,
        "programme_items_in_pdf": 3,
        "programme_status": {"ALREADY_EXISTS": 2, "RESOLUTION_FAILED": 1},
        "credits_in_pdf": 1,
        "credit_status": {"WRITTEN": 1},
        "characters_in_pdf": 1,
        "character_status": {"UNMATCHED_EVENT": 1},
        "unaccounted_programme_items": 0,
        "unaccounted_credits": 0,
        "unaccounted_characters": 0,
    }
    assert full_ingestion_pass(audit)


def test_full_ingestion_fails_only_when_unaccounted():
    audit = {
        "dated_blocks_found": 1,
        "dated_blocks_processed": 1,
        "programme_items_in_pdf": 1,
        "programme_status": {"RESOLUTION_FAILED": 1},
        "credits_in_pdf": 0,
        "credit_status": {},
        "characters_in_pdf": 0,
        "character_status": {},
        "unaccounted_programme_items": 1,
        "unaccounted_credits": 0,
        "unaccounted_characters": 0,
    }
    assert not full_ingestion_pass(audit)


def test_accepted_frontend_history_marker_exists():
    marker = Path(__file__).parent / "artifacts" / "pdf-bulk-ingestion" / "frontend-freeze.json"
    assert marker.exists()
    assert "b2123ce993f6a0ee6bad5ab590b2c649fee2a1bf" in marker.read_text(encoding="utf-8")
