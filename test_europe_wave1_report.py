from jobs.render_europe_wave1_report import build_report


def test_wave1_report_has_required_totals_and_compact_blocker_rows():
    report = build_report({
        "venues": [
            {"venue_id": "wiener_musikverein", "status": "READY_FOR_APPROVAL", "summary": {"counts": {"events": 5, "safe_programme_relationships": 4, "credits_safe": 3}}},
            {"venue_id": "bozar", "status": "SOURCE_PARTIAL", "blocker": "detail mapping missing", "next_technical_fix": "add detail parser", "summary": {}},
        ]
    })
    assert report["VENUES_ATTEMPTED"] == 2
    assert report["VENUES_PRODUCTION_READY"] == 1
    assert report["VENUES_BLOCKED"] == 1
    assert report["TOTAL_PRODUCTION_VENUES"] == 10
    assert report["TOTAL_EVENTS"] == 5
    assert report["TOTAL_PROGRAMME_RELATIONSHIPS"] == 4
    assert report["TOTAL_CREDITS"] == 3
    assert report["blocked"] == [{"venue": "bozar", "blocker": "detail mapping missing", "next technical fix": "add detail parser"}]
