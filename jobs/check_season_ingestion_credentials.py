from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from season_ingestion.credentials import check_required_credentials

p=argparse.ArgumentParser(); p.add_argument('--mode',choices=('dry-run','notification','apply'),required=True); a=p.parse_args(); result=check_required_credentials(a.mode)
print('CREDENTIAL_PREFLIGHT=' + ('PASS' if result['configured'] else 'FAIL'))
if result['missing']: print('MISSING=' + ','.join(result['missing']))
raise SystemExit(0 if result['configured'] else 1)
