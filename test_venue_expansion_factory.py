from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jobs import run_venue_expansion_factory as factory
from season_ingestion.production_graph import ProductionGraphRPCError


def _write_publish_artifacts(root: Path, venue_id: str, *, event_key: str, eligible: bool = True) -> None:
    directory = root / venue_id
    directory.mkdir(parents=True)
    final = directory / "final_staging.json"
    final.write_text(json.dumps({"events": [{"event_key": event_key}]}) + "\n", encoding="utf-8")
    graph = {
        "events": [{"event_key": event_key}],
        "composers": [],
        "works": [],
        "relationships": [],
        "event_credits": [],
    }
    (directory / "production_graph_staging.json").write_text(json.dumps(graph) + "\n", encoding="utf-8")
    manifest = {
        "venue": venue_id,
        "season": "2026-27",
        "dry_run_id": f"run-{venue_id}",
        "eligible_for_apply": eligible,
        "final_staging_hash": hashlib.sha256(final.read_bytes()).hexdigest(),
        "safe_event_count": 1,
        "safe_composer_count": 0,
        "safe_work_count": 0,
        "safe_relationship_count": 0,
    }
    (directory / "approval_manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")


def _result(venue_id: str, status: str, *, events: int = 1, review_items: int = 0) -> dict:
    return {
        "venue_id": venue_id,
        "season": "2026-27",
        "status": status,
        "production_writes": 0,
        "summary": {
            "venue": venue_id,
            "season": "2026-27",
            "source_capability": "SOURCE_PASS",
            "global_master_preflight": "PASS",
            "counts": {"events_discovered": events, "review_items": review_items, "writes": 0},
            "detail_enrichment": {"programme_items": 0, "credits_total": 0},
            "capability_profile": {
                "discovery": {"discovered_by": "source_discovery"},
                "occurrence_source": {"source_family": "STRUCTURED_HTML"},
                "detail_source": {"source_family": "DETAIL_HTML"},
            },
        },
    }


def test_parser_uses_canonical_target_selection_and_operational_flags():
    args = factory.build_parser().parse_args([
        "--season", "2026-27", "--scope", "selected", "--venue-ids", "a,b",
        "--target-file", "custom.yml", "--resume", "--publish",
    ])
    assert args.scope == "selected"
    assert factory.parse_venue_ids(args.venue_ids) == ["a", "b"]
    assert args.target_file == Path("custom.yml")
    assert args.resume is True and args.publish is True


def test_factory_delegates_acquisition_to_existing_runner_and_target_file(tmp_path, monkeypatch):
    calls = {}

    def fake_acquisition(**kwargs):
        calls.update(kwargs)
        return {"season": "2026-27", "venues": [], "production_writes": 0}

    monkeypatch.setattr(factory.run_europe_auto_factory, "run_factory", fake_acquisition)
    result = factory.run_factory(
        season="2026-27",
        scope="pending",
        selected=[],
        output_root=tmp_path / "out",
        state_path=tmp_path / "state.json",
        target_path=tmp_path / "targets.yml",
        resume=True,
        publish=False,
    )
    assert calls["target_path"] == tmp_path / "targets.yml"
    assert calls["resume_root"] == tmp_path / "out"
    assert result["production_writes"] == 0


def test_mixed_batch_isolated_and_safe_review_facts_can_publish(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "check_required_credentials", lambda mode: {"configured": True, "missing": []})
    _write_publish_artifacts(tmp_path, "ready", event_key="ready-event")
    _write_publish_artifacts(tmp_path, "review", event_key="review-event")
    results = [
        _result("ready", "READY_FOR_APPROVAL"),
        _result("review", "REVIEW_REQUIRED", review_items=1),
        _result("blocked", "FAILED", events=0),
    ]
    applied = []

    def apply(payload):
        applied.append(payload["events"][0]["event_key"])
        return {"ok": True}

    batch = {"season": "2026-27", "venues": results, "production_writes": 0}
    output = factory._publish_batch(
        batch,
        output_root=tmp_path,
        publish=True,
        resume=False,
        apply=apply,
        smoke=lambda result, **_: {"status": "PASS"},
    )
    assert applied == ["ready-event", "review-event"]
    assert output["published"] == 1
    assert output["partial_published"] == 1
    assert output["blocked"] == 1
    assert output["failure_isolation"] == "PASS"
    assert output["publish_health"] == "PASS"
    assert output["idempotency"] == "NOT_VERIFIED"
    assert output["venues"][1]["factory_report"]["review_items"] == 1


def test_partial_valid_occurrences_are_materialized_through_shared_graph_path(tmp_path, monkeypatch):
    result = _result("partial", "SOURCE_PARTIAL", events=2)
    directory = tmp_path / "partial"
    directory.mkdir()
    (directory / "final_staging.json").write_text(json.dumps({"events": [{"event_key": "partial-event"}]}) + "\n", encoding="utf-8")
    (directory / "snapshot.json").write_text("{}", encoding="utf-8")
    (directory / "source_audit.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(factory, "assess_release_candidate", lambda **_: {"events_rejected": 0, "release_status": "REVIEW_RELEASE_CANDIDATE"})

    def materialize(directory, summary, *, venue_id, allow_partial=False):
        assert allow_partial is True
        (directory / "production_graph_staging.json").write_text(json.dumps({"events": [{"event_key": "partial-event"}]}) + "\n", encoding="utf-8")

    monkeypatch.setattr(factory, "_write_production_graph_staging", materialize)
    monkeypatch.setattr(factory, "check_required_credentials", lambda mode: {"configured": True, "missing": []})
    applied = []
    publish_result = factory._publish_one(
        result,
        output_root=tmp_path,
        publish=True,
        apply=lambda payload: applied.append(payload) or {"ok": True},
    )
    assert publish_result["status"] == "APPLY_SUCCESS"
    assert publish_result["partial"] is True
    assert applied and (directory / "materialization_report.json").exists()


def test_no_publish_never_calls_atomic_writer(tmp_path, monkeypatch):
    _write_publish_artifacts(tmp_path, "ready", event_key="ready-event")
    called = []
    result = factory._publish_one(
        _result("ready", "READY_FOR_APPROVAL"),
        output_root=tmp_path,
        publish=False,
        apply=lambda payload: called.append(payload),
    )
    assert result["status"] == "READY_TO_PUBLISH"
    assert result["production_writes"] == 0
    assert called == []


def test_resume_skips_already_applied_venue_and_is_idempotent(tmp_path):
    _write_publish_artifacts(tmp_path, "ready", event_key="ready-event")
    prior = {
        "schema_version": factory.PUBLISH_PROGRESS_SCHEMA_VERSION,
        "season": "2026-27",
        "venues": {"ready": {"production_status": "APPLY_SUCCESS", "production_writes": 1, "frontend_status": "PASS"}},
    }
    (tmp_path / "factory_publish_progress.json").write_text(json.dumps(prior), encoding="utf-8")
    called = []
    batch = {"season": "2026-27", "venues": [_result("ready", "READY_FOR_APPROVAL")], "production_writes": 0}
    output = factory._publish_batch(
        batch,
        output_root=tmp_path,
        publish=True,
        resume=True,
        apply=lambda payload: called.append(payload),
        smoke=lambda result, **_: {"status": "PASS"},
    )
    assert called == []
    assert output["published"] == 1
    assert output["venues"][0]["factory_report"]["production_status"] == "APPLY_SUCCESS"


def test_frontend_smoke_checks_search_and_detail_without_writes(tmp_path, monkeypatch):
    _write_publish_artifacts(tmp_path, "ready", event_key="ready-event")
    payloads = []

    class Response:
        def __init__(self, body):
            self.status = 200
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(self.body).encode("utf-8")

    def sender(request, timeout=0):
        payloads.append(json.loads(request.data.decode("utf-8")))
        if payloads[-1]["action"] == "schedule_events":
            return Response({"events": [{"event_id": "ready-event"}]})
        return Response({"event": {"event_id": "ready-event"}})

    monkeypatch.setenv("BYELINGUA_FRONTEND_API_URL", "https://frontend.example/api")
    result = factory._frontend_smoke(_result("ready", "READY_FOR_APPROVAL"), output_root=tmp_path, sender=sender)
    assert result == {"status": "PASS", "search": "PASS", "detail": "PASS"}
    assert [payload["action"] for payload in payloads] == ["schedule_events", "schedule_event_detail"]


def test_gap_report_uses_explicit_recovery_types_and_source_layers():
    result = _result("gap", "REVIEW_REQUIRED", events=2)
    report = factory._operational_venue_report(
        result,
        output_root=Path("."),
        publish_result={"status": "NOT_PUBLISHABLE", "production_writes": 0},
        frontend_result={"status": "NOT_RUN"},
    )
    assert "PROGRAMME_EXTRACTION_FAILED" in report["gap_types"]
    assert "DETAIL_SOURCE_MISSING" in report["recovery_routes"]
    assert report["occurrence_source"] == "STRUCTURED_HTML"
    assert report["enrichment_sources"] == ["DETAIL_HTML"]
    assert report["final_status"] == "REVIEW_ONLY"


def test_operational_report_separates_programme_content_from_work_resolution():
    result = _result("metrics", "REVIEW_REQUIRED", events=4)
    result["summary"]["detail_enrichment"].update({
        "programme_items": 3,
        "work_resolution": {"existing_exact": 1, "review": 2, "new_candidate": 0, "not_run": 0},
    })
    result["summary"]["content_recovery"] = {
        "events": [
            {"expected_work": True, "programme_status": "RESOLVED"},
            {"expected_work": True, "programme_status": "RESOLVED"},
            {"expected_work": True, "programme_status": "PROGRAMME_SOURCE_NOT_PUBLISHED"},
            {"expected_work": False, "programme_status": "PROGRAMME_RESOLUTION_FAILED"},
        ]
    }
    report = factory._operational_venue_report(
        result,
        output_root=Path("."),
        publish_result={"status": "NOT_PUBLISHABLE", "production_writes": 0},
        frontend_result={"status": "NOT_RUN"},
    )
    assert report["work_global_resolution_resolved"] == 1
    assert report["work_global_resolution_review"] == 2
    assert report["programme_content_resolved"] == 3
    assert report["programme_content_terminal_unresolved"] == 1
    assert report["programme_resolved"] == 3
    assert report["programme_failed"] == 1


def test_rpc_response_body_is_persisted_in_isolated_publish_blocker(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "check_required_credentials", lambda mode: {"configured": True, "missing": []})
    _write_publish_artifacts(tmp_path, "rpc-failed", event_key="rpc-event")

    result = factory._publish_one(
        _result("rpc-failed", "READY_FOR_APPROVAL"),
        output_root=tmp_path,
        publish=True,
        apply=lambda payload: (_ for _ in ()).throw(ProductionGraphRPCError(400, "column does not exist")),
    )
    assert result["status"] == "APPLY_FAILED"
    assert "column does not exist" in result["blocker"]
    assert "HTTP 400" in result["blocker"]
    saved = json.loads((tmp_path / "rpc-failed" / "apply_result.json").read_text(encoding="utf-8"))
    assert saved["apply_error"]["http_status"] == 400
    assert "column does not exist" in saved["apply_error"]["message"]


def _idempotent_payload():
    return {
        "source": "source-a",
        "events": [{"event_key": "event-a", "source": "source-a", "source_event_id": "source-event-a"}],
        "relationships": [{"event_key": "event-a", "work_id": "work-a", "order": 1}],
        "event_credits": [{"event_key": "event-a", "artist_id": "artist-a", "role": "conductor", "character_id": None}],
    }


def test_run_idempotency_is_scoped_and_excludes_historical_rows():
    def reader(table, _select, _filters):
        if table == "events":
            return [{"id": "event-db-a", "event_key": "event-a"}]
        if table == "event_sources":
            return [{"event_id": "event-db-a", "source": "source-a", "source_event_id": "source-event-a"}]
        if table == "event_programme":
            return [{"event_id": "event-db-a", "work_id": "work-a", "order": 1}]
        if table == "event_credits":
            return [
                {"event_id": "event-db-a", "artist_id": "artist-a", "role": "conductor", "character_id": None},
                {"event_id": "historical-event", "artist_id": "historical-artist", "role": "conductor", "character_id": None},
                {"event_id": "historical-event", "artist_id": "historical-artist", "role": "conductor", "character_id": None},
            ]
        return []

    result = factory.verify_run_idempotency(
        [_idempotent_payload()],
        row_reader=reader,
        first_apply={"events": 183, "event_work": 88, "credits": 991, "sources": 183},
    )
    assert result["idempotency_scope"] == "current-run"
    assert result["verification_phase"] == "post-apply-replay"
    assert result["historical_duplicates_excluded"] is True
    assert result["idempotency_verified"] is True
    assert result["payload_events"] == 1
    assert result["payload_event_work"] == 1
    assert result["payload_credits"] == 1
    assert result["payload_sources"] == 1
    assert "first_apply_new_events" not in result
    assert "first_apply_new_event_work" not in result
    assert "first_apply_new_credits" not in result
    assert "first_apply_new_sources" not in result
    assert result["replay_new_events"] == 0
    assert result["replay_new_event_work"] == 0
    assert result["replay_new_credits"] == 0
    assert result["replay_new_sources"] == 0
    assert result["new_events"] == 0
    assert result["new_event_work_relationships"] == 0
    assert result["new_credits"] == 0
    assert result["run_duplicate_credit_identity"] == 0


def test_run_idempotency_detects_current_run_duplicate_credit():
    payload = _idempotent_payload()
    payload["event_credits"].append(dict(payload["event_credits"][0]))
    result = factory.verify_run_idempotency([payload], row_reader=lambda *_: [])
    assert result["idempotency_verified"] is False
    assert result["run_duplicate_credit_identity"] == 1
    assert result["historical_duplicates_excluded"] is True


def test_run_idempotency_uses_credit_character_text_identity():
    payload = _idempotent_payload()
    payload["event_credits"][0]["character"] = "Leila"

    def reader(table, _select, _filters):
        if table == "events":
            return [{"id": "event-db-a", "event_key": "event-a"}]
        if table == "event_sources":
            return [{"event_id": "event-db-a", "source": "source-a", "source_event_id": "source-event-a"}]
        if table == "event_programme":
            return [{"event_id": "event-db-a", "work_id": "work-a", "order": 1}]
        if table == "event_credits":
            return [{
                "event_id": "event-db-a",
                "artist_id": "artist-a",
                "role": "conductor",
                "character_id": "character-db-a",
                "character": "Leila",
            }]
        return []

    result = factory.verify_run_idempotency([payload], row_reader=reader)
    assert result["replay_new_credits"] == 0
    assert result["idempotency_verified"] is True


def test_run_idempotency_reports_one_missing_identity_without_writing():
    payload = {
        "source": "source-a",
        "events": [{"event_key": "event-missing"}],
        "relationships": [],
        "event_credits": [],
    }
    calls = []

    def reader(table, _select, _filters):
        calls.append(table)
        return []

    result = factory.verify_run_idempotency([payload], row_reader=reader)
    assert result["payload_events"] == 1
    assert result["replay_new_events"] == 1
    assert result["replay_new_event_work"] == 0
    assert result["replay_new_credits"] == 0
    assert result["replay_new_sources"] == 0
    assert result["idempotency_verified"] is False
    assert calls == ["events"]


def test_run_idempotency_result_is_propagated_to_batch_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "check_required_credentials", lambda mode: {"configured": True, "missing": []})
    _write_publish_artifacts(tmp_path, "ready", event_key="ready-event")
    result = factory._publish_batch(
        {"season": "2026-27", "venues": [_result("ready", "READY_FOR_APPROVAL")], "production_writes": 0},
        output_root=tmp_path,
        publish=True,
        resume=False,
        apply=lambda payload: {"ok": True},
        smoke=lambda result, **_: {"status": "PASS"},
        idempotency_verify=lambda payloads: {
            "idempotency_scope": "current-run",
            "historical_duplicates_excluded": True,
            "run_duplicate_event_identity": 0,
            "run_duplicate_event_work": 0,
            "run_duplicate_credit_identity": 0,
            "run_duplicate_source_identity": 0,
            "new_events": 0,
            "new_event_work_relationships": 0,
            "new_credits": 0,
            "new_source_rows": 0,
            "idempotency_verified": True,
        },
    )
    assert result["idempotency"] == "PASS"
    assert result["idempotency_verified"] is True
    assert result["run_duplicate_credit_identity"] == 0
    operational = json.loads((tmp_path / "factory_operational_report.json").read_text(encoding="utf-8"))
    assert operational["idempotency_verified"] is True


def test_batch_summary_reports_payload_counts_separately_from_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "check_required_credentials", lambda mode: {"configured": True, "missing": []})
    _write_publish_artifacts(tmp_path, "ready", event_key="ready-event")
    calls = []

    def verifier(payloads):
        calls.append(payloads)
        return {
            "idempotency_scope": "current-run",
            "verification_phase": "post-apply-replay",
            "historical_duplicates_excluded": True,
            "run_duplicate_event_identity": 0,
            "run_duplicate_event_work": 0,
            "run_duplicate_credit_identity": 0,
            "run_duplicate_source_identity": 0,
            "new_events": 0,
            "new_event_work_relationships": 0,
            "new_credits": 0,
            "new_source_rows": 0,
            "idempotency_verified": True,
        }

    result = factory._publish_batch(
        {"season": "2026-27", "venues": [_result("ready", "READY_FOR_APPROVAL")], "production_writes": 0},
        output_root=tmp_path,
        publish=True,
        resume=False,
        apply=lambda payload: {"ok": True},
        smoke=lambda result, **_: {"status": "PASS"},
        idempotency_verify=verifier,
    )
    assert len(calls) == 1
    assert result["payload_events"] == 1
    assert result["payload_event_work"] == 0
    assert result["payload_credits"] == 0
    assert result["payload_sources"] == 0
    assert "first_apply_new_events" not in result
    assert result["replay_new_events"] == 0
    assert result["replay_new_event_work"] == 0
    assert result["replay_new_credits"] == 0
    assert result["replay_new_sources"] == 0
    assert result["idempotency"] == "PASS"
    assert result["idempotency_verified"] is True
