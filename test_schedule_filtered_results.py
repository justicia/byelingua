import json
import unittest
from unittest.mock import patch

from api.index import READ_CACHE, combined_entity_events


def performance(key, venue="Other hall", city="Paris", date="2026-10-01", event_type="concert"):
    return {
        "event_id": key, "title": "Concert", "date": date, "start_time": "19:30:00",
        "venue": venue, "organization": venue, "city": city,
        "event_type": event_type, "room": None,
    }


class FilteredScheduleResultsTests(unittest.TestCase):
    def setUp(self):
        READ_CACHE.clear()
        self.addCleanup(READ_CACHE.clear)

    def search(self, catalog, query):
        reads = []

        def service(method, path, *, params=None):
            self.assertEqual(method, "GET")
            if path == "/rest/v1/venues":
                return [{"name": r["venue"], "city": r["city"], "country_code": "GB" if r["city"] == "London" else "FR"} for r in catalog]
            self.assertEqual(path, "/rest/v1/event_catalog_v1")
            self.assertEqual(params["order"], "date.asc,start_time.asc,event_id.asc")
            offset = int(params["offset"])
            reads.append(offset)
            candidates = catalog
            if params.get("venue", "").startswith("in.("):
                names = json.loads("[" + params["venue"][4:-1] + "]")
                candidates = [r for r in candidates if r["venue"] in names]
            elif params.get("venue"):
                candidates = []
            return candidates[offset:offset + int(params["limit"])]

        with patch("api.index.supabase_service", side_effect=service):
            result = combined_entity_events(query)
            count = len(reads)
            self.assertEqual(combined_entity_events(query), result)
            self.assertEqual(len(reads), count)
        return result["events"], reads

    def test_royal_opera_house_returns_all_446_performances_after_first_page(self):
        prefix = [performance(str(i)) for i in range(1000)]
        royal = [performance(f"royal-{i}", "Royal Opera House", "London") for i in range(446)]
        events, offsets = self.search(prefix + royal, {
            "cities": ["London"], "venues": ["Royal Opera House"],
            "venue_keys": ["royal opera house|london"],
        })
        self.assertEqual([e["event_id"] for e in events], [e["event_id"] for e in royal])
        self.assertEqual(offsets, [0])

    def test_date_and_type_filters_include_matches_on_later_pages(self):
        prefix = [performance(str(i), date="2026-09-30") for i in range(1000)]
        tail = [
            performance("opera", "Royal Opera House", "London", event_type="opera"),
            performance("ballet", "Royal Opera House", "London", event_type="ballet"),
            performance("later", "Royal Opera House", "London", date="2026-11-01", event_type="opera"),
        ]
        events, _ = self.search(prefix + tail, {
            "cities": ["London"], "event_type": "opera",
            "date_from": "2026-10-01", "date_to": "2026-10-31",
        })
        self.assertEqual([e["event_id"] for e in events], ["opera"])

    def test_city_results_above_one_thousand_are_not_cut_off(self):
        catalog = [performance(str(i), "London Hall", "London") for i in range(1306)]
        events, _ = self.search(catalog, {"cities": ["London"]})
        self.assertEqual(len(events), 1306)
        self.assertEqual(events[-1]["event_id"], "1305")

    def test_venue_text_search_uses_catalog_rooms_without_extra_reads(self):
        catalog = [performance(str(i)) for i in range(1000)]
        catalog.append(performance("royal", "Royal Opera House", "London"))
        events, _ = self.search(catalog, {"venue_query": "Royal Opera House"})
        self.assertEqual([e["event_id"] for e in events], ["royal"])


if __name__ == "__main__":
    unittest.main()
