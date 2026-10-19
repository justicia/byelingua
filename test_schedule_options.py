import unittest
from unittest.mock import patch

from api.index import READ_CACHE, schedule_options


class ScheduleOptionsPaginationTests(unittest.TestCase):
    def setUp(self):
        READ_CACHE.clear()
        self.addCleanup(READ_CACHE.clear)
        self.names = ["Southbank Centre", "Wigmore Hall", "Royal Opera House", "Inactive Hall"]
        self.organizations = [{"id": str(i), "name": name} for i, name in enumerate(self.names)]
        self.venues = [
            {"id": str(i), "name": name, "city": "London", "country_code": "GB", "organization_id": str(i)}
            for i, name in enumerate(self.names)
        ]

    def catalog_row(self, name):
        return {"organization": name, "venue": name}

    def check_catalog(self, catalog, server_cap):
        offsets = []

        def service(method, path, *, params=None):
            self.assertEqual(method, "GET")
            if path == "/rest/v1/organizations":
                return self.organizations
            if path == "/rest/v1/venues":
                return self.venues
            self.assertEqual(path, "/rest/v1/event_catalog_v1")
            self.assertEqual(params["select"], "organization,venue")
            self.assertEqual(params["order"], "event_id.asc")
            offset = int(params["offset"])
            offsets.append(offset)
            return catalog[offset:offset + min(int(params["limit"]), server_cap)]

        with patch("api.index.supabase_service", side_effect=service) as mocked:
            result = schedule_options()
            reads = mocked.call_count
            self.assertEqual(schedule_options(), result)
            self.assertEqual(mocked.call_count, reads, "Repeated options reads should use the cache")
        return result, offsets

    def test_royal_opera_house_after_first_thousand_rows_remains_selectable(self):
        catalog = [self.catalog_row("Southbank Centre")] * 1000
        catalog += [self.catalog_row("Wigmore Hall"), self.catalog_row("Royal Opera House")]
        result, offsets = self.check_catalog(catalog, server_cap=1000)
        self.assertEqual([v["name"] for v in result["venues"]], self.names[:3])
        self.assertEqual(result["cities"], ["London"])
        self.assertEqual(result["venues"][-1]["country_code"], "GB")
        self.assertEqual(offsets, [0, 1000, 1002])

    def test_reads_beyond_old_five_thousand_row_limit(self):
        catalog = [self.catalog_row("Southbank Centre")] * 5000
        catalog += [self.catalog_row("Royal Opera House")]
        result, offsets = self.check_catalog(catalog, server_cap=1000)
        self.assertIn("Royal Opera House", [v["name"] for v in result["venues"]])
        self.assertEqual(offsets, [0, 1000, 2000, 3000, 4000, 5000, 5001])

    def test_lower_server_cap_does_not_skip_records_or_stop_early(self):
        catalog = [self.catalog_row(name) for name in self.names[:3]]
        catalog += [{"organization": "Other organization", "venue": "Inactive Hall"}]
        result, offsets = self.check_catalog(catalog, server_cap=2)
        self.assertEqual([v["name"] for v in result["venues"]], self.names[:3])
        self.assertEqual(offsets, [0, 2, 4])

    def test_empty_catalog_preserves_directory_fallback(self):
        result, offsets = self.check_catalog([], server_cap=1000)
        self.assertEqual([v["name"] for v in result["venues"]], self.names)
        self.assertEqual(offsets, [0])


if __name__ == "__main__":
    unittest.main()
