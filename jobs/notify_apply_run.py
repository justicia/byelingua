from __future__ import annotations
import argparse,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from season_ingestion.notifications import github_run_url, notification_summary, render_email, send_resend

p=argparse.ArgumentParser(); p.add_argument('--output-dir',type=Path,required=True); a=p.parse_args(); out=a.output_dir; result=json.loads((out/'apply_result.json').read_text(encoding='utf-8'))
status=result.get('status','APPLY_FAILED'); summary={"venue":result['venue'],"season":result['season'],"mode":"apply","source_capability":"SOURCE_PASS","global_master_preflight":"PASS","counts":{"events_discovered":result.get('runtime_scope',{}).get('events',0),"review_items":0,"writes":result.get('production_writes',0)},"detail_enrichment":{"composer_resolution":{},"work_resolution":{}},"gates":{}}
subject,html_body,text_body=render_email(summary,status=status,run_url=github_run_url()); ns=notification_summary(summary,status=status,run_id=os.getenv('GITHUB_RUN_ID','local'))
try: send_resend(subject,html_body,text_body); ns.update(notification_status='SENT',sent_at=datetime.now(timezone.utc).isoformat())
except Exception as exc: ns.update(notification_status='FAILED',failure_category='NOTIFICATION_PROVIDER_ERROR',failure_reason=str(exc)[:200])
(out/'notification_summary.json').write_text(json.dumps(ns,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(ns,ensure_ascii=False)); raise SystemExit(0)
