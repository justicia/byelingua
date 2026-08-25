import tempfile
import unittest
from pathlib import Path
import socket
from unittest.mock import patch
from urllib.error import HTTPError

from jobs.ingest_work_character_catalog_v1 import bootstrap_inputs, bootstrap_preflight, snapshot_payload
from season_ingestion.contracts import GlobalEntitySnapshot
from season_ingestion.work_character_catalog import EvidenceCache, WikidataReference, ingest_work_catalog, normalize_work_title


class FakeCache:
    def get_json(self, url, params):
        if params.get("action") == "wbsearchentities":
            if "Le nozze" not in params.get("search", "") and "Mozart" in params.get("search", ""):
                return {"search": [{"id": "Q_MOZART"}]}, {"source": "fake"}
            return {"search": [{"id": "Q_FIGARO"}]}, {"source": "fake"}
        if params.get("action") == "wbgetentities":
            qid = params["ids"]
            if qid == "Q_MOZART":
                return {"entities": {qid: {"labels": {"en": {"value": "Wolfgang Amadeus Mozart"}}, "claims": {}}}}, {"source": "fake"}
            return {"entities": {qid: {"labels": {"en": {"value": "Le nozze di Figaro"}}, "aliases": {}, "claims": {"P86": [{"mainsnak": {"datavalue": {"value": {"id": "Q_MOZART"}}}}]}}}}, {"source": "fake"}
        return {}, {"source": "fake"}


class WorkCharacterCatalogTests(unittest.TestCase):
    def test_wikidata_work_match_requires_composer(self):
        client = WikidataReference(FakeCache())
        self.assertEqual(client.resolve_work("Le nozze di Figaro", "Wolfgang Amadeus Mozart")["work_match_status"], "SAFE_WORK_QID")

        class WrongComposerCache(FakeCache):
            def get_json(self, url, params):
                payload, evidence = super().get_json(url, params)
                if params.get("action") == "wbgetentities" and params.get("ids") == "Q_FIGARO":
                    payload["entities"]["Q_FIGARO"]["claims"]["P86"][0]["mainsnak"]["datavalue"]["value"]["id"] = "Q_OTHER"
                return payload, evidence

        self.assertEqual(WikidataReference(WrongComposerCache()).resolve_work("Le nozze di Figaro", "Wolfgang Amadeus Mozart")["work_match_status"], "SOURCE_NO_MATCH")

    def test_work_title_normalization_removes_format_chars_without_space(self):
        self.assertEqual(normalize_work_title("Die Zauber\u00adflöte"), normalize_work_title("Die Zauberflöte"))
        self.assertEqual(normalize_work_title("Die Zauber\u200bflöte"), normalize_work_title("Die Zauberflote"))

    def test_http_429_is_not_empty_search(self):
        with tempfile.TemporaryDirectory() as directory:
            error = HTTPError("https://www.wikidata.org/w/api.php", 429, "rate", {}, None)
            with patch("season_ingestion.work_character_catalog.urlopen", side_effect=error), patch("season_ingestion.work_character_catalog.time.sleep"):
                payload, evidence = EvidenceCache(Path(directory)).get_json("https://www.wikidata.org/w/api.php", {"action": "wbsearchentities", "search": "Carmen"})
            self.assertIsNone(payload)
            self.assertEqual(evidence["status"], "SOURCE_RATE_LIMITED")

    def test_timeout_is_not_empty_search(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("season_ingestion.work_character_catalog.urlopen", side_effect=socket.timeout("timeout")):
                payload, evidence = EvidenceCache(Path(directory)).get_json("https://www.wikidata.org/w/api.php", {"action": "wbsearchentities", "search": "Carmen"})
            self.assertIsNone(payload)
            self.assertEqual(evidence["status"], "SOURCE_TIMEOUT")

    def test_valid_empty_search_is_source_no_match(self):
        class EmptyCache(FakeCache):
            def get_json(self, url, params):
                if params.get("action") == "wbsearchentities":
                    return {"search": []}, {"status": "SOURCE_OK", "source": "fake"}
                return super().get_json(url, params)

        result = WikidataReference(EmptyCache()).resolve_work("Carmen", "Georges Bizet")
        self.assertEqual(result["work_match_status"], "SOURCE_NO_MATCH")

    def test_soft_hyphen_work_matches_candidate_label_with_composer(self):
        class SoftHyphenCache(FakeCache):
            def get_json(self, url, params):
                if params.get("action") == "wbsearchentities":
                    if "Mozart" in params.get("search", ""):
                        return {"search": [{"id": "Q_ZAUBER"}]}, {"status": "SOURCE_OK", "source": "fake"}
                    return {"search": [{"id": "Q_ZAUBER"}]}, {"status": "SOURCE_OK", "source": "fake"}
                if params.get("action") == "wbgetentities" and params.get("ids") == "Q_ZAUBER":
                    return {"entities": {"Q_ZAUBER": {"labels": {"de": {"value": "Die Zauberflöte"}}, "aliases": {}, "claims": {"P86": [{"mainsnak": {"datavalue": {"value": {"id": "Q_MOZART"}}}}]}}}}, {"status": "SOURCE_OK", "source": "fake"}
                return super().get_json(url, params)

        result = WikidataReference(SoftHyphenCache()).resolve_work("Die Zauber\u00adflöte", "Wolfgang Amadeus Mozart")
        self.assertEqual(result["work_match_status"], "SAFE_WORK_QID")

    def test_composer_entity_rate_limit_is_partial_not_mismatch(self):
        class RateLimitedComposerCache:
            def get_json(self, url, params):
                if params.get("action") == "wbsearchentities":
                    return {"search": [{"id": "Q5064"}]}, {"status": "SOURCE_OK", "source": "fake"}
                if params.get("action") == "wbgetentities":
                    ids = params["ids"].split("|")
                    if "Q5064" in ids:
                        return {"entities": {"Q5064": {"labels": {"de": {"value": "Die Zauberflöte"}}, "claims": {"P86": [{"mainsnak": {"datavalue": {"value": {"id": "Q254"}}}}]}}}}, {"status": "SOURCE_OK", "source": "fake"}
                    return None, {"status": "SOURCE_RATE_LIMITED", "source": "fake"}
                return {}, {"status": "SOURCE_OK", "source": "fake"}

        result = WikidataReference(RateLimitedComposerCache()).resolve_work("Die Zauberflöte", "Wolfgang Amadeus Mozart")
        self.assertEqual(result["work_match_status"], "SOURCE_PARTIAL_WIKIDATA")
        self.assertNotEqual(result["candidates"][0]["rejection_reason"], "COMPOSER_MISMATCH")

    def test_entity_qid_is_fetched_once_per_run(self):
        class CountingCache(FakeCache):
            def __init__(self):
                self.calls = []
            def get_json(self, url, params):
                if params.get("action") == "wbgetentities":
                    self.calls.append(tuple(sorted(params["ids"].split("|"))))
                return super().get_json(url, params)

        cache = CountingCache()
        ref = WikidataReference(cache)
        ref._entities(["Q254"])
        ref._entities(["Q254"])
        self.assertEqual(sum("Q254" in call for call in cache.calls), 1)

    def test_adaptive_search_stops_after_successful_first_strategy(self):
        class SearchCountingCache(FakeCache):
            def __init__(self):
                self.searches = []
            def get_json(self, url, params):
                if params.get("action") == "wbsearchentities":
                    self.searches.append(params["search"])
                return super().get_json(url, params)

        cache = SearchCountingCache()
        result = WikidataReference(cache).resolve_work("Le nozze di Figaro", "Wolfgang Amadeus Mozart")
        self.assertEqual(result["work_match_status"], "SAFE_WORK_QID")
        self.assertEqual(len(cache.searches), 1)

    def test_retry_after_is_honored(self):
        with tempfile.TemporaryDirectory() as directory:
            error = HTTPError("https://www.wikidata.org/w/api.php", 429, "rate", {"Retry-After": "7"}, None)
            with patch("season_ingestion.work_character_catalog.urlopen", side_effect=error), patch("season_ingestion.work_character_catalog.time.sleep") as sleeper:
                EvidenceCache(Path(directory)).get_json("https://www.wikidata.org/w/api.php", {"action": "wbsearchentities", "search": "Carmen"})
            self.assertIn(7.0, [call.args[0] for call in sleeper.call_args_list])

    def test_three_final_rate_limits_open_circuit(self):
        with tempfile.TemporaryDirectory() as directory:
            error = HTTPError("https://www.wikidata.org/w/api.php", 429, "rate", {}, None)
            cache = EvidenceCache(Path(directory))
            with patch("season_ingestion.work_character_catalog.urlopen", side_effect=error), patch("season_ingestion.work_character_catalog.time.sleep"):
                for _ in range(3):
                    cache.get_json("https://www.wikidata.org/w/api.php", {"action": "wbsearchentities", "search": str(_)})
            self.assertTrue(cache.circuit_breaker_open)

    def test_wikipedia_only_reference_is_partial_not_canonical(self):
        class StubWikidata:
            def resolve_work(self, title, composer):
                return {"wikidata_work_qid": "Q_WORK", "work_match_status": "SAFE_WORK_QID", "evidence": []}

            def character_candidates(self, qid):
                return [], []

        class StubWikipedia:
            def page_reference(self, title, language):
                return [{"displayed_role": "Count Almaviva", "page_language": "en"}], []

        catalog, references, _ = ingest_work_catalog(
            {"work_id": "w", "canonical_work_title": "Le nozze di Figaro", "composer": "Mozart", "original_language": "it"},
            StubWikidata(),
            StubWikipedia(),
        )
        self.assertEqual(catalog["evidence_status"], "CATALOG_PARTIAL")
        self.assertEqual(catalog["characters"], [])
        self.assertEqual(references[0]["displayed_role"], "Count Almaviva")

    def test_offline_cache_never_attempts_network(self):
        with tempfile.TemporaryDirectory() as directory:
            payload, evidence = EvidenceCache(Path(directory), offline=True).get_json("https://example.test", {"q": "x"})
            self.assertIsNone(payload)
            self.assertTrue(evidence["offline"])

    def test_p674_and_p1441_are_unioned_and_deduplicated(self):
        class ReverseCache(FakeCache):
            def get_json(self, url, params):
                if "query.wikidata.org" in url:
                    return {"results": {"bindings": [{"character": {"value": "http://www.wikidata.org/entity/Q_CHAR"}}]}}, {"source": "fake"}
                if params.get("action") == "wbgetentities" and params.get("ids") == "Q_WORK":
                    return {"entities": {"Q_WORK": {"labels": {"en": {"value": "Work"}}, "claims": {"P674": [{"mainsnak": {"datavalue": {"value": {"id": "Q_CHAR"}}}}]}}}}, {"source": "fake"}
                if params.get("action") == "wbgetentities" and params.get("ids") == "Q_CHAR":
                    return {"entities": {"Q_CHAR": {"labels": {"de": {"value": "Figaro"}}, "aliases": {}, "claims": {}}}}, {"source": "fake"}
                return super().get_json(url, params)

        rows, _ = WikidataReference(ReverseCache()).character_candidates("Q_WORK")
        self.assertEqual([row["wikidata_qid"] for row in rows], ["Q_CHAR"])
        self.assertEqual(rows[0]["relationship_type"], "P674")

    def test_wikipedia_role_parser_uses_role_column_only(self):
        class HtmlCache:
            def get_json(self, url, params):
                if params.get("action") == "opensearch":
                    return ["Work", ["Work"], [], []], {"source": "fake"}
                if params.get("action") == "parse":
                    return {"parse": {"text": {"*": '<table><tr><th>Role</th><th>Voice</th><th>Premiere cast</th></tr><tr><td>Figaro</td><td>baritone</td><td>Artist Name</td></tr></table>'}}}, {"source": "fake"}
                return [[], [], [], []], {"source": "fake"}

        rows, _ = __import__("season_ingestion.work_character_catalog", fromlist=["WikipediaReference"]).WikipediaReference(HtmlCache()).page_reference("Work", "en")
        self.assertEqual([row["displayed_role"] for row in rows], ["Figaro"])
        self.assertNotIn("Artist Name", [row["displayed_role"] for row in rows])

    def test_cloud_bootstrap_builds_inputs_from_frozen_snapshot(self):
        snapshot = GlobalEntitySnapshot(
            generated_at="2026-08-25T00:00:00Z",
            source="fake-read-only",
            freshness_seconds=0,
            entities={
                "composer": [{"id": "c1", "canonical_name": "Richard Wagner"}],
                "work": [{"id": "w1", "title": "Tannhäuser", "composer_id": "c1"}],
                "character": [{"id": "ch1", "canonical_name": "Wotan"}],
                "artist": [],
            },
            character_aliases=[{"id": "a1", "character_id": "ch1", "alias": "Wotan"}],
            work_characters=[
                {"id": "wc1", "work_id": "w1", "canonical_name": "Wotan", "character_uid": None},
                {"id": "wc2", "work_id": "w1", "canonical_name": "Wotan", "character_uid": "ch1"},
            ],
            health={"global_master_loaded": True},
        )
        work_input, phase2, payload = bootstrap_inputs(snapshot)
        self.assertEqual(work_input["works"][0]["composer_canonical_name"], "Richard Wagner")
        self.assertEqual(phase2["rows"][0]["work_character_id"], "wc1")
        self.assertEqual(bootstrap_preflight(snapshot, work_input)["unlinked"], 1)
        self.assertEqual(snapshot_payload(snapshot)["work_characters"], snapshot.work_characters)

    def test_missing_composer_isolated_from_valid_work(self):
        snapshot = GlobalEntitySnapshot(
            generated_at="2026-08-25T00:00:00Z", source="fake-read-only", freshness_seconds=0,
            entities={
                "composer": [{"id": "c1", "canonical_name": "Richard Wagner"}],
                "work": [
                    {"id": "w-valid", "title": "Tannhäuser", "composer_id": "c1"},
                    {"id": "w-blocked", "title": "Living Legacies", "composer_id": None},
                ],
                "character": [], "artist": [],
            },
            work_characters=[
                {"id": "wc-valid", "work_id": "w-valid", "canonical_name": "Wotan", "character_uid": None},
                {"id": "wc-blocked", "work_id": "w-blocked", "canonical_name": "Legacy", "character_uid": None},
            ],
        )
        work_input, phase2, _ = bootstrap_inputs(snapshot)
        preflight = bootstrap_preflight(snapshot, work_input)
        self.assertEqual(preflight["works_with_composer_master"], 1)
        self.assertEqual(preflight["works_missing_composer_master"], 1)
        self.assertEqual(preflight["unlinked_rows_with_composer_master"], 1)
        self.assertEqual(preflight["unlinked_rows_missing_composer_master"], 1)
        statuses = {item["work_title"]: item["status"] for item in preflight["work_input_status"]}
        self.assertEqual(statuses["Tannhäuser"], "RUNNABLE")
        self.assertEqual(statuses["Living Legacies"], "INPUT_BLOCKED_MISSING_COMPOSER")
        self.assertEqual(len(phase2["rows"]), 2)


if __name__ == "__main__":
    unittest.main()
