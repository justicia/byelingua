from season_ingestion.reconciliation import ExistingRecord, reconcile


def existing(**changes):
    row = {"event_id": "e1", "source": "wiener_staatsoper", "source_event_id": "w1", "source_url": "https://x/1", "event_key": "wiener:key1", "title": "Opera", "date": "2027-02-01"}
    row.update(changes)
    return ExistingRecord(**row)


def staging(**changes):
    row = {"source": "wiener_staatsoper", "source_event_id": "w1", "source_url": "https://x/1", "event_key": "wiener:key1", "title": "Opera", "date": "2027-02-01"}
    row.update(changes)
    return row


def test_identity_match_is_safe_update():
    result = reconcile([staging()], [existing()], "wiener_staatsoper")
    assert result["counts"]["source_identity_matches"] == 1
    assert result["counts"]["safe_update"] == 1
    assert result["collision_guard_blocked"] is False


def test_source_url_only_match_is_manual_review_and_blocks():
    result = reconcile([staging(source_event_id="new")], [existing()], "wiener_staatsoper")
    assert result["counts"]["source_url_only_matches"] == 1
    assert result["collision_guard_blocked"] is True


def test_safe_insert_is_always_blocked():
    result = reconcile([staging(source_event_id="new", source_url="https://new")], [existing()], "wiener_staatsoper")
    assert result["counts"]["safe_insert"] == 1
    assert result["collision_guard_blocked"] is True


def test_populated_staging_with_no_existing_season_is_an_explicit_anomaly():
    result = reconcile([staging()], [], "wiener_staatsoper")
    assert result["counts"]["safe_insert"] == 1
    assert result["collision_guard_blocked"] is True
    assert result["anomalies"] == [{
        "type": "existing_season_records_missing",
        "existing_records": 0,
        "staging_records": 1,
        "reason": "refusing to treat a populated staging season as safe inserts",
    }]


def test_missing_event_key_blocks():
    result = reconcile([staging()], [existing(event_key=None)], "wiener_staatsoper")
    assert result["existing_missing_event_key"] == 1
    assert result["collision_guard_blocked"] is True


def test_duplicate_identity_conflicts_block():
    result = reconcile([staging()], [existing(event_id="e1"), existing(event_id="e2")], "wiener_staatsoper")
    assert result["counts"]["one_to_many_conflicts"] == 1
    assert result["collision_guard_blocked"] is True


def test_teatro_real_coverage():
    result = reconcile([], [existing(source="teatro_real", date="2027-02-22"), existing(source="teatro_real", event_id="e2", source_event_id="tr2", date="2027-03-01")], "teatro_real")
    assert result["teatro_real_coverage"]["records_after_2027_02_19"] == 2


def test_apply_guard_blocks_url_collision_and_unmatched_old_record():
    result = reconcile(
        [staging(source_event_id="new", source_url="https://same")],
        [existing(source_event_id="old", source_url="https://same", event_key="old-key")],
        "wiener_staatsoper",
    )
    assert result["collision_guard_blocked"] is True
    assert any(item["type"] == "source_url_identity_collision" for item in result["anomalies"])


def test_wiener_386_identity_matches_preserve_database_event_keys():
    current = [existing(event_id=f"e{i}", source_event_id=f"w{i}", source_url=f"https://x/{i}", event_key=f"db-key-{i}") for i in range(386)]
    staged = [staging(source_event_id=f"w{i}", source_url=f"https://x/{i}", event_key=f"staging-key-{i}") for i in range(386)]
    result = reconcile(staged, current, "wiener_staatsoper")
    assert result["counts"]["source_identity_matches"] == 386
    assert result["counts"]["safe_update"] == 386
    assert result["counts"]["safe_insert"] == 0
    assert result["counts"]["manual_review"] == 0
    assert result["collision_guard_blocked"] is False
