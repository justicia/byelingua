import unittest
from unittest.mock import patch

from api import index as schedule_api


EVENT_ID = "paris-event-1"
INTERNAL_EVENT_ID = "internal-event-1"
ARTIST_ID = "11111111-1111-1111-1111-111111111111"
CHARACTER_ID = "22222222-2222-2222-2222-222222222222"
WORK_ID = "33333333-3333-3333-3333-333333333333"


def catalog_row():
    return {
        "event_id": EVENT_ID,
        "source": "official",
        "source_event_id": "source-1",
        "source_url": "https://example.test/event-1",
        "organization": "Opéra national de Paris",
        "venue": "Palais Garnier",
        "room": None,
        "date": "2026-11-02",
        "start_time": "19:30:00",
        "end_time": None,
        "timezone": "Europe/Paris",
        "event_type": "concert",
        "title": "Paris Concert",
        "original_title": None,
        "status": "scheduled",
        "ticket_url": "https://example.test/tickets",
        "fetched_at": None,
        "source_updated_at": None,
        "review_status": "ready",
    }


class FakeSupabase:
    def __init__(self):
        self.calls = []

    def __call__(self, method, path, params=None, **kwargs):
        self.calls.append((method, path, dict(params or {})))
        if path == "/rest/v1/event_catalog_v1":
            return [catalog_row()]
        if path == "/rest/v1/venues":
            return [{"name": "Palais Garnier", "city": "Paris"}]
        if path == "/rest/v1/events":
            event_key = str((params or {}).get("event_key") or "")
            if event_key.startswith("eq."):
                return [{"id": INTERNAL_EVENT_ID, "room": "Main Hall"}]
            if event_key.startswith("in."):
                return [{"event_key": EVENT_ID, "room": "Main Hall"}]
            event_ids = str((params or {}).get("id") or "")
            if event_ids.startswith("in."):
                return [{"id": INTERNAL_EVENT_ID, "event_key": EVENT_ID}]
            return []
        if path == "/rest/v1/event_programme":
            return [{"event_id": INTERNAL_EVENT_ID}]
        if path == "/rest/v1/event_credits":
            return [{"event_id": INTERNAL_EVENT_ID, "artist_id": ARTIST_ID, "role": "soloist", "character": None}]
        if path == "/rest/v1/event_character_catalog_v1":
            row = catalog_row()
            row.update({
                "work_title": "A Work",
                "composer": "A Composer",
                "character_id": CHARACTER_ID,
                "canonical_name": "A Character",
                "raw_character": "A Character",
                "artist_name": "An Artist",
                "role": "performer",
                "character": "A Character",
            })
            return [row]
        if path == "/rest/v1/works":
            return [{"id": WORK_ID, "title": "A Work", "composer": "A Composer"}]
        return []


class ScheduleBuilderSchemaTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeSupabase()
        self.supabase_patch = patch.object(schedule_api, "supabase_service", self.fake)
        self.supabase_patch.start()

    def tearDown(self):
        self.supabase_patch.stop()

    def catalog_calls(self):
        return [call for call in self.fake.calls if call[1] == "/rest/v1/event_catalog_v1"]

    def test_catalog_projection_matches_live_view_and_excludes_stale_fields(self):
        self.assertNotIn("work_title", schedule_api.EVENT_CATALOG_SELECT)
        self.assertNotIn("composer", schedule_api.EVENT_CATALOG_SELECT)
        self.assertNotIn("city", schedule_api.EVENT_CATALOG_SELECT)
        self.assertIn("event_id", schedule_api.EVENT_CATALOG_SELECT)
        self.assertIn("title", schedule_api.EVENT_CATALOG_SELECT)
        self.assertIn("date", schedule_api.EVENT_CATALOG_SELECT)
        self.assertIn("start_time", schedule_api.EVENT_CATALOG_SELECT)
        self.assertIn("source_url", schedule_api.EVENT_CATALOG_SELECT)

    def test_paris_schedule_search_uses_title_and_schema_supported_city_fallback(self):
        result = schedule_api.schedule_events({
            "date_from": "2026-11-01",
            "date_to": "2026-11-30",
            "cities": ["Paris"],
            "organizations": [],
            "venues": [],
        })

        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["title"], "Paris Concert")
        self.assertEqual(result["events"][0]["city"], "Paris")
        self.assertEqual(result["items"], result["events"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["page_size"], 15)
        self.assertEqual(self.catalog_calls()[0][2]["select"], schedule_api.EVENT_CATALOG_SELECT)

    def test_work_search_uses_event_programme_and_catalog_title(self):
        result = schedule_api.combined_entity_events({
            "work_id": WORK_ID,
            "date_from": "2026-11-01",
            "date_to": "2026-11-30",
            "cities": [],
        })

        self.assertEqual([row["event_id"] for row in result["events"]], [EVENT_ID])
        self.assertEqual(self.catalog_calls()[0][2]["select"], schedule_api.EVENT_CATALOG_SELECT)

    def test_character_and_artist_search_paths_remain_valid(self):
        character_result = schedule_api.combined_entity_events({
            "character_id": CHARACTER_ID,
            "date_from": "2026-11-01",
            "date_to": "2026-11-30",
            "cities": ["Paris"],
        })
        artist_result = schedule_api.combined_entity_events({
            "artist_id": ARTIST_ID,
            "date_from": "2026-11-01",
            "date_to": "2026-11-30",
            "cities": ["Paris"],
        })

        self.assertEqual(len(character_result["events"]), 1)
        self.assertEqual(len(artist_result["events"]), 1)
        character_calls = [call for call in self.fake.calls if call[1] == "/rest/v1/event_character_catalog_v1"]
        self.assertEqual(character_calls[0][2]["select"], schedule_api.EVENT_CHARACTER_CATALOG_SELECT)

    def test_event_detail_uses_current_catalog_title(self):
        result = schedule_api.schedule_event_detail(EVENT_ID)

        self.assertEqual(result["event"]["title"], "Paris Concert")
        self.assertEqual(result["event"]["city"], "Paris")
        self.assertEqual(self.catalog_calls()[0][2]["select"], schedule_api.EVENT_CATALOG_SELECT)


if __name__ == "__main__":
    unittest.main()
