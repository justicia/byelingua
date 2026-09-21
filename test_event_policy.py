from season_ingestion.event_policy import apply_publication_policy, classify_performance_type, visitor_exclusion_reason
from season_ingestion.schema import CanonicalEvent


def event(title: str, *, event_type: str = "performance", raw=None, credits=None):
    return CanonicalEvent(
        source="test", source_event_id=title, source_url="https://example.test/event",
        organization="Example", venue="Example Hall", city="Berlin", country="Germany",
        timezone="Europe/Berlin", title=title, date="2026-09-01", start_time="19:00",
        end_time=None, room=None, event_type=event_type, raw=raw or {}, credits=credits or [],
    )


def test_visitor_tours_are_removed_before_publication():
    kept, report = apply_publication_policy([
        event("Architecture Tour"),
        event("Behind the Scenes Tour"),
        event("Exhibition Tours"),
        event("Tea and Tour"),
        event("FÜHRUNG BAUSTELLE STAMMHAUS"),
        event("TAWumm! Kinderführung - Auf Beethovens Spuren"),
        event("Tosca", raw={"category": "opera"}),
    ])

    assert [row.title for row in kept] == ["Tosca"]
    assert report["excluded_visitor_events"] == 6


def test_german_words_containing_fuhrung_are_not_tours():
    kept, report = apply_publication_policy([
        event("Einführungsmatinee SIEGFRIED"),
        event("Die Entführung aus dem Serail", raw={"category": "Opera"}),
    ])
    assert len(kept) == 2
    assert report["excluded_visitor_events"] == 0


def test_performance_types_are_not_collapsed_to_generic_performance():
    rows = [
        event("Tosca", raw={"category": "Opera"}),
        event("Swan Lake", raw={"category": "Ballet"}),
        event("Piano Recital"),
        event("Violin Concerto"),
    ]

    assert [classify_performance_type(row) for row in rows] == [
        "opera", "ballet", "recital", "concerto",
    ]


def test_unknown_generic_performance_is_explicitly_unclassified():
    assert classify_performance_type(event("Lucidity")) == "unclassified_performance"


def test_official_visitor_type_is_excluded_even_when_title_omits_tour():
    row = event("Stages and Cells of Covent Garden", event_type="visitor_activity")
    assert visitor_exclusion_reason(row) == "VISITOR_ACTIVITY"


def test_existing_canonical_event_type_keeps_underscore_form():
    row = event("Family Sundays", event_type="children_family")
    assert classify_performance_type(row) == "children_family"


def test_explicit_official_activity_type_wins_over_secondary_genre_tag():
    row = event("Friends Rehearsals", event_type="rehearsal", raw={"official_tags": ["Rehearsals", "Ballet and dance"]})
    assert classify_performance_type(row) == "rehearsal"


def test_plural_recitals_are_classified_as_recital():
    assert classify_performance_type(event("Recitals at Lunch")) == "recital"
