import re
import unittest
from pathlib import Path
from unittest.mock import patch


from api.index import (
    ScheduleSearchValidationError,
    artist_events,
    character_events,
    combined_entity_events,
    schedule_events,
    work_events,
)


def event(event_id, date="2026-10-01", **values):
    return {
        "event_id": event_id,
        "title": "Concert",
        "work_title": "Lumière et Pesanteur",
        "composer": "Kaija Saariaho",
        "date": date,
        "start_time": "19:30:00",
        "organization": "City Opera",
        "venue": "Opéra de Paris",
        "city": "Paris",
        "event_type": "concert",
        **values,
    }


class ScheduleSearchApiTests(unittest.TestCase):
    def setUp(self):
        from api.index import READ_CACHE
        READ_CACHE.clear()

    @patch("api.index._schedule_rooms_by_key", return_value={})
    @patch("api.index._cached_supabase_get")
    def test_open_ended_dates_and_legacy_range_are_bounded(self, cached, _rooms):
        cached.return_value = [
            event("before", "2026-09-01"),
            event("inside-a", "2026-10-01"),
            event("inside-b", "2026-11-01"),
            event("after", "2026-12-01"),
        ]
        cases = [
            ({"date_from": "2026-10-01"}, ["inside-a", "inside-b", "after"], "(date.gte.2026-10-01)"),
            ({"date_to": "2026-11-01"}, ["before", "inside-a", "inside-b"], "(date.lte.2026-11-01)"),
            ({"date_from": "2026-10-01", "date_to": "2026-11-01"}, ["inside-a", "inside-b"], "(date.gte.2026-10-01,date.lte.2026-11-01)"),
        ]
        for query, expected_ids, expected_filter in cases:
            with self.subTest(query=query):
                result = schedule_events(query)
                self.assertEqual([row["event_id"] for row in result["events"]], expected_ids)
                params = cached.call_args.args[1]
                self.assertEqual(params["and"], expected_filter)
                self.assertEqual(params["limit"], "1000")
                self.assertEqual(params["order"], "date.asc,start_time.asc")

    @patch("api.index._schedule_venue_directory", return_value=(
        {"opéra de paris": "Paris", "wiener staatsoper": "Vienna"},
        {"opéra de paris": "fr", "wiener staatsoper": "at"},
    ))
    @patch("api.index._schedule_rooms_by_key", return_value={})
    @patch("api.index._cached_supabase_get")
    def test_city_and_country_queries_are_independent(self, cached, _rooms, _directory):
        cached.return_value = [
            event("paris", venue="Opéra de Paris", city=None),
            event("vienna", venue="Wiener Staatsoper", city=None),
        ]
        self.assertEqual([row["event_id"] for row in schedule_events({"location_query": "Paris"})["events"]], ["paris"])
        self.assertEqual([row["event_id"] for row in schedule_events({"location_query": "France"})["events"]], ["paris"])
        self.assertEqual([row["event_id"] for row in schedule_events({"location_query": "奥地利"})["events"]], ["vienna"])

    @patch("api.index._schedule_rooms_by_key", return_value={"hall": "Grande Salle Pierre Boulez"})
    @patch("api.index._cached_supabase_get")
    def test_venue_and_hall_query_is_case_and_accent_insensitive_and_keeps_exact_filter(self, cached, _rooms):
        cached.return_value = [
            event("hall", venue="Philharmonie de Paris"),
            event("opera", venue="Opéra de Paris"),
            event("other", venue="Wiener Staatsoper"),
        ]
        self.assertEqual([row["event_id"] for row in schedule_events({"venue_query": "GRANDE salle"})["events"]], ["hall"])
        result = schedule_events({"venue_query": "opera de paris", "venues": ["Opéra de Paris"]})
        self.assertEqual([row["event_id"] for row in result["events"]], ["opera"])

    @patch("api.index._schedule_rooms_by_key", return_value={})
    @patch("api.index.event_keys_for_internal_ids", return_value={"internal-work": "work-performance"})
    @patch("api.index._cached_supabase_get")
    def test_composer_search_works_without_dates(self, cached, _keys, _rooms):
        def rows(path, params=None, ttl=60):
            if path == "/rest/v1/works":
                return [{"id": "work-1"}]
            if path == "/rest/v1/event_programme":
                return [{"event_id": "internal-work"}]
            if path == "/rest/v1/event_catalog_v1":
                self.assertNotIn("and", params)
                return [event("work-performance")]
            return []
        cached.side_effect = rows
        result = work_events({"composer_query": "Saariaho"})
        self.assertEqual([row["event_id"] for row in result["events"]], ["work-performance"])

    @patch("api.index._schedule_venue_directory", return_value=({}, {}))
    @patch("api.index._schedule_rooms_by_key", return_value={})
    @patch("api.index._cached_supabase_get")
    def test_character_text_search_works_without_dates(self, cached, _rooms, _directory):
        character_id = "123e4567-e89b-42d3-a456-426614174000"
        def rows(path, params=None, ttl=60):
            if path == "/rest/v1/work_characters":
                return [{"id": character_id, "canonical_name": "Kundry"}]
            if path == "/rest/v1/character_aliases":
                return []
            if path == "/rest/v1/event_character_catalog_v1":
                self.assertEqual(params["character_id"], f"eq.{character_id}")
                self.assertNotIn("and", params)
                return [event("kundry-performance", canonical_name="Kundry", event_type=None)]
            if path == "/rest/v1/event_catalog_v1":
                return [{"event_id": "kundry-performance", "event_type": "opera"}]
            return []
        cached.side_effect = rows
        result = character_events({"character_query": "kundry", "event_type": "opera"})
        self.assertEqual([row["event_id"] for row in result["events"]], ["kundry-performance"])

    @patch("api.index._schedule_venue_directory", return_value=({}, {}))
    @patch("api.index._schedule_rooms_by_key", return_value={})
    @patch("api.index.event_keys_for_internal_ids", return_value={"internal-artist": "artist-performance"})
    @patch("api.index._cached_supabase_get")
    def test_artist_text_search_works_without_dates(self, cached, _keys, _rooms, _directory):
        artist_id = "123e4567-e89b-42d3-a456-426614174001"
        def rows(path, params=None, ttl=60):
            if path == "/rest/v1/artists":
                return [{"id": artist_id, "artist_name": "Piotr Beczała"}]
            if path == "/rest/v1/event_credits":
                return [{"event_id": "internal-artist", "artist_id": artist_id, "role": "Tenor", "artists": {"artist_name": "Piotr Beczała"}}]
            if path == "/rest/v1/event_catalog_v1":
                self.assertNotIn("and", params)
                return [event("artist-performance")]
            return []
        cached.side_effect = rows
        result = artist_events({"artist_query": "piotr beczala"})
        self.assertEqual([row["event_id"] for row in result["events"]], ["artist-performance"])

    @patch("api.index._schedule_rooms_by_key", return_value={})
    @patch("api.index._cached_supabase_get")
    def test_event_type_is_a_standalone_condition(self, cached, _rooms):
        cached.return_value = [event("opera", event_type="opera"), event("concert", event_type="concert")]
        result = schedule_events({"event_type": "opera"})
        self.assertEqual([row["event_id"] for row in result["events"]], ["opera"])

    def test_combined_entity_conditions_intersect_without_overwriting(self):
        work_id = "123e4567-e89b-42d3-a456-426614174010"
        character_id = "123e4567-e89b-42d3-a456-426614174011"
        artist_id = "123e4567-e89b-42d3-a456-426614174012"
        query = {
            "date_from": "2026-10-01",
            "location_query": "Paris",
            "venue_query": "Opéra",
            "event_type": "opera",
            "work_id": work_id,
            "character_id": character_id,
            "artist_id": artist_id,
        }
        with patch("api.index.work_events", return_value={"events": [event("a"), event("shared") ]}) as work, \
             patch("api.index.character_events", return_value={"events": [event("shared"), event("b")]}) as character, \
             patch("api.index.artist_events", return_value={"events": [event("shared"), event("c")]}) as artist:
            result = combined_entity_events(query)
        self.assertEqual([row["event_id"] for row in result["events"]], ["shared"])
        for called in (work, character, artist):
            self.assertEqual(called.call_args.args[0], query)

    def test_empty_search_returns_localizable_validation_code(self):
        with self.assertRaises(ScheduleSearchValidationError) as raised:
            combined_entity_events({})
        self.assertEqual(raised.exception.error_code, "SCHEDULE_SEARCH_CONDITION_REQUIRED")

    def test_search_ui_uses_bilingual_fields_and_one_button_handler(self):
        html = Path(__file__).with_name("schedule.html").read_text(encoding="utf-8")
        date_from = re.search(r'<input id="dateFrom"[^>]*>', html).group(0)
        date_to = re.search(r'<input id="dateTo"[^>]*>', html).group(0)
        venue = re.search(r'<input id="venueSearch"[^>]*>', html).group(0)
        self.assertNotIn("required", date_from)
        self.assertNotIn("required", date_to)
        self.assertIn('placeholder="例如：柏林爱乐厅、巴黎歌剧院"', venue)
        self.assertIn("venue_query:venueInput?.value.trim()||''", html)
        self.assertIn("searchRequired:'请至少输入一个搜索条件。'", html)
        self.assertIn("searchRequired:'Enter at least one search condition.'", html)
        self.assertIn("unifiedSearchButton.onclick=runEntitySearch", html)
        self.assertIn("event.stopImmediatePropagation();\n      runEntitySearch();", html)
        self.assertIn("document.getElementById('search')?.remove()", html)


if __name__ == "__main__":
    unittest.main()
