from __future__ import annotations

import json
from pathlib import Path

from ingestion.adapters.teatro_real import _parse_credit_column, build_preview, parse_calendar_html, parse_detail_html
from ingestion.schema import normalize_search_key, searchable_text, stable_event_identity, validate_event


CALENDAR_FIXTURE = """
<div class="calendario-mensual-sidebar">
  <div class="item-box" id="box09-2026-23">
    <div class="contentbox"><div class="item-box--premiere__text">
      <div class="item-box--premiere__text--title"><a><span>Ópera</span><h3><a href="/es/espectaculo/manon-lescaut">Manon Lescaut</a></h3></a></div>
      <div class="item-box--premiere__text--btn"><a>19:30</a></div>
    </div></div>
  </div>
</div>
"""


def test_calendar_is_performance_level_and_has_stable_identity():
    first = parse_calendar_html(CALENDAR_FIXTURE)
    second = parse_calendar_html(CALENDAR_FIXTURE)
    assert len(first) == 1
    assert first[0]["date"] == "2026-09-23"
    assert first[0]["start_time"] == "19:30"
    assert first[0]["source_url"].endswith("/es/espectaculo/manon-lescaut")
    assert first[0]["event_type"] == "opera"
    assert stable_event_identity(first[0]) == stable_event_identity(second[0])


def test_pdf_credit_semantics_keep_cast_and_artistic_team_separate():
    cast_lines = [
        {"text": "Manon Lescaut", "fonts": {"FoundrySterling-Light"}, "demi_text": "", "label_text": "Manon Lescaut"},
        {"text": "Sondra Radvanovsky 23 sep", "fonts": {"FoundrySterling-Demi", "BookExpert"}, "demi_text": "Sondra Radvanovsky", "label_text": ""},
        {"text": "Lescaut Lucas Meachem", "fonts": {"FoundrySterling-Light", "FoundrySterling-Demi"}, "demi_text": "Lucas Meachem", "label_text": "Lescaut"},
    ]
    team_lines = [
        {"text": "Dirección musical Conductor", "fonts": {"FoundrySterling-Book"}, "demi_text": "", "label_text": "Dirección musical Conductor"},
        {"text": "Nicola Luisotti", "fonts": {"FoundrySterling-Demi"}, "demi_text": "Nicola Luisotti", "label_text": ""},
    ]
    cast = _parse_credit_column(cast_lines, cast=True)
    team = _parse_credit_column(team_lines, cast=False)
    assert cast[0]["character_role"] == "Manon Lescaut"
    assert cast[0]["person"] == "Sondra Radvanovsky"
    assert cast[0]["role_type"] == "character"
    assert cast[1]["character_role"] == "Lescaut"
    assert team[0]["artistic_function"] == "Conductor"
    assert team[0]["character_role"] is None


def test_search_normalization_preserves_display_values():
    event = {
        "title": "Le nozze di Figaro",
        "display_title": "Las bodas de Fígaro",
        "organization": "Teatro Real",
        "venue": "Théâtre de test",
        "city": "Madrid",
        "programme": [{"title": "Œuvre", "composer": "François Test"}],
        "credits": [{"person": "Hélène", "character_role": "Susanna"}],
    }
    key = searchable_text(event)
    for query in ("figaro", "theatre", "oeuvre", "francois", "helene"):
        assert normalize_search_key(query) in key
    assert event["programme"][0]["composer"] == "François Test"


def test_detail_cast_dates_are_performance_specific_and_team_is_separate():
    detail = parse_detail_html(
        """
        <div class="wrap-content-hero"><h4>Opera</h4><h2>Giacomo Puccini</h2><h1>Manon Lescaut</h1></div>
        <ul class="lista-artistas">
          <li><span class="lista-artistas-text">Musical conductor</span><span class="lista-artistas-title">Nicola Luisotti</span></li>
        </ul>
        <div class="page-thumb-artist__block"><p><a>
          <span class="position">Manon Lescaut</span><span class="title">Sondra Radvanovsky</span>
          <span class="date">Sep - 23, 26, 29 Oct - 02, 05</span>
        </a></p></div>
        """
    )
    assert detail["programme"] == [{"composer": "Giacomo Puccini", "title": "Manon Lescaut"}]
    assert detail["artistic_team"][0]["artistic_function"] == "Conductor"
    assert detail["cast"][0]["character_role"] == "Manon Lescaut"
    assert detail["cast"][0]["applicable_dates"] == [
        "2026-09-23", "2026-09-26", "2026-09-29", "2026-10-02", "2026-10-05"
    ]


def test_identity_ignores_localized_display_title_but_keeps_occurrence():
    first = {"source": "teatro_real", "source_url": "https://example/show/marriage-figaro", "organization": "Teatro Real", "venue": "Teatro Real", "room": None, "display_title": "The Marriage of Figaro", "date": "2026-11-10", "start_time": "19:30"}
    second = {**first, "display_title": "Las bodas de Fígaro"}
    assert stable_event_identity(first) == stable_event_identity(second)
    assert stable_event_identity(first) != stable_event_identity({**first, "date": "2026-11-11"})


def test_local_official_sources_regression_if_available():
    root = Path(__file__).parent
    calendar = root / "work" / "teatro-real" / "calendar.html"
    pdf = root / "work" / "teatro-real" / "teatro-real-2026-27.pdf"
    if not calendar.exists() or not pdf.exists():
        return
    preview = build_preview(calendar.read_text(encoding="utf-8"), pdf)
    events = preview["events"]
    assert preview["audit"]["event_count"] >= 250
    assert preview["audit"]["duplicate_source_event_ids"] == 0

    manon = next(event for event in events if event["source_url"].endswith("/manon-lescaut") and event["date"] == "2026-09-23")
    assert manon["programme"] == [{"composer": "Giacomo Puccini", "title": "Manon Lescaut"}]
    assert any(row["character_role"] == "Manon Lescaut" for row in manon["cast"])
    assert any(row["artistic_function"] == "Conductor" for row in manon["artistic_team"])
    assert all(row["role_type"] == "character" for row in manon["cast"])
    assert all(not row.get("character_role") for row in manon["artistic_team"])

    preestreno = next(event for event in events if event["display_title"] == "Preestreno Joven 'Manon Lescaut'")
    assert preestreno["date"] == "2026-09-20"
    assert preestreno["start_time"] == "18:00"
    assert preestreno["source_url"].endswith("/preestreno-joven-manon-lescaut")
    assert preestreno["title"] == "Manon Lescaut"
    assert preestreno["programme"] == [{"composer": "Giacomo Puccini", "title": "Manon Lescaut"}]
    assert preestreno["artistic_team"]
    assert preestreno["cast"] == []

    dance = next(event for event in events if event["display_title"] == "Alvin Ailey American Dance Theater")
    assert dance["event_type"] == "dance"
    assert dance["programme"]
    assert dance["artistic_team"]
    assert dance["cast"] == []

    figaro = next(event for event in events if event["display_title"] == "Las bodas de Fígaro" and "#" not in event["source_url"])
    assert figaro["title"] == "Le nozze di Figaro"
    assert any(row["character_role"].startswith("El conde de Almaviva") for row in figaro["cast"])

    parallel = next(event for event in events if event["source_url"].endswith("katia-kabanova#actividadesCulturales"))
    assert parallel["event_type"] == "opera"
    assert parallel["programme"]
    assert parallel["artistic_team"]
    assert parallel["cast"]

    messiah = next(event for event in events if "mesias" in event["source_url"])
    assert messiah["cast"] == []
    assert messiah["artistic_team"]

    bluebeard = next(event for event in events if "castillo-barbazul" in event["source_url"])
    assert len(bluebeard["programme"]) == 3
    assert all("min" not in row["title"].casefold() for row in bluebeard["programme"])
    assert all("interview" not in row["title"].casefold() for row in bluebeard["programme"])

    tannhauser = next(event for event in events if event["source_url"].endswith("/tannhauser"))
    assert tannhauser["programme"] == [{"composer": "Richard Wagner", "title": "Tannhäuser"}]
    assert tannhauser["cast"] and tannhauser["artistic_team"]

    for event in events:
        validate_event(event)
        assert event["source_event_id"]
        assert event["source_url"].startswith("https://www.teatroreal.es/")


if __name__ == "__main__":
    test_calendar_is_performance_level_and_has_stable_identity()
    test_pdf_credit_semantics_keep_cast_and_artistic_team_separate()
    test_search_normalization_preserves_display_values()
    test_local_official_sources_regression_if_available()
    print("Teatro Real adapter: ok")
