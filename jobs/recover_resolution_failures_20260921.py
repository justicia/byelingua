from __future__ import annotations

"""Bounded recovery for the existing 20260921 production-completeness review rows.

This job never crawls a source and never creates an Event from a missing source
identity.  It only promotes rows whose official artifact already carries a
resolved Composer/Artist identity and uses the existing production graph RPC.
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from season_ingestion.credit_resolution import canonical_role
from season_ingestion.global_master import EXPECTED_PROJECT_REF, load_global_snapshot, normalize_identity, resolve_entity
from season_ingestion.product_contract import declare_product_contract
from season_ingestion.production_graph import apply_graph, validate_production_graph_contract
from season_ingestion.unicode_integrity import validate_unicode_integrity


RUN_ROOT = ROOT / "tmp" / "production-completeness-run-20260921"
ENV_FILE = Path(r"C:\Users\cheng\AppData\Local\Temp\byelingua-dev.env")

SAFE_WORKS = {
    ("Leoš Janáček", "Jenůfa"),
    ("Giuseppe Verdi", "Aida"),
    ("Thomas Adès", "The Exterminating Angel"),
    ("Claudio Monteverdi", "L’incoronazione di Poppea"),
    ("Giuseppe Verdi", "La forza del destino"),
    ("Johann Strauss II", "Die Fledermaus für Kinder"),
    ("Henry Purcell", "Dido & Aeneas"),
    ("Manuel Busto", "Blood Wedding"),
    ("Wolfgang Amadeus Mozart", "The Marriage of Figaro"),
}
REJECTED_WORKS = {
    ("Henry Purcell", "Tanztheater Wuppertal Pina Bausch"),
    ("Alban Berg", "Wozzeck Alban Berg Alain Altinoglu, Christophe Coppens"),
    ("Ludwig van Beethoven", "Beethoven, Portrait Between Joy and Sorrow"),
}
COUNTRY_CODES = {"Spain": "ES", "Belgium": "BE", "France": "FR", "Germany": "DE", "Austria": "AT", "Netherlands": "NL", "Switzerland": "CH", "United Kingdom": "GB", "Italy": "IT"}


def env() -> None:
    values = dotenv_values(ENV_FILE)
    os.environ.update({k: v for k, v in values.items() if v})
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url.endswith(f"{EXPECTED_PROJECT_REF}.supabase.co"):
        raise RuntimeError("PRODUCTION_PREFLIGHT=FAIL reason=WRONG_PROJECT")
    if not os.environ.get("SUPABASE_SECRET_KEY"):
        raise RuntimeError("PRODUCTION_PREFLIGHT=FAIL reason=CREDENTIAL_OR_QUERY_PATH")


def get_rows(table: str, fields: str) -> list[dict]:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SECRET_KEY"]
    rows: list[dict] = []
    offset = 0
    while True:
        query = urlencode({"select": fields, "limit": "1000", "offset": str(offset), "order": "id.asc"})
        req = Request(f"{url}/rest/v1/{table}?{query}", headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urlopen(req, timeout=90) as response:
            batch = json.loads(response.read().decode("utf-8"))
        if not isinstance(batch, list):
            raise RuntimeError(f"query failed for {table}")
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000


def load_artifacts() -> tuple[dict[str, dict], list[tuple[str, dict]], list[tuple[str, dict]]]:
    events: dict[str, dict] = {}
    for path in RUN_ROOT.glob("*/normalized.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for event in payload if isinstance(payload, list) else []:
            events[event["event_key"]] = {**event, "_venue_dir": path.parent.name}
    programmes: list[tuple[str, dict]] = []
    credits: list[tuple[str, dict]] = []
    for path in RUN_ROOT.glob("*/resolution_staging.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload if isinstance(payload, list) else payload.get("review", []):
            programmes.append((path.parent.name, row))
    for path in RUN_ROOT.glob("*/credit_resolution_staging.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("review_event_credits", []):
            credits.append((path.parent.name, row))
    return events, programmes, credits


def event_payload(event: dict) -> dict:
    raw = event.get("raw") or {}
    source_title = raw.get("source_title") or event.get("title")
    return {
        "event_key": event["event_key"], "source": event["source"], "source_event_id": event["source_event_id"],
        "source_url": event["source_url"], "title": event.get("title") or source_title, "original_title": source_title,
        "date": event["date"], "start_time": event.get("start_time"), "end_time": event.get("end_time"),
        "timezone": event.get("timezone") or "UTC", "event_type": event.get("event_type") or "performance",
        "room": event.get("room"), "ticket_url": event.get("source_url"),
    }


def group_payloads(events: dict[str, dict], programmes: list[tuple[str, dict]], credits: list[tuple[str, dict]], event_sources: dict[tuple[str, str], dict], snapshot) -> tuple[dict[str, dict], dict]:
    payloads: dict[str, dict] = {}
    stats = {"programme": Counter(), "credits": Counter(), "taxonomy_programme": Counter(), "taxonomy_cast": Counter(), "work_specs": set(), "artist_specs": set(), "event_keys": set()}
    def payload_for(event: dict) -> dict:
        key = event["_venue_dir"]
        if key in payloads:
            return payloads[key]
        org_name = event.get("organization") or key
        venue_name = event.get("venue") or org_name
        payloads[key] = {"source": event["source"], "organization": {"name": org_name, "slug": event["source"]}, "venue": {"name": venue_name, "city": event.get("city") or "", "country_code": COUNTRY_CODES.get(event.get("country"), event.get("country") or "")}, "events": [], "event_sources": [], "composers": [], "works": [], "relationships": [], "artists": [], "event_credits": []}
        return payloads[key]
    def ensure_event(payload: dict, event: dict) -> None:
        if not any(row["event_key"] == event["event_key"] for row in payload["events"]):
            payload["events"].append(event_payload(event)); payload["event_sources"].append({"event_key": event["event_key"], "source": event["source"], "source_event_id": event["source_event_id"], "source_url": event["source_url"]}); stats["event_keys"].add(event["event_key"])
    comp_by_name = {normalize_identity(r.get("canonical_name")): r for r in snapshot.entities.get("composer", [])}
    for venue, row in programmes:
        title = row.get("source_title") or ""
        composer = row.get("canonical_composer") or ""
        reason = row.get("reason") or ""
        if row.get("status") == "existing" or reason.startswith(("unique existing", "exact operational")):
            continue
        if not row.get("work_id") and (composer, title) in SAFE_WORKS:
            event = events.get(row.get("event_key")); comp = comp_by_name.get(normalize_identity(composer))
            if not event or not comp or (event["source"], event["source_event_id"]) not in event_sources:
                stats["programme"]["rejected_missing_existing_event"] += 1; stats["taxonomy_programme"]["OTHER_EXPLICIT_REASON"] += 1; continue
            payload = payload_for(event); ensure_event(payload, event)
            work_key = f"recovery:{normalize_identity(composer)}:{normalize_identity(title)}"
            if not any(w["candidate_key"] == work_key for w in payload["works"]):
                payload["works"].append({"candidate_key": work_key, "normalized_source_title": normalize_identity(title), "proposed_canonical_title": title, "composer_id": comp["id"], "composer": comp["canonical_name"], "source_url": (row.get("provenance") or {}).get("source_url"), "source_field": (row.get("provenance") or {}).get("source_field")}); stats["work_specs"].add(work_key)
            rel = {"event_key": event["event_key"], "candidate_key": work_key, "order": int(row.get("original_programme_order") or row.get("source_programme_index") or 1)}
            if rel not in payload["relationships"]:
                payload["relationships"].append(rel); stats["programme"]["attempted"] += 1
            stats["taxonomy_programme"]["WORK_NOT_IN_CANONICAL_DB"] += 1
        elif not row.get("work_id"):
            if (composer, title) in REJECTED_WORKS:
                taxonomy_reason = "WORK_COMPOSER_MISMATCH"
            elif reason in {"AMBIGUOUS_PRODUCTION_TITLE"}:
                taxonomy_reason = "SOURCE_TITLE_AMBIGUOUS"
            elif reason in {"MATCHED_PRODUCTION_HAS_NO_CANONICAL_COMPOSER", "composer unresolved; Work resolution deferred"}:
                taxonomy_reason = "COMPOSER_ALIAS_MISSING"
            elif reason == "NEW_PRODUCTION_REQUIRES_AUTHORITY_VERIFICATION":
                taxonomy_reason = "WORK_NOT_IN_CANONICAL_DB"
            else:
                taxonomy_reason = "OTHER_EXPLICIT_REASON"
            stats["taxonomy_programme"][taxonomy_reason] += 1
    for venue, row in credits:
        credit = row.get("credit") or {}; status = credit.get("resolution_status")
        if status == "REVIEW_ROLE_UNKNOWN" and credit.get("source_role") == "performer" and credit.get("artist_resolution", {}).get("status") in {"SAFE_EXISTING", "SAFE_NEW_ARTIST"}:
            event = events.get(row.get("event_key"))
            if not event or (event["source"], event["source_event_id"]) not in event_sources:
                stats["credits"]["rejected_missing_existing_event"] += 1; stats["taxonomy_cast"]["OTHER_EXPLICIT_REASON"] += 1; continue
            payload = payload_for(event); ensure_event(payload, event); artist = credit["artist_resolution"]; identity = artist.get("lookup_key")
            if artist.get("status") == "SAFE_NEW_ARTIST" and not any(a.get("identity_key") == identity for a in payload["artists"]):
                payload["artists"].append({"identity_key": identity, "lookup_key": identity, "artist_name": artist.get("canonical_name") or credit.get("source_artist_name"), "canonical_name": artist.get("canonical_name") or credit.get("source_artist_name")}); stats["artist_specs"].add(identity)
            row_payload = {"event_key": event["event_key"], "artist_id": artist.get("artist_id"), "artist_identity_key": identity, "artist_name": artist.get("canonical_name") or credit.get("source_artist_name"), "role": "performer", "instrument": credit.get("instrument"), "voice_type": credit.get("voice_type"), "character_id": None, "character": None, "raw_character": None, "source_url": credit.get("source_url"), "source_field": credit.get("source_field")}
            if not any((c.get("event_key"), c.get("artist_id") or c.get("artist_identity_key"), c.get("role")) == (row_payload["event_key"], row_payload.get("artist_id") or identity, "performer") for c in payload["event_credits"]):
                payload["event_credits"].append(row_payload); stats["credits"]["attempted"] += 1
            stats["taxonomy_cast"]["ROLE_PARSE_FAILURE"] += 1
        elif status == "REVIEW_ARTIST_CONFLICT":
            stats["taxonomy_cast"]["PERSON_ROLE_AMBIGUOUS"] += 1
    for p in payloads.values():
        p["expected"] = {k: len(p.get(k, [])) for k in ("events", "composers", "works", "relationships", "artists", "event_credits")}
        declare_product_contract(p); validate_unicode_integrity(p); validate_production_graph_contract(p)
    return payloads, stats


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--apply", action="store_true"); args = parser.parse_args()
    env(); events, programmes, credits = load_artifacts(); snapshot = load_global_snapshot()
    source_rows = get_rows("event_sources", "event_id,source,source_event_id,source_url")
    event_sources = {(r["source"], r["source_event_id"]): r for r in source_rows}
    payloads, stats = group_payloads(events, programmes, credits, event_sources, snapshot)
    # Pin every batch to the already-existing organization/venue identity.
    # The RPC may create a missing venue, so a recovery batch must refuse that
    # path by using the database's current slug/name pair.
    organizations = get_rows("organizations", "id,name,slug")
    venues = get_rows("venues", "id,organization_id,name,city,country_code")
    for payload in payloads.values():
        matches = [v for v in venues if v.get("name") == payload["venue"]["name"] and (not payload["venue"].get("city") or v.get("city") == payload["venue"].get("city"))]
        if not matches:
            raise RuntimeError(f"RECOVERY_TARGET_VENUE_MISSING:{payload['venue']['name']}")
        selected = matches[0]
        org = next((o for o in organizations if o.get("id") == selected.get("organization_id")), None)
        if not org:
            raise RuntimeError(f"RECOVERY_TARGET_ORGANIZATION_MISSING:{payload['venue']['name']}")
        payload["organization"] = {"name": org["name"], "slug": org["slug"]}
        payload["venue"]["country_code"] = selected.get("country_code") or payload["venue"].get("country_code")
        declare_product_contract(payload); validate_unicode_integrity(payload); validate_production_graph_contract(payload)
    apply_results = []; rolled_back = 0
    if args.apply:
        for venue, payload in payloads.items():
            if not payload["relationships"] and not payload["event_credits"]: continue
            try: apply_results.append({"venue": venue, "result": apply_graph(payload)})
            except Exception as exc: rolled_back += len(payload["relationships"]) + len(payload["event_credits"]); apply_results.append({"venue": venue, "error": f"{type(exc).__name__}: {exc}"})
    report = {"production_project_ref": EXPECTED_PROJECT_REF, "mode": "APPLY" if args.apply else "AUDIT", "source_artifact": str(RUN_ROOT), "programmes_observed": len(programmes), "credits_observed": len(credits), "payloads": {k: {x: len(v.get(x, [])) for x in ("events", "works", "relationships", "artists", "event_credits")} for k, v in payloads.items()}, "taxonomy": {"programme": dict(stats["taxonomy_programme"]), "cast": dict(stats["taxonomy_cast"])}, "programme_write_attempted": stats["programme"]["attempted"], "credit_write_attempted": stats["credits"]["attempted"], "rolled_back": rolled_back, "new_work_candidates": len(stats["work_specs"]), "new_artist_candidates": len(stats["artist_specs"]), "apply_results": apply_results}
    out = ROOT / "tmp" / "resolution-recovery-20260921"; out.mkdir(parents=True, exist_ok=True); (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"); print(json.dumps(report, ensure_ascii=False, indent=2)); return 0 if not any("error" in x for x in apply_results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
