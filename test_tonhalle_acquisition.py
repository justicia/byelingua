from __future__ import annotations

import json

from season_ingestion.tonhalle_acquisition import acquire_source_facts


OFFICIAL = "https://tonhalle-orchester.ch/en/concerts/saison-2026-27/"
DETAIL = "https://tonhalle-orchester.ch/en/concerts/ariadne-auf-naxos/"


def _config() -> dict:
    return {
        "venue_id": "tonhalle_zurich",
        "source_id": "tonhalle_zurich",
        "official_source": OFFICIAL,
        "listing_source": OFFICIAL,
        "organization": "Tonhalle-Gesellschaft Zürich",
        "venue": "Tonhalle Zürich",
        "city": "Zürich",
        "country": "Switzerland",
        "timezone": "Europe/Zurich",
        "source_contract": {"writes": False},
    }


LISTING_DOCUMENT = {
    "@type": "Event",
    "name": "Ariadne auf Naxos",
    "startDate": "2026-09-16T19:30:00+02:00",
    "url": DETAIL,
    "location": {"@type": "Place", "name": "Tonhalle Maag"},
}
DETAIL_DOCUMENT = {
    "@type": "Event",
    "name": "Ariadne auf Naxos",
    "startDate": "2026-09-16T19:30:00+02:00",
    "url": DETAIL,
    "location": {"@type": "Place", "name": "Tonhalle Maag"},
    "workPerformed": [{
        "@type": "MusicComposition",
        "name": "Ariadne auf Naxos",
        "composer": {"@type": "Person", "name": "Richard Strauss"},
    }],
    "performer": [{"@type": "Person", "name": "José Example"}],
}
LISTING = f'<html><body><div class="js-calendarlist-list"><div class="row data"><div class="col-left"><div class="date">Wed 16. Sep</div><div class="hour">19.30</div></div><div class="col-middle"><div class="event" data-timestamp="1789579800"><h3>Ariadne auf Naxos</h3></div><div class="member"><span class="member-name">José Example</span><span class="member-function">Soloist</span></div><a class="desktop-linkoverlay" href="{DETAIL}"></a></div></div></div><script type="application/ld+json">{json.dumps(LISTING_DOCUMENT)}</script></body></html>'
DETAIL_PAGE = f'<html><body><script type="application/ld+json">{json.dumps(DETAIL_DOCUMENT)}</script></body></html>'


class _Response:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


class _Session:
    def get(self, url, **kwargs):
        assert kwargs["timeout"] == 30
        return _Response(DETAIL_PAGE if "/ariadne-auf-naxos/" in url else LISTING)


def test_deterministic_tonhalle_monthly_acquisition_returns_contract_facts():
    facts, metadata = acquire_source_facts(
        config=_config(),
        season="2026-27",
        discovery={
            "status": "PASS",
            "discovered_mode": "HTML",
            "discovered_endpoint": "https://www.tonhalle-orchester.ch/en/concerts/kalender/?date={month_epoch}",
            "pagination": "month query parameter date",
        },
        session=_Session(),
    )

    assert len(facts["events"]) == 1
    assert facts["events"][0]["title"] == "Ariadne auf Naxos"
    assert facts["events"][0]["programme"][0]["composer"] == "Richard Strauss"
    assert facts["events"][0]["credits"][0]["artist_name"] == "José Example"
    assert metadata["events"] == 1
    assert metadata["programme"] == 1
    assert metadata["credits"] == 1
