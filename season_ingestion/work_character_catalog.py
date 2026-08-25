"""Read-only Work Character Catalog ingestion from Wikidata/Wikipedia.

The module produces evidence and candidate metadata only.  It has no Supabase
imports and deliberately does not call the Character Writer.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from normalization.characters import normalize_key


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_API = "https://{language}.wikipedia.org/w/api.php"


def _norm(value: str) -> str:
    return normalize_key(value).replace("-", " ").strip()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class EvidenceCache:
    def __init__(self, root: Path, *, offline: bool = False):
        self.root = Path(root)
        self.offline = offline
        self.root.mkdir(parents=True, exist_ok=True)

    def get_json(self, url: str, params: dict) -> tuple[dict | None, dict]:
        query = urlencode(params, doseq=True)
        full_url = f"{url}?{query}"
        cache_key = _sha256(full_url.encode("utf-8"))
        cache_path = self.root / f"{cache_key}.json"
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return payload["payload"], payload["evidence"]
        if self.offline:
            return None, {"source_url": full_url, "cache_hit": False, "offline": True}
        request = Request(full_url, headers={"User-Agent": "ByelinguaWorkCharacterCatalog/1.0"})
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read()
        except Exception as error:
            return None, {
                "source_url": full_url,
                "cache_hit": False,
                "error_type": type(error).__name__,
                "error": str(error),
            }
        payload = json.loads(raw.decode("utf-8"))
        evidence = {
            "source_url": full_url,
            "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "raw_evidence_sha256": _sha256(raw),
            "cache_hit": False,
        }
        cache_path.write_text(json.dumps({"payload": payload, "evidence": evidence}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload, evidence


class WikidataReference:
    def __init__(self, cache: EvidenceCache):
        self.cache = cache

    def _search(self, query: str) -> tuple[list[dict], dict]:
        payload, evidence = self.cache.get_json(
            WIKIDATA_API,
            {"action": "wbsearchentities", "search": query, "language": "en", "format": "json", "limit": 10},
        )
        return ((payload or {}).get("search") or []), evidence

    def _entity(self, qid: str) -> tuple[dict | None, dict]:
        payload, evidence = self.cache.get_json(
            WIKIDATA_API,
            {"action": "wbgetentities", "ids": qid, "languages": "en|de|fr|es|it", "props": "labels|aliases|claims|sitelinks", "format": "json"},
        )
        return ((payload or {}).get("entities") or {}).get(qid), evidence

    def _reverse_characters(self, work_qid: str) -> tuple[list[str], dict]:
        query = f"SELECT ?character WHERE {{ ?character wdt:P1441 wd:{work_qid}. }}"
        payload, evidence = self.cache.get_json(
            "https://query.wikidata.org/sparql",
            {"query": query, "format": "json"},
        )
        bindings = (((payload or {}).get("results") or {}).get("bindings") or [])
        return [str(row.get("character", {}).get("value", "")).rsplit("/", 1)[-1] for row in bindings], evidence

    @staticmethod
    def _labels(entity: dict) -> dict:
        return {key: value.get("value", "") for key, value in (entity.get("labels") or {}).items()}

    @staticmethod
    def _aliases(entity: dict) -> dict:
        return {key: [item.get("value", "") for item in values] for key, values in (entity.get("aliases") or {}).items()}

    @staticmethod
    def _claim_qids(entity: dict, property_id: str) -> list[str]:
        return [
            claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            for claim in (entity.get("claims") or {}).get(property_id, [])
            if claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
        ]

    def resolve_work(self, title: str, composer: str) -> dict:
        title_results, title_search_evidence = self._search(title)
        combined_results, combined_search_evidence = self._search(f"{title} {composer}".strip()) if composer else ([], {})
        work_results = {item.get("id"): item for item in [*title_results, *combined_results] if item.get("id")}
        candidates = []
        entity_evidence = []
        for item in work_results.values():
            qid = item.get("id")
            if not qid:
                continue
            entity, evidence = self._entity(qid)
            if not entity:
                continue
            labels = self._labels(entity)
            aliases = self._aliases(entity)
            title_match = any(_norm(value) == _norm(title) for value in [*labels.values(), *sum(aliases.values(), [])])
            claimed_composers = set(self._claim_qids(entity, "P86")) | set(self._claim_qids(entity, "P170"))
            composer_match = False
            for composer_qid in claimed_composers:
                claimed, _ = self._entity(composer_qid)
                if claimed:
                    composer_labels = self._labels(claimed)
                    composer_aliases = self._aliases(claimed)
                    names = [*composer_labels.values(), *sum(composer_aliases.values(), [])]
                    composer_match = any(_norm(value) == _norm(composer) for value in names)
                if composer_match:
                    break
            if title_match and composer_match:
                candidates.append({"qid": qid, "entity": entity, "labels": labels, "aliases": aliases, "composer_match": composer_match})
            entity_evidence.append(evidence)
        status = "SAFE_WORK_QID" if len(candidates) == 1 and candidates[0]["composer_match"] else "REVIEW_WORK_QID"
        selected = candidates[0] if len(candidates) == 1 else None
        return {
            "wikidata_work_qid": selected["qid"] if selected else None,
            "work_match_status": status,
            "candidates": [{"qid": row["qid"], "labels": row["labels"]} for row in candidates],
            "sitelinks": (selected["entity"].get("sitelinks") if selected else {}),
            "original_language": self._language_from_claim(selected["entity"]) if selected else None,
            "work_search_candidates": list(work_results),
            "title_match_candidates": [row["qid"] for row in candidates if row.get("labels")],
            "composer_match_candidates": [row["qid"] for row in candidates if row.get("composer_match")],
            "evidence": [title_search_evidence, combined_search_evidence, *entity_evidence],
        }

    def _language_from_claim(self, entity: dict | None) -> str | None:
        qids = self._claim_qids(entity or {}, "P407")
        names = {"Q1860": "en", "Q188": "de", "Q652": "it", "Q1321": "es", "Q150": "fr"}
        for qid in qids:
            if qid in names:
                return names[qid]
        return None

    def character_candidates(self, work_qid: str) -> tuple[list[dict], list[dict]]:
        entity, entity_evidence = self._entity(work_qid)
        if not entity:
            return [], [entity_evidence]
        candidates = []
        evidence = [entity_evidence]
        qids_and_types = [(qid, "P674") for qid in self._claim_qids(entity, "P674")]
        reverse_qids, reverse_evidence = self._reverse_characters(work_qid)
        qids_and_types.extend((qid, "P1441") for qid in reverse_qids)
        seen = set()
        for qid, relationship_type in qids_and_types:
            if qid in seen:
                continue
            seen.add(qid)
            character, character_evidence = self._entity(qid)
            if not character:
                continue
            candidates.append({
                "wikidata_qid": qid,
                "labels": self._labels(character),
                "aliases": self._aliases(character),
                "present_in_work_evidence": f"wikidata:{relationship_type}",
                "relationship_type": relationship_type,
            })
            evidence.append(character_evidence)
        evidence.append(reverse_evidence)
        return candidates, evidence


class WikipediaReference:
    def __init__(self, cache: EvidenceCache):
        self.cache = cache

    @staticmethod
    def _clean(value: str) -> str:
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\[[^]]+\]", "", value)
        return re.sub(r"\s+", " ", html.unescape(value)).strip(" ;:\n")

    def page_reference(self, title: str, language: str, *, sitelinks: dict | None = None) -> tuple[list[dict], list[dict]]:
        language = language if language in {"de", "en", "fr", "es", "it"} else "en"
        api = WIKIPEDIA_API.format(language=language)
        search_evidence = {}
        exact = None
        if sitelinks:
            exact = (sitelinks.get(f"{language}wiki") or {}).get("title")
        if not exact:
            search, search_evidence = self.cache.get_json(api, {"action": "opensearch", "search": title, "limit": 5, "namespace": 0, "format": "json"})
            titles = (search or [[], [], [], []])[1] if search else []
            exact = next((value for value in titles if _norm(value) == _norm(title)), titles[0] if titles else None)
        if not exact:
            return [], [search_evidence]
        parsed, parse_evidence = self.cache.get_json(api, {"action": "parse", "page": exact, "prop": "text|wikitext", "format": "json", "disableeditsection": 1})
        html = ((parsed or {}).get("parse") or {}).get("text", {}).get("*", "")
        references = []
        role_tables_found = 0
        rejected = 0
        for table in re.findall(r"<table[\s\S]*?</table>", html, flags=re.I):
            rows = re.findall(r"<tr[\s\S]*?</tr>", table, flags=re.I)
            if not rows:
                continue
            headers = [self._clean(cell) for cell in re.findall(r"<th[^>]*>([\s\S]*?)</th>", rows[0], flags=re.I)]
            role_index = next((index for index, header in enumerate(headers) if re.search(r"\b(role|character|rolle|personnage|personaggio|personaje|personagem)\b", header, re.I)), None)
            if role_index is None:
                continue
            role_tables_found += 1
            for row in rows[1:]:
                cells = re.findall(r"<(?:td|th)[^>]*>([\s\S]*?)</(?:td|th)>", row, flags=re.I)
                if role_index >= len(cells):
                    continue
                displayed = self._clean(cells[role_index])
                if not displayed or len(displayed) >= 120:
                    rejected += 1
                    continue
                others = [self._clean(cell) for index, cell in enumerate(cells) if index != role_index]
                references.append({
                    "page_language": language,
                    "page_title": exact,
                    "source_url": f"https://{language}.wikipedia.org/wiki/{exact.replace(' ', '_')}",
                    "displayed_role": displayed,
                    "linked_character_page": None,
                    "descriptor": others[-1] if others else None,
                    "voice_type_if_present": others[0] if others and any(re.search(r"voice|stimm|voix|voce|voz", value, re.I) for value in headers) else None,
                    "metrics": {"wikipedia_role_tables_found": role_tables_found, "wikipedia_non_role_cells_rejected": rejected},
                })
        return references, [search_evidence, parse_evidence]


def ingest_work_catalog(work: dict, wikidata: WikidataReference, wikipedia: WikipediaReference) -> tuple[dict, list[dict], list[dict]]:
    title = str(work.get("canonical_work_title") or work.get("work_title") or "").strip()
    composer = str(work.get("composer_canonical_name") or work.get("composer") or "").strip()
    language = work.get("original_language")
    wikidata_result = wikidata.resolve_work(title, composer)
    language_source = "trusted_byelingua" if language else None
    if not language:
        language = wikidata_result.get("original_language")
        language_source = "wikidata:P407" if language else None
    candidates, wikidata_evidence = ([], [])
    if wikidata_result.get("wikidata_work_qid"):
        candidates, wikidata_evidence = wikidata.character_candidates(wikidata_result["wikidata_work_qid"])
    try:
        wikipedia_rows, wikipedia_evidence = wikipedia.page_reference(title, language or "en", sitelinks=wikidata_result.get("sitelinks"))
    except TypeError:
        wikipedia_rows, wikipedia_evidence = wikipedia.page_reference(title, language or "en")
    prior_catalog_used = False
    if not candidates and work.get("evidence_status") == "CATALOG_READY" and work.get("canonical_roles"):
        candidates = [
            {
                "wikidata_qid": None,
                "labels": {language or "en": role.get("canonical_name", "")},
                "aliases": {},
                "present_in_work_evidence": "prior_approved_catalog",
            }
            for role in work.get("canonical_roles", [])
            if role.get("canonical_name")
        ]
        prior_catalog_used = bool(candidates)
        wikidata_evidence.append({"source": "prior_approved_catalog", "used": prior_catalog_used})
    evidence_status = "CATALOG_WORK_QID_REVIEW"
    if not language:
        evidence_status = "CATALOG_SOURCE_MISSING"
    elif wikidata_result["work_match_status"] == "SAFE_WORK_QID":
        evidence_status = "CATALOG_READY" if candidates else ("CATALOG_PARTIAL" if wikipedia_rows else "CATALOG_SOURCE_MISSING")
    elif prior_catalog_used:
        evidence_status = "CATALOG_READY"
    if not wikidata_result.get("wikidata_work_qid") and not wikipedia_rows and not prior_catalog_used:
        evidence_status = "CATALOG_SOURCE_MISSING"
    catalog = {
        "work_id": work.get("work_id"),
        "composer_id": work.get("composer_id"),
        "composer": composer,
        "canonical_work_title": title,
        "original_language": language,
        "original_language_source": language_source,
        "work_match_diagnostics": {
            "composer_id": work.get("composer_id"),
            "composer_name": composer,
            "work_search_candidates": wikidata_result.get("work_search_candidates", []),
            "title_match_candidates": wikidata_result.get("title_match_candidates", []),
            "composer_match_candidates": wikidata_result.get("composer_match_candidates", []),
            "selected_qid": wikidata_result.get("wikidata_work_qid"),
            "rejection_reason": None if wikidata_result.get("wikidata_work_qid") else wikidata_result.get("work_match_status"),
        },
        "external_ids": {"wikidata": wikidata_result.get("wikidata_work_qid")},
        "evidence_status": evidence_status,
        "characters": [
            {
                "canonical_name": (entry.get("labels") or {}).get(language or "") or "",
                "proposed_identity_key": ":".join([normalize_key(composer) or "unknown", normalize_key(title) or "unknown", normalize_key((entry.get("labels") or {}).get(language or "") or "unknown") or "unknown"]),
                "wikidata_qid": entry.get("wikidata_qid"),
                "aliases": entry.get("aliases", {}),
                "source_labels": [],
                "voice_type": None,
                "evidence_sources": [entry.get("present_in_work_evidence", "wikidata:P674")],
                "confidence": "candidate",
                "resolution_status": "CANDIDATE_REVIEW" if (entry.get("labels") or {}).get(language or "") else "REVIEW_CANONICAL_SOURCE",
            }
            for entry in candidates
        ],
    }
    evidence = [*wikidata_result.get("evidence", []), *wikidata_evidence, *wikipedia_evidence]
    return catalog, wikipedia_rows, evidence
