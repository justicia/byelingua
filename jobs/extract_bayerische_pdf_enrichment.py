#!/usr/bin/env python3
"""Build structured, non-sensitive Bayerische PDF enrichment staging.

This job reads the user-provided official season PDF and the already committed
read-only Bayerische occurrence staging.  It does not fetch the web, call
Supabase, or mutate production.  The output contains structured production
rows and safe credit candidates only; it deliberately excludes the PDF's raw
text and any production rows not needed for the enrichment review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path


PDF_PAGE_MAP = [
    ("siegfried", "SIEGFRIED", "Siegfried", "Richard Wagner", 22),
    ("maria-stuarda", "MARIA STUARDA", "Maria Stuarda", "Gaetano Donizetti", 26),
    ("doctor-atomic", "DOCTOR ATOMIC", "Doctor Atomic", "John Adams", 30),
    ("mazeppa", "MAZEPPA", "Mazeppa", "Pjotr Tschaikowski", 34),
    ("werther", "WERTHER", "Werther", "Jules Massenet", 38),
    ("goetterdaemmerung", "GÖTTERDÄMMERUNG", "Götterdämmerung", "Richard Wagner", 42),
    ("death-in-venice", "DEATH IN VENICE", "Death in Venice", "Benjamin Britten", 46),
    ("liberty", "LIBERTY", "Liberty", "Diana Syrse", 53),
    ("die-kreide-im-mund-des-wolfs", "DIE KREIDE IM MUND DES WOLFS", "Die Kreide im Mund des Wolfs", "Gordon Kampe", 54),
    ("koma-il-combattimento", "KOMA / IL COMBATTIMENTO DI TANCREDI E CLORINDA", "Koma / Il combattimento di Tancredi e Clorinda", "Georg Friedrich Haas / Claudio Monteverdi", 55),
    ("carmen", "CARMEN", "Carmen", "Georges Bizet", 58),
    ("of-one-blood", "OF ONE BLOOD", "Of One Blood", "Brett Dean", 59),
    ("lelisir-damore", "L’ELISIR D’AMORE", "L’elisir d’amore", "Gaetano Donizetti", 60),
    ("lucrezia-borgia", "LUCREZIA BORGIA", "Lucrezia Borgia", "Gaetano Donizetti", 61),
    ("faust", "FAUST", "Faust", "Charles Gounod", 62),
    ("semele", "SEMELE", "Semele", "Georg Friedrich Händel", 63),
    ("katja-kabanova", "KÁŤA KABANOVÁ", "Káťa Kabanová", "Leoš Janáček", 64),
    ("don-giovanni", "DON GIOVANNI", "Don Giovanni", "Wolfgang Amadeus Mozart", 65),
    ("die-entfuehrung-aus-dem-serail", "DIE ENTFÜHRUNG AUS DEM SERAIL", "Die Entführung aus dem Serail", "Wolfgang Amadeus Mozart", 66),
    ("idomeneo", "IDOMENEO", "Idomeneo", "Wolfgang Amadeus Mozart", 67),
    ("die-zauberfloete", "DIE ZAUBERFLÖTE", "Die Zauberflöte", "Wolfgang Amadeus Mozart", 68),
    ("la-boheme", "LA BOHÈME", "La Bohème", "Giacomo Puccini", 69),
    ("madama-butterfly", "MADAMA BUTTERFLY", "Madama Butterfly", "Giacomo Puccini", 70),
    ("manon-lescaut", "MANON LESCAUT", "Manon Lescaut", "Giacomo Puccini", 71),
    ("tosca", "TOSCA", "Tosca", "Giacomo Puccini", 72),
    ("die-nacht-vor-weihnachten", "DIE NACHT VOR WEIHNACHTEN", "Die Nacht vor Weihnachten", "Nikolai Rimski-Korsakow", 73),
    ("il-barbiere-di-siviglia", "IL BARBIERE DI SIVIGLIA", "Il barbiere di Siviglia", "Gioachino Rossini", 74),
    ("la-cenerentola", "LA CENERENTOLA", "La Cenerentola", "Gioachino Rossini", 75),
    ("die-fledermaus", "DIE FLEDERMAUS", "Die Fledermaus", "Johann Strauß", 76),
    ("ariadne-auf-naxos", "ARIADNE AUF NAXOS", "Ariadne auf Naxos", "Richard Strauss", 77),
    ("der-rosenkavalier", "DER ROSENKAVALIER", "Der Rosenkavalier", "Richard Strauss", 78),
    ("pique-dame", "PIQUE DAME", "Pique Dame", "Pjotr Tschaikowski", 79),
    ("un-ballo-in-maschera", "UN BALLO IN MASCHERA", "Un ballo in maschera", "Giuseppe Verdi", 80),
    ("macbeth", "MACBETH", "Macbeth", "Giuseppe Verdi", 81),
    ("rigoletto", "RIGOLETTO", "Rigoletto", "Giuseppe Verdi", 82),
    ("la-traviata", "LA TRAVIATA", "La Traviata", "Giuseppe Verdi", 83),
    ("der-fliegende-hollaender", "DER FLIEGENDE HOLLÄNDER", "Der fliegende Holländer", "Richard Wagner", 84),
    ("parsifal", "PARSIFAL", "Parsifal", "Richard Wagner", 85),
    ("das-rheingold", "DAS RHEINGOLD", "Das Rheingold", "Richard Wagner", 86),
    ("tannhaeuser", "TANNHÄUSER", "Tannhäuser", "Richard Wagner", 87),
    ("die-walkuere", "DIE WALKÜRE", "Die Walküre", "Richard Wagner", 88),
    ("carpathia", "CARPATHIA", "Carpathia – Der Mythos der Untoten", "Milko Lazar", 103),
    ("orpheus-und-eurydike", "ORPHEUS UND EURYDIKE", "Orpheus und Eurydike", "Christoph W. Gluck", 107),
    ("waves-and-circles", "WAVES AND CIRCLES", "Waves and Circles", "William Forsythe / Emma Portner / Maurice Béjart", 120),
    ("common-ground", "COMMON GROUND", "Common Ground", "Alexander Ekman / Johan Inger / Jiří Kylián", 121),
    ("giselle", "GISELLE", "Giselle", "Adolphe Adam", 122),
    ("illusionen-wie-schwanensee", "ILLUSIONEN – WIE SCHWANENSEE", "Illusionen – Wie Schwanensee", "Pjotr Tschaikowski", 123),
    ("die-kameliendame", "DIE KAMELIENDAME", "Die Kameliendame", "John Neumeier", 124),
    ("der-nussknacker", "DER NUSSKNACKER", "Der Nussknacker", "Pjotr Tschaikowski", 125),
    ("cinderella", "CINDERELLA", "Cinderella", "Sergej Prokofjew", 126),
]


STAGE_SLUG_ALIASES = {
    "c-a-r-p-a-t-h-i-a-der-mythos-der-untoten": "carpathia",
    "orpheus-und-eurydikevon-christoph-w-gluck-tanzoper-von-pina-bausch": "orpheus-und-eurydike",
}


def row(artist, role, source_role, character=None, credit_kind=None):
    if credit_kind is None:
        credit_kind = "ensemble" if role in {"orchestra", "choir", "ensemble"} else (
            "cast" if role == "performer" else "artistic_team"
        )
    value = {
        "artist_name": artist,
        "role": role,
        "source_role": source_role,
        "credit_kind": credit_kind,
        "raw_pdf_artist": artist,
        "raw_pdf_role": source_role,
    }
    if character is not None:
        value["character"] = character
        value["raw_character"] = character
    return value


def cast(character, artist):
    return row(artist, "performer", character, character)


def team(artist, role, source_role):
    return row(artist, role, source_role)


MANUAL_TEMPLATES = {
    "carmen": [
        team("Francesco Ivan Ciampa", "conductor", "Musikalische Leitung"),
        team("Lina Wertmüller", "stage_director", "Nach einer Produktion von"),
        team("Enrico Job", "production_designer", "Bühne und Kostüme"),
        team("Franco Marri", "lighting_designer", "Licht"),
        cast("Zuniga", "Roman Chabaranok"), cast("Zuniga", "Paweł Horodyski"),
        cast("Moralès", "Vitor Bispo"), cast("Moralès", "Armand Rabot"),
        cast("Don José", "Benjamin Bernheim"), cast("Don José", "Piotr Beczała"),
        cast("Escamillo", "Andrei Zhilikhovsky"), cast("Escamillo", "Christian Van Horn"),
        cast("Dancaïro", "Zhe Liu"), cast("Remendado", "Zipei Zheng"),
        cast("Frasquita", "Lilit Davtyan"), cast("Frasquita", "Sarah Dufresne"),
        cast("Mercédès", "Ekaterine Buachidze"),
        cast("Carmen", "Maria Barakova"), cast("Carmen", "Aigul Akhmetshina"),
        cast("Micaëla", "Mané Galoyan"), cast("Micaëla", "Nicole Car"),
        row("Bayerisches Staatsorchester", "orchestra", "Bayerisches Staatsorchester"),
        row("Bayerischer Staatsopernchor", "choir", "Bayerischer Staatsopernchor"),
        row("Kinderchor der Bayerischen Staatsoper", "choir", "Kinderchor der Bayerischen Staatsoper"),
    ],
    "of-one-blood": [
        team("Markus Stenz", "conductor", "Musikalische Leitung"),
        team("Claus Guth", "stage_director", "Inszenierung"),
        team("Etienne Pluss", "set_designer", "Bühne"),
        team("Ursula Kudrna", "costume_designer", "Kostüme"),
        team("Michael Bauer", "lighting_designer", "Licht"),
        team("Sommer Ulrickson", "choreographer", "Choreographie"),
        team("Yvonne Gebauer", "dramaturg", "Dramaturgie"),
        cast("Elizabeth I, Queen of England", "Johanni van Oostrum"),
        cast("Mary, Queen of Scots", "Vera-Lotte Boecker"),
        cast("Female Consort I", "Seonwoo Lee"), cast("Female Consort II", "Elene Gvritishvili"),
        cast("Female Consort III", "Lotte Betts-Dean"), cast("Female Consort IV", "Meg Brilleslyper"),
        cast("Female Consort V / Jane Kennedy", "Freya Apffelstaedt"),
        cast("Male Consort I / Lord Darnley", "Liam Bonthrone"), cast("Male Consort II", "Joel Williams"),
        cast("Male Consort III / Rizzio", "Andrew Hamilton"), cast("Male Consort IV", "Armand Rabot"),
        cast("Male Consort V / Executioner", "Paweł Horodyski"),
        cast("Solo-Cembalo", "Mahan Esfahani"),
        row("Bayerisches Staatsorchester", "orchestra", "Bayerisches Staatsorchester"),
        row("Bayerischer Staatsopernchor", "choir", "Bayerischer Staatsopernchor"),
    ],
    "pique-dame": [
        team("Dima Slobodeniouk", "conductor", "Musikalische Leitung"),
        team("Benedict Andrews", "stage_director", "Inszenierung"),
        team("Rufus Didwiszus", "set_designer", "Bühne"),
        team("Victoria Behr", "costume_designer", "Kostüme"),
        team("Jon Clark", "lighting_designer", "Licht"),
        team("Klevis Elmazaj", "choreographer", "Choreographie"),
        cast("Hermann", "Ivan Gyngazov"), cast("Tomski", "Vladislav Sulimsky"),
        cast("Fürst Jelezki", "Andrei Zhilikhovsky"), cast("Tschekalinski", "Alexander Fedorov"),
        cast("Surin", "Roman Chabaranok"), cast("Tschaplizki", "Tansel Akzeybek"),
        cast("Narumow", "Paweł Horodyski"), cast("Festordner", "Shawn Roth"),
        cast("Die Gräfin", "Elena Zaremba"), cast("Lisa", "Asmik Grigorian"),
        cast("Polina", "Victoria Karkacheva"), cast("Die Gouvernante", "Freya Apffelstaedt"),
        cast("Mascha", "Martina Myskohlid"),
        row("Bayerisches Staatsorchester", "orchestra", "Bayerisches Staatsorchester"),
        row("Bayerischer Staatsopernchor", "choir", "Bayerischer Staatsopernchor"),
        row("Kinderchor der Bayerischen Staatsoper", "choir", "Kinderchor der Bayerischen Staatsoper"),
    ],
    "macbeth": [
        team("Marco Armiliato", "conductor", "Musikalische Leitung"),
        team("Martin Kušej", "stage_director", "Regie"),
        team("Martin Zehetgruber", "set_designer", "Bühne"),
        team("Werner Fritz", "costume_designer", "Kostüme"),
        team("Reinhard Traub", "lighting_designer", "Licht"),
        cast("Macbeth", "Igor Golovatenko"), cast("Banco", "Christian Van Horn"),
        cast("Lady Macbeth", "Anastasia Bartoli"), cast("Dame der Lady Macbeth", "Mirjam Mesak"),
        cast("Macduff", "Granit Musliu"), cast("Malcolm", "Michael Butler"),
        cast("Arzt", "Martin Snell"), cast("Diener / Mörder", "Christian Rieger"),
        cast("Erste Erscheinung", "Hector Bloggs"), cast("Zweite Erscheinung", "Tata Razmadze"),
        cast("Dritte Erscheinung", "Solist des Tölzer Knabenchors"),
        row("Bayerisches Staatsorchester", "orchestra", "Bayerisches Staatsorchester"),
        row("Bayerischer Staatsopernchor", "choir", "Bayerischer Staatsopernchor"),
    ],
    "tosca": [
        team("Francesco Ivan Ciampa", "conductor", "Musikalische Leitung"),
        team("Kornél Mundruczó", "stage_director", "Inszenierung"),
        team("Monika Pormale", "production_designer", "Bühne und Kostüme"),
        team("Felice Ross", "lighting_designer", "Licht"),
        team("Rūdolfs Baltiņš", "video_designer", "Video"),
        team("Kata Wéber", "dramaturg", "Dramaturgie"),
        cast("Floria Tosca", "Eleonora Buratto"), cast("Mario Cavaradossi", "Joshua Guerrero"),
        cast("Baron Scarpia", "Gerald Finley"), cast("Cesare Angelotti", "Roman Chabaranok"),
        cast("Der Mesner", "Martin Snell"), cast("Spoletta", "Tansel Akzeybek"),
        cast("Sciarrone", "Christian Rieger"), cast("Gefängniswärter", "Daniel Vening"),
        cast("Stimme eines Hirten", "Solist des Tölzer Knabenchors"),
        row("Bayerisches Staatsorchester", "orchestra", "Bayerisches Staatsorchester"),
        row("Bayerischer Staatsopernchor", "choir", "Bayerischer Staatsopernchor"),
        row("Kinderchor der Bayerischen Staatsoper", "choir", "Kinderchor der Bayerischen Staatsoper"),
    ],
    "cinderella": [
        team("Christopher Wheeldon", "choreographer", "Choreographie"),
        team("Julian Crouch", "production_designer", "Bühne und Kostüme"),
        team("Natasha Katz", "lighting_designer", "Licht"),
        team("Daniel Brodie", "video_designer", "Projektionen"),
        team("Craig Lucas", "librettist", "Libretto"),
        team("Jason Fowler", "rehearsal_director", "Einstudierung"),
        team("Jonathan Howells", "rehearsal_director", "Einstudierung"),
        team("Charles Andersen", "rehearsal_director", "Einstudierung"),
        team("Gavin Sutherland", "conductor", "Musikalische Leitung"),
        row("Bayerisches Staatsballett", "ensemble", "Bayerisches Staatsballett"),
        row("Bayerisches Staatsorchester", "orchestra", "Bayerisches Staatsorchester"),
    ],
}


MANUAL_ADDITIONS = {
    "siegfried": [
        cast("Waldvogel", "Solist des Tölzer Knabenchors"),
    ],
    "maria-stuarda": [
        team("Giulia Bruschi", "set_designer", "Bühne"),
        team("Riccardo Mainetti", "set_designer", "Bühne"),
    ],
    "die-zauberfloete": [
        cast("Drei Knaben", "Solisten des Tölzer Knabenchors"),
    ],
    "der-fliegende-hollaender": [
        row("Bayerischer Staatsopernchor", "choir", "Bayerischer Staatsopernchor"),
        row("Extrachor der Bayerischen Staatsoper", "choir", "Extrachor der Bayerischen Staatsoper"),
    ],
    "parsifal": [
        row("Bayerischer Staatsopernchor", "choir", "Bayerischer Staatsopernchor"),
        row("Extrachor der Bayerischen Staatsoper", "choir", "Extrachor der Bayerischen Staatsoper"),
    ],
    "tannhaeuser": [
        cast("Vier Edelknaben", "Solisten des Tölzer Knabenchors"),
    ],
    "die-kameliendame": [
        team("Dmitry Mayboroda", "pianist", "Klavier"),
        row("Bayerisches Staatsballett", "ensemble", "Bayerisches Staatsballett"),
        row("Bayerisches Junior Ballett München", "ensemble", "Bayerisches Junior Ballett München"),
    ]
}


# The PDF marks multiple singers for the same role with cast variants (1/2),
# while the committed occurrence staging may intentionally have no cast for a
# date. Until the variant marker is tied to an individual occurrence, those
# cast rows remain review-only; unambiguous production team rows can still be
# safely propagated.
AMBIGUOUS_CAST_PRODUCTIONS = {
    "carmen",
    "maria-stuarda",
    "werther",
    "katja-kabanova",
    "la-cenerentola",
    "rigoletto",
    "parsifal",
}


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def dedupe(rows):
    output = OrderedDict()
    for item in rows:
        key = (norm(item.get("artist_name")), norm(item.get("role")), norm(item.get("character")))
        output.setdefault(key, item)
    return list(output.values())


def page_texts(path: Path):
    text = path.read_text(encoding="utf-8").replace(r"\n", "\n")
    pages = {int(number): body.strip() for number, body in re.findall(r"=== PAGE (\d+) ===\n(.*?)(?=\n=== PAGE |\Z)", text, re.S)}
    return pages


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def event_template(events, spec_key):
    if spec_key in MANUAL_TEMPLATES:
        return dedupe(MANUAL_TEMPLATES[spec_key])
    selected = max(events, key=lambda event: len(event.get("credits") or []), default={})
    rows = dedupe(selected.get("credits") or [])
    rows.extend(MANUAL_ADDITIONS.get(spec_key, []))
    return dedupe(rows)


DETAIL_PAGE_OVERRIDES = {
    22: 23, 26: 27, 30: 31, 34: 35, 38: 39, 42: 43, 46: 47,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--pdf-pages", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    events = source["events"]
    pages = page_texts(args.pdf_pages)
    by_slug = {}
    for event in events:
        canonical = STAGE_SLUG_ALIASES.get(event.get("slug"), event.get("slug"))
        by_slug.setdefault(canonical, []).append(event)

    production_blocks = []
    all_rows = []
    candidates = []
    unmatched = []
    for key, heading, work_title, composer, page_number in PDF_PAGE_MAP:
        matched_events = by_slug.get(key, [])
        if not matched_events:
            unmatched.append(key)
        evidence_page = DETAIL_PAGE_OVERRIDES.get(page_number, page_number)
        template = event_template(matched_events, key)
        if key not in MANUAL_TEMPLATES:
            evidence_text = norm(pages.get(evidence_page, ""))
            template = [item for item in template if norm(item.get("artist_name")) in evidence_text]
        template = dedupe(template + MANUAL_ADDITIONS.get(key, []))
        rows = []
        for item in template:
            enriched = {
                **item,
                "production_key": key,
                "production_title": heading,
                "work_title": work_title,
                "composer": composer,
                "source_document": args.pdf.name,
                "source_page_number": evidence_page,
                "source_page_contains_artist": norm(item.get("artist_name")) in norm(pages.get(evidence_page, "")),
            }
            rows.append(enriched)
            all_rows.append(enriched)
        event_keys = [f"{event.get('source', 'munich_bayerische_staatsoper')}:{event.get('source_event_id')}" for event in matched_events]
        empty_events = [event for event in matched_events if not (event.get("credits") or [])]
        for event in empty_events:
            for item in rows:
                if item.get("credit_kind") == "cast" and key in AMBIGUOUS_CAST_PRODUCTIONS:
                    continue
                if norm(item.get("artist_name")) in {"n. n.", "n.n.", ""}:
                    continue
                candidates.append({
                    "event_key": f"{event.get('source', 'munich_bayerische_staatsoper')}:{event.get('source_event_id')}",
                    "source_event_id": event.get("source_event_id"),
                    "production_key": key,
                    "production_title": heading,
                    "work_title": work_title,
                    "composer": composer,
                    "artist_name": item["artist_name"],
                    "role": item["role"],
                    "character": item.get("character"),
                    "raw_character": item.get("raw_character"),
                    "source_role": item["source_role"],
                    "credit_kind": item["credit_kind"],
                    "source_document": args.pdf.name,
                    "source_page_number": page_number,
                    "candidate_reason": "matched PDF production template to event with no existing credits",
                })
        production_blocks.append({
            "production_key": key,
            "production_title": heading,
            "work_title": work_title,
            "composer": composer,
            "source_page_number": page_number,
            "source_page_has_text": bool(pages.get(page_number)),
            "matched_event_count": len(matched_events),
            "matched_event_keys": event_keys,
            "events_without_credits": len(empty_events),
            "structured_rows": rows,
            "classification": "ALREADY_PRESENT" if matched_events and not empty_events else (
                "SAFE_INSERT_CREDIT_TEMPLATE" if matched_events else "REVIEW_UNMATCHED_PRODUCTION"
            ),
        })

    artists = sorted({item["artist_name"] for item in all_rows if item.get("artist_name")})
    cast_rows = [item for item in all_rows if item.get("credit_kind") == "cast"]
    team_rows = [item for item in all_rows if item.get("credit_kind") in {"artistic_team", "ensemble"}]
    review_cast_rows = [
        item for item in all_rows
        if item.get("credit_kind") == "cast" and item.get("production_key") in AMBIGUOUS_CAST_PRODUCTIONS
    ]
    matched = [block for block in production_blocks if block["matched_event_count"]]
    covered = sum(block["matched_event_count"] for block in matched)
    summary = {
        "schema_version": "bayerische-staatsoper-official-pdf-enrichment-staging-v1",
        "source_document": args.pdf.name,
        "source_pdf_sha256": sha256(args.pdf),
        "pages_read": max(pages) if pages else 0,
        "text_pages": sum(bool(value) for value in pages.values()),
        "productions_found": len(PDF_PAGE_MAP),
        "productions_matched": len(matched),
        "productions_unmatched": len(unmatched),
        "unmatched_production_keys": unmatched,
        "events_covered": covered,
        "cast_rows_extracted": len(cast_rows),
        "team_rows_extracted": len(team_rows),
        "programme_rows_extracted": len(PDF_PAGE_MAP),
        "safe_credit_candidate_rows": len(candidates),
        "safe_candidate_events": len({item["event_key"] for item in candidates}),
        "review_cast_rows_variant_unresolved": len(review_cast_rows),
        "artist_names_in_extraction": len(artists),
        "production_writes": 0,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "bayerische_pdf_extraction_staging.json").write_text(
        json.dumps({"summary": summary, "productions": production_blocks, "rows": all_rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output / "bayerische_pdf_credit_candidates.json").write_text(
        json.dumps({"summary": summary, "candidates": candidates}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
