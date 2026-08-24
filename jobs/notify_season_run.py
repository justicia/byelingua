from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from season_ingestion.notifications import build_approval_manifest, classify_dry_run, github_run_url, notification_summary, render_email, send_resend

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--output-dir',type=Path,required=True); a=p.parse_args()
    out=a.output_dir; out.mkdir(parents=True, exist_ok=True)
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8')) if (out/'summary.json').exists() else {"venue":os.getenv("INPUT_VENUE","unknown"),"season":os.getenv("INPUT_SEASON","unknown"),"mode":os.getenv("INPUT_MODE","dry-run"),"source_capability":"SOURCE_UNSUPPORTED","global_master_preflight":"FAIL","counts":{"events_discovered":0,"review_items":0,"writes":0},"gates":{}}
    status, eligible, _=classify_dry_run(summary)
    manifest=None
    if eligible:
        manifest=build_approval_manifest(summary,out/'final_staging.json',run_id=os.getenv('GITHUB_RUN_ID','local'),commit=os.getenv('GITHUB_SHA','unknown'))
        (out/'approval_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); status='READY_FOR_APPROVAL'
    subject, html_body, text_body=render_email(summary,status=status,manifest=manifest,run_url=github_run_url())
    ns=notification_summary(summary,status=status,run_id=os.getenv('GITHUB_RUN_ID','local'))
    try:
        send_resend(subject,html_body,text_body); ns.update(notification_status='SENT',sent_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        ns.update(notification_status='FAILED',failure_category='NOTIFICATION_PROVIDER_ERROR',failure_reason=str(exc)[:200])
    (out/'notification_summary.json').write_text(json.dumps(ns,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(ns,ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
