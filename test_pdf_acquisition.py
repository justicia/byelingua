from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from season_ingestion import pdf_acquisition as pdf


PDF_URL = "https://www.barbican.org.uk/sites/default/files/documents/2026-04/Classical%20Music%20Listings%202026-27.pdf"


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, content: bytes):
        self.content = content
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.content)


def _request() -> dict:
    return {
        "venue_id": "barbican_centre",
        "season": "2026-27",
        "official_source_url": PDF_URL,
        "source_id": "barbican_centre",
        "source_contract": {"schema_version": "official-source-contract-v2", "writes": False},
    }


def _pdf_source() -> dict:
    return {
        "source_url": PDF_URL,
        "sha256": "a" * 64,
        "byte_size": 123,
        "page_count": 2,
    }


def _event(*, date: str, page: int, title: str = "Concert", programme_title: str = "Symphony") -> dict:
    return {
        "source_event_id": f"barbican-{date}",
        "source_url": PDF_URL,
        "title": title,
        "date": date,
        "start_time": "19:30",
        "end_time": None,
        "programme": [
            {
                "source_title": programme_title,
                "source_programme_index": 1,
                "original_programme_order": 1,
                "composer": "Composer",
                "provenance": {
                    "source_url": PDF_URL,
                    "pdf_page": page,
                    "source_field": "official.programme",
                },
            }
        ],
        "credits": [
            {
                "artist_name": "Artist",
                "source_role": "Piano",
                "function": "soloist",
                "credit_kind": "cast",
                "source_url": PDF_URL,
                "source_field": "official.pdf.credit",
                "provenance": {
                    "source_url": PDF_URL,
                    "pdf_page": page,
                    "source_field": "official.pdf.credit",
                },
            }
        ],
    }


def _partial(events: list[dict]) -> dict:
    return {
        "schema_version": "hermes-source-facts-v1",
        "venue_id": "barbican_centre",
        "season": "2026-27",
        "source_id": "barbican_centre",
        "source_type": "html",
        "official_source_url": PDF_URL,
        "source_contract": {"schema_version": "official-source-contract-v2", "writes": False},
        "events": events,
    }


def test_download_pdf_validates_and_fingerprints_cached_bytes(tmp_path, monkeypatch):
    payload = b"%PDF-1.7\nfixture"
    session = FakeSession(payload)
    monkeypatch.setattr(pdf, "_pdf_page_count", lambda path: 25)

    artifact = pdf.download_pdf(PDF_URL, tmp_path, session=session)

    assert artifact["source_url"] == PDF_URL
    assert artifact["byte_size"] == len(payload)
    assert artifact["page_count"] == 25
    assert artifact["sha256"] == hashlib.sha256(payload).hexdigest()
    assert Path(artifact["path"]).read_bytes() == payload
    assert session.calls[0][0] == PDF_URL
    assert session.calls[0][1]["timeout"] == pdf.DEFAULT_DOWNLOAD_TIMEOUT_SECONDS


def test_download_pdf_rejects_non_pdf_response(tmp_path):
    with pytest.raises(pdf.PdfAcquisitionError, match="%PDF-"):
        pdf.download_pdf(PDF_URL, tmp_path, session=FakeSession(b"not a pdf"))


def test_chunking_preserves_page_boundaries_and_char_limit():
    pages = [
        {"page": 1, "text": "one", "status": "TEXT_OK", "source_url": PDF_URL, "pdf_sha256": "a" * 64},
        {"page": 2, "text": "two", "status": "TEXT_OK", "source_url": PDF_URL, "pdf_sha256": "a" * 64},
        {"page": 3, "text": "three", "status": "TEXT_OK", "source_url": PDF_URL, "pdf_sha256": "a" * 64},
        {"page": 4, "text": "", "status": "TEXT_EMPTY", "source_url": PDF_URL, "pdf_sha256": "a" * 64},
    ]

    chunks = pdf.chunk_pdf_pages(pages, max_pages=2, max_chars=10)

    assert [[page["page"] for page in chunk["pages"]] for chunk in chunks] == [[1, 2], [3, 4]]
    assert all(chunk["char_count"] <= 10 for chunk in chunks)
    assert "[PDF PAGE 1]" in chunks[0]["text"]
    assert "[PDF PAGE 3]" not in chunks[0]["text"]


def test_chunk_prompt_contains_only_bounded_text_and_provenance():
    pages = [
        {"page": 2, "text": "Ariadne auf Naxos — 12 May 2027, 19:30", "status": "TEXT_OK", "source_url": PDF_URL, "pdf_sha256": "b" * 64},
        {"page": 3, "text": "Staatsoper Unter den Linden", "status": "TEXT_OK", "source_url": PDF_URL, "pdf_sha256": "b" * 64},
    ]
    chunk = pdf.chunk_pdf_pages(pages, max_pages=1, max_chars=2000)[0]

    prompt = pdf.build_pdf_chunk_prompt(_request(), chunk, pdf_source=_pdf_source())

    assert "Do not use Browser Automation" in prompt
    assert "Ariadne auf Naxos" in prompt
    assert "Staatsoper Unter den Linden" not in prompt
    assert '"page": 2' in prompt
    assert "Never send the whole PDF" not in prompt


def test_merge_deduplicates_occurrence_not_production_title():
    first = _event(date="2027-05-12", page=4, programme_title="Symphony")
    duplicate = _event(date="2027-05-12", page=4, programme_title="Symphony")
    second_occurrence = _event(date="2027-05-13", page=5, programme_title="Symphony")

    facts = pdf.merge_pdf_chunk_facts(
        [_partial([first, second_occurrence]), _partial([duplicate])],
        request=_request(),
        pdf_source=_pdf_source(),
    )

    assert len(facts["events"]) == 2
    assert [event["date"] for event in facts["events"]] == ["2027-05-12", "2027-05-13"]
    assert facts["events"][0]["programme"][0]["source_programme_index"] == 1
    assert facts["source_contract"]["pdf_source_mode"] == "FULL_SOURCE"


def test_merge_rejects_all_empty_partial_chunks():
    with pytest.raises(pdf.PdfAcquisitionError, match="no explicit events"):
        pdf.merge_pdf_chunk_facts(
            [_partial([])],
            request=_request(),
            pdf_source=_pdf_source(),
        )


def _layout_line(text: str, *, bold: bool = False, words: list[dict] | None = None) -> dict:
    return {
        "page": 2,
        "column": 1,
        "text": text,
        "words": words or [{"text": token, "bold": bold, "italic": False} for token in text.split()],
        "bold_ratio": 1.0 if bold else 0.0,
    }


def test_deterministic_segmentation_and_extraction_uses_columns_and_dates():
    pages = [
        {
            "page": 2,
            "source_url": PDF_URL,
            "columns": [
                {
                    "column": 1,
                    "lines": [
                        _layout_line("October 2026"),
                        _layout_line("London Symphony Orchestra", bold=True),
                        _layout_line(
                            "Ludwig van Beethoven Symphony No. 5",
                            words=[
                                {"text": "Ludwig", "bold": True},
                                {"text": "van", "bold": True},
                                {"text": "Beethoven", "bold": True},
                                {"text": "Symphony", "bold": False},
                                {"text": "No.", "bold": False},
                                {"text": "5", "bold": False},
                            ],
                        ),
                        _layout_line(
                            "Sir Simon Rattle conductor",
                            words=[
                                {"text": "Sir", "bold": True},
                                {"text": "Simon", "bold": True},
                                {"text": "Rattle", "bold": True},
                                {"text": "conductor", "bold": False},
                            ],
                        ),
                        _layout_line("Sat 3 Oct 2026, 7.30pm, Hall", bold=True),
                        _layout_line("BBC Symphony Orchestra", bold=True),
                        _layout_line(
                            "Johannes Brahms Symphony No. 1",
                            words=[
                                {"text": "Johannes", "bold": True},
                                {"text": "Brahms", "bold": True},
                                {"text": "Symphony", "bold": False},
                                {"text": "No.", "bold": False},
                                {"text": "1", "bold": False},
                            ],
                        ),
                        _layout_line("Sun 4 Oct 2026, 7pm, Milton Court", bold=True),
                    ],
                }
            ],
        }
    ]

    blocks = pdf.segment_event_blocks(pages)
    facts, residual = pdf.build_deterministic_source_facts(
        _request(),
        blocks,
        pdf_source=_pdf_source(),
    )

    assert len([block for block in blocks if block["kind"] == "single"]) == 2
    assert residual == []
    assert len(facts["events"]) == 2
    assert facts["events"][0]["title"] == "London Symphony Orchestra"
    assert facts["events"][0]["date"] == "2026-10-03"
    assert facts["events"][0]["start_time"] == "19:30"
    assert facts["events"][0]["room"] == "Hall"
    assert facts["events"][0]["programme"][0]["source_title"] == "Symphony No. 5"
    assert facts["events"][0]["credits"][0]["artist_name"] == "Sir Simon Rattle"
    assert facts["events"][0]["provenance"]["pdf_page"] == 2


def test_range_only_blocks_are_not_emitted_as_occurrences():
    pages = [
        {
            "page": 1,
            "source_url": PDF_URL,
            "columns": [
                {
                    "column": 2,
                    "lines": [
                        _layout_line("An Anatomy of Melancholy", bold=True),
                        _layout_line("9-13 Sep 2026, various times, The Pit"),
                    ],
                }
            ],
        }
    ]

    blocks = pdf.segment_event_blocks(pages)

    assert len(blocks) == 1
    assert blocks[0]["kind"] == "range"
    assert blocks[0]["date"] is None


def test_residual_prompt_is_bounded_and_browser_free():
    block = {
        "pdf_page": 4,
        "raw_text": "Unresolved heading\n" + ("source text " * 500),
    }

    prompt = pdf.build_residual_block_prompt(_request(), block, source_url=PDF_URL)

    assert len(prompt) <= 3000
    assert "Browser Automation" in prompt
    assert "web search" in prompt
    assert "PDF download" in prompt
    assert "source text" in prompt
