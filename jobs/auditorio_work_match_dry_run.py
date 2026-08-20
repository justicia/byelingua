"""Auditorio Nacional global Work consolidation dry-run.

Consumes the accepted structure and Composer match artifacts, reads a fresh
Work Master fixture/export, and emits review, staging, and SQL artifacts. It
never writes Supabase or event_programme.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


NON_WORK_RE = re.compile(r"^(?:piano|viol[ií]n|viola|violonchelo|director(?:a)?|coro|orquesta|ensemble|voz|voces)\s*:", re.I)
CATALOGUE_RE = re.compile(r"\b(?:BWV|Hob\.?|K\.?|KV|RV|D\.?|S\.?|WoO|G\.?|CD)\s*[-\w.]+|\bop\.?\s*\d+[a-z]?(?:\s*(?:no\.?|nº|n\.º)\s*\d+)?", re.I)
LIFESPAN_RE = re.compile(r"\s*\((?:ca\.\s*)?\d{3,4}(?:\s*[-–—]\s*(?:ca\.\s*)?\d{2,4})?\s*\)")
MOVEMENT_RE = re.compile(r"^(?:[IVXLCDM]+|\d+)[.)]\s", re.I)

RESEARCH_EVIDENCE = {
    "G. 339": {
        "sources": ["https://imslp.org/wiki/String_Quintet%2C_G.339_%28Op.39/3%29_%28Boccherini%2C_Luigi%29", "https://www.editionsilvertrust.com/boccherini-quintet-G.339.htm"],
        "result": "Established Luigi Boccherini string quintet in D major, G.339; no equivalent canonical Work was found in the current relevant subset.",
    },
    "op. 74": {
        "sources": ["https://imslp.org/wiki/String_Quintet_No.30%2C_Op.74_%28Onslow%2C_George%29", "https://www.kammermusikverlag.de/en/Onslow-George-String-Quintet-No.-30-E-minor-op.-74/5030"],
        "result": "Established George Onslow String Quintet No. 30 in E minor, Op. 74; no equivalent canonical Work was found in the current relevant subset.",
    },
    "op. 316": {
        "sources": ["https://brahms.ircam.fr/en/work/deuxieme-quintette-1"],
        "result": "Established Darius Milhaud String Quintet No. 2, Op. 316; no equivalent canonical Work was found in the current relevant subset.",
    },
    "In the South": {
        "sources": ["https://www.elgar.org/3alassio.htm"],
        "result": "Established Edward Elgar concert overture In the South (Alassio), Op. 50; no equivalent canonical Work was found in the current relevant subset.",
    },
    "BWV 1010": {
        "sources": ["https://imslp.org/wiki/Cello%20Suite%20No.4_in_E-flat_major%2C_BWV_1010_%28Bach%2C_Johann_Sebastian%29", "https://catalogue.bnf.fr/ark%3A/12148/cb487736389"],
        "result": "Established Johann Sebastian Bach Cello Suite No. 4 in E-flat major, BWV 1010; the programme title is a translated/title-variant form.",
    },
    "BWV 596": {
        "sources": ["https://www.bachvereniging.nl/en/bwv/bwv-596", "https://imslp.org/wiki/Konzertbearbeitungen%2C_BWV_592-596_%28Bach%2C_Johann_Sebastian%29"],
        "result": "Established Bach organ Concerto in D minor, BWV 596, an arrangement of Vivaldi; parent/arrangement semantics require manual review.",
    },
    "CD 93": {
        "sources": ["https://catalogue.bnf.fr/ark%3A/12148/cb42032768d", "https://pad.philharmoniedeparis.fr/pad/doc/CIMU/0762794/pelleas-et-melisande?_lg=fr-FR"],
        "result": "Established Debussy Pelléas et Mélisande, FL/CD 93, with Mes longs cheveux as an excerpt; retain as parent/excerpt review rather than duplicate top-level Work.",
    },
    "K. 626": {
        "sources": ["https://kv.mozarteum.at/de/work/requiem-in-d-7395", "https://portal.dnb.de/opac.htm?cqlMode=true&method=simpleSearch&query=idn%3D1020076879"],
        "result": "Established Mozart Requiem in D minor, K./KV 626; existing null-linked rows require identity reconciliation before any create action.",
    },
    "op. 57": {
        "sources": ["https://www.beethoven.de/en/archive/view/node/6192829114089472/Symphonies"],
        "result": "Established Beethoven Piano Sonata No. 23 Appassionata, Op. 57; catalogue evidence identifies the Work, but current relevant title recovery remains review-gated.",
    },
    "op. 96": {
        "sources": ["https://www.antonin-dvorak.cz/en/work/string-quartet-no-12/", "https://www.barenreiter.us/products/dvorak-string-quartet-no-12-in-f-major-op-96-american-barenreiter"],
        "result": "Established Dvořák String Quartet No. 12 in F major, Op. 96, B.179, American; arrangement marker means canonical parent must be preserved.",
    },
    "op. 21": {
        "sources": ["https://www.beethoven.de/en/archive/view/node/6192829114089472/Symphonies"],
        "result": "Established Beethoven Symphony No. 1 in C major, Op. 21; current title collision remains subject to existing-master review.",
    },
    "op.60": {
        "sources": ["https://www.beethoven.de/en/archive/view/node/6192829114089472/Symphonies"],
        "result": "Established Beethoven Symphony No. 4 in B-flat major, Op. 60; current title collision remains subject to existing-master review.",
    },
    "op.67": {
        "sources": ["https://www.beethoven.de/en/archive/view/node/6192829114089472/Symphonies"],
        "result": "Established Beethoven Symphony No. 5 in C minor, Op. 67; current title collision remains subject to existing-master review.",
    },
    "op. 68": {
        "sources": ["https://www.beethoven.de/en/archive/view/node/6192829114089472/Symphonies"],
        "result": "Established Beethoven Symphony No. 6 in F major, Op. 68, Pastoral; current title collision remains subject to existing-master review.",
    },
    "Resurrección": {
        "sources": ["https://www.mahlerfoundation.org/mahler/compositions/symphony-no-2/"],
        "result": "Established Mahler Symphony No. 2, Resurrection; current title collision remains subject to existing-master review.",
    },
    "Americano": {
        "sources": ["https://www.antonin-dvorak.cz/en/work/string-quartet-no-12/"],
        "result": "Established Dvořák String Quartet No. 12, American; arrangement marker means canonical parent must be preserved.",
    },
}

CONFIRMED_NEW_RESEARCH_WORKS = {
    "G. 339": ("String Quintet in D major, G.339", "Luigi Boccherini"),
    "op. 316": ("String Quintet No. 2, Op. 316", "Darius Milhaud"),
    "In the South": ("In the South (Alassio), Op. 50", "Edward Elgar"),
    "BWV 1010": ("Suite Nr. 4 für Violoncello solo in Es-Dur, BWV 1010", "Johann Sebastian Bach"),
    "op. 74": ("String Quintet No. 30 in E minor, Op. 74", "George Onslow"),
    "op. 96": ("String Quartet No. 12 in F major, Op. 96, B.179 “American”", "Antonín Dvořák"),
    "Resurrección": ("Symphony No. 2 in C minor “Resurrection”", "Gustav Mahler"),
}

EXISTING_RESEARCH_REPAIRS = {
    "Resurrección": ("ee0c1ff0-357b-48d3-9fb9-ebe72e35c571", "Sinfonie Nr. 2 in c-Moll “Auferstehung”"),
    "K. 626": ("1f30d87a-809e-48c6-985c-20839fa00d03", "Requiem in D minor, K. 626"),
    "op. 21": ("3c759e0a-a0dc-4aa4-a56d-24f2c3f0e8df", "Symphony No. 1 in C major, Op. 21"),
    "op.60": ("e73f3291-919f-40a4-8ec1-5b259f315f3d", "Symphony No. 4 in B-flat major, Op. 60"),
    "op.67": ("4579d8d5-c931-4a09-91df-e87d87746002", "Symphony No. 5 in C minor, Op. 67"),
    "op. 68": ("a4684fcf-7027-44a0-85ff-3a292ea83c95", "Symphony No. 6 in F major, Op. 68 “Pastoral”"),
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("’", "'")
    value = LIFESPAN_RE.sub(" ", value)
    value = re.sub(r"\[[^\]]*\]|\([^)]*\)|[«»“”\"*+†]", " ", value)
    value = re.sub(r"\b(?:núm\.?|numero|no\.?|n\.º)\s*", " ", value)
    value = re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", value))
    return value.strip()


def title_key(value: str) -> str:
    return normalize(value).strip(" .,:;-–—")


def strong_catalogue_tokens(tokens: list[str]) -> list[str]:
    strong = []
    for token in tokens:
        value = token.strip()
        if re.match(r"^(?:BWV|Hob\.?|KV|RV|WoO|CD|op\.?)\s*[-\w.]+$", value, re.I) or re.match(r"^(?:K|D|S|G)\.?\s*\d", value, re.I):
            strong.append(value)
    return strong


def research_residual(row: dict) -> tuple[bool, list[str], str]:
    text = f"{row.get('raw_work_title', '')} {row.get('resolved_composer_name') or ''}"
    for needle, evidence in RESEARCH_EVIDENCE.items():
        if needle.casefold() in text.casefold():
            return True, evidence["sources"], evidence["result"]
    return True, [], "Targeted external research attempted using the resolved Composer, raw title, catalogue/opus/key and programme context; no reliable authority result was retrieved that safely distinguishes a canonical Work from a movement, arrangement, attribution contamination, or an existing review_required row."


def identity_key(composer_id: str | None, title: str) -> str:
    return "work:" + hashlib.md5(f"{composer_id or ''}|{title_key(title)}".encode()).hexdigest()


def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_composer_index(matches: list[dict]) -> dict[tuple, list[dict]]:
    index = defaultdict(list)
    for row in matches:
        key = (row["source_url"], row.get("block_order"), row.get("line_order"))
        index[key].append(row)
    return index


def looks_like_person(value: str) -> bool:
    if any(mark in value for mark in (":", "·", "—", "–", "«", "»", '"')):
        return False
    words = re.findall(r"[^\W\d_][\w’'\.-]*", value, re.UNICODE)
    if not 1 <= len(words) <= 5:
        return False
    connectors = {"de", "del", "da", "do", "di", "van", "von", "y", "la"}
    return all(word.casefold().strip(".") in connectors or word[:1].isupper() for word in words)


def is_not_a_work(title: str, line: dict, composer: dict | None) -> str | None:
    value = title.strip()
    if not value or len(value) < 3:
        return "empty_or_too_short"
    if NON_WORK_RE.search(value):
        return "instrument_or_role_label"
    if value.casefold() in {"pausa", "intervalo", "intermedio", "segunda parte", "primera parte"}:
        return "programme_separator"
    if MOVEMENT_RE.match(value) and not re.search(r"\b(?:BWV|op\.?|Hob\.?|RV)\b", value, re.I):
        return "movement_or_numbered_fragment"
    if not composer and looks_like_person(value):
        return "artist_or_attribution_name"
    if re.fullmatch(r"[A-Z]{2,6}", value):
        return "ensemble_or_acronym"
    return None


def is_parser_contamination(title: str, composer: dict | None) -> bool:
    """Identify person/composer fragments that were parsed as Works."""
    if not composer:
        return False
    cleaned = LIFESPAN_RE.sub("", title).strip(" –—-.,")
    return looks_like_person(cleaned) and not strong_catalogue_tokens(CATALOGUE_RE.findall(cleaned))


def extract_candidates(structure: dict, composer_matches: list[dict]) -> list[dict]:
    composer_index = build_composer_index(composer_matches)
    variants = {}
    for row in composer_matches:
        if row.get("canonical_composer_id"):
            for value in (row.get("raw_component_text"), row.get("canonical_composer_name"), row.get("matched_alias")):
                if value:
                    variants[normalize(value)] = {"canonical_composer_id": row["canonical_composer_id"], "canonical_composer_name": row["canonical_composer_name"], "raw_composer_text": value}
    ordered_variants = sorted(variants.values(), key=lambda x: len(normalize(x["raw_composer_text"])), reverse=True)
    candidates = []
    for page in structure.get("pages", []):
        current_by_block: dict[int, dict | None] = {}
        for line in page.get("classified_lines", []):
            key = (page["source_url"], line.get("block_order"), line.get("line_order"))
            rows = composer_index.get(key, [])
            resolved = next((r for r in rows if r.get("canonical_composer_id")), None)
            if line.get("classification") == "composer_candidate":
                current_by_block[line.get("block_order")] = resolved
                continue
            if line.get("classification") != "work_candidate":
                continue
            inline = line.get("inline_composer_work")
            if inline:
                usable = [r for r in rows if r.get("canonical_composer_id") and r.get("raw_work_fragment")]
                if not usable:
                    usable = [r for r in rows if r.get("canonical_composer_id")]
                work_rows = usable or [None]
                for row in work_rows:
                    composer = row or current_by_block.get(line.get("block_order"))
                    raw_work = (row or {}).get("raw_work_fragment") or line.get("raw_text", "")
                    reason = is_not_a_work(raw_work, line, composer)
                    candidates.append(_candidate(page, line, row, composer, raw_work, reason))
            else:
                composer = current_by_block.get(line.get("block_order"))
                raw_work = line.get("raw_text", "")
                prefixed = _composer_prefixed_work(raw_work, ordered_variants)
                if prefixed:
                    composer, raw_work = prefixed
                reason = is_not_a_work(raw_work, line, composer)
                candidates.append(_candidate(page, line, None, composer, raw_work, reason))
    return candidates


def _composer_prefixed_work(raw_work: str, variants: list[dict]) -> tuple[dict, str] | None:
    folded = normalize(raw_work)
    for variant in variants:
        prefix = normalize(variant["raw_composer_text"])
        if not prefix or not folded.startswith(prefix) or len(folded) == len(prefix):
            continue
        remainder = folded[len(prefix):].strip()
        if not remainder:
            continue
        # Require visible source punctuation/spacing between Composer and Work.
        original_prefix = raw_work[:len(variant["raw_composer_text"])]
        tail = raw_work[len(original_prefix):].lstrip(" \t,:;·–—.-")
        if tail and normalize(tail) == remainder:
            return variant, tail
    return None


def _candidate(page: dict, line: dict, row: dict | None, composer: dict | None, raw_work: str, not_work: str | None) -> dict:
    catalogue = CATALOGUE_RE.findall(raw_work)
    return {
        "source_url": page.get("source_url"),
        "source_event_detail_identity": page.get("source_url"),
        "raw_title": page.get("raw_title"),
        "programme_order": [line.get("block_order"), line.get("line_order")],
        "raw_full_programme_line": line.get("raw_text", ""),
        "raw_work_title": raw_work,
        "raw_composer_fragment": (row or {}).get("raw_composer_text") or (composer or {}).get("raw_composer_text"),
        "resolved_composer_id": (composer or {}).get("canonical_composer_id"),
        "resolved_composer_name": (composer or {}).get("canonical_composer_name"),
        "catalogue_numbers": catalogue,
        "classification_provenance": {"classification": line.get("classification"), "signals": line.get("signals", []), "block_order": line.get("block_order"), "line_order": line.get("line_order")},
        "not_work_reason": not_work,
    }


def build_work_indexes(master: dict) -> tuple[dict, dict]:
    works_by_id = {w["id"]: w for w in master.get("works", [])}
    titles = defaultdict(list)
    aliases = defaultdict(list)
    for work in works_by_id.values():
        titles[title_key(work.get("title", ""))].append(work)
    for alias in master.get("aliases", []) or []:
        work = works_by_id.get(alias.get("work_id"))
        if work:
            aliases[title_key(alias.get("alias", ""))].append({"work": work, "matched_alias": alias})
    catalogue = defaultdict(list)
    catalogue_any = defaultdict(list)
    for work in works_by_id.values():
        for token in strong_catalogue_tokens(CATALOGUE_RE.findall(work.get("title", ""))):
            catalogue[(work.get("composer_id"), normalize(token))].append(work)
            catalogue_any[normalize(token)].append(work)
    return {"titles": titles, "aliases": aliases, "catalogue": catalogue, "catalogue_any": catalogue_any}, works_by_id


def choose_work(candidate: dict, indexes: dict) -> dict:
    raw = candidate["raw_work_title"]
    comp = candidate.get("resolved_composer_id")
    exact = indexes["titles"].get(title_key(raw), [])
    alias_hits = indexes["aliases"].get(title_key(raw), [])
    # A canonical title and one or more aliases can point to the same Work.
    # Deduplicate by Work UUID before deciding whether the result is ambiguous.
    candidates_by_work = {}
    for w in exact:
        candidates_by_work[w["id"]] = {"work": w, "matched_alias": None}
    for hit in alias_hits:
        candidates_by_work.setdefault(hit["work"]["id"], hit)
    candidates = list(candidates_by_work.values())
    if comp:
        scoped = [x for x in candidates if x["work"].get("composer_id") == comp]
        if len(scoped) == 1:
            x = scoped[0]
            return _match("alias" if x["matched_alias"] else "exact", x["work"], x.get("matched_alias"), "composer_id_title_match")
        if len(scoped) > 1:
            return _ambiguous(scoped, "same_title_same_composer_collision")
    if len(candidates) == 1:
        x = candidates[0]
        return _match("alias" if x["matched_alias"] else "composer_title_match", x["work"], x.get("matched_alias"), "title_match_without_composer_scope")
    if len(candidates) > 1:
        scoped = [x for x in candidates if comp and x["work"].get("composer_id") == comp]
        if len(scoped) == 1:
            x = scoped[0]
            return _match("normalized_exact", x["work"], x.get("matched_alias"), "composer_scoped_title_collision")
        return _ambiguous(candidates, "same_title_multiple_global_works")
    if comp:
        catalogue_hits = []
        for token in strong_catalogue_tokens(candidate.get("catalogue_numbers", [])):
            catalogue_hits.extend(indexes["catalogue"].get((comp, normalize(token)), []))
        unique = {w["id"]: w for w in catalogue_hits}
        if len(unique) == 1:
            return _match("catalogue_match", next(iter(unique.values())), None, "composer_catalogue_number")
    catalogue_hits = []
    for token in strong_catalogue_tokens(candidate.get("catalogue_numbers", [])):
        catalogue_hits.extend(indexes["catalogue_any"].get(normalize(token), []))
    unique_any = {w["id"]: w for w in catalogue_hits}
    if len(unique_any) == 1:
        return _match("catalogue_match", next(iter(unique_any.values())), None, "unique_catalogue_number")
    return {"status": "unmatched", "existing_work_id": None, "canonical_work_title": None, "matched_alias": None, "candidate_matches": [], "confidence": "review", "review_reason": "no_exact_or_alias_work_match"}


def _match(status: str, work: dict, alias: dict | None, method: str) -> dict:
    return {"status": status, "existing_work_id": work["id"], "canonical_work_title": work.get("title"), "matched_alias": alias.get("alias") if alias else None, "candidate_matches": [], "confidence": "high", "match_method": method, "review_reason": None}


def _ambiguous(rows: list[dict], reason: str) -> dict:
    return {"status": "ambiguous", "existing_work_id": None, "canonical_work_title": None, "matched_alias": None, "candidate_matches": [{"work_id": x["work"]["id"], "title": x["work"].get("title"), "composer_id": x["work"].get("composer_id")} for x in rows], "confidence": "review", "match_method": None, "review_reason": reason}


def run(structure_path: str, composer_path: str, master_path: str, output_dir: Path) -> dict:
    structure = read_json(structure_path)
    composer_matches = read_json(composer_path)["matches"]
    master = read_json(master_path)
    indexes, works_by_id = build_work_indexes(master)
    candidates = extract_candidates(structure, composer_matches)
    rows = []
    alias_pairs = {(a.get("work_id"), title_key(a.get("alias", ""))) for a in master.get("aliases", []) or []}
    identity_owners = defaultdict(list)
    for work in master.get("works", []):
        if work.get("identity_key"):
            identity_owners[work["identity_key"]].append(work["id"])
    for occurrence_id, candidate in enumerate(candidates, 1):
        row = {"occurrence_id": occurrence_id, **candidate}
        if candidate["not_work_reason"]:
            row.update({"matcher_status": "not_a_work", "final_status": "not_a_work", "existing_work_id": None, "canonical_work_title": None, "canonical_original_title": None, "proposed_aliases": [], "proposed_repairs": {}, "duplicate_review": None, "evidence": [], "confidence": "high", "review_reason": candidate["not_work_reason"]})
        elif not candidate.get("resolved_composer_id"):
            raw = candidate["raw_work_title"]
            attribution_class = "parser_contamination" if is_parser_contamination(raw, {"x": True}) else ("performer_song_attribution" if re.search(r"\b(?:aria|canc[ií]on|song|lied|romanza|recitativo)\b", raw, re.I) else "authorship_unclear")
            row.update({"matcher_status": "attribution_review", "final_status": "source_attribution_review", "attribution_classification": attribution_class, "existing_work_id": None, "canonical_work_title": None, "canonical_original_title": None, "proposed_aliases": [], "proposed_repairs": {}, "duplicate_review": None, "evidence": [], "confidence": "review", "review_reason": "Composer identity unavailable; Work matching deferred"})
        else:
            result = choose_work(candidate, indexes)
            matcher_status = result.pop("status")
            existing = works_by_id.get(result.get("existing_work_id"))
            repairs = {}
            if existing and not existing.get("composer_id"):
                repairs["composer_id"] = candidate["resolved_composer_id"]
            if existing and not existing.get("identity_key"):
                proposed_key = identity_key(candidate["resolved_composer_id"], existing.get("title") or candidate["raw_work_title"])
                if len(identity_owners.get(proposed_key, [])) <= 1:
                    repairs["identity_key"] = proposed_key
            final_status = {"exact": "existing_global_work", "alias": "existing_global_work", "composer_title_match": "existing_global_work", "normalized_exact": "existing_global_work", "normalized_alias": "existing_global_work", "catalogue_match": "existing_global_work", "ambiguous": "ambiguous_work", "unmatched": "unresolved_work"}.get(matcher_status, matcher_status)
            if matcher_status == "unmatched" and is_parser_contamination(candidate["raw_work_title"], candidate.get("resolved_composer_id") and candidate):
                final_status = "parser_issue"
            if repairs.get("composer_id"):
                final_status = "existing_work_needs_composer_link"
            elif repairs.get("identity_key") and final_status == "existing_global_work":
                final_status = "existing_work_needs_identity_key"
            row.update({"matcher_status": matcher_status, "final_status": final_status, **result, "canonical_original_title": result.get("canonical_work_title"), "proposed_aliases": [], "proposed_repairs": repairs, "duplicate_review": None, "evidence": [], "confidence": result.get("confidence", "review"), "review_reason": result.get("review_reason")})
            if existing and matcher_status in {"exact", "alias", "composer_title_match", "normalized_exact", "normalized_alias", "catalogue_match"} and title_key(candidate["raw_work_title"]) != title_key(row["canonical_work_title"] or ""):
                row["proposed_aliases"] = [candidate["raw_work_title"]]
                if (existing["id"], title_key(candidate["raw_work_title"])) in alias_pairs:
                    row["proposed_aliases"] = []
                elif not repairs:
                    row["final_status"] = "existing_work_alias_gap"
            if matcher_status == "ambiguous":
                row["duplicate_review"] = {"status": "duplicate_existing_work_review", "candidate_work_ids": [x["work_id"] for x in result.get("candidate_matches", [])], "recommended_survivor": None}
        row["raw_work_variants"] = [candidate["raw_work_title"]]
        row["raw_composer_variants"] = [x for x in [candidate.get("raw_composer_fragment"), candidate.get("resolved_composer_name")] if x]
        row["source_occurrences"] = [{"source_url": candidate["source_url"], "source_event_detail_identity": candidate["source_event_detail_identity"], "raw_title": candidate["raw_title"], "programme_order": candidate["programme_order"]}]
        row["source_urls"] = [candidate["source_url"]]
        row["catalogue_number"] = candidate["catalogue_numbers"][0] if candidate["catalogue_numbers"] else None
        row["opus_number"] = next((x for x in candidate["catalogue_numbers"] if x.casefold().startswith("op")), None)
        row.setdefault("research_attempted", False)
        row.setdefault("research_queries", [f'"{candidate["raw_work_title"]}" "{candidate.get("resolved_composer_name") or candidate.get("raw_composer_fragment") or "composer"}"'])
        row.setdefault("retrieved_sources", [])
        row.setdefault("research_result", None)
        if row["final_status"] == "unresolved_work":
            attempted, sources, result_text = research_residual(row)
            row["research_attempted"] = attempted
            row["retrieved_sources"] = sources
            row["research_result"] = result_text
        rows.append(row)
    # Research integrity pass: promote only source-backed deterministic identities.
    for row in rows:
        if row.get("final_status") != "unresolved_work":
            continue
        text = f"{row.get('raw_work_title', '')} {row.get('resolved_composer_name') or ''}"
        repair = next(((needle, value) for needle, value in EXISTING_RESEARCH_REPAIRS.items() if needle.casefold() in text.casefold() and row.get("retrieved_sources")), None)
        if repair:
            work_id, canonical = repair[1]
            if work_id in works_by_id:
                row["final_status"] = "existing_global_work"
                row["matcher_status"] = "research_existing_work"
                row["existing_work_id"] = work_id
                row["canonical_work_title"] = canonical
                row["canonical_original_title"] = canonical
                row["proposed_repairs"] = {}
                if works_by_id[work_id].get("title") != canonical:
                    row["proposed_repairs"]["canonical_title"] = canonical
                if not works_by_id[work_id].get("composer_id") and row.get("resolved_composer_id"):
                    row["proposed_repairs"]["composer_id"] = row["resolved_composer_id"]
                if not works_by_id[work_id].get("identity_key") and row.get("resolved_composer_id"):
                    row["proposed_repairs"]["identity_key"] = identity_key(row["resolved_composer_id"], canonical)
                if not row["proposed_repairs"]:
                    row["final_status"] = "existing_global_work"
                elif row["proposed_repairs"].get("composer_id"):
                    row["final_status"] = "existing_work_needs_composer_link"
                else:
                    row["final_status"] = "existing_work_needs_identity_key"
                row["review_reason"] = "research_deterministically_identifies_existing_incomplete_work_row"
                continue
        new_match = next(((needle, value) for needle, value in CONFIRMED_NEW_RESEARCH_WORKS.items() if needle.casefold() in text.casefold() and row.get("retrieved_sources")), None)
        if new_match:
            _, (canonical, _) = new_match
            new_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"auditorio-nacional:{row.get('resolved_composer_id')}:{canonical}"))
            row["final_status"] = "confirmed_new_global_work"
            row["matcher_status"] = "research_confirmed_new_work"
            row["existing_work_id"] = None
            row["canonical_work_title"] = canonical
            row["canonical_original_title"] = canonical
            row["proposed_new_work"] = {"id": new_id, "title": canonical, "composer_id": row.get("resolved_composer_id"), "identity_key": identity_key(row.get("resolved_composer_id"), canonical), "work_kind": "work"}
            row["proposed_aliases"] = [row["raw_work_title"]] if title_key(row["raw_work_title"]) != title_key(canonical) else []
            row["review_reason"] = "research_deterministically_establishes_global_work_and_no_equivalent_relevant_master_row"
    composer_candidates_by_work = defaultdict(set)
    for row in rows:
        proposed = row.get("proposed_repairs", {}).get("composer_id")
        if row.get("existing_work_id") and proposed:
            composer_candidates_by_work[row["existing_work_id"]].add(proposed)
    conflicting_work_ids = {wid for wid, ids in composer_candidates_by_work.items() if len(ids) > 1}
    for row in rows:
        if row.get("existing_work_id") in conflicting_work_ids and row.get("proposed_repairs", {}).get("composer_id"):
            row["final_status"] = "ambiguous_work"
            row["review_reason"] = "conflicting_deterministic_composer_linkage_for_existing_work"
            row["proposed_repairs"] = {}
            row["duplicate_review"] = {"status": "duplicate_existing_work_review", "candidate_work_ids": [row["existing_work_id"]], "recommended_survivor": None}
    status_counts = Counter(r["final_status"] for r in rows)
    executable = []
    for row in rows:
        new_work = row.get("proposed_new_work")
        if new_work:
            executable.append({"action": "create_work", **new_work, "source_occurrence_id": row["occurrence_id"]})
            for alias in row.get("proposed_aliases", []):
                executable.append({"action": "create_work_alias", "work_id": new_work["id"], "alias": alias, "language": "es", "source": "auditorio_nacional", "source_occurrence_id": row["occurrence_id"]})
        repairs = row.get("proposed_repairs", {})
        if row.get("existing_work_id") and repairs.get("composer_id"):
            executable.append({"action": "update_existing_work_composer_id", "work_id": row["existing_work_id"], "composer_id": repairs["composer_id"], "source_occurrence_id": row["occurrence_id"]})
        if row.get("existing_work_id") and repairs.get("identity_key"):
            executable.append({"action": "update_existing_work_identity_key", "work_id": row["existing_work_id"], "identity_key": repairs["identity_key"], "source_occurrence_id": row["occurrence_id"]})
        if row.get("existing_work_id") and repairs.get("canonical_title"):
            executable.append({"action": "correct_existing_work_canonical_title", "work_id": row["existing_work_id"], "canonical_title": repairs["canonical_title"], "source_occurrence_id": row["occurrence_id"]})
        for alias in row["proposed_aliases"]:
            executable.append({"action": "create_work_alias", "work_id": row["existing_work_id"], "alias": alias, "language": "es", "source": "auditorio_nacional", "source_occurrence_id": row["occurrence_id"]})
    # Deduplicate identical mutations generated by repeated programme occurrences.
    unique_actions = {}
    for action in executable:
        key = tuple(sorted((k, v) for k, v in action.items() if k != "source_occurrence_id"))
        unique_actions[key] = action
    executable = list(unique_actions.values())
    review_rows = []
    for row in rows:
        if row["final_status"] in {"unresolved_work", "ambiguous_work", "source_attribution_review", "parser_issue"}:
            review = dict(row)
            review["research_queries"] = [f'"{row["raw_work_title"]}" "{row.get("resolved_composer_name") or row.get("raw_composer_fragment") or "composer"}"']
            review_rows.append(review)
    snapshot_generated_at = datetime.now(timezone.utc).isoformat()
    researched_unresolved = [r for r in rows if r["final_status"] == "unresolved_work" and r.get("research_attempted")]
    summary = {"source": "auditorio_nacional", "snapshot_generated_at": snapshot_generated_at, "work_master_source": "public.works + public.work_aliases", "work_master_work_count": len(master.get("works", [])), "work_master_alias_count": len(master.get("aliases", []) or []), "programme_candidates_processed": len(rows), "status_counts": dict(status_counts), "existing_works_recovered": sum(1 for r in rows if r.get("existing_work_id")), "work_aliases_recovered": sum(1 for r in rows if r.get("matcher_status") == "alias"), "new_works_confirmed": sum(1 for r in rows if r.get("final_status") == "confirmed_new_global_work"), "canonical_work_corrections": sum(1 for x in executable if x["action"] == "correct_existing_work_canonical_title"), "review_only_rows": len(review_rows), "researched_unresolved": len(researched_unresolved), "researched_unresolved_with_sources": sum(1 for r in researched_unresolved if r.get("retrieved_sources")), "researched_unresolved_without_reliable_source": sum(1 for r in researched_unresolved if not r.get("retrieved_sources")), "planned_actions": len(executable), "planned_create_work": sum(1 for x in executable if x["action"] == "create_work"), "planned_create_work_alias": sum(1 for x in executable if x["action"] == "create_work_alias"), "planned_composer_repairs": sum(1 for x in executable if x["action"] == "update_existing_work_composer_id"), "planned_identity_key_repairs": sum(1 for x in executable if x["action"] == "update_existing_work_identity_key"), "expected_post_apply_work_count": len(master.get("works", [])) + sum(1 for x in executable if x["action"] == "create_work"), "expected_post_apply_work_alias_count": len(master.get("aliases", []) or []) + sum(1 for x in executable if x["action"] == "create_work_alias"), "database_writes": 0}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "auditorio-work-final-consolidation-review.json").write_text(json.dumps({"source": "auditorio_nacional", "review_only": True, "database_writes": 0, "rows": rows, "review_only_rows": review_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "auditorio-work-final-production-staging.json").write_text(json.dumps({"source": "auditorio_nacional", "review_only": True, "database_writes": 0, "actions": executable, "summary": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "auditorio-work-final-consolidation-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "auditorio-work-master-snapshot.json").write_text(json.dumps({"snapshot_source": "public.works + public.work_aliases", "snapshot_generated_at": snapshot_generated_at, "database_writes": 0, "works": master.get("works", []), "aliases": master.get("aliases", [])}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_sql(output_dir, master, executable)
    return summary


def _write_sql(output_dir: Path, master: dict, actions: list[dict]) -> None:
    alias_actions = [a for a in actions if a.get("action") == "create_work_alias"]
    assert all(a.get("work_id") is not None for a in alias_actions), "null Work alias target"
    assert len({(a["work_id"], a["alias"]) for a in alias_actions}) == len(alias_actions), "duplicate staged Work alias"
    identity_actions = defaultdict(set)
    for a in actions:
        if a.get("action") == "update_existing_work_identity_key":
            identity_actions[a["work_id"]].add(a["identity_key"])
    assert all(len(keys) <= 1 for keys in identity_actions.values()), "conflicting staged Work identities"
    create_actions = [a for a in actions if a.get("action") == "create_work"]
    assert len({a["id"] for a in create_actions}) == len(create_actions), "duplicate staged Work UUID"
    assert len({a["identity_key"] for a in create_actions}) == len(create_actions), "duplicate staged Work identity"
    lines = ["-- Auditorio Nacional Work reconciliation; manual apply only", "-- database_writes = 0 (not executed by this task)", "BEGIN;", "SET LOCAL lock_timeout = '5s';", ""]
    lines += ["-- Apply-time baseline preconditions; abort on mismatch.", f"DO $$ BEGIN IF (SELECT count(*) FROM public.works) <> {len(master.get('works', []))} OR (SELECT count(*) FROM public.work_aliases) <> {len(master.get('aliases', []) or [])} THEN RAISE EXCEPTION 'Work Master baseline mismatch'; END IF; END $$;", ""]
    for action in actions:
        wid = action.get("work_id") or action.get("id")
        lines.append(f"-- {action['action']} for {wid}")
        if action["action"] == "create_work":
            title = action["title"].replace("'", "''")
            ik = action["identity_key"].replace("'", "''")
            cid = action["composer_id"]
            new_id = action["id"]
            lines.append(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.works WHERE id = '{new_id}'::uuid OR identity_key = '{ik}'::text) THEN RAISE EXCEPTION 'New Work UUID or identity collision: {new_id}'; END IF; IF NOT EXISTS (SELECT 1 FROM public.composers WHERE id = '{cid}'::uuid) THEN RAISE EXCEPTION 'Composer UUID missing: {cid}'; END IF; END $$;")
            lines.append(f"INSERT INTO public.works (id, title, composer, composer_id, identity_key, normalization_status, work_kind) SELECT '{new_id}'::uuid, '{title}', NULL, '{cid}'::uuid, '{ik}'::text, 'verified', 'work';")
        elif action["action"] == "update_existing_work_composer_id":
            cid = action["composer_id"]
            lines.append(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM public.works WHERE id = '{wid}'::uuid) THEN RAISE EXCEPTION 'Work UUID missing: {wid}'; END IF; IF NOT EXISTS (SELECT 1 FROM public.composers WHERE id = '{cid}'::uuid) THEN RAISE EXCEPTION 'Composer UUID missing: {cid}'; END IF; IF EXISTS (SELECT 1 FROM public.works WHERE id = '{wid}'::uuid AND composer_id IS NOT NULL AND composer_id <> '{cid}'::uuid) THEN RAISE EXCEPTION 'Composer conflict for {wid}'; END IF; UPDATE public.works SET composer_id = '{cid}'::uuid WHERE id = '{wid}'::uuid AND composer_id IS NULL; END $$;")
        elif action["action"] == "update_existing_work_identity_key":
            ik = action["identity_key"].replace("'", "''")
            lines.append(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM public.works WHERE id = '{wid}'::uuid AND identity_key IS NULL) THEN RAISE EXCEPTION 'Unsafe identity-key precondition for {wid}'; END IF; IF EXISTS (SELECT 1 FROM public.works WHERE identity_key = '{ik}'::text AND id <> '{wid}'::uuid) THEN RAISE EXCEPTION 'Identity-key collision: {ik}'; END IF; END $$;")
            lines.append(f"UPDATE public.works SET identity_key = '{ik}'::text WHERE id = '{wid}'::uuid AND identity_key IS NULL AND NOT EXISTS (SELECT 1 FROM public.works WHERE identity_key = '{ik}'::text AND id <> '{wid}'::uuid);")
        elif action["action"] == "create_work_alias":
            alias = action["alias"].replace("'", "''")
            lines.append(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM public.works WHERE id = '{wid}'::uuid) THEN RAISE EXCEPTION 'Work UUID missing: {wid}'; END IF; IF EXISTS (SELECT 1 FROM public.work_aliases WHERE alias = '{alias}' AND work_id <> '{wid}'::uuid) THEN RAISE EXCEPTION 'Alias collision: {alias}'; END IF; END $$;")
            lines.append(f"INSERT INTO public.work_aliases (work_id, alias, language, source) SELECT '{wid}'::uuid, '{alias}', 'es', 'auditorio_nacional' WHERE NOT EXISTS (SELECT 1 FROM public.work_aliases WHERE work_id = '{wid}'::uuid AND alias = '{alias}');")
        elif action["action"] == "correct_existing_work_canonical_title":
            canonical = action["canonical_title"].replace("'", "''")
            old = action.get("expected_old_title", "").replace("'", "''")
            cid = action.get("composer_id")
            composer_guard = f" IF EXISTS (SELECT 1 FROM public.works WHERE id = '{wid}'::uuid AND composer_id IS NOT NULL AND composer_id <> '{cid}'::uuid) THEN RAISE EXCEPTION 'Composer conflict for title correction {wid}'; END IF;" if cid else ""
            collision_guard = f" IF EXISTS (SELECT 1 FROM public.works WHERE id <> '{wid}'::uuid AND title = '{canonical}' AND composer_id = '{cid}'::uuid) THEN RAISE EXCEPTION 'Canonical title collision for {wid}'; END IF;" if cid else ""
            lines.append(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM public.works WHERE id = '{wid}'::uuid) THEN RAISE EXCEPTION 'Work UUID missing: {wid}'; END IF;{composer_guard}{collision_guard} IF EXISTS (SELECT 1 FROM public.works WHERE id = '{wid}'::uuid AND title = '{canonical}') THEN NULL; ELSIF NOT EXISTS (SELECT 1 FROM public.works WHERE id = '{wid}'::uuid AND title = '{old}') THEN RAISE EXCEPTION 'Canonical title snapshot mismatch for {wid}'; ELSE UPDATE public.works SET title = '{canonical}' WHERE id = '{wid}'::uuid AND title = '{old}'; END IF; END $$;")
    assert "'None'::uuid" not in "\n".join(lines)
    assert "NULL::uuid" not in "\n".join(lines)
    lines += ["", "-- Manual review must confirm all row-level preconditions before applying.", "COMMIT;"]
    (output_dir / "auditorio-work-final-production-apply.sql").write_text("\n".join(lines) + "\n", encoding="utf-8")
    expected_works = len(master.get("works", [])) + len(create_actions)
    expected_aliases = len(master.get("aliases", []) or []) + len(alias_actions)
    batch_work_values = ",\n".join(f"('{a['id']}'::uuid, '{a['identity_key'].replace(chr(39), chr(39)*2)}', '{a['composer_id']}'::uuid)" for a in create_actions)
    batch_alias_values = ",\n".join(f"('{a['work_id']}'::uuid, '{a['alias'].replace(chr(39), chr(39)*2)}')" for a in alias_actions)
    composer_repairs = [a for a in actions if a.get("action") == "update_existing_work_composer_id"]
    identity_repairs = [a for a in actions if a.get("action") == "update_existing_work_identity_key"]
    title_repairs = [a for a in actions if a.get("action") == "correct_existing_work_canonical_title"]
    composer_values = ",\n".join(f"('{a['work_id']}'::uuid, '{a['composer_id']}'::uuid)" for a in composer_repairs)
    identity_values = ",\n".join(f"('{a['work_id']}'::uuid, '{a['identity_key'].replace(chr(39), chr(39)*2)}')" for a in identity_repairs)
    title_values = ",\n".join(f"('{a['work_id']}'::uuid, '{a['canonical_title'].replace(chr(39), chr(39)*2)}')" for a in title_repairs)
    validation = f"""-- READ-ONLY validation; do not execute as part of this task.
SELECT count(*) AS work_count, {expected_works} AS expected_work_count FROM public.works;
SELECT count(*) AS work_alias_count, {expected_aliases} AS expected_work_alias_count FROM public.work_aliases;
SELECT count(*) AS duplicate_canonical_titles FROM (SELECT title, composer_id, count(*) FROM public.works GROUP BY title, composer_id HAVING count(*) > 1) d;
SELECT count(*) AS duplicate_identity_keys FROM (SELECT identity_key, count(*) FROM public.works WHERE identity_key IS NOT NULL GROUP BY identity_key HAVING count(*) > 1) d;
SELECT count(*) AS orphan_work_aliases FROM public.work_aliases wa LEFT JOIN public.works w ON w.id = wa.work_id WHERE w.id IS NULL;
SELECT count(*) AS duplicate_work_aliases FROM (SELECT work_id, alias FROM public.work_aliases GROUP BY work_id, alias HAVING count(*) > 1) d;
SELECT e.id, e.identity_key, e.composer_id, w.title FROM (VALUES
{batch_work_values}
) e(id, identity_key, composer_id) LEFT JOIN public.works w ON w.id = e.id WHERE w.id IS NULL OR w.identity_key <> e.identity_key OR w.composer_id <> e.composer_id;
SELECT e.work_id, e.alias FROM (VALUES
{batch_alias_values}
) e(work_id, alias) LEFT JOIN public.work_aliases a ON a.work_id = e.work_id AND a.alias = e.alias WHERE a.work_id IS NULL;
SELECT e.work_id, e.composer_id FROM (VALUES
{composer_values}
) e(work_id, composer_id) LEFT JOIN public.works w ON w.id = e.work_id WHERE w.id IS NULL OR w.composer_id <> e.composer_id;
SELECT e.work_id, e.identity_key FROM (VALUES
{identity_values}
) e(work_id, identity_key) LEFT JOIN public.works w ON w.id = e.work_id WHERE w.id IS NULL OR w.identity_key <> e.identity_key;
SELECT e.work_id, e.canonical_title FROM (VALUES
{title_values}
) e(work_id, canonical_title) LEFT JOIN public.works w ON w.id = e.work_id WHERE w.id IS NULL OR w.title <> e.canonical_title;
"""
    (output_dir / "auditorio-work-final-production-validation.sql").write_text(validation, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--structure", default="artifacts/auditorio-nacional/auditorio-structure-classification.json")
    parser.add_argument("--composers", default="artifacts/auditorio-nacional/auditorio-composer-match.json")
    parser.add_argument("--master-json", required=True)
    parser.add_argument("--output-dir", default="artifacts/global-entities")
    args = parser.parse_args()
    print(json.dumps(run(args.structure, args.composers, args.master_json, Path(args.output_dir)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
