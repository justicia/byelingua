import unittest

from season_ingestion.adapters.auditorio_nacional import deduplicate_occurrences


def occurrence(detail_room=None, listing_room="Sala de Cámara", time="2027-01-01 20:00"):
    return {
        "source_url": "https://official.example/detail",
        "raw_datetime": time,
        "raw_title": "Test",
        "raw_listing_venue": listing_room,
        "raw_venue": detail_room,
        "official_room_raw": detail_room,
        "normalized_room": {"Sala Sinfónica": "SALA_SINFONICA", "Sala de Cámara": "SALA_DE_CAMARA"}.get(detail_room, "ROOM_NOT_STATED"),
        "room_resolution_status": "DETAIL_ROOM_VERIFIED" if detail_room else "REVIEW_LOCATION",
        "room_evidence": ([{"room_raw": detail_room}] if detail_room else []),
    }


class AuditorioRoomResolutionTests(unittest.TestCase):
    def test_detail_room_wins_and_emits_one_event(self):
        result = deduplicate_occurrences([occurrence("Sala Sinfónica", "Sala de Cámara"), occurrence("Sala Sinfónica", "Sala Sinfónica")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["normalized_room"], "SALA_SINFONICA")

    def test_detail_camara_is_one_event(self):
        result = deduplicate_occurrences([occurrence("Sala de Cámara", "Sala Sinfónica"), occurrence("Sala de Cámara", "Otros espacios")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["normalized_room"], "SALA_DE_CAMARA")

    def test_other_listing_detail_main_hall_is_one_event(self):
        result = deduplicate_occurrences([occurrence("Sala Sinfónica", "Otros espacios")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["normalized_room"], "SALA_SINFONICA")

    def test_conflicting_listing_without_detail_is_review(self):
        result = deduplicate_occurrences([occurrence(None, "Sala Sinfónica"), occurrence(None, "Sala de Cámara")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["room_resolution_status"], "REVIEW_LOCATION")

    def test_generic_other_does_not_promote(self):
        result = deduplicate_occurrences([occurrence(None, "Otros espacios")])
        self.assertEqual(result[0]["normalized_room"], "ROOM_NOT_STATED")
        self.assertEqual(result[0]["raw_listing_venue"], "Otros espacios")

    def test_shared_detail_distinct_times_remain_distinct(self):
        result = deduplicate_occurrences([occurrence("Sala Sinfónica", time="2027-01-01 20:00"), occurrence("Sala Sinfónica", time="2027-01-02 20:00")])
        self.assertEqual(len(result), 2)

    def test_legacy_source_id_shadow_cannot_create_second_event(self):
        legacy = occurrence("Sala Sinfónica", "Sala de Cámara")
        legacy["source_event_id"] = "legacy-direct-source-id"
        canonical = occurrence("Sala Sinfónica", "Sala Sinfónica")
        canonical["source_event_id"] = "canonical-hash-id"
        self.assertEqual(len(deduplicate_occurrences([legacy, canonical])), 1)

    def test_room_normalization_does_not_change_occurrence_identity(self):
        item = occurrence("Sala Sinfónica", "Sala de Cámara", "2027-06-22 20:00")
        result = deduplicate_occurrences([item])
        self.assertEqual((result[0]["raw_datetime"], result[0]["source_url"]), ("2027-06-22 20:00", "https://official.example/detail"))


if __name__ == "__main__":
    unittest.main()
