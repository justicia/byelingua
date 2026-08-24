from __future__ import annotations
import hashlib, json
from pathlib import Path

class ApprovalMismatch(RuntimeError): pass

def validate_approval(manifest_path: Path, staging_path: Path, *, approved_run_id: str, venue: str, season: str, commit: str | None = None) -> dict:
    if not approved_run_id:
        raise ApprovalMismatch('APPROVAL_MISMATCH: approved_run_id is required')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if not manifest.get('eligible_for_apply') or str(manifest.get('dry_run_id')) != str(approved_run_id):
        raise ApprovalMismatch('APPROVAL_MISMATCH: manifest is not eligible or run id differs')
    if manifest.get('venue') != venue or manifest.get('season') != season:
        raise ApprovalMismatch('APPROVAL_MISMATCH: venue or season differs')
    if commit and manifest.get('git_commit') != commit:
        raise ApprovalMismatch('APPROVAL_MISMATCH: approved commit differs')
    if hashlib.sha256(staging_path.read_bytes()).hexdigest() != manifest.get('final_staging_hash'):
        raise ApprovalMismatch('APPROVAL_MISMATCH: final staging hash differs')
    return manifest
