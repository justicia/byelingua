from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from season_ingestion.notifications import github_run_url, notification_summary, render_github_summary, write_github_step_summary

p = argparse.ArgumentParser()
p.add_argument('--output-dir', type=Path, required=True)
a = p.parse_args()
out = a.output_dir
result = json.loads((out / 'apply_result.json').read_text(encoding='utf-8'))
status = result.get('status', 'APPLY_FAILED')
summary = {
    "venue": result['venue'],
    "season": result['season'],
    "mode": "apply",
    "source_capability": "SOURCE_PASS",
    "global_master_preflight": "PASS",
    "counts": {
        "events_discovered": result.get('runtime_scope', {}).get('events', 0),
        "review_items": 0,
        "writes": result.get('production_writes', 0),
    },
    "detail_enrichment": {"composer_resolution": {}, "work_resolution": {}},
    "gates": {},
}
failure_reason = result.get('failure_reason')
markdown = render_github_summary(summary, status=status, run_url=github_run_url(), failure_reason=failure_reason)
wrote_summary = write_github_step_summary(markdown)
ns = notification_summary(summary, status=status, notification_status='SUMMARY_WRITTEN' if wrote_summary else 'SUMMARY_UNAVAILABLE', run_id=os.getenv('GITHUB_RUN_ID', 'local'))
ns['summary_written'] = wrote_summary
if failure_reason:
    ns['failure_reason'] = str(failure_reason)[:300]
(out / 'notification_summary.json').write_text(json.dumps(ns, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(ns, ensure_ascii=False))
raise SystemExit(0)
