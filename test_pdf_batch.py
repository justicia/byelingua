from __future__ import annotations

from season_ingestion.pdf_batch import (
    BATCH_VENUES,
    _facts_from_blocks,
    segment_enrichment_pages,
    segment_komische_calendar,
)


PDF_URL = "https://example.test/komische.pdf"
SHA = "a" * 64


def _page(number: int, text: str) -> dict:
    return {
        "page": number,
        "text": text,
        "status": "TEXT_OK",
        "source_url": PDF_URL,
        "pdf_sha256": SHA,
    }


def test_batch_targets_are_exactly_the_requested_five_and_exclude_frozen_venues():
    assert BATCH_VENUES == (
        "deutsche_oper_berlin",
        "dutch_national_opera",
        "komische_oper_berlin",
        "theatre_champs_elysees",
        "southbank_centre",
    )
    assert "barbican_centre" not in BATCH_VENUES
    assert "elbphilharmonie" not in BATCH_VENUES
    assert "tonhalle_zurich" not in BATCH_VENUES
    assert "lauditori_barcelona" not in BATCH_VENUES


def test_komische_calendar_adapter_uses_explicit_month_year_and_occurrence_rows():
    pages = [
        _page(
            171,
            """169
SPIELPLAN
September 2O26
MI
16.
19:30 Lear PREMIERE P
@FLUGHAFEN TEMPELHOF / HANGAR 4
FR 18. 19:30 Lear @FLUGHAFEN TEMPELHOF / HANGAR 4 D
oktober 2O26
DO 1. 19:30 Lear E
""",
        )
    ]

    blocks = segment_komische_calendar(pages)

    assert [(block["date"], block["times"][0], block["title"]) for block in blocks] == [
        ("2026-09-16", "19:30", "Lear"),
        ("2026-09-18", "19:30", "Lear"),
        ("2026-10-01", "19:30", "Lear"),
    ]
    assert blocks[0]["room"] == "FLUGHAFEN TEMPELHOF / HANGAR 4"
    assert blocks[0]["pdf_page"] == 171


def test_komische_calendar_continuation_line_is_not_an_invented_occurrence():
    pages = [_page(178, "April 2O27\nSO 4. 12:00 EINFÜHRUNGSMATINEE\nKonrad oder Das Kind aus\n16:00 der Konservenbüchse WIEDERAUFNAHME C\n")]

    blocks = segment_komische_calendar(pages)

    assert len(blocks) == 2
    assert blocks[0]["title"] == "EINFÜHRUNGSMATINEE"
    assert blocks[1]["title"] == "Konrad oder Das Kind aus der Konservenbüchse"
    assert blocks[1]["date"] == "2027-04-04"


def test_batch_facts_keep_pdf_provenance_without_inventing_programme_from_calendar_title():
    request = {
        "venue_id": "komische_oper_berlin",
        "season": "2026-27",
        "source_id": "komische_oper_berlin",
        "official_source_url": PDF_URL,
        "source_contract": {"writes": False},
    }
    source = {"source_url": PDF_URL, "sha256": SHA, "byte_size": 10, "page_count": 1}
    blocks = [{
        "block_index": 1,
        "kind": "single",
        "date": "2026-09-16",
        "times": ["19:30"],
        "title": "Lear",
        "add_programme": True,
        "pdf_page": 171,
        "pdf_pages": [171],
        "source_url": PDF_URL,
        "pdf_sha256": SHA,
        "raw_text": "19:30 Lear",
    }]

    facts = _facts_from_blocks(request, blocks, source)

    event = facts["events"][0]
    assert event["provenance"]["source_url"] == PDF_URL
    assert event["provenance"]["pdf_page"] == 171
    assert event["provenance"]["pdf_sha256"] == SHA
    assert event["programme"] == []
    assert event["data_quality"]["programme"]["status"] == "NO_PROGRAMME_EVIDENCE"


def test_enrichment_only_pages_are_review_blocks_not_occurrences():
    pages = [_page(1, "Premieren\nPremiere: 19. September 2026\n"), _page(2, "Forward planner highlights\n")]

    deutsche = segment_enrichment_pages(pages, "deutsche_oper_berlin")
    southbank = segment_enrichment_pages(pages, "southbank_centre")

    assert len(deutsche) == 1
    assert deutsche[0]["kind"] == "enrichment"
    assert len(southbank) == 2
    assert all(block["kind"] == "enrichment" for block in southbank)
