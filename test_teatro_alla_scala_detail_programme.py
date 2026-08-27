from __future__ import annotations

import unittest

from season_ingestion.adapters.detail_linked_listing import DetailLinkedListingAdapter


SETTINGS = {
    "source_id": "teatro_alla_scala",
    "organization": "Teatro alla Scala",
    "venue": "Teatro alla Scala",
    "city": "Milan",
    "country": "Italy",
    "timezone": "Europe/Rome",
    "detail_profile": "teatro_alla_scala",
    "detail_type_selector": ".cnt__leaf",
    "detail_composer_selector": ".cnt__subtitle",
    "programme_section_selector": "section#programme",
    "programme_row_selector": "table tbody tr",
    "season_start_month": 8,
    "season_end_month": 7,
    "season_bounds": {"2026-27": {"season_start": "2026-08-01", "season_end": "2027-08-31"}},
    "performance_container_selector": "time[datetime]",
    "performance_date_selector": ":scope",
}


def parse(detail: str, url: str = "https://www.teatroallascala.org/en/season/2026-2027/opera/test.html"):
    adapter = DetailLinkedListingAdapter(
        {**SETTINGS, "listing_source": "https://www.teatroallascala.org/en/calendar.html"},
        fetch={url: detail}.__getitem__,
    )
    return adapter._events_from_detail(detail, url, "Fallback", "2026-27")


class TeatroAllaScalaDetailProgrammeTests(unittest.TestCase):
    def test_single_work_opera_extracts_header_composer_and_work(self):
        html = """<div class='cnt__leaf'>Opera</div><h1 class='cnt__title'>Otello</h1>
        <div class='cnt__subtitle'>Giuseppe Verdi</div>
        <time datetime='2026-12-07T18:00:00+01:00'>Mon 7 December 2026</time>"""
        event = parse(html)[0]
        self.assertEqual(event.event_type, "opera")
        self.assertEqual(event.programme[0]["source_title"], "Otello")
        self.assertEqual(event.programme[0]["composer"], "Giuseppe Verdi")

    def test_multi_work_concert_preserves_rows_and_order(self):
        html = """<div class='cnt__leaf'>Symphony Concerts</div><h1 class='cnt__title'>Alexander Soddy / Beethoven, Shostakovich</h1>
        <section id='programme'><table><tbody>
        <tr><td class='dt'>Ludwig van Beethoven</td><td><p><em>Concerto </em>in D major, Op. 61<br>for violin and orchestra</p></td></tr>
        <tr><td class='dt'>Dmitri Shostakovich</td><td><p><em>Symphony </em>No. 5 in D minor, Op. 47</p></td></tr>
        </tbody></table></section><time datetime='2027-01-11T20:00:00+01:00'>Mon</time>"""
        event = parse(html, "https://www.teatroallascala.org/en/season/2026-2027/concerts/test.html")[0]
        self.assertEqual(event.event_type, "concert")
        self.assertEqual([x["source_programme_index"] for x in event.programme], [1, 2])
        self.assertEqual([x["source_title"] for x in event.programme], ["Concerto in D major, Op. 61", "Symphony No. 5 in D minor, Op. 47"])
        self.assertEqual([x["composer"] for x in event.programme], ["Ludwig van Beethoven", "Dmitri Shostakovich"])

    def test_ballet_mixed_programme_does_not_collapse_to_event_title(self):
        html = """<div class='cnt__leaf'>Ballet</div><h1 class='cnt__title'>Dawson / Morau Double Bill</h1>
        <section id='programme'><table><tbody>
        <tr><td><strong>The Four Seasons</strong></td><td><p><strong>David Dawson</strong>, choreography<br><strong>Max Richter</strong>, music</p></td></tr>
        <tr><td><strong>Étude</strong></td><td><p><strong>Marcos Morau</strong>, choreography<br><strong>Gustave Rudman</strong>, music</p></td></tr>
        </tbody></table></section><time datetime='2027-06-03T20:00:00+01:00'>Thu</time>"""
        event = parse(html, "https://www.teatroallascala.org/en/season/2026-2027/ballet/test.html")[0]
        self.assertEqual(event.event_type, "ballet")
        self.assertEqual([x["source_title"] for x in event.programme], ["The Four Seasons", "Étude"])
        self.assertEqual([x["composer"] for x in event.programme], ["Max Richter", "Gustave Rudman"])

    def test_detail_dates_do_not_multiply_occurrences(self):
        html = """<div class='cnt__leaf'>Opera</div><h1 class='cnt__title'>Otello</h1><div class='cnt__subtitle'>Giuseppe Verdi</div>
        <time datetime='2026-12-07T18:00:00+01:00'>one</time><time datetime='2026-12-10T20:00:00+01:00'>two</time>"""
        events = parse(html)
        self.assertEqual([(x.date, x.start_time) for x in events], [("2026-12-07", "18:00"), ("2026-12-10", "20:00")])

    def test_localized_work_title_remains_source_title_for_shared_resolver(self):
        html = """<div class='cnt__leaf'>Opera</div><h1 class='cnt__title'>The Magic Flute</h1><div class='cnt__subtitle'>Wolfgang Amadeus Mozart</div>
        <time datetime='2027-02-01T20:00:00+01:00'>one</time>"""
        event = parse(html)[0]
        self.assertEqual(event.programme[0]["source_title"], "The Magic Flute")
        self.assertNotIn("canonical_work_title", event.programme[0])


if __name__ == "__main__":
    unittest.main()
