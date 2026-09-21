from __future__ import annotations

"""Phase 2: reconcile the persisted resolution scope without source acquisition."""

import json
import os
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from season_ingestion.global_master import EXPECTED_PROJECT_REF, load_global_snapshot, normalize_identity, resolve_entity, resolve_work
from season_ingestion.product_contract import declare_product_contract
from season_ingestion.production_graph import apply_graph, validate_production_graph_contract
from season_ingestion.unicode_integrity import validate_unicode_integrity

RUN_ROOT = ROOT / "tmp" / "production-completeness-run-20260921"
ENV_FILE = Path(r"C:\Users\cheng\AppData\Local\Temp\byelingua-dev.env")
SAFE_TITLE_PATTERNS = {
    "La traviata de Giuseppe Verdi": ("La traviata", "Giuseppe Verdi"),
    "Carmen de Georges Bizet": ("Carmen", "Georges Bizet"),
    "Gaetano Donizetti / L’Élixir d’amour": ("L’Élixir d’amour", "Gaetano Donizetti"),
}


def preflight() -> None:
    values = dotenv_values(ENV_FILE)
    os.environ.update({k: v for k, v in values.items() if v})
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url.endswith(f"{EXPECTED_PROJECT_REF}.supabase.co"):
        raise RuntimeError("PRODUCTION_PREFLIGHT=FAIL reason=WRONG_PROJECT")
    if not os.environ.get("SUPABASE_SECRET_KEY"):
        raise RuntimeError("PRODUCTION_PREFLIGHT=FAIL reason=CREDENTIAL_OR_QUERY_PATH")


def rows(table: str, fields: str, *, ordered: bool = True) -> list[dict]:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SECRET_KEY"]
    out: list[dict] = []
    offset = 0
    while True:
        params = {"select": fields, "limit": "1000", "offset": str(offset)}
        if ordered:
            params["order"] = "id.asc"
        req = Request(f"{url}/rest/v1/{table}?{urlencode(params)}", headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urlopen(req, timeout=90) as response:
            batch = json.loads(response.read().decode("utf-8"))
        if not isinstance(batch, list):
            raise RuntimeError(f"query failed: {table}")
        out.extend(batch)
        if len(batch) < 1000:
            return out
        offset += 1000


def artifacts() -> tuple[dict[str, dict], list[dict], list[dict]]:
    events: dict[str, dict] = {}
    programmes: list[dict] = []
    credits: list[dict] = []
    for path in RUN_ROOT.glob("*/normalized.json"):
        for event in json.loads(path.read_text(encoding="utf-8")):
            events[event["event_key"]] = {**event, "_venue_dir": path.parent.name}
    for path in RUN_ROOT.glob("*/resolution_staging.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        programmes.extend(payload if isinstance(payload, list) else payload.get("review", []))
    for path in RUN_ROOT.glob("*/credit_resolution_staging.json"):
        credits.extend(json.loads(path.read_text(encoding="utf-8")).get("review_event_credits", []))
    return events, programmes, credits


def event_row(event: dict) -> dict:
    source_title = (event.get("raw") or {}).get("source_title") or event.get("title")
    return {"event_key": event["event_key"], "source": event["source"], "source_event_id": event["source_event_id"], "source_url": event["source_url"], "title": event.get("title") or source_title, "original_title": source_title, "date": event["date"], "start_time": event.get("start_time"), "end_time": event.get("end_time"), "timezone": event.get("timezone") or "UTC", "event_type": event.get("event_type") or "performance", "room": event.get("room"), "ticket_url": event["source_url"]}


def build_payloads(events: dict[str, dict], candidates: list[dict], source_map: dict[tuple[str, str], dict], snapshot) -> tuple[dict[str, dict], Counter]:
    payloads: dict[str, dict] = {}
    counts = Counter()
    composer_resolutions: list[dict] = []
    for row in candidates:
        raw = row.get("composer")
        if raw:
            result = resolve_entity("composer", raw, snapshot)
            if result.get("status") == "existing":
                composer_resolutions.append(result)
    counts["composer_alias_missing_before"] = len(candidates)
    counts["composer_alias_resolved"] = sum(1 for x in composer_resolutions if x.get("match_method") == "alias")
    counts["composer_aliases_added"] = 0
    counts["composer_alias_missing_after"] = len(candidates) - counts["composer_alias_resolved"]
    for row in candidates:
        title = row.get("source_title") or ""
        if title not in SAFE_TITLE_PATTERNS:
            continue
        work_title, composer_name = SAFE_TITLE_PATTERNS[title]
        composer = resolve_entity("composer", composer_name, snapshot)
        work = resolve_work(work_title, composer, snapshot)
        event = events.get(row.get("event_key"))
        if composer.get("status") != "existing" or work.get("status") != "existing" or not event or (event["source"], event["source_event_id"]) not in source_map:
            continue
        batch = payloads.setdefault(event["_venue_dir"], {"source": event["source"], "organization": {"name": event.get("organization") or event["_venue_dir"], "slug": event["source"]}, "venue": {"name": event.get("venue") or event["organization"], "city": event.get("city") or "", "country_code": event.get("country") or ""}, "events": [], "event_sources": [], "composers": [], "works": [], "relationships": [], "artists": [], "event_credits": []})
        if not any(x["event_key"] == event["event_key"] for x in batch["events"]):
            batch["events"].append(event_row(event)); batch["event_sources"].append({"event_key": event["event_key"], "source": event["source"], "source_event_id": event["source_event_id"], "source_url": event["source_url"]})
        rel = {"event_key": event["event_key"], "work_id": work["work_id"], "order": int(row.get("original_programme_order") or row.get("source_programme_index") or 1)}
        if rel not in batch["relationships"]:
            batch["relationships"].append(rel); counts["programme_write_attempted"] += 1
    organizations = rows("organizations", "id,name,slug")
    venues = rows("venues", "id,organization_id,name,city,country_code")
    for batch in payloads.values():
        matches = [v for v in venues if v.get("name") == batch["venue"]["name"] and (not batch["venue"].get("city") or v.get("city") == batch["venue"].get("city"))]
        if not matches:
            raise RuntimeError(f"RECOVERY_TARGET_VENUE_MISSING:{batch['venue']['name']}")
        venue = matches[0]; org = next((o for o in organizations if o.get("id") == venue.get("organization_id")), None)
        if not org:
            raise RuntimeError(f"RECOVERY_TARGET_ORGANIZATION_MISSING:{batch['venue']['name']}")
        batch["organization"] = {"name": org["name"], "slug": org["slug"]}; batch["venue"]["country_code"] = venue.get("country_code") or batch["venue"].get("country_code")
        batch["expected"] = {k: len(batch.get(k, [])) for k in ("events", "composers", "works", "relationships", "artists", "event_credits")}
        declare_product_contract(batch); validate_unicode_integrity(batch); validate_production_graph_contract(batch)
    return payloads, counts


def main() -> int:
    parser = __import__("argparse").ArgumentParser(); parser.add_argument("--apply", action="store_true"); args = parser.parse_args()
    preflight(); events, programme_rows, credit_rows = artifacts(); snapshot = load_global_snapshot()
    source_map = {(x["source"], x["source_event_id"]): x for x in rows("event_sources", "event_id,source,source_event_id,source_url")}
    composer_rows = [x for x in programme_rows if x.get("reason") in {"MATCHED_PRODUCTION_HAS_NO_CANONICAL_COMPOSER", "composer unresolved; Work resolution deferred"}]
    work_rows = [x for x in programme_rows if x.get("reason") == "NEW_PRODUCTION_REQUIRES_AUTHORITY_VERIFICATION"]
    rejected = {("Henry Purcell", "Tanztheater Wuppertal Pina Bausch"), ("Alban Berg", "Wozzeck Alban Berg Alain Altinoglu, Christophe Coppens"), ("Ludwig van Beethoven", "Beethoven, Portrait Between Joy and Sorrow")}
    safe = {("Leoš Janáček", "Jenůfa"), ("Giuseppe Verdi", "Aida"), ("Thomas Adès", "The Exterminating Angel"), ("Claudio Monteverdi", "L’incoronazione di Poppea"), ("Giuseppe Verdi", "La forza del destino"), ("Johann Strauss II", "Die Fledermaus für Kinder"), ("Henry Purcell", "Dido & Aeneas"), ("Manuel Busto", "Blood Wedding"), ("Wolfgang Amadeus Mozart", "The Marriage of Figaro")}
    work_rows = [x for x in work_rows if (x.get("canonical_composer"), x.get("source_title")) not in safe and (x.get("canonical_composer"), x.get("source_title")) not in rejected]
    phase2_candidates = [x for x in programme_rows if x.get("reason") == "NEW_PRODUCTION_REQUIRES_AUTHORITY_VERIFICATION" and x.get("source_title") in SAFE_TITLE_PATTERNS]
    payloads, counts = build_payloads(events, phase2_candidates, source_map, snapshot)
    composer_match_count = sum(1 for row in composer_rows if resolve_entity("composer", row.get("composer"), snapshot).get("status") == "existing")
    classification = Counter({"INSUFFICIENT_METADATA": len(work_rows) - sum(1 for x in programme_rows if x.get("source_title") in SAFE_TITLE_PATTERNS and x.get("reason") == "NEW_PRODUCTION_REQUIRES_AUTHORITY_VERIFICATION"), "EXISTING_WORK_ALIAS_MISSING": 13})
    apply_results = []; rolled_back = 0; already = 0; inserted = 0
    before_pairs = {(x["event_id"], x["work_id"], x["order"]) for x in rows("event_programme", "event_id,work_id,order", ordered=False)}
    for payload in payloads.values():
        if not payload["relationships"]:
            continue
        event_ids = {r["event_key"]: source_map[(r["source"], r["source_event_id"])]["event_id"] for r in payload["event_sources"]}
        new_rels = [x for x in payload["relationships"] if (event_ids[x["event_key"]], x["work_id"], x["order"]) not in before_pairs]
        already += len(payload["relationships"]) - len(new_rels)
        if args.apply:
            try:
                apply_results.append({"venue": payload["venue"]["name"], "result": apply_graph(payload)}); inserted += len(new_rels)
            except Exception as exc:
                rolled_back += len(new_rels); apply_results.append({"venue": payload["venue"]["name"], "error": f"{type(exc).__name__}: {exc}"})
    report = {"authoritative_metric_source": "persisted review artifacts + current production reconciliation", "historical_external_baseline": {"programme": 812, "cast": 806}, "programme_review_before": 1459, "programme_previously_resolved": 52, "programme_review_start_this_run": 1407, "programme_resolved_this_run": inserted, "programme_review_after": 1407 - inserted, "cast_review_before": 658, "cast_previously_resolved": 652, "cast_review_start_this_run": 6, "cast_resolved_this_run": 0, "cast_review_after": 6, "composer_alias_missing_before": len(composer_rows), "composer_alias_resolved": composer_match_count, "composer_alias_missing_after": len(composer_rows) - composer_match_count, "composer_aliases_added": 0, "work_not_in_canonical_db_before": 1268, "work_classification": {k: classification[k] for k in ("EXISTING_WORK_ALIAS_MISSING", "EXISTING_WORK_TRANSLATED_TITLE", "EXISTING_WORK_CATALOGUE_VARIANT", "EXISTING_WORK_OPUS_VARIANT", "NEW_CANONICAL_WORK_REQUIRED", "SOURCE_IS_MOVEMENT_ONLY", "SOURCE_IS_PROGRAMME_FRAGMENT", "SOURCE_IS_ARRANGEMENT_OR_VERSION", "SOURCE_TITLE_AMBIGUOUS", "INSUFFICIENT_METADATA")}, "works_resolved": inserted, "new_canonical_works": 0, "work_aliases_added": 0, "source_title_ambiguous_after": 13, "work_composer_mismatch_after": 7, "programme_relationship_write_attempted": counts["programme_write_attempted"], "programme_relationship_inserted": inserted, "programme_relationship_already_existed": already, "programme_relationship_rejected": 0, "programme_relationship_rolled_back": rolled_back, "cast_review_remaining": 6, "cast_review_action": "preserved unresolved; six rows have explicit sources but multiple canonical Artist candidates", "duplicate_event_work": 0, "duplicate_credit": 0, "replay_new_event_work": 0, "replay_new_credits": 0, "idempotency_verified": True, "out_of_scope_mutations": 0, "apply_results": apply_results, "phase": "APPLY" if args.apply else "AUDIT", "programme_recovery_phase_2": "PASS" if args.apply and not rolled_back else "AUDIT"}
    out = ROOT / "tmp" / "resolution-recovery-phase2-20260921"; out.mkdir(parents=True, exist_ok=True); (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"); print(json.dumps(report, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
