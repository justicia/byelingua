"""Read-only guard for the fixed Byelingua production Supabase project.

The guard deliberately fails closed.  A wrong project is reported as
``WRONG_PROJECT``; a correct project whose read path cannot see the known
production sentinels is reported as ``CREDENTIAL_OR_QUERY_PATH``.  It never
tries another project reference and has no write path.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PRODUCTION_PROJECT_REF = "pdtunknwruokybtuehua"
PRODUCTION_CATALOG_PATH = "/rest/v1/event_catalog_v1"


@dataclass(frozen=True)
class ProductionSentinel:
    key: str
    pattern: str
    minimum_events: int


PRODUCTION_SENTINELS = (
    ProductionSentinel("palau_de_la_musica_catalana", "Palau de la Música Catalana", 400),
    ProductionSentinel("royal_opera_house", "Royal Opera House", 400),
    ProductionSentinel("teatro_alla_scala", "Teatro alla Scala", 150),
    ProductionSentinel("auditorio_nacional", "Auditorio Nacional", 500),
)


def project_ref_from_url(url: str) -> str | None:
    match = re.fullmatch(r"https://([a-z0-9]+)\.supabase\.co/?", str(url or "").strip(), re.I)
    return match.group(1).lower() if match else None


def _result(*, status: str, reason: str | None, project_ref: str | None, counts: dict[str, int] | None = None) -> dict:
    return {
        "production_preflight": status,
        "reason": reason,
        "production_project_ref": project_ref,
        "expected_project_ref": PRODUCTION_PROJECT_REF,
        "sentinel_counts": counts or {},
    }


def _count_sentinel(*, base_url: str, key: str, sentinel: ProductionSentinel, fetcher=urlopen) -> int:
    # Search both canonical organization and venue labels because the view
    # exposes both, while retaining a single read-only query path.
    wildcard = sentinel.pattern.replace("*", "")
    or_filter = f"(organization.ilike.*{wildcard}*,venue.ilike.*{wildcard}*)"
    query = urlencode({"select": "event_id", "or": or_filter, "limit": "1"})
    request = Request(
        f"{base_url.rstrip('/')}{PRODUCTION_CATALOG_PATH}?{query}",
        method="GET",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Prefer": "count=exact",
        },
    )
    try:
        with fetcher(request, timeout=45) as response:
            if getattr(response, "status", 200) != 200:
                raise RuntimeError(f"HTTP {getattr(response, 'status', 'unknown')}")
            content_range = ""
            headers = getattr(response, "headers", None)
            if headers is not None:
                content_range = str(headers.get("Content-Range", ""))
            match = re.search(r"/(\d+|\*)$", content_range)
            if match and match.group(1) != "*":
                return int(match.group(1))
            # A test double or a proxy may omit Content-Range.  Only accept a
            # complete, unbounded JSON response; a limited response is not
            # evidence that the sentinel exists.
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, list) and len(payload) != 1:
                return len(payload)
            raise RuntimeError("missing exact Content-Range")
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
        raise RuntimeError(f"sentinel query failed for {sentinel.key}: {type(exc).__name__}") from exc


def production_identity_preflight(
    *,
    supabase_url: str | None = None,
    readonly_key: str | None = None,
    fetcher=urlopen,
) -> dict:
    """Return a read-only production identity report; never switches refs."""
    url = str(supabase_url if supabase_url is not None else os.environ.get("SUPABASE_URL", "")).strip()
    project_ref = project_ref_from_url(url)
    if project_ref != PRODUCTION_PROJECT_REF:
        return _result(status="FAIL", reason="WRONG_PROJECT", project_ref=project_ref)
    key = str(readonly_key if readonly_key is not None else os.environ.get("SUPABASE_READONLY_KEY", "")).strip()
    if not key:
        return _result(status="FAIL", reason="CREDENTIAL_OR_QUERY_PATH", project_ref=project_ref)
    counts: dict[str, int] = {}
    try:
        for sentinel in PRODUCTION_SENTINELS:
            counts[sentinel.key] = _count_sentinel(base_url=url, key=key, sentinel=sentinel, fetcher=fetcher)
    except RuntimeError:
        return _result(status="FAIL", reason="CREDENTIAL_OR_QUERY_PATH", project_ref=project_ref, counts=counts)
    if any(counts[s.key] < s.minimum_events for s in PRODUCTION_SENTINELS):
        return _result(status="FAIL", reason="CREDENTIAL_OR_QUERY_PATH", project_ref=project_ref, counts=counts)
    return _result(status="PASS", reason=None, project_ref=project_ref, counts=counts)
