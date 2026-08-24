from __future__ import annotations
import os

REQUIRED = {
    "dry-run": ("SUPABASE_URL", "SUPABASE_READONLY_KEY"),
    "notification": ("RESEND_API_KEY", "INGESTION_NOTIFICATION_EMAIL", "RESEND_FROM_EMAIL"),
    "apply": ("SUPABASE_URL", "SUPABASE_SECRET_KEY"),
}

def check_required_credentials(mode: str) -> dict:
    if mode not in REQUIRED:
        raise ValueError(f"unknown credential mode: {mode}")
    missing = [name for name in REQUIRED[mode] if not str(os.getenv(name, "")).strip()]
    return {"mode": mode, "configured": not missing, "missing": missing}
