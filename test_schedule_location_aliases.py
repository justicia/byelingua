import unittest
from unittest.mock import Mock, patch

from api.index import (
    READ_CACHE, _schedule_country_code, _schedule_event_matches,
    _schedule_location_venue_names, handler,
)


class ScheduleLocationAliasTests(unittest.TestCase):
    def setUp(self):
        READ_CACHE.clear()
        self.addCleanup(READ_CACHE.clear)

    def test_country_labels_are_normalized_without_database_changes(self):
        for value, expected in [("Germany", "de"), ("DE", "de"), ("德国", "de"),
                                ("Austria", "at"), ("United Kingdom", "gb"),
                                ("France", "fr"), ("Belgium", "be"), ("Italy", "it")]:
            with self.subTest(value=value):
                self.assertEqual(_schedule_country_code(value), expected)

    def test_city_with_missing_country_still_matches_chinese_country(self):
        row = {"venue": "Rudolfinum", "city": "Prague", "country_code": None}
        self.assertEqual(_schedule_country_code(None, "Prague"), "cz")
        self.assertTrue(_schedule_event_matches(dict(row), {"location_query": "捷克"}))
        self.assertTrue(_schedule_event_matches(dict(row), {"location_query": "布拉格"}))

    def test_chinese_city_and_country_match_the_same_venue(self):
        row = {"venue": "Philharmonie Berlin", "city": "Berlin", "country_code": "Germany"}
        for query in ["柏林", "Berlin", "德国", "Germany", "Deutschland"]:
            with self.subTest(query=query):
                self.assertTrue(_schedule_event_matches(dict(row), {"location_query": query}))
        self.assertFalse(_schedule_event_matches(dict(row), {"location_query": "法国"}))

    @patch("api.index.supabase_service")
    def test_directory_limits_database_query_to_requested_city_and_venue_aliases(self, service):
        service.return_value = [
            {"name": "Auditorio Nacional de Música", "city": "Madrid", "country_code": "Spain"},
            {"name": "Auditorio Nacional de Musica", "city": "Madrid", "country_code": "ES"},
            {"name": "Other Hall", "city": "Madrid", "country_code": "ES"},
            {"name": "Berlin Hall", "city": "Berlin", "country_code": "Germany"},
        ]
        query = {"location_query": "马德里", "venue_keys": ["auditorio nacional de musica|madrid"]}
        self.assertEqual(_schedule_location_venue_names(query), ["Auditorio Nacional de Musica", "Auditorio Nacional de Música"])
        self.assertEqual(_schedule_location_venue_names({"location_query": "德国"}), ["Berlin Hall"])
        self.assertEqual(service.call_count, 1)
        self.assertIsNone(_schedule_location_venue_names({}))

    @patch("api.index.public_payload")
    @patch("api.index.schedule_options", return_value={"venues": []})
    def test_only_public_options_get_has_shared_directory_cache(self, options, public):
        request = object.__new__(handler)
        request.path = "/api?action=schedule_options"
        request.send_json = Mock()
        request.do_GET()
        request.send_json.assert_called_once_with(200, {"venues": []}, "public, max-age=600, s-maxage=600, stale-while-revalidate=60")
        options.assert_called_once()
        public.assert_not_called()


if __name__ == "__main__":
    unittest.main()
