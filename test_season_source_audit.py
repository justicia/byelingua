from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

import jobs.audit_season_sources as audit_job
from season_ingestion.audit import (
    IDENTITY_SHAPES,
    PRODUCTION_SOURCES,
    AuditReadError,
    audit_season_sources,
    classify_identity,
    fetch_source_rows,
    summarize_source,
)


CONFIG = {
    "venues": {
        source: (
            {"season_bounds": {"2026-27": {"season_start": "2026-08-28", "season_end": "2027-08-31"}}}
            if source == "operadeparis"
            else {}
        )
        for source in PRODUCTION_SOURCES
    }
}


def row(number: int, *, source_id: str | None = None, date: str = "2026-09-01", url: str | None = None):
    identity = str(number) if source_id is None else source_id
    return {
        "event_id": f"event-{number}",
        "source_event_id": identity,
        "event_key": f"test:{identity}" if identity else None,
        "date": date,
        "source_url": url or f"https://official.example/events/{number}",
    }


class Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def api_row(number: int):
    return {
        "event_id": f"event-{number}",
        "source": "operadeparis",
        "source_event_id": str(number),
        "source_url": "https://www.operadeparis.fr/production",
        "events": {"id": f"event-{number}", "event_key": f"operadeparis:{number}", "date": "2026-09-01"},
    }


def test_default_run_audits_all_five_sources_and_resolves_bounds():
    calls = []

    def fetch(source, start, end):
        calls.append((source, start, end))
        return [row(len(calls))]

    report = audit_season_sources("2026-27", CONFIG, fetch_rows=fetch)

    assert report["source_count"] == 5
    assert report["total_records"] == 5
    assert report["audit_passed"] is True
    assert {source["source"] for source in report["sources"]} == set(PRODUCTION_SOURCES)
    assert calls[1] == ("operadeparis", "2026-08-28", "2027-08-31")
    assert all(call[1:] == ("2026-09-01", "2027-08-31") for call in calls if call[0] != "operadeparis")
    assert report["sources"][1]["season_bounds_source"] == "configured"
    assert report["sources"][0]["season_bounds_source"] == "default"


def test_fetch_uses_filtered_explicit_select_and_multiple_pages(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://database.example")
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly-test-value")
    requests = []

    def fetcher(request, timeout):
        requests.append(request)
        offset = int(parse_qs(urlparse(request.full_url).query)["offset"][0])
        return Response([api_row(offset + 1), api_row(offset + 2)] if offset == 0 else [api_row(3)])

    rows = fetch_source_rows("operadeparis", "2026-08-28", "2027-08-31", page_size=2, fetcher=fetcher)

    assert len(rows) == 3
    assert len(requests) == 2
    query = parse_qs(urlparse(requests[0].full_url).query)
    assert query["source"] == ["eq.operadeparis"]
    assert query["events.date"] == ["gte.2026-08-28", "lte.2027-08-31"]
    assert query["order"] == ["event_id.asc,source_event_id.asc"]
    assert query["select"] == ["event_id,source,source_event_id,source_url,events!inner(id,event_key,date)"]
    assert "*" not in query["select"][0]
    assert all(request.get_method() == "GET" for request in requests)
    assert all(request.data is None for request in requests)


def test_same_event_id_with_different_source_ids_reads_all_pages(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://database.example")
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly-test-value")

    first = api_row(1)
    second = api_row(2)
    second["event_id"] = first["event_id"]
    second["events"]["id"] = first["event_id"]
    pages = iter(([first], [second], []))

    rows = fetch_source_rows(
        "operadeparis",
        "2026-08-28",
        "2027-08-31",
        page_size=1,
        fetcher=lambda *_args, **_kwargs: Response(next(pages)),
    )

    assert [item["source_event_id"] for item in rows] == ["1", "2"]


def test_exact_source_row_repeated_across_pages_reports_pagination_duplicate(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://database.example")
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly-test-value")

    with pytest.raises(AuditReadError, match="duplicate source row") as error:
        fetch_source_rows("operadeparis", "2026-08-28", "2027-08-31", page_size=1, fetcher=lambda *_args, **_kwargs: Response([api_row(1)]))

    assert error.value.code == "pagination_duplicate_row"


def test_pagination_nontermination_is_an_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://database.example")
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly-test-value")

    count = 0

    def unique_pages(*_args, **_kwargs):
        nonlocal count
        count += 1
        return Response([api_row(count)])

    with pytest.raises(AuditReadError, match="did not terminate"):
        fetch_source_rows("operadeparis", "2026-08-28", "2027-08-31", page_size=1, maximum_pages=2, fetcher=unique_pages)


def test_pagination_duplicate_row_code_is_preserved_in_report():
    def duplicate(*_args):
        raise AuditReadError("pagination returned duplicate source row", code="pagination_duplicate_row")

    report = audit_season_sources("2026-27", CONFIG, sources=["operadeparis"], fetch_rows=duplicate)

    assert report["sources"][0]["failures"][0]["code"] == "pagination_duplicate_row"


@pytest.mark.parametrize(
    ("value", "source", "expected"),
    [
        ("8928", "operadeparis", "numeric"),
        ("123e4567-e89b-12d3-a456-426614174000", "x", "uuid"),
        ("operadeparis:8928", "operadeparis", "source_prefixed"),
        ("opera-2026-09-12-1930", "x", "date_composite"),
        ("le-barbier-de-seville", "operadeparis", "slug_or_text"),
        ("https://example.org/event", "x", "url_like"),
        ("###", "x", "other"),
    ],
)
def test_identity_classification(value, source, expected):
    assert classify_identity(value, source) == expected


def test_identity_statistics_use_all_rows_while_samples_are_bounded():
    rows = [row(i, source_id=str(i)) for i in range(1, 26)]
    report = summarize_source("test", "2026-09-01", "2027-08-31", rows, bounds_source="default")

    assert report["identity_shape"]["numeric"] == 25
    assert set(report["identity_shape"]) == set(IDENTITY_SHAPES)
    assert len(report["sample_first_events"]) == 10
    assert len(report["sample_last_events"]) == 10


def test_reused_production_url_is_informational_and_capped():
    rows = [row(i, url="https://official.example/one-production") for i in range(25)]
    report = summarize_source("test", "2026-09-01", "2027-08-31", rows, bounds_source="default")

    assert report["audit_passed"] is True
    assert report["reused_url_count"] == 1
    assert report["top_reused_urls"][0]["record_count"] == 25
    assert len(report["top_reused_urls"][0]["source_event_ids"]) == 20


@pytest.mark.parametrize(
    ("rows", "code"),
    [
        ([], "zero_records"),
        ([row(1, source_id="")], "missing_source_event_ids"),
        ([row(1, source_id="same"), row(2, source_id="same")], "duplicate_source_identities"),
        ([row(1, date="2026-08-31")], "out_of_season_bounds"),
    ],
)
def test_required_data_failures_block_audit(rows, code):
    report = summarize_source("test", "2026-09-01", "2027-08-31", rows, bounds_source="default")
    assert report["audit_passed"] is False
    assert code in {failure["code"] for failure in report["failures"]}


def test_multiple_source_identities_per_event_id_is_a_data_quality_failure():
    first = row(1, source_id="production-a")
    second = row(2, source_id="production-b")
    second["event_id"] = first["event_id"]

    report = summarize_source("test", "2026-09-01", "2027-08-31", [first, second], bounds_source="default")

    issue = report["multiple_source_identities_per_event_id"]
    assert issue == {
        "count": 1,
        "samples": [
            {
                "event_id": "event-1",
                "source_identities": [
                    {"source": "test", "source_event_id": "production-a"},
                    {"source": "test", "source_event_id": "production-b"},
                ],
            }
        ],
    }
    assert report["audit_passed"] is False
    assert "multiple_source_identities_per_event_id" in {failure["code"] for failure in report["failures"]}


def test_permission_error_preserves_complete_report():
    def denied(*_args):
        raise AuditReadError("Supabase audit read returned HTTP 403")

    report = audit_season_sources("2026-27", CONFIG, fetch_rows=denied)

    assert report["audit_passed"] is False
    assert report["source_count"] == 5
    assert len(report["sources"]) == 5
    assert len(report["failures"]) == 5
    assert all(source["failures"][0]["code"] == "read_or_configuration_error" for source in report["sources"])


def test_http_permission_error_is_sanitized(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://database.example")
    monkeypatch.setenv("SUPABASE_READONLY_KEY", "readonly-test-value")

    def denied(request, timeout):
        raise HTTPError(request.full_url, 403, "forbidden", {}, None)

    with pytest.raises(AuditReadError, match="HTTP 403"):
        fetch_source_rows("operadeparis", "2026-08-28", "2027-08-31", fetcher=denied)


def test_cli_writes_failure_report_and_returns_nonzero(monkeypatch, tmp_path):
    output = tmp_path / "season-source-audit.json"
    failed_report = {
        "generated_at": "2026-08-15T00:00:00+00:00",
        "season": "2026-27",
        "source_count": 5,
        "total_records": 0,
        "audit_passed": False,
        "sources": [],
        "failures": [{"source": "operadeparis", "failures": [{"code": "read_or_configuration_error"}]}],
    }
    monkeypatch.setattr(audit_job, "audit_season_sources", lambda *_args: failed_report)

    result = audit_job.main(["--season", "2026-27", "--output", str(output)])

    assert result == 1
    assert json.loads(output.read_text()) == failed_report


def test_workflow_is_manual_read_only_and_always_uploads_failure_report():
    workflow = open(".github/workflows/season-source-audit.yml", encoding="utf-8").read()

    assert "name: Season source audit" in workflow
    assert "workflow_dispatch:" in workflow
    assert "SUPABASE_READONLY_KEY:" in workflow
    assert "SUPABASE_SECRET_KEY" not in workflow
    assert "if: always()" in workflow
    assert "season-source-audit.json" in workflow
    for forbidden in ("schedule:", "push:", "pull_request:", "sync_season.py", "apply", "insert", "update", "delete"):
        assert forbidden not in workflow.lower()
