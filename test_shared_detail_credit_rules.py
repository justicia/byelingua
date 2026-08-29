from __future__ import annotations

from bs4 import BeautifulSoup

from season_ingestion.adapters.detail_linked_listing import _credits
from season_ingestion.credit_resolution import canonical_role, resolve_credit
from season_ingestion.adapters.teatro_real import TeatroRealAdapter


def test_multilingual_team_labels_normalize_without_name_specific_rules():
    assert canonical_role("Dirección musical") == "conductor"
    assert canonical_role("Chef d'orchestre") == "conductor"
    assert canonical_role("mise en scène") == "stage_director"
    assert canonical_role("Director") == "stage_director"
    assert canonical_role("Orquesta") == "orchestra"
    assert canonical_role("Chœur") == "choir"


def test_structured_tables_separate_cast_from_team_and_filter_alternate_dates():
    html = """
    <table class='team'><tr><th>Dirección musical</th><td>María García</td></tr>
      <tr><th>Orquesta</th><td>Orquesta A, Orquesta B</td></tr></table>
    <section id='cast'><table><tr><td class='dt'>Rodolfo</td>
      <td>Ana Pérez (3, 6 Feb.) / Lucía López (23 Feb.)</td></tr></table></section>
    """
    rows = _credits(BeautifulSoup(html, "html.parser"), "https://official.example/detail", "2027-02-23")
    assert {(row["function"], row["credit_kind"]) for row in rows} == {
        ("conductor", "artistic_team"), ("orchestra", "ensemble"), ("performer", "cast")
    }
    cast = [row for row in rows if row["credit_kind"] == "cast"]
    assert [row["artist_name"] for row in cast] == ["Lucía López"]
    assert cast[0]["character"] == cast[0]["raw_character"] == "Rodolfo"
    assert {row["artist_name"] for row in rows if row["credit_kind"] == "ensemble"} == {"Orquesta A", "Orquesta B"}


def test_unresolved_raw_character_is_preserved_for_review():
    result = resolve_credit({
        "artist_name": "Ana Pérez",
        "source_role": "Rodolfo",
        "credit_kind": "cast",
        "raw_character": "Rodolfo",
    }, work_id=None, snapshot=type("Snapshot", (), {"entities": {"artist": []}, "character_aliases": []})())
    assert result["source_character"] == "Rodolfo"
    assert result["resolution_status"] == "SAFE_UNRESOLVED_CHARACTER"


def test_teatro_real_detail_enrichment_reuses_production_team_and_filters_cast_by_date():
    calendar = """
    <div class='calendario-mensual-sidebar'><div class='item-box' id='box02-2027-23'>
      <div class='contentbox'><div class='item-box--premiere__text--title'><span>Ópera</span>
        <h3><a href='/es/espectaculo/example'>Example</a></h3></div>
        <div class='item-box--premiere__text--btn'><a>19:30</a></div></div></div></div>
    """
    detail = """
    <div class='wrap-content-hero'><h4>Ópera</h4><h2>Wolfgang Amadeus Mozart</h2><h1>Example</h1></div>
    <ul class='lista-artistas'><li><span class='lista-artistas-text'>Dirección musical</span>
      <span class='lista-artistas-title'>Maestra Example</span></li></ul>
    <div class='page-thumb-artist__block'><p><a><span class='position'>Rodolfo</span>
      <span class='title'>Singer Example</span><span class='date'>Feb - 23</span></a></p></div>
    """
    settings = {
        "organization": "Teatro Real", "venue": "Teatro Real", "city": "Madrid",
        "country": "Spain", "timezone": "Europe/Madrid",
        "calendar_url": "https://www.teatroreal.es/en/calendario",
        "season_bounds": {"2026-27": {"season_start": "2026-09-01", "season_end": "2027-07-31"}},
        "detail_enrichment": True,
    }
    pages = {
        settings["calendar_url"]: calendar,
        "https://www.teatroreal.es/es/espectaculo/example": detail,
    }
    events = TeatroRealAdapter(settings, fetch=pages.__getitem__).ingest("2026-27")
    assert len(events) == 1
    assert events[0].programme[0]["composer"] == "Wolfgang Amadeus Mozart"
    assert {row["function"] for row in events[0].credits} == {"conductor", "performer"}
    assert {row["artist_name"] for row in events[0].credits} == {"Maestra Example", "Singer Example"}
