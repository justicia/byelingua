"""Auditorio Nacional Phase 3.1 global Composer matcher dry-run.

The matcher consumes only the validated Phase 2.3 classification artifact.  It
loads the current global Composer Master read-only, writes reproducible
snapshots, and never creates entities or aliases.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LIFESPAN_RE = re.compile(r"\s*\((?:\*|ca\.\s*)?\d{3,4}(?:\s*[–—-]\s*(?:\*|ca\.\s*)?\d{2,4})?\s*\)\s*$", re.I)
INCOMPLETE_LIFESPAN_RE = re.compile(r"\s*\(\s*\d{3,4}\s*$")
MALFORMED_MARKERS = {"universo"}
ATTRIBUTION_ONLY = {"sinatra", "bocelli", "e. piaf", "braulio"}
NON_PERSON = {"tradicional", "anónimo", "anonymous", "traditional"}
ROLE_WORDS = re.compile(r"\b(?:soprano|mezzosoprano|tenor|bar[ií]tono|bajo|contratenor|cantante|piano|viol[ií]n|director(?:a)?|coro|órgano|clave)\b", re.I)
CATALOGUE_WORDS = re.compile(r"\b(?:BWV|Op\.?|W\.?|Hob\.?|K\.?|KV|RV|CD)\b|\b(?:sinfon[ií]a|concierto|sonata|obertura|suite|polka|vals|marcha|canzon|milonga|rhapsody|gloria|pasión|danzas?|czárdás|souvenirs)\b", re.I)
WORK_CONTAMINATION_WORDS = re.compile(r"\b(?:durch adams fall|eine sammlung von liedern|souvenirs de voyage|de salomé)\b", re.I)
ROMAN_ONLY_RE = re.compile(r"^[IVXLCDM]+(?:\.?|\))?$", re.I)
FALSE_POSITIVE_BY_CONTEXT = {
    "jocan": "ensemble_or_organization_fragment",
    "obc": "ensemble_or_organization_fragment",
    "agrippina": "cast_role_or_character_fragment",
    "poppea": "cast_role_or_character_fragment",
    "ottone": "cast_role_or_character_fragment",
    "nerone": "cast_role_or_character_fragment",
    "claudio": "cast_role_or_character_fragment",
    "pallante": "cast_role_or_character_fragment",
    "narciso": "cast_role_or_character_fragment",
    "tenor": "performer_role_fragment",
    "piano": "instrument_role_fragment",
    "bailarín": "performer_role_fragment",
    "barítono-bajo": "performer_role_fragment",
    "directora pequeños cantores": "performer_role_fragment",
    "palacio real de madrid": "place_or_institution_attribution",
    "xácara de reyes": "work_or_programme_fragment",
}


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def strip_lifespan(value: str) -> str:
    return normalize_space(INCOMPLETE_LIFESPAN_RE.sub("", LIFESPAN_RE.sub("", value)))


def proposed_alias(value: str) -> str:
    # Remove source-only programme numbering in addition to lifespan syntax;
    # preserve the untouched spelling in raw_source_values/evidence.
    return normalize_space(re.sub(r"^\s*\d+\.\s*", "", strip_lifespan(value)))


def lookup_normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", strip_lifespan(value))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("’", "'")
    return normalize_space(re.sub(r"[^\w]+", " ", value, flags=re.UNICODE))


def exact_normalize(value: str) -> str:
    return strip_lifespan(value).casefold()


def split_components(raw: str) -> list[str]:
    return [part.strip() for part in raw.split("/") if part.strip()] or [raw]


def _tokens(value: str) -> list[str]:
    return re.findall(r"[\wÀ-ÿ]+", strip_lifespan(value), flags=re.UNICODE)


def _surface_candidates(raw: str, indexes: dict) -> list[dict]:
    """Return canonical/alias rows whose surface spelling begins the source."""
    candidates = []
    surfaces = []
    for key_rows in indexes["exact"].values():
        for row in key_rows:
            surface = row.get("matched_alias") or row["canonical_name"]
            surfaces.append((surface, row))
    for surface, row in sorted(surfaces, key=lambda item: len(item[0]), reverse=True):
        if raw.casefold().startswith(surface.casefold()):
            tail = raw[len(surface):]
            if not tail or tail[0] in " \t,:;–—-·.":
                candidates.append({"surface": raw[:len(surface)], "row": row, "tail": tail.lstrip(" \t,:;–—-·.")})
    return candidates


def recover_existing_identity(raw: str, indexes: dict) -> dict | None:
    """Conservative surname/initial recovery against the complete global master."""
    clean = strip_lifespan(raw)
    words = _tokens(clean)
    if not words or ROMAN_ONLY_RE.fullmatch(clean):
        return None
    surname = lookup_normalize(words[-1])
    candidates_by_id = {}
    for variant, row in indexes["variants"]:
        variant_words = _tokens(variant)
        if variant_words and lookup_normalize(variant_words[-1]) == surname:
            candidates_by_id[row["id"]] = row
    candidates = list(candidates_by_id.values())
    if not candidates:
        return None
    initial_words = words[:-1]
    if initial_words and not all(len(word) == 1 for word in initial_words if word.casefold() not in {"van", "von", "de", "di", "da"}):
        return None
    if initial_words:
        initials = [word[0].casefold() for word in initial_words if word.casefold() not in {"van", "von", "de", "di", "da"}]
        compatible = []
        for row in candidates:
            canonical_words = _tokens(row["canonical_name"])
            canonical_initials = [word[0].casefold() for word in canonical_words[:-1]]
            if len(initials) <= len(canonical_initials) and all(a == b for a, b in zip(initials, canonical_initials)):
                compatible.append(row)
        candidates = compatible
    if len(candidates) == 1:
        row = candidates[0]
        return {"composer_id": row["id"], "canonical_name": row["canonical_name"], "match_method": "deterministic_initial_surname" if initial_words else "deterministic_surname", "confidence": "high"}
    return {"ambiguous": True, "candidate_matches": [{"composer_id": row["id"], "canonical_name": row["canonical_name"]} for row in candidates]}


def sanitize_inline(item: dict, indexes: dict) -> tuple[str, str | None, str | None]:
    """Repair only structured extraction; never rewrite raw source fields."""
    raw = item["raw_composer_text"]
    fragment = item["raw_component_text"]
    if item.get("classification_source") != "inline_composer_work":
        return fragment, None, None
    if lookup_normalize(fragment) in item.get("page_artist_names", set()):
        return fragment, None, "performer_attribution"
    if re.fullmatch(r"J\.-P\.\s*Rameau", raw, re.I):
        return raw.strip(), None, "preserved_initial_group"
    role_match = ROLE_WORDS.search(raw)
    uppercase_performer = re.match(r"^[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ' -]{3,}\s+[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ' -]{2,}\s+", raw)
    if role_match and ((f"({fragment})" in raw) or (uppercase_performer and role_match.start() > 0)):
        return fragment, None, "cast_or_role_contamination"
    if re.search(r"\b(?:orquesta|joven orquesta|coro|ensemble)\b", raw, re.I) and (f"({fragment})" in raw or fragment.isupper()):
        return fragment, None, "ensemble_or_organization_fragment"
    # Work-first rows with an explicit parenthetical composer retain the full
    # opus/catalogue text as Work, including the number before the parenthesis.
    parenthetical = re.search(r"\(([^()]+)\)\s*$", raw)
    if parenthetical:
        recovered_parenthetical = recover_existing_identity(parenthetical.group(1), indexes)
        if recovered_parenthetical and not recovered_parenthetical.get("ambiguous"):
            return parenthetical.group(1).strip(), raw[:parenthetical.start()].strip(), "sanitized_parenthetical_composer"
    # Explicit `de NAME` attribution wins over trailing annotation markers.
    for surface, _row in sorted(indexes["variants"], key=lambda item: len(item[0]), reverse=True):
        match = re.search(r"\bde\s+" + re.escape(surface), raw, re.I)
        if match:
            start = match.start() + len(match.group(0)) - len(surface)
            return raw[start:start + len(surface)], raw[:match.start()].strip(), "sanitized_de_composer_attribution"
    # Composer: Work has stronger structure than Work (Subtitle).
    if ":" in raw:
        composer_text, work_text = raw.split(":", 1)
        recovered_colon = recover_existing_identity(composer_text.strip(), indexes)
        if recovered_colon and not recovered_colon.get("ambiguous"):
            return composer_text.strip(), work_text.strip(), "sanitized_composer_colon_work"
    # First recover a composer prefix from the untouched line. This handles
    # MAHLER/ELGAR/BEETHOVEN, Bernstein, Vivaldi, and safe initial groups.
    prefix = _surface_candidates(raw, indexes)
    if prefix:
        hit = prefix[0]
        if hit["tail"]:
            return hit["surface"], hit["tail"], "sanitized_composer_work_prefix"
    first_word = re.match(r"^([\wÀ-ÿ]+)(?=\s|[:,·-])", raw, re.UNICODE)
    if first_word:
        recovered = recover_existing_identity(first_word.group(1), indexes)
        if recovered and not recovered.get("ambiguous"):
            tail = raw[first_word.end():].lstrip(" \t,:;–—-·.")
            if tail:
                return first_word.group(1), tail, "sanitized_surname_work_prefix"
    catalogue_prefix = re.match(r"^(.+?)(?:,\s*|\s+)(?:BWV|Op\.?|W\.?|Hob\.?|K\.?|KV|RV|CD)\b", fragment, re.I)
    if catalogue_prefix and recover_existing_identity(catalogue_prefix.group(1), indexes):
        return catalogue_prefix.group(1).strip(), None, "sanitized_catalogue_suffix"
    # Work-first rows: find a deterministic global name after a sentence dot.
    for name in sorted(indexes["composers"].values(), key=lambda row: len(row["canonical_name"]), reverse=True):
        marker = ". " + name["canonical_name"]
        position = raw.casefold().rfind(marker.casefold())
        if position >= 0:
            return raw[position + 2:].strip(), raw[:position].strip(), "sanitized_trailing_composer"
    trailing = re.search(r"\.\s+(\d+\.\s+)?(.+?\s*\([^)]*\))$", raw)
    if trailing:
        trailing_text = trailing.group(2).strip()
        trailing_matches = unique_matches(
            indexes["exact"].get(exact_normalize(trailing_text), []),
            trailing_text,
        )
        recovered_trailing = recover_existing_identity(trailing_text, indexes)
        if len(trailing_matches) == 1 or (recovered_trailing and not recovered_trailing.get("ambiguous")):
            return trailing_text, raw[:trailing.start()].strip(), "sanitized_trailing_composer"
    # A parenthesized attribution is usable only when it resolves and the line
    # is not a performer/cast structure.
    parenthetical = re.search(r"\(([^()]+)\)", raw)
    if parenthetical:
        parenthetical_text = parenthetical.group(1).strip()
        # Prefer an exact existing alias before surname/initial recovery;
        # shared surnames can make recovery ambiguous even when the source
        # gives a deterministic alias such as A. Márquez.
        parenthetical_matches = unique_matches(
            indexes["exact"].get(exact_normalize(parenthetical_text), []),
            parenthetical_text,
        )
        if len(parenthetical_matches) == 1:
            return parenthetical_text, raw[:parenthetical.start()].strip(), "sanitized_parenthetical_composer"
        if recover_existing_identity(parenthetical_text, indexes):
            return parenthetical_text, raw[:parenthetical.start()].strip(), "sanitized_parenthetical_composer"
    recovered_fragment = recover_existing_identity(fragment, indexes)
    if recovered_fragment and not recovered_fragment.get("ambiguous"):
        return fragment, None, None
    if CATALOGUE_WORDS.search(fragment) or WORK_CONTAMINATION_WORDS.search(fragment) or re.fullmatch(r"[A-Z](?:\.[A-Z])+\.?", fragment.strip()) or ROMAN_ONLY_RE.fullmatch(fragment.strip()):
        return fragment, None, "work_or_catalogue_fragment"
    return fragment, None, None


def page_artist_context(page: dict) -> set[str]:
    names = set()
    for line in page.get("classified_lines", []):
        raw = normalize_space(line.get("raw_text", ""))
        signals = set(line.get("signals", []))
        if line.get("classification") in {"artist_candidate", "cast_candidate", "artistic_team_candidate"} or signals.intersection({"artist_role_override", "artist_role_lookahead_override", "artist_or_credit_signal", "ensemble_override", "cast_separator"}):
            names.add(lookup_normalize(raw))
        if "cast_separator" in signals and "–" in raw:
            names.add(lookup_normalize(raw.rsplit("–", 1)[1].strip()))
        role = ROLE_WORDS.search(raw)
        if role and ("(" in raw or "," in raw):
            base = raw.split("(", 1)[0].strip().rstrip(",")
            if base:
                names.add(lookup_normalize(base))
    return names


def fetch_master(url: str, key: str) -> dict:
    rows = {}
    aliases = []
    for table, params in (
        ("composers", {"select": "id,canonical_name,identity_key", "order": "canonical_name,id"}),
        ("composer_aliases", {"select": "alias,composer_id", "order": "alias,composer_id"}),
    ):
        query = urlencode(params)
        req = Request(f"{url.rstrip('/')}/rest/v1/{table}?{query}", headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not isinstance(data, list):
            raise RuntimeError(f"Supabase {table} read did not return rows")
        if table == "composers":
            rows = {row["id"]: row for row in data}
        else:
            aliases = data
    return {"composers": list(rows.values()), "aliases": aliases}


def build_indexes(master: dict) -> dict:
    composers = {row["id"]: row for row in master["composers"]}
    exact = defaultdict(list)
    normalized = defaultdict(list)
    variants = []
    for row in composers.values():
        item = {"composer_id": row["id"], "canonical_name": row["canonical_name"], "identity_key": row.get("identity_key"), "match_method": "canonical_name"}
        exact[exact_normalize(row["canonical_name"])].append(item)
        normalized[lookup_normalize(row["canonical_name"])].append(item)
        variants.append((row["canonical_name"], row))
    for alias in master["aliases"]:
        composer = composers.get(alias.get("composer_id"))
        if not composer or not alias.get("alias"):
            continue
        item = {"composer_id": composer["id"], "canonical_name": composer["canonical_name"], "identity_key": composer.get("identity_key"), "matched_alias": alias["alias"], "match_method": "composer_alias"}
        exact[exact_normalize(alias["alias"])].append(item)
        normalized[lookup_normalize(alias["alias"])].append(item)
        variants.append((alias["alias"], composer))
    return {"composers": composers, "exact": exact, "normalized": normalized, "variants": variants}


def fuzzy_candidates(raw: str, indexes: dict) -> list[dict]:
    target = lookup_normalize(raw)
    scored = []
    for key, rows in indexes["normalized"].items():
        score = difflib.SequenceMatcher(None, target, key).ratio()
        if score >= 0.86:
            for row in rows:
                scored.append({"composer_id": row["composer_id"], "canonical_name": row["canonical_name"], "score": round(score, 4)})
    return sorted({row["composer_id"]: row for row in scored}.values(), key=lambda r: r["score"], reverse=True)[:5]


def unique_matches(matches: list[dict], raw: str) -> dict[str, dict]:
    """Deduplicate IDs while retaining the source spelling for matched_alias."""
    wanted = strip_lifespan(raw).casefold()
    selected = {}
    for row in matches:
        current = selected.get(row["composer_id"])
        if current is None or (row.get("matched_alias") or "").casefold() == wanted:
            selected[row["composer_id"]] = row
    return selected


def false_positive_reason(raw: str, item: dict) -> str | None:
    key = lookup_normalize(raw)
    classification = item["classification_source"]
    signals = " ".join(item.get("classification_signals", [])).casefold()
    if classification not in {"composer_candidate", "inline_composer_work", "composer_attribution"}:
        return "unapproved_classification"
    if item.get("sanitation_reason") in {"cast_or_role_contamination", "ensemble_or_organization_fragment", "work_or_catalogue_fragment", "performer_attribution"}:
        return item["sanitation_reason"]
    if classification == "inline_composer_work" and (WORK_CONTAMINATION_WORDS.search(raw) or raw.casefold().startswith("de ")):
        return "work_or_catalogue_fragment"
    if key in NON_PERSON or key.startswith("tradicional de "):
        return "non_person_attribution"
    for value, reason in FALSE_POSITIVE_BY_CONTEXT.items():
        if lookup_normalize(value) == key:
            return reason
    # Structural signals are evidence, not a global blacklist.  Only use them
    # for the known non-person forms above; ordinary programme composer lines
    # also carry signals such as after_programme_context and must pass through.
    return None


def resolve_component(raw: str, indexes: dict) -> dict:
    result = {"raw_component_text": raw, "lookup_normalized": lookup_normalize(raw), "match_status": "unmatched", "canonical_composer_id": None, "canonical_composer_name": None, "match_method": None, "matched_alias": None, "candidate_matches": [], "confidence": None, "evidence": [], "review_reason": None}
    lifespan = LIFESPAN_RE.search(raw)
    if lifespan:
        result["evidence"].append({"type": "lifespan", "value": lifespan.group(0).strip()})
    if any(marker in result["lookup_normalized"].split() for marker in MALFORMED_MARKERS):
        result["review_reason"] = "malformed_source_identity_not_repaired"
        result["candidate_matches"] = fuzzy_candidates(raw, indexes)
        return result
    if ROMAN_ONLY_RE.fullmatch(raw.strip()):
        result["match_status"] = "false_positive_input"
        result["review_reason"] = "roman_numeral_or_catalogue_fragment"
        return result
    if result["lookup_normalized"] in {lookup_normalize(value) for value in ATTRIBUTION_ONLY}:
        result["match_status"] = "attribution_review"
        result["review_reason"] = "person_named_without_proven_composer_authorship"
        return result
    for method, matches in (("exact", indexes["exact"].get(exact_normalize(raw), [])), ("normalized", indexes["normalized"].get(result["lookup_normalized"], []))):
        unique = unique_matches(matches, raw)
        if len(unique) > 1:
            result.update(match_status="ambiguous", candidate_matches=list(unique.values()), review_reason="multiple_canonical_composer_ids_for_lookup")
            return result
        if len(unique) == 1:
            row = next(iter(unique.values()))
            if len(result["lookup_normalized"].split()) == 1 and len(lookup_normalize(row["canonical_name"]).split()) > 1 and not row.get("matched_alias"):
                result.update(match_status="ambiguous", candidate_matches=[row], review_reason="surname_only_collision_guard")
                return result
            status = "alias" if row.get("matched_alias") and method == "exact" else "normalized_alias" if row.get("matched_alias") else "exact" if method == "exact" else "normalized_exact"
            result.update(match_status=status, canonical_composer_id=row["composer_id"], canonical_composer_name=row["canonical_name"], match_method=method, matched_alias=row.get("matched_alias"), confidence="high")
            if lifespan:
                result["evidence"].append({"type": "lifespan_assisted_lookup", "value": lifespan.group(0).strip()})
            return result
    recovered = recover_existing_identity(raw, indexes)
    if recovered:
        if recovered.get("ambiguous"):
            result["candidate_matches"] = recovered["candidate_matches"]
            result["review_reason"] = "surname_or_initial_collision"
            return result
        result.update(match_status="high_confidence", canonical_composer_id=recovered["composer_id"], canonical_composer_name=recovered["canonical_name"], match_method=recovered["match_method"], confidence=recovered["confidence"], evidence=result["evidence"] + [{"type": "deterministic_existing_identity_recovery"}])
        return result
    result["candidate_matches"] = fuzzy_candidates(raw, indexes)
    result["review_reason"] = "fuzzy_candidates_review_only" if result["candidate_matches"] else "no_exact_or_alias_match"
    return result


def collect_inputs(path: str, indexes: dict) -> list[dict]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    output = []
    for page in document.get("pages", []):
        page_artist_names = page_artist_context(page)
        for line in page.get("classified_lines", []):
            classification = line.get("classification")
            fragments = []
            provenance = None
            if classification == "composer_candidate":
                fragments = split_components(line.get("raw_text", ""))
            elif classification == "work_candidate" and (line.get("inline_composer_work") or {}).get("raw_composer_fragment"):
                fragments = split_components(line["inline_composer_work"]["raw_composer_fragment"])
                provenance = "inline_composer_work"
                classification = "inline_composer_work"
            elif classification == "composer_attribution":
                fragments = list(line.get("raw_named_composer_fragments") or [])
                provenance = "raw_named_composer_fragments"
            for fragment in fragments:
                item = {"source_url": page.get("source_url"), "raw_title": page.get("raw_title"), "raw_composer_text": line.get("raw_text", ""), "raw_component_text": fragment, "classification_source": classification, "block_order": line.get("block_order"), "line_order": line.get("line_order"), "fragment_provenance": provenance, "classification_signals": line.get("signals", []), "page_artist_names": page_artist_names}
                if classification == "inline_composer_work":
                    item["raw_component_text"], item["raw_work_fragment"], item["sanitation_reason"] = sanitize_inline(item, indexes)
                    if item["raw_component_text"] != fragment:
                        item["fragment_provenance"] = "phase3.2_sanitized_inline_composer_work"
                item.pop("page_artist_names", None)
                output.append(item)
    return output


def build_review_rows(results: list[dict]) -> list[dict]:
    rows = []
    for row in results:
        if row["match_status"] == "attribution_review":
            category = "attribution_review"
        elif row["review_reason"] == "malformed_source_identity_not_repaired":
            category = "malformed_source"
        elif row["match_status"] == "ambiguous":
            category = "ambiguous_identity"
        elif row["match_status"] == "unmatched" and row["candidate_matches"]:
            category = "possible_existing_global_identity"
        elif row["match_status"] == "unmatched":
            category = "new_global_composer_candidate"
        else:
            continue
        rows.append({"category": category, "raw_component_text": row["raw_component_text"], "raw_composer_text": row["raw_composer_text"], "source_url": row["source_url"], "raw_title": row["raw_title"], "candidate_matches": row["candidate_matches"], "review_reason": row["review_reason"]})
    return rows


def validate_artifact_counts(summary: dict, results: list[dict], review_rows: list[dict]) -> None:
    statuses = Counter(row["match_status"] for row in results)
    for status in ("exact", "alias", "normalized_exact", "normalized_alias", "high_confidence", "ambiguous", "unmatched", "false_positive_input", "attribution_review"):
        field = f"{status}_count"
        if summary[field] != statuses[status]:
            raise RuntimeError(f"artifact consistency failure: {field}={summary[field]} rows={statuses[status]}")
    categories = Counter(row["category"] for row in review_rows)
    expected = {
        "possible_existing_global_identity_count": categories["possible_existing_global_identity"],
        "new_global_composer_candidate_count": categories["new_global_composer_candidate"],
        "malformed_source_count": categories["malformed_source"],
    }
    for field, actual in expected.items():
        if summary[field] != actual:
            raise RuntimeError(f"artifact consistency failure: {field}={summary[field]} rows={actual}")


def run(input_path: str, master: dict, output_dir: Path) -> dict:
    indexes = build_indexes(master)
    existing_alias_keys = {(lookup_normalize(row["alias"]), row["composer_id"]) for row in master["aliases"]}
    results, gaps = [], {}
    for occurrence_id, item in enumerate(collect_inputs(input_path, indexes), 1):
        gate = false_positive_reason(item["raw_component_text"], item)
        match = resolve_component(item["raw_component_text"], indexes) if not gate else {"raw_component_text": item["raw_component_text"], "lookup_normalized": lookup_normalize(item["raw_component_text"]), "match_status": "false_positive_input", "canonical_composer_id": None, "canonical_composer_name": None, "match_method": None, "matched_alias": None, "candidate_matches": [], "confidence": None, "evidence": [], "review_reason": gate}
        row = {"occurrence_id": occurrence_id, **item, **match}
        results.append(row)
        if match["match_status"] == "unmatched" and match["candidate_matches"] and "score" in match["candidate_matches"][0]:
            top = match["candidate_matches"][0]
            alias = proposed_alias(item["raw_component_text"])
            key = (lookup_normalize(alias), top["composer_id"])
            if key in existing_alias_keys:
                continue
            gaps.setdefault(key, {"proposed_alias": alias, "suggested_global_composer_id": top["composer_id"], "canonical_name": top["canonical_name"], "confidence": top["score"], "review_reason": "fuzzy similarity is review evidence only", "raw_source_values": [], "evidence": []})["evidence"].append({"source_url": item["source_url"], "source_title": item["raw_title"], "raw_source": item["raw_component_text"]})
            gaps[key]["raw_source_values"].append(item["raw_component_text"])
    statuses = Counter(row["match_status"] for row in results)
    matched_statuses = {"exact", "alias", "normalized_exact", "normalized_alias", "high_confidence"}
    matched = sum(statuses[s] for s in matched_statuses)
    review_rows = build_review_rows(results)
    review_categories = Counter(row["category"] for row in review_rows)
    new_rows = [row for row in review_rows if row["category"] == "new_global_composer_candidate"]
    unique_new = {lookup_normalize(row["raw_component_text"]) for row in new_rows}
    summary = {"source": "auditorio_nacional", "global_master_source": "public.composers + public.composer_aliases", "global_master_composer_count": len(master["composers"]), "global_master_alias_count": len(master["aliases"]), "total_composer_occurrences": len({(r["source_url"], r["block_order"], r["line_order"], r["raw_composer_text"], r["classification_source"]) for r in results}), "total_composer_components": len(results), "unique_raw_composer_strings": len({r["raw_composer_text"] for r in results}), "unique_normalized_composer_strings": len({r["lookup_normalized"] for r in results}), "exact_count": statuses["exact"], "alias_count": statuses["alias"], "normalized_exact_count": statuses["normalized_exact"], "normalized_alias_count": statuses["normalized_alias"], "high_confidence_count": statuses["high_confidence"], "ambiguous_count": statuses["ambiguous"], "unmatched_count": statuses["unmatched"], "false_positive_input_count": statuses["false_positive_input"], "not_applicable_identity_count": statuses["not_applicable_identity"], "attribution_review_count": statuses["attribution_review"], "unique_canonical_composers_matched": len({r["canonical_composer_id"] for r in results if r["canonical_composer_id"]}), "multi_composer_occurrence_count": sum("/" in r["raw_composer_text"] for r in results), "lifespan_assisted_match_count": sum(any(e.get("type") == "lifespan_assisted_lookup" for e in r["evidence"]) for r in results), "alias_gap_count": sum(len(v["evidence"]) for v in gaps.values()), "alias_gap_unique_count": len(gaps), "possible_existing_global_identity_count": review_categories["possible_existing_global_identity"], "new_global_composer_candidate_count": review_categories["new_global_composer_candidate"], "new_global_composer_candidate_occurrence_count": len(new_rows), "new_global_composer_candidate_unique_identity_count": len(unique_new), "collision_count": sum(r["match_status"] == "ambiguous" for r in results), "malformed_source_count": review_categories["malformed_source"], "matched_percentage": round(100 * matched / len(results), 2) if results else 0, "ambiguous_percentage": round(100 * statuses["ambiguous"] / len(results), 2) if results else 0, "unmatched_percentage": round(100 * statuses["unmatched"] / len(results), 2) if results else 0, "database_writes": 0}
    summary["status_counts"] = dict(statuses)
    summary["review_category_counts"] = dict(review_categories)
    validate_artifact_counts(summary, results, review_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "auditorio-composer-match.json").write_text(json.dumps({"source": "auditorio_nacional", "matches": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "auditorio-composer-match-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "auditorio-composer-alias-gaps.json").write_text(json.dumps({"source": "auditorio_nacional", "alias_gaps": list(gaps.values())}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "auditorio-composer-new-entity-review.json").write_text(json.dumps({"source": "auditorio_nacional", "review_only": True, "database_writes": 0, "rows": review_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="artifacts/auditorio-nacional/auditorio-structure-classification.json")
    parser.add_argument("--output-dir", default="artifacts/auditorio-nacional")
    parser.add_argument("--master-json", help="offline master fixture for tests")
    parser.add_argument("--supabase-url")
    parser.add_argument("--supabase-key")
    args = parser.parse_args()
    if args.master_json:
        master = json.loads(Path(args.master_json).read_text(encoding="utf-8"))
    else:
        import os
        master = fetch_master(args.supabase_url or os.environ["SUPABASE_URL"], args.supabase_key or os.environ["SUPABASE_ANON_KEY"])
    out = Path(args.output_dir)
    snapshot = {"snapshot_source": "public.composers + public.composer_aliases", "snapshot_generated_at": datetime.now(timezone.utc).isoformat(), "database_writes": 0, "composers": master["composers"], "aliases": master["aliases"]}
    (out.parent / "global-entities").mkdir(parents=True, exist_ok=True)
    (out.parent / "global-entities" / "composer-master-snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = run(args.input, master, out)
    snapshot_summary = {"composer_count": len(master["composers"]), "alias_count": len(master["aliases"]), "snapshot_source": snapshot["snapshot_source"], "snapshot_generated_at": snapshot["snapshot_generated_at"], "database_writes": 0}
    (out.parent / "global-entities" / "composer-master-snapshot-summary.json").write_text(json.dumps(snapshot_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
