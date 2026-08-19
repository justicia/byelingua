from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _supabase_config():
    url = os.environ.get(
        "SUPABASE_URL",
        "",
    ).rstrip("/")

    key = os.environ.get(
        "SUPABASE_SECRET_KEY",
        "",
    )

    if not url or not key:
        raise RuntimeError(
            "Character writer requires "
            "SUPABASE_URL and SUPABASE_SECRET_KEY"
        )

    return url, key


def _request(
    method,
    table,
    *,
    params=None,
    payload=None,
    prefer=None,
    sender=urlopen,
):
    url, key = _supabase_config()

    endpoint = f"{url}/rest/v1/{table}"

    if params:
        endpoint += "?" + urlencode(
            params,
            doseq=True,
        )

    body = None

    if payload is not None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if prefer:
        headers["Prefer"] = prefer

    request = Request(
        endpoint,
        data=body,
        method=method,
        headers=headers,
    )

    with sender(
        request,
        timeout=60,
    ) as response:
        content = response.read()

        if not content:
            return []

        return json.loads(
            content.decode("utf-8")
        )

def upsert_global_character(
    resolved,
    *,
    sender=urlopen,
):
    if resolved.get("kind") != "character":
        return None

    identity_key = str(
        resolved.get("identity_key") or ""
    ).strip()

    canonical_name = str(
        resolved.get("canonical_name") or ""
    ).strip()

    if not identity_key:
        raise ValueError(
            "Resolved character is missing identity_key."
        )

    if not canonical_name:
        raise ValueError(
            "Resolved character is missing canonical_name."
        )

    existing = _request(
        "GET",
        "characters",
        params={
            "identity_key": f"eq.{identity_key}",
            "select": "id,canonical_name,identity_key",
            "limit": "1",
        },
        sender=sender,
    )

    if existing:
        return str(existing[0]["id"])

    rows = _request(
        "POST",
        "characters",
        params={
            "on_conflict": "identity_key",
        },
        payload={
            "identity_key": identity_key,
            "canonical_name": canonical_name,
        },
        prefer=(
            "resolution=merge-duplicates,"
            "return=representation"
        ),
        sender=sender,
    )

    if not rows:
        raise RuntimeError(
            "Global character UPSERT returned no row."
        )

    return str(rows[0]["id"])


def upsert_work_character(
    work_id,
    character_uid,
    canonical_name,
    *,
    sender=urlopen,
):
    work_id = str(
        work_id or ""
    ).strip()

    character_uid = str(
        character_uid or ""
    ).strip()

    canonical_name = str(
        canonical_name or ""
    ).strip()

    if not work_id:
        raise ValueError(
            "Work-character relation is missing work_id."
        )

    if not character_uid:
        raise ValueError(
            "Work-character relation is missing character_uid."
        )

    if not canonical_name:
        raise ValueError(
            "Work-character relation is missing canonical_name."
        )

    existing = _request(
        "GET",
        "work_characters",
        params={
            "work_id": f"eq.{work_id}",
            "canonical_name": f"eq.{canonical_name}",
            "select": "id,character_uid,canonical_name",
            "limit": "1",
        },
        sender=sender,
    )

    if existing:
        relation = existing[0]

        if str(
            relation.get("character_uid") or ""
        ) != character_uid:
            _request(
                "PATCH",
                "work_characters",
                params={
                    "id": f"eq.{relation['id']}",
                },
                payload={
                    "character_uid": character_uid,
                },
                prefer="return=minimal",
                sender=sender,
            )

        return str(relation["id"])

    rows = _request(
        "POST",
        "work_characters",
        params={
            "on_conflict": "work_id,canonical_name",
        },
        payload={
            "work_id": work_id,
            "canonical_name": canonical_name,
            "character_uid": character_uid,
        },
        prefer=(
            "resolution=merge-duplicates,"
            "return=representation"
        ),
        sender=sender,
    )

    if not rows:
        raise RuntimeError(
            "Work-character UPSERT returned no row."
        )

    return str(rows[0]["id"])

def upsert_character_aliases(
    character_uid,
    aliases,
    *,
    source="character_registry",
    sender=urlopen,
):
    character_uid = str(
        character_uid or ""
    ).strip()

    if not character_uid:
        raise ValueError(
            "Character aliases are missing character_uid."
        )

    if not aliases:
        return 0

    written = 0

    for language, alias_values in aliases.items():
        if not isinstance(alias_values, list):
            continue

        for alias in alias_values:
            alias = str(
                alias or ""
            ).strip()

            if not alias:
                continue

            alias_language = (
                None
                if language == "source"
                else str(language or "").strip() or None
            )

            _request(
                "POST",
                "character_aliases",
                params={
                    "on_conflict": "character_id,alias",
                },
                payload={
                    "character_id": character_uid,
                    "alias": alias,
                    "language": alias_language,
                    "source": source,
                },
                prefer=(
                    "resolution=merge-duplicates,"
                    "return=minimal"
                ),
                sender=sender,
            )

            written += 1

    return written

def upsert_resolved_character(
    work_id,
    resolved,
    *,
    sender=urlopen,
):
    if resolved.get("kind") != "character":
        return None

    character_uid = upsert_global_character(
        resolved,
        sender=sender,
    )

    if not character_uid:
        return None

    aliases = resolved.get("aliases") or {}

    upsert_character_aliases(
        character_uid,
        aliases,
        sender=sender,
    )

    relation_id = upsert_work_character(
        work_id,
        character_uid,
        resolved.get("canonical_name"),
        sender=sender,
    )

    return relation_id