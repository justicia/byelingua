from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from season_ingestion.approval import ApprovalMismatch, validate_approval, validate_write_scope
from season_ingestion.production_graph import apply_graph
from season_ingestion.credentials import check_required_credentials

def write_result(out: Path, result: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out/'apply_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary={"venue":result["venue"],"season":result["season"],"mode":"apply","apply_status":result["status"],"counts":{"writes":result.get("production_writes",0)},"apply_result":result}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--approved-dir',type=Path,required=True); p.add_argument('--output-dir',type=Path,required=True); p.add_argument('--approved-run-id',required=True); p.add_argument('--venue',required=True); p.add_argument('--season',required=True); p.add_argument('--commit')
    a=p.parse_args(); out=a.output_dir; base={"approved_run_id":a.approved_run_id,"apply_run_id":os.getenv('GITHUB_RUN_ID','local'),"venue":a.venue,"season":a.season,"status":"APPLY_FAILED","approval_status":"NOT_STARTED","transaction":"NOT_STARTED","approved_scope":{},"runtime_scope":{},"production_result":{},"verification":{},"production_writes":0}
    try:
        manifest=validate_approval(a.approved_dir/'approval_manifest.json',a.approved_dir/'final_staging.json',approved_run_id=a.approved_run_id,venue=a.venue,season=a.season,commit=None)
        base["approval_status"]="VALID"
        credential_status=check_required_credentials("apply")
        base["credentials"]={"apply": "PASS" if credential_status["configured"] else "NOT_CONFIGURED"}
        if not credential_status["configured"]: raise ApprovalMismatch('WRITER_CREDENTIAL_MISSING: ' + ','.join(credential_status['missing']))
        graph_path=a.approved_dir/'production_graph_staging.json'
        if not graph_path.exists(): raise ApprovalMismatch('APPROVAL_ARTIFACT_NOT_FOUND: production_graph_staging.json')
        payload=json.loads(graph_path.read_text(encoding='utf-8'))
        runtime={"events":len(payload.get('events',[])),"composers":len(payload.get('composers',[])),"works":len(payload.get('works',[])),"relationships":len(payload.get('relationships',[]))}
        approved={"events":manifest.get('safe_event_count',0),"composers":manifest.get('safe_composer_count',0),"works":manifest.get('safe_work_count',0),"relationships":manifest.get('safe_relationship_count',0)}
        base.update(approved_scope=approved,runtime_scope=runtime)
        validate_write_scope(manifest,runtime)
        response=apply_graph(payload)
        base.update(status='APPLY_SUCCESS',transaction='COMMITTED',production_result=response,production_writes=sum(runtime.values()),verification={"status":"PASS"})
    except ApprovalMismatch as exc:
        base.update(status='APPLY_FAILED',failure_category=str(exc).split(':',1)[0],failure_reason=str(exc),production_writes=0)
    except Exception as exc:
        base.update(status='APPLY_ROLLED_BACK',transaction='ROLLED_BACK',failure_category='PRODUCTION_GRAPH_ERROR',failure_reason=str(exc)[:300],production_writes=0)
    write_result(out,base); print(json.dumps(base,ensure_ascii=False)); return 0 if base['status']=='APPLY_SUCCESS' else 2
if __name__=='__main__': raise SystemExit(main())
