"""Read-only Work Character Catalog ingestion from Wikidata/Wikipedia.

The module produces evidence and candidate metadata only.  It has no Supabase
imports and deliberately does not call the Character Writer.
"""

from __future__ import annotations

import hashlib
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
        composer_results, composer_evidence = self._search(composer) if composer else ([], {})
        composer_qids = {item.get("id") for item in composer_results if item.get("id")}
        work_results, work_search_evidence = self._search(f"{title} {composer}".strip())
        candidates = []
        entity_evidence = []
        for item in work_results[:10]:
            qid = item.get("id")
            if not qid:
                continue
            entity, evidence = self._entity(qid)
            if not entity:
                continue
            labels = self._labels(entity)
            aliases = self._aliases(entity)
            title_match = any(_norm(value) == _norm(title) for value in [*labels.values(), *sum(aliases.values(), [])])
            composer_match = bool(set(self._claim_qids(entity, "P86")) & composer_qids) or bool(set(self._claim_qids(entity, "P170")) & composer_qids)
            if title_match and (composer_match or not composer_qids):
                candidates.append({"qid": qid, "entity": entity, "labels": labels, "aliases": aliases, "composer_match": composer_match})
            entity_evidence.append(evidence)
        status = "SAFE_WORK_QID" if len(candidates) == 1 and candidates[0]["composer_match"] else "REVIEW_WORK_QID"
        selected = candidates[0] if len(candidates) == 1 else None
        return {
            "wikidata_work_qid": selected["qid"] if selected else None,
            "work_match_status": status,
            "candidates": [{"qid": row["qid"], "labels": row["labels"]} for row in candidates],
            "evidence": [composer_evidence, work_search_evidence, *entity_evidence],
        }

    def character_candidates(self, work_qid: str) -> tuple[list[dict], list[dict]]:
        entity, entity_evidence = self._entity(work_qid)
        if not entity:
            return [], [entity_evidence]
        candidates = []
        evidence = [entity_evidence]
        for qid in self._claim_qids(entity, "P674"):
            character, character_evidence = self._entity(qid)
            if not character:
                continue
            candidates.append({
                "wikidata_qid": qid,
                "labels": self._labels(character),
                "aliases": self._aliases(character),
                "present_in_work_evidence": "wikidata:P674",
            })
            evidence.append(character_evidence)
        return candidates, evidence


class WikipediaReference:
    def __init__(self, cache: EvidenceCache):
        self.cache = cache

    def page_reference(self, title: str, language: str) -> tuple[list[dict], list[dict]]:
        language = language if language in {"de", "en", "fr", "es", "it"} else "en"
        api = WIKIPEDIA_API.format(language=language)
        search, search_evidence = self.cache.get_json(api, {"action": "opensearch", "search": title, "limit": 5, "namespace": 0, "format": "json"})
        titles = (search or [[], [], [], []])[1] if search else []
        exact = next((value for value in titles if _norm(value) == _norm(title)), titles[0] if titles else None)
        if not exact:
            return [], [search_evidence]
        parsed, parse_evidence = self.cache.get_json(api, {"action": "parse", "page": exact, "prop": "text|wikitext", "format": "json", "disableeditsection": 1})
        html = ((parsed or {}).get("parse") or {}).get("text", {}).get("*", "")
        references = []
        for table in re.findall(r"<table[\s\S]*?</table>", html, flags=re.I):
            if not re.search(r"character|role|dramatis|cast", table, flags=re.I):
                continue
            cells = re.findall(r"<(?:th|td)[^>]*>([\s\S]*?)</(?:th|td)>", table, flags=re.I)
            for cell in cells:
                displayed = re.sub(r"<[^>]+>", " ", cell)
                displayed = re.sub(r"\[[^]]+\]", "", displayed)
                displayed = re.sub(r"\s+", " ", displayed).strip(" ;:\n")
                if displayed and len(displayed) < 120:
                    references.append({
                        "page_language": language,
                        "page_title": exact,
                        "source_url": f"https://{language}.wikipedia.org/wiki/{exact.replace(' ', '_')}",
                        "displayed_role": displayed,
                        "linked_character_page": None,
                        "descriptor": None,
                        "voice_type_if_present": None,
                    })
        return references, [search_evidence, parse_evidence]


def ingest_work_catalog(work: dict, wikidata: WikidataReference, wikipedia: WikipediaReference) -> tuple[dict, list[dict], list[dict]]:
    title = str(work.get("canonical_work_title") or work.get("work_title") or "").strip()
    composer = str(work.get("composer") or "").strip()
    language = work.get("original_language")
    wikidata_result = wikidata.resolve_work(title, composer)
    candidates, wikidata_evidence = ([], [])
    if wikidata_result.get("wikidata_work_qid"):
        candidates, wikidata_evidence = wikidata.character_candidates(wikidata_result["wikidata_work_qid"])
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
    if wikidata_result["work_match_status"] == "SAFE_WORK_QID":
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
        "external_ids": {"wikidata": wikidata_result.get("wikidata_work_qid")},
        "evidence_status": evidence_status,
        "characters": [
            {
                "canonical_name": (entry.get("labels") or {}).get(language or "") or (entry.get("labels") or {}).get("en") or next(iter(entry.get("labels", {}).values()), ""),
                "proposed_identity_key": ":".join([normalize_key(composer) or "unknown", normalize_key(title) or "unknown", normalize_key((entry.get("labels") or {}).get(language or "") or (entry.get("labels") or {}).get("en") or "unknown") or "unknown"]),
                "wikidata_qid": entry.get("wikidata_qid"),
                "aliases": entry.get("aliases", {}),
                "source_labels": [],
                "voice_type": None,
                "evidence_sources": [entry.get("present_in_work_evidence", "wikidata:P674")],
                "confidence": "candidate",
                "resolution_status": "CANDIDATE_REVIEW",
            }
            for entry in candidates
        ],
    }
    evidence = [*wikidata_result.get("evidence", []), *wikidata_evidence, *wikipedia_evidence]
    return catalog, wikipedia_rows, evidence
