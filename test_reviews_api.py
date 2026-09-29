import unittest
from unittest.mock import patch

from api import reviews


class ReviewScoreTests(unittest.TestCase):
    def test_final_score_uses_overall_and_component_categories(self):
        rows = [
            {"component_type": "conductor", "rating": 5},
            {"component_type": "soloist", "rating": 4},
            {"component_type": "orchestra", "rating": 5},
            {"component_type": "stage", "rating": 3},
        ]
        self.assertEqual(reviews._final_score(5, rows), 4.6)

    def test_multiple_soloists_count_as_one_component_category(self):
        rows = [
            {"component_type": "conductor", "rating": 5},
            {"component_type": "soloist", "rating": 5},
            {"component_type": "soloist", "rating": 4},
            {"component_type": "orchestra", "rating": 5},
            {"component_type": "stage", "rating": 4},
        ]
        self.assertEqual(reviews._final_score(5, rows), 4.8)

    def test_overall_is_final_when_no_components_are_rated(self):
        self.assertEqual(reviews._final_score(4, []), 4.0)


class PersonalStatusTests(unittest.TestCase):
    def test_attended_takes_precedence(self):
        self.assertEqual(
            reviews._derived_personal_status({"attendance_status": "attended", "intent_status": "interested"}),
            "attended",
        )

    def test_must_go_maps_to_going_for_legacy_rows(self):
        self.assertEqual(
            reviews._derived_personal_status({"attendance_status": None, "intent_status": "must_go"}),
            "going",
        )


class PublicReviewPrivacyTests(unittest.TestCase):
    def test_public_response_never_returns_user_id(self):
        event = {"id": "event-internal", "event_key": "event-public", "title": "Test", "date": "2026-09-29"}
        database_reviews = [{
            "id": "review-1",
            "user_id": "user-secret",
            "overall_rating": 5,
            "final_score": 4.8,
            "comment": "Excellent.",
            "identity_mode": "anonymous",
            "updated_at": "2026-09-29T10:00:00+00:00",
        }]

        def fake_supabase(method, path, **kwargs):
            if path == "/rest/v1/event_reviews":
                return database_reviews
            if path == "/rest/v1/user_event_component_ratings":
                return []
            if path == "/rest/v1/profiles":
                self.fail("Anonymous reviews must not query public profile data.")
            return []

        with patch.object(reviews, "_event_internal_id", return_value="event-internal"), \
             patch.object(reviews, "_event_rows", return_value=[event]), \
             patch.object(reviews, "supabase_service", side_effect=fake_supabase):
            payload = reviews.public_event_reviews("event-public")

        self.assertEqual(payload["reviews"][0]["author"]["display_name"], "Anonymous")
        self.assertNotIn("user_id", payload["reviews"][0])
        self.assertNotIn("user-secret", repr(payload["reviews"]))


if __name__ == "__main__":
    unittest.main()
