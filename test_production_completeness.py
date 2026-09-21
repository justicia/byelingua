from __future__ import annotations

from pathlib import Path

import season_ingestion.production_completeness as completeness
from season_ingestion.content_recovery import recover_missing_content
from season_ingestion.reconciliation import ExistingRecord


def _record(
    event_id: str,
    event_key: str,
    *,
    title: str = "The Ayoub Sisters",
    source_url: str = "https://bynder.southbankcentre.co.uk/asset/forward-planner.pdf",
) -> ExistingRecord:
    return ExistingRecord(
        event_id=event_id,
        source="southbank_centre",
        source_event_id=f"source-{event_id}",
        source_url=source_url,
        event_key=event_key,
        title=title,
        date="2026-10-11",
        fields={"start_time": "19:30", "event_type": "concert"},
    )


def _registry() -> dict:
    return {
        "venues": {
            "southbank_centre": {
                "source_id": "southbank_centre",
                "official_source": "https://www.southbankcentre.co.uk/whats-on",
                "listing_source": "https://www.southbankcentre.co.uk/whats-on",
                "organization": "Southbank Centre",
                "venue": "Southbank Centre",
                "city": "London",
                "country": "United Kingdom",
                "timezone": "Europe/London",
                "season_bounds": {"2026-27": {"season_start": "2026-09-01", "season_end": "2027-08-31"}},
            }
        }
    }


def test_collect_production_gaps_preserves_existing_identity_and_selects_missing_layers(monkeypatch):
    records = [_record("event-1", "southbank_centre:production-key-1"), _record("event-2", "southbank_centre:production-key-2")]

    monkeypatch.setattr(completeness, "fetch_existing_sources", lambda *args, **kwargs: records)

    def rows(table, select, event_ids, **kwargs):
        if table == "event_programme":
            return [{"event_id": "event-1", "work_id": "work-1", "order": 1}]
        return [{"event_id": "event-2", "artist_id": "artist-2", "role": "ensemble", "character": None}]

    monkeypatch.setattr(completeness, "_readonly_rows", rows)
    groups, baseline = completeness.collect_production_gap_events("2026-27", registry=_registry())

    assert baseline["events"] == 2
    assert baseline["production_gap_events"] == 2
    assert len(groups) == 1
    assert {event.event_key for event in groups[0]["events"]} == {
        "southbank_centre:production-key-1",
        "southbank_centre:production-key-2",
    }
    assert all(event.raw["production_event_key"] == event.event_key for event in groups[0]["events"])
    assert all(event.raw["source_records"] for event in groups[0]["events"])


def test_targeted_discovery_is_official_and_event_scoped(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_request(**kwargs):
        captured["request"] = kwargs
        return {"official_source_url": "https://official.example/season"}

    def fake_discovery(request, **kwargs):
        captured["discovery_request"] = request
        return {
            "discovered_endpoint": "https://official.example/events/ayoub-sisters",
            "detail_urls": [],
        }

    monkeypatch.setattr(completeness, "build_request", fake_request)
    monkeypatch.setattr(completeness, "acquire_source_discovery", fake_discovery)
    config = _registry()["venues"]["southbank_centre"] | {"official_source": "https://official.example/season"}
    event = completeness._build_gap_event(
        [_record("event-1", "southbank_centre:production-key-1")],
        config,
        programme_present=False,
        credits_present=False,
    )
    discover = completeness.build_targeted_discovery(
        venue_id="southbank_centre",
        season="2026-27",
        config=config,
        artifact_root=tmp_path,
    )

    assert discover(event) == ["https://official.example/events/ayoub-sisters"]
    targeted = captured["discovery_request"]["targeted_enrichment"]
    assert targeted["event_title"] == event.title
    assert targeted["event_date"] == event.date
    assert targeted["existing_source_url"] == event.source_url


def test_gap_scan_uses_secret_only_as_a_read_credential_when_available(monkeypatch):
    apply_modes = []
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test-secret-not-used-for-a-request")
    monkeypatch.setattr(
        completeness,
        "fetch_existing_sources",
        lambda *args, **kwargs: apply_modes.append(kwargs["apply_mode"]) or [],
    )

    completeness.collect_production_gap_events("2026-27", selected=["southbank_centre"], registry=_registry())

    assert apply_modes == [True]


def test_content_recovery_keeps_production_event_key_when_detail_enriches_existing_event():
    event = completeness._build_gap_event(
        [_record("event-1", "southbank_centre:production-key-1", title="The Ayoub Sisters", source_url="https://official.example/events/ayoub-sisters")],
        _registry()["venues"]["southbank_centre"],
        programme_present=False,
        credits_present=False,
    )

    class Adapter:
        def _fetch(self, url):
            return """
            <html><body><h1>The Ayoub Sisters</h1>
            <p>OBC</p><p>Music by Ludwig van Beethoven</p></body></html>
            """

    enriched = recover_missing_content(
        [event],
        adapter=Adapter(),
        config={"official_source": "https://official.example/season"},
        season="2026-27",
    )
    assert enriched["events"][0].event_key == "southbank_centre:production-key-1"
