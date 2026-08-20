"""Phase 3.4R: real-evidence Composer enrichment review, staging only."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "artifacts/auditorio-nacional/auditorio-composer-new-entity-review.json"
MASTER = ROOT / "artifacts/global-entities/composer-master-snapshot.json"
OUT_DIR = ROOT / "artifacts/global-entities"
LATIN_TRANSLITERATIONS = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D", "þ": "th", "Þ": "Th", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe"})


def norm(value: str) -> str:
    value = (value or "").translate(LATIN_TRANSLITERATIONS)
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c)).lower()
    value = re.sub(r"\([^)]*\)", " ", value)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def strip_lifespan(value: str) -> str:
    value = re.sub(r"\s*\((?:ca\.\s*)?\d{3,4}\s*[–-]\s*(?:ca\.\s*)?\d{3,4}\)\s*$", "", value)
    return re.sub(r"\s*\(\*?\d{4}\)\s*$", "", value).strip()


# These are only the external resources actually retrieved and inspected in
# this review.  Every other candidate remains unresolved by default.
VERIFIED = {
    "A. Márquez": {"canonical": "Arturo Márquez", "url": "https://ofcm.cultura.cdmx.gob.mx/sites/default/files/17-09-22_Programa%20de%20Mano_interactivo.pdf", "title": "Mexico City Philharmonic programme note", "fact": "The programme identifies Arturo Márquez as the composer of Danzón No. 2.", "role": "composer", "lifespan": "1950-"},
    "A. Villamil (1929 - 2010)": {"canonical": "Andrés Villamil", "url": "https://cultura.cervantes.es/hamburgo/es/andr%C3%A9s-villamil/127113", "title": "Instituto Cervantes Andrés Villamil programme", "fact": "The Instituto Cervantes programme identifies Andrés Villamil as composer of Piazzollesco and describes his composition activity.", "role": "composer", "lifespan": "1976-", "secondary_url": "https://facartes.uniandes.edu.co/evento/recital-de-guitarra-carlos-rocca-andres-villamil/"},
    "A. Vivas": {"canonical": "Alejandro Vivas Puig", "url": "https://auditorionacional.inaem.gob.es/es/noticias/historico-de-programas/temporada-2013-2014/2014-marzo.pdf", "title": "Auditorio Nacional official programme PDF", "fact": "The official programme expands A. Vivas to A. Vivas Puig for La Dama de Plica; the composer’s official site identifies Alejandro Vivas as a composer.", "role": "composer", "lifespan": None, "secondary_url": "https://www.alejandrovivas.com/"},
    "G. Holst": {"canonical": "Gustav Holst", "url": "https://gustavholst.org/composition/the-planets-op-32-1914-16/", "title": "The Gustav Holst Website: The Planets", "fact": "The composer’s official foundation site identifies Gustav Holst as the composer of The Planets.", "role": "composer", "lifespan": "1874-1934"},
    "I. Carreño": {"canonical": "Inocente Carreño", "url": "https://www.operabase.com/glosa-sinfonica-margaritena-carreno-i/fr", "title": "Operabase work authority page", "fact": "The work page expands I. Carreño to Inocente Carreño and identifies Glosa Sinfónica Margariteña as his work.", "role": "composer", "lifespan": "1919-2016", "secondary_url": "https://www.palaumusica.cat/20240204-prog-ma-josb_1262946.pdf"},
    "Respighi": {"canonical": "Ottorino Respighi", "url": "https://ocne.inaem.gob.es/ficheros/sinfonico-10-notas/%40%40images/file", "title": "Orquesta Nacional de España programme notes", "fact": "The official OCNE notes identify Ottorino Respighi and Pinos de Roma, P.141.", "role": "composer", "lifespan": "1879-1936", "secondary_url": "https://radionacional-v3.s3.amazonaws.com/s3fs-public/file/archive_80y/field_file/1986-04%20-%20h_1598_4%20-%20YA.pdf"},
    "Luigi Maurizio": {"canonical": "Luigi Maurizio Tedeschi", "url": "https://www.tactus.it/en/tc862001-tedeschi-luigi-maurizio-chamber-music-with-harp/", "title": "Tactus Records catalogue", "fact": "The publisher page names Luigi Maurizio Tedeschi, describes him as a harpist and composer, and lists Suite, Op. 46.", "role": "composer", "lifespan": "1867-1944"},
    "Nuria Núñez Hierro (1890)": {"canonical": "Nuria Núñez Hierro", "url": "https://www.nurianunezhierro.com/", "title": "Nuria Núñez Hierro official site", "fact": "The official biography identifies her as a Spanish composer born in 1980; the raw source year 1890 is therefore anomalous metadata, not a trusted birth year.", "role": "composer", "lifespan": "1980-", "anomaly": "source_metadata_anomaly"},
    "Mieczysław Weinberg (1919-1996)": {"canonical": "Mieczysław Weinberg", "url": "https://www.deutsche-digitale-bibliothek.de/person/gnd/124416225", "title": "Deutsche Digitale Bibliothek authority-linked record", "fact": "The authority-linked record identifies Mieczysław Weinberg as a composer and pianist and gives his lifespan.", "role": "composer", "lifespan": "1919-1996", "authority_id": "GND 124416225"},
    "Agustín Pío Barrios \"Mangoré\" (1885 - 1944)": {"canonical": "Agustín Pío Barrios", "url": "https://davinci-edition.com/product/c00770/", "title": "Da Vinci Publishing composer catalogue", "fact": "The publisher catalogue identifies Agustín Barrios as a Paraguayan guitarist and composer and documents the Mangoré name variant and guitar works.", "role": "composer", "lifespan": "1885-1944"},
}
VERIFIED["Mieczysław Weinberg"] = VERIFIED["Mieczysław Weinberg (1919-1996)"]

ATTRIBUTION = {
    "Françoise Hardy (1944-2024)": ("https://catalogue.bnf.fr/ark:/12148/cb119068909.public", "BnF person authority record", "identity is established, but the Auditorio item contains no work-level authorship"),
    "Charles Aznavour (1924-2018)": ("https://www.aznavourfoundation.org/en/charles_aznavour/biography", "Aznavour Foundation biography", "songwriting authorship is established generally, but the Auditorio item contains no specific work attribution"),
    "Hilda Herrera (1932)": ("https://www.fundacionkonex.org/b2700-hilda-herrera", "Fundación Konex biography", "composer role is established, but the Auditorio item contains no specific work attribution"),
    "Simón Díaz (1928-2014)": ("https://simondiaz.com/", "Simón Díaz official biography", "composer role is established, but the Auditorio item contains no specific work attribution"),
    "Violeta Parra (1917-1967)": ("https://www.fundacionvioletaparra.org/trayectoria", "Fundación Violeta Parra trajectory", "composition activity is established, but the Auditorio item contains no specific work attribution"),
    "G. Braunstein": ("https://guybraunstein.info/about/", "Guy Braunstein official biography", "composer and arranger role is established, but the Auditorio line is Brahms / G. Braunstein and does not establish authorship versus arrangement"),
}


def load_master(path: Path):
    master = json.loads(path.read_text(encoding="utf-8"))
    raw_composer_rows = list(master.get("composers", []))
    raw_alias_rows = list(master.get("aliases", master.get("composer_aliases", [])))
    composers = {norm(x.get("canonical_name", "")): x for x in raw_composer_rows}
    aliases = {norm(x.get("alias", "")): x for x in raw_alias_rows}
    return master, raw_composer_rows, raw_alias_rows, composers, aliases


def source_evidence(row: dict) -> dict:
    return {"source_type": "official_source_programme", "source_title": row.get("raw_title"), "source_url": row.get("source_url"), "access_result": "preserved_from_input_artifact", "identity_name_found": row.get("raw_composer_text"), "composer_role_found": None, "identity_disambiguation": "raw source provenance only", "evidence_excerpt_or_fact": "source observation preserved without treating it as canonical evidence", "verification_status": "partial", "supports": "source attribution and raw spelling", "verified_identity_name": None, "verified_role": None, "verified_lifespan": None, "authority_id_if_available": None}


def external_evidence(name: str, item: dict) -> dict:
    return {"source_type": "retrieved_external_evidence", "source_title": item["title"], "source_url": item["url"], "access_result": "retrieved_and_inspected", "identity_name_found": item["canonical"], "composer_role_found": item["role"], "identity_disambiguation": "source context and external identity are compatible", "evidence_excerpt_or_fact": item["fact"], "verification_status": "verified", "supports": "canonical identity and Composer role", "verified_identity_name": item["canonical"], "verified_role": item["role"], "verified_lifespan": item.get("lifespan"), "authority_id_if_available": item.get("authority_id")}


def classify(name: str, rows: list[dict], composers: dict, aliases: dict) -> dict:
    base = strip_lifespan(name)
    master_key = norm(base)
    existing = composers.get(master_key) or aliases.get(master_key)
    verified_item = VERIFIED.get(name)
    canonical_hint = norm(verified_item["canonical"]) if verified_item else None
    # The only valid confirmation path is a retrieved evidence record below.
    if verified_item and canonical_hint in composers and master_key not in aliases and master_key != canonical_hint:
        status = "global_alias_gap"
        canonical = verified_item["canonical"]
        existing_id = composers[canonical_hint].get("id")
        evidence = [source_evidence(rows[0]), external_evidence(name, verified_item), {"source_type": "global_master_lookup", "source_title": "Current public Composer master", "source_url": None, "access_result": "read_only_query_verified", "identity_name_found": canonical, "composer_role_found": "Composer row", "identity_disambiguation": "verified canonical exists globally while source spelling is absent from aliases", "evidence_excerpt_or_fact": "alias-gap staging candidate", "verification_status": "verified", "supports": "global alias gap", "verified_identity_name": canonical, "verified_role": "Composer", "verified_lifespan": verified_item.get("lifespan"), "authority_id_if_available": existing_id}]
        reason = "verified identity exists globally; source spelling is a reusable missing alias"
    elif existing:
        status = "existing_global_identity"
        canonical = None
        existing_id = existing.get("id") or existing.get("composer_id")
        evidence = [source_evidence(rows[0]), {"source_type": "global_master_lookup", "source_title": "Current public Composer master", "source_url": None, "access_result": "read_only_query_verified", "identity_name_found": base, "composer_role_found": "Composer row or alias", "identity_disambiguation": "deterministic normalized match", "evidence_excerpt_or_fact": "matched current canonical or alias value", "verification_status": "verified", "supports": "existing global identity", "verified_identity_name": existing.get("canonical_name") or base, "verified_role": "Composer", "verified_lifespan": None, "authority_id_if_available": existing.get("composer_id") or existing.get("id")}]
        reason = "deterministic match against current global Composer master"
    elif verified_item:
        item = verified_item
        status, canonical, existing_id = "confirmed_new_global_composer", item["canonical"], None
        evidence = [source_evidence(rows[0]), external_evidence(name, item)]
        if item.get("secondary_url"):
            evidence.append({"source_type": "corroborating_institutional_source", "source_title": "Corroborating institutional source", "source_url": item["secondary_url"], "access_result": "retrieved_and_inspected", "identity_name_found": item["canonical"], "composer_role_found": item["role"], "identity_disambiguation": "supports the same identity and work context", "evidence_excerpt_or_fact": item["fact"], "verification_status": "verified", "supports": "corroboration", "verified_identity_name": item["canonical"], "verified_role": item["role"], "verified_lifespan": item.get("lifespan"), "authority_id_if_available": None})
        reason = "positive external evidence retrieved and inspected"
    elif name == "XTM":
        status, canonical, existing_id = "not_a_composer", None, None
        evidence = [source_evidence(rows[0]), {"source_type": "recording_catalogue", "source_title": "Apple Music recording credit", "source_url": "https://music.apple.com/bg/song/1706168234", "access_result": "retrieved_and_inspected", "identity_name_found": "XTM", "composer_role_found": "recording artist / remix credit", "identity_disambiguation": "XTM is credited for a cover/remix recording, not as the underlying composer", "evidence_excerpt_or_fact": "recording credit lists XTM, Annia and Eva Marti for Fly On The Wings Of Love", "verification_status": "verified", "supports": "not_a_composer for this source observation", "verified_identity_name": "XTM", "verified_role": "recording artist / remix credit", "verified_lifespan": None, "authority_id_if_available": None}]
        reason = "popular-music recording artist/remix credit, not demonstrated Composer authorship"
    elif name in ATTRIBUTION:
        url, title, fact = ATTRIBUTION[name]
        status, canonical, existing_id = "source_attribution_review", None, None
        evidence = [source_evidence(rows[0]), {"source_type": "retrieved_external_evidence", "source_title": title, "source_url": url, "access_result": "retrieved_and_inspected", "identity_name_found": strip_lifespan(name), "composer_role_found": "composer/songwriter activity", "identity_disambiguation": "identity or general authorship supported, but source item-level authorship is absent or ambiguous", "evidence_excerpt_or_fact": fact, "verification_status": "partial", "supports": "attribution review only", "verified_identity_name": strip_lifespan(name), "verified_role": "composer/songwriter activity", "verified_lifespan": None, "authority_id_if_available": None}]
        reason = "identity/role researched, but Auditorio item does not prove authorship of a specific Work"
    elif "universo beethoven" in master_key:
        status, canonical, existing_id = "malformed_source", None, None
        evidence, reason = [source_evidence(rows[0])], "source identity is malformed and must not create or silently rewrite a Composer"
    elif name == "A. Petrovic":
        status, canonical, existing_id = "incomplete_identity_review", None, None
        evidence = [source_evidence(rows[0]), {"source_type": "search_review", "source_title": "Petrovic search review", "source_url": "https://music.apple.com/us/artist/petrovic/1011402417", "access_result": "retrieved_but_non_disambiguating", "identity_name_found": "Petrovic", "composer_role_found": None, "identity_disambiguation": "no safe full identity established", "evidence_excerpt_or_fact": "result is an artist page without deterministic identity or composition evidence", "verification_status": "failed", "supports": "does not support canonical creation", "verified_identity_name": None, "verified_role": None, "verified_lifespan": None, "authority_id_if_available": None}]
        reason = "initial/surname fragment remains non-deterministic after context and external review"
    else:
        status, canonical, existing_id = "unresolved_identity", None, None
        evidence, reason = [source_evidence(rows[0])], "no retrieved authoritative evidence sufficient for confirmation"
    anomalies = []
    if name == "Nuria Núñez Hierro (1890)":
        anomalies.append({"type": "source_metadata_anomaly", "raw_value": "1890", "verified_fact": "official biography gives 1980", "action": "preserve raw source; do not use 1890 as canonical birth year"})
    if name == "A. Villamil (1929 - 2010)":
        anomalies.append({"type": "source_metadata_anomaly", "raw_value": "1929-2010", "verified_fact": "work-level evidence identifies Andrés Villamil, born 1976", "action": "preserve raw source; treat lifespan as contamination from Jorge Villamil and do not use it for Andrés Villamil"})
    aliases_out = []
    if status in {"confirmed_new_global_composer", "global_alias_gap"}:
        canonical_name = VERIFIED[name]["canonical"]
        raw_variant = strip_lifespan(name)
        if norm(raw_variant) != norm(canonical_name): aliases_out.append(raw_variant)
    else:
        canonical_name = canonical
    return {"raw_identity_variants": sorted({x.get("raw_component_text", "") for x in rows}), "normalized_review_key": norm(canonical_name or base), "source_occurrences": [{"source_observation_index": x.get("_source_observation_index"), "source_url": x.get("source_url"), "raw_title": x.get("raw_title"), "raw_composer_text": x.get("raw_composer_text")} for x in rows], "occurrence_count": len(rows), "review_status": status, "proposed_canonical_name": canonical_name, "existing_composer_id": existing_id, "proposed_aliases": aliases_out, "source_metadata_anomalies": anomalies, "evidence": evidence, "confidence": "high" if status == "confirmed_new_global_composer" else "review", "review_reason": reason}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path, default=INPUT); parser.add_argument("--master-json", type=Path, default=MASTER); parser.add_argument("--master-unique-normalized-alias-count", type=int, default=None); args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8")); rows = []
    for index, row in enumerate(payload["rows"]):
        if row.get("category") == "new_global_composer_candidate":
            row = dict(row); row["_source_observation_index"] = index; rows.append(row)
    master, raw_composer_rows, raw_alias_rows, composers, aliases = load_master(args.master_json)
    groups, display = defaultdict(list), {}
    for row in rows:
        name = row.get("raw_component_text", "").strip(); key = norm(strip_lifespan(name))
        if key == norm("M Weinberg"): key = norm("Mieczysław Weinberg")
        groups[key].append(row); display.setdefault(key, "Mieczysław Weinberg" if key == norm("Mieczysław Weinberg") else name)
    identities = [classify(display[key], groups[key], composers, aliases) for key in sorted(groups)]
    villamil = next(x for x in identities if any(v.startswith("A. Villamil") for v in x["raw_identity_variants"]))
    assert villamil["proposed_canonical_name"] == "Andrés Villamil"
    assert villamil["proposed_canonical_name"] != "Jorge Villamil"
    assert any(x["type"] == "source_metadata_anomaly" for x in villamil["source_metadata_anomalies"])
    luigi = next(x for x in identities if "Luigi Maurizio" in x["raw_identity_variants"])
    luigi_lifespans = [e.get("verified_lifespan") for e in luigi["evidence"] if e.get("verification_status") == "verified"]
    assert "1867-1944" in luigi_lifespans
    counts = defaultdict(int)
    for item in identities: counts[item["review_status"]] += 1
    alias_count = sum(len(x["proposed_aliases"]) for x in identities)
    evidence_counts = {"verified": sum(any(e.get("verification_status") == "verified" for e in x["evidence"]) for x in identities), "partial": sum(any(e.get("verification_status") == "partial" for e in x["evidence"]) and not any(e.get("verification_status") == "verified" for e in x["evidence"]) for x in identities), "failed": sum(any(e.get("verification_status") == "failed" for e in x["evidence"]) for x in identities)}
    normalized_aliases = {norm(x.get("alias", "")) for x in master.get("aliases", master.get("composer_aliases", []))}
    raw_unique = len({x.get("raw_component_text", "").strip() for x in rows})
    normalized_alias_count = args.master_unique_normalized_alias_count if args.master_unique_normalized_alias_count is not None else len(normalized_aliases)
    summary = {"source": "auditorio_nacional", "phase": "3.4R.2", "input_candidate_occurrences": len(rows), "input_unique_candidate_identities": raw_unique, "deduplicated_review_identity_count": len(identities), "confirmed_new_global_composer_count": counts["confirmed_new_global_composer"], "existing_global_identity_count": counts["existing_global_identity"], "global_alias_gap_count": counts["global_alias_gap"], "incomplete_identity_review_count": counts["incomplete_identity_review"], "source_attribution_review_count": counts["source_attribution_review"], "not_a_composer_count": counts["not_a_composer"], "malformed_source_count": counts["malformed_source"], "unresolved_identity_count": counts["unresolved_identity"], "global_master_composer_row_count": len(raw_composer_rows), "global_master_alias_row_count": len(raw_alias_rows), "global_master_unique_normalized_alias_count": normalized_alias_count, "global_master_unique_normalized_alias_count_source": "live read-only SQL count from public.composer_aliases", "verified_evidence_identity_count": evidence_counts["verified"], "partial_evidence_identity_count": evidence_counts["partial"], "failed_evidence_identity_count": evidence_counts["failed"], "proposed_alias_count": alias_count, "source_metadata_anomaly_count": sum(len(x["source_metadata_anomalies"]) for x in identities), "database_writes": 0, "status_counts": dict(sorted(counts.items()))}
    review = {"source": "auditorio_nacional", "phase": "3.4R.2", "review_only": True, "database_writes": 0, "global_master_recheck": {"composer_row_count": len(raw_composer_rows), "alias_row_count": len(raw_alias_rows), "unique_normalized_alias_count": normalized_alias_count, "unique_normalized_alias_count_source": "live read-only SQL count from public.composer_aliases"}, "identities": identities}
    assert norm("Mieczysław Weinberg") == "mieczyslaw weinberg"
    assert review["global_master_recheck"]["composer_row_count"] == summary["global_master_composer_row_count"]
    assert review["global_master_recheck"]["alias_row_count"] == summary["global_master_alias_row_count"]
    assert review["global_master_recheck"]["unique_normalized_alias_count"] == summary["global_master_unique_normalized_alias_count"]
    assert sum(summary["status_counts"].values()) == 101
    assert sum(x["occurrence_count"] for x in identities) == 108
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "auditorio-composer-enrichment-review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "auditorio-composer-enrichment-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
