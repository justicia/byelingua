from __future__ import annotations
import argparse
from pathlib import Path
from season_ingestion.approval import validate_approval

p=argparse.ArgumentParser()
p.add_argument('--manifest',type=Path,required=True)
p.add_argument('--staging',type=Path,required=True)
p.add_argument('--approved-run-id',required=True)
p.add_argument('--venue',required=True)
p.add_argument('--season',required=True)
p.add_argument('--commit')
a=p.parse_args()
validate_approval(a.manifest,a.staging,approved_run_id=a.approved_run_id,venue=a.venue,season=a.season,commit=a.commit)
print('APPROVAL_VALIDATION=PASS')
