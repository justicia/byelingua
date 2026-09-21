from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from season_ingestion.production_identity import production_identity_preflight


class _Response:
    status = 200

    def __init__(self, count: int):
        self.headers = {"Content-Range": f"0-0/{count}"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps([{"event_id": "sentinel"}]).encode("utf-8")


def test_wrong_project_is_not_replaced_with_another_reference():
    calls = []

    def fetcher(request, timeout):
        calls.append(request.full_url)
        return _Response(999)

    report = production_identity_preflight(
        supabase_url="https://another-project.supabase.co",
        readonly_key="readonly",
        fetcher=fetcher,
    )
    assert report["production_preflight"] == "FAIL"
    assert report["reason"] == "WRONG_PROJECT"
    assert calls == []


def test_correct_project_without_read_credential_is_credential_failure():
    report = production_identity_preflight(
        supabase_url="https://pdtunknwruokybtuehua.supabase.co",
        readonly_key="",
    )
    assert report == {
        "production_preflight": "FAIL",
        "reason": "CREDENTIAL_OR_QUERY_PATH",
        "production_project_ref": "pdtunknwruokybtuehua",
        "expected_project_ref": "pdtunknwruokybtuehua",
        "sentinel_counts": {},
    }


def test_correct_project_with_visible_sentinels_passes():
    expected = {
        "palau_de_la_musica_catalana": 444,
        "royal_opera_house": 446,
        "teatro_alla_scala": 190,
        "auditorio_nacional": 548,
    }

    def fetcher(request, timeout):
        query = parse_qs(urlparse(request.full_url).query)
        text = query["or"][0]
        key = next(name for name in expected if name.replace("_", " ").split()[0] in text.lower())
        return _Response(expected[key])

    report = production_identity_preflight(
        supabase_url="https://pdtunknwruokybtuehua.supabase.co",
        readonly_key="readonly",
        fetcher=fetcher,
    )
    assert report["production_preflight"] == "PASS"
    assert report["reason"] is None
    assert report["sentinel_counts"] == expected


def test_correct_project_but_zero_sentinels_fails_without_ref_search():
    calls = []

    def fetcher(request, timeout):
        calls.append(request.full_url)
        return _Response(0)

    report = production_identity_preflight(
        supabase_url="https://pdtunknwruokybtuehua.supabase.co",
        readonly_key="readonly",
        fetcher=fetcher,
    )
    assert report["production_preflight"] == "FAIL"
    assert report["reason"] == "CREDENTIAL_OR_QUERY_PATH"
    assert report["production_project_ref"] == "pdtunknwruokybtuehua"
    assert all("pdtunknwruokybtuehua.supabase.co" in call for call in calls)
