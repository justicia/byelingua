import tempfile
import unittest
from pathlib import Path

from season_ingestion.work_character_catalog import EvidenceCache, WikidataReference, ingest_work_catalog


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

        self.assertEqual(WikidataReference(WrongComposerCache()).resolve_work("Le nozze di Figaro", "Wolfgang Amadeus Mozart")["work_match_status"], "REVIEW_WORK_QID")

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


if __name__ == "__main__":
    unittest.main()
