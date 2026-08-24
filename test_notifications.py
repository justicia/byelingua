import os
from pathlib import Path
from season_ingestion.notifications import build_approval_manifest, classify_dry_run, render_email, render_github_summary, write_github_step_summary
from season_ingestion.approval import ApprovalMismatch, validate_write_scope


def summary(source="SOURCE_PASS"):
    return {"venue":"Opernhaus Zürich","season":"2026-27","mode":"dry-run","source_capability":source,"global_master_preflight":"PASS","counts":{"events_discovered":196,"review_items":59,"writes":0},"detail_enrichment":{"composer_resolution":{"review":0},"work_resolution":{"review":59}},"gates":{"duplicate_event_identity":True,"untraceable":True,"source_order_missing":True}}


def test_ready_for_approval_with_review_backlog(tmp_path):
    s=summary(); assert classify_dry_run(s)==("DRY_RUN_SUCCESS",True,[])
    p=tmp_path/'final_staging.json'; p.write_text('{"events":[]}',encoding='utf-8')
    m=build_approval_manifest(s,p,run_id='123',commit='abc')
    assert m['eligible_for_apply'] and m['final_staging_hash']
    assert 'READY_FOR_APPROVAL' in render_email(s,status='READY_FOR_APPROVAL',manifest=m)[2]
    md=render_github_summary(s,status='READY_FOR_APPROVAL',manifest=m)
    assert 'Opernhaus Zürich' in md
    assert 'READY_FOR_APPROVAL' in md
    assert 'Production writes:** 0' in md
    assert 'Review items:** 59' in md


def test_github_step_summary_written(tmp_path, monkeypatch):
    target=tmp_path/'step-summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(target))
    assert write_github_step_summary('# Status\n') is True
    assert target.read_text(encoding='utf-8') == '# Status\n'


def test_github_step_summary_optional_without_actions_env(monkeypatch):
    monkeypatch.delenv('GITHUB_STEP_SUMMARY',raising=False)
    assert write_github_step_summary('# Status\n') is False


def test_source_blocked_not_eligible():
    assert classify_dry_run(summary('SOURCE_BLOCKED'))[1] is False


def test_manifest_hash_is_stable(tmp_path):
    p=tmp_path/'final_staging.json'; p.write_text('{"a":1}',encoding='utf-8')
    s=summary(); a=build_approval_manifest(s,p,run_id='1',commit='c',created_at='t'); b=build_approval_manifest(s,p,run_id='1',commit='c',created_at='t')
    assert a['final_staging_hash']==b['final_staging_hash']


def test_runtime_write_scope_cannot_exceed_approval():
    try: validate_write_scope({'safe_event_count': 1}, {'events': 2})
    except ApprovalMismatch: return
    raise AssertionError('scope mismatch was not rejected')
