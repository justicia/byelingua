from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from season_ingestion.notifications import build_approval_manifest, classify_dry_run, github_run_url, notification_summary, render_github_summary, write_github_step_summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / 'summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.exists() else {
        "venue": os.getenv("INPUT_VENUE", "unknown"),
        "season": os.getenv("INPUT_SEASON", "unknown"),
        "mode": os.getenv("INPUT_MODE", "dry-run"),
        "scope": os.getenv("INPUT_SCOPE", "full-season"),
        "source_capability": "SOURCE_UNSUPPORTED",
        "global_master_preflight": "FAIL",
        "counts": {"events_discovered": 0, "review_items": 0, "writes": 0},
        "gates": {},
    }
    status, eligible, blockers = classify_dry_run(summary)
    manifest = None
    if eligible:
        manifest = build_approval_manifest(
            summary,
            out / 'final_staging.json',
            run_id=os.getenv('GITHUB_RUN_ID', 'local'),
            commit=os.getenv('GITHUB_SHA', 'unknown'),
        )
        (out / 'approval_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        status = 'READY_FOR_APPROVAL'
    failure_reason = ', '.join(blockers) if blockers else None
    markdown = render_github_summary(summary, status=status, manifest=manifest, run_url=github_run_url(), failure_reason=failure_reason)
    wrote_summary = write_github_step_summary(markdown)
    ns = notification_summary(summary, status=status, notification_status='SUMMARY_WRITTEN' if wrote_summary else 'SUMMARY_UNAVAILABLE', run_id=os.getenv('GITHUB_RUN_ID', 'local'))
    ns['summary_written'] = wrote_summary
    if failure_reason:
        ns['failure_reason'] = failure_reason
    (out / 'notification_summary.json').write_text(json.dumps(ns, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(ns, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
