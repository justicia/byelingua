import json
import unittest
from pathlib import Path


ARTIFACT = Path("artifacts/auditorio-nacional")


class AuditorioStructureRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parser = json.loads((ARTIFACT / "auditorio-parser-dry-run.json").read_text(encoding="utf-8"))
        classified = json.loads((ARTIFACT / "auditorio-structure-classification.json").read_text(encoding="utf-8"))
        cls.raw = {row["source_url"]: row for row in parser["occurrences"]}
        cls.pages = {row["source_url"]: row for row in classified["pages"]}

    def page(self, title_fragment):
        return next(page for page in self.pages.values() if title_fragment in page["raw_title"])

    def test_raw_blocks_are_preserved_byte_for_byte_as_unicode_data(self):
        for url, page in self.pages.items():
            self.assertEqual(self.raw[url]["raw_content_blocks"], page["raw_content_blocks"])

    def test_ocne_sinfonico_04_programme_is_not_artist_data(self):
        page = self.page("OCNE. Sinfónico 04")
        programme = {"Claude Debussy / José Luis Turina", "La catedral sumergida (núm. 10 del Libro I de Preludios)", "Claude Debussy", "El mar", "Manuel de Falla / Ernesto Halffter", "Atlàntida, cantata escénica (selección)"}
        self.assertTrue(all(line["classification"] not in {"artist_candidate", "role_candidate"} for line in page["classified_lines"] if line["raw_text"] in programme))

    def test_atlantida_programme_sequence_spans_blocks(self):
        page = self.page("Atlántida Chamber Orchestra. Las 4 Estaciones")
        lines = page["classified_lines"]
        values = [line["raw_text"] for line in lines]
        names = ["Johann Sebastian Bach (1685–1750)", "Tomaso Albinoni (1671–1751)", "Antonio Vivaldi (1678–1741)"]
        self.assertEqual([next(line["classification"] for line in lines if line["raw_text"] == name) for name in names], ["composer_candidate"] * 3)
        self.assertEqual(sorted(values.index(name) for name in names), [values.index(name) for name in names])

    def test_orcam_mixed_block_transitions_from_artists_to_programme(self):
        lines = self.page("ORCAM. Sinfónico 1.")["classified_lines"]
        composer_index = next(index for index, line in enumerate(lines) if line["classification"] == "composer_candidate")
        self.assertTrue(any(line["classification"] == "artist_candidate" for line in lines[:composer_index]))
        self.assertTrue(any(line["classification"] == "work_candidate" for line in lines[composer_index + 1:]))

    def test_lifespan_and_inline_forms(self):
        lifespan = self.page("CNDM. Mario Brunello")
        self.assertGreaterEqual(sum(line["classification"] == "composer_candidate" and "(" in line["raw_text"] for line in lifespan["classified_lines"]), 2)
        inline = self.page("Excelentia. Violín Chaikovsky")
        self.assertGreaterEqual(sum("inline_composer_work" in signal for line in inline["classified_lines"] for signal in line["signals"]), 3)

    def test_freeform_film_does_not_emit_works(self):
        page = self.page("Film Symphony Orchestra. Odisea")
        self.assertEqual(page["structure_class"], "FREEFORM_PROGRAMME")
        self.assertFalse(any(line["classification"] == "work_candidate" for line in page["classified_lines"]))

    def test_staged_work_is_cast_and_team(self):
        page = self.page("Excelentia. Ópera: IL Trovatore")
        self.assertTrue(any(line["classification"] == "cast_candidate" for line in page["classified_lines"]))
        self.assertTrue(any(line["classification"] == "artistic_team_candidate" for line in page["classified_lines"]))

    def test_aplazado_is_status_metadata(self):
        page = self.page("CNDM. Barbara Hannigan")
        self.assertEqual([line["classification"] for line in page["classified_lines"][:2]], ["status_notice", "status_notice"])

    def assert_lines(self, title, expected):
        page = self.page(title)
        indexed = {line["raw_text"]: line["classification"] for line in page["classified_lines"]}
        for raw_text, classification in expected.items():
            self.assertEqual(indexed.get(raw_text), classification, f"{title}: {raw_text}")

    def test_required_sequence_regressions(self):
        self.assert_lines("OCNE. Sinfónico 01", {
            "Mikel Urquiza": "composer_candidate", "Deseo tomó delicia*": "work_candidate",
            "Gustav Mahler": "composer_candidate", "Sinfonía núm. 2en Do menor, «Resurrección»": "work_candidate",
        })
        self.assert_lines("OCNE. Sinfónico 02", {
            "Jean Sibelius": "composer_candidate", "Concierto para violín en Re menor, op. 47": "work_candidate",
            "Núria Giménez-Comas": "composer_candidate", "Nostalgia of light, Yearning for…": "work_candidate",
            "Ludwig van Beethoven": "composer_candidate", "Sinfonía núm. 7 en La mayor, op. 92 [36’]": "work_candidate",
        })
        self.assert_lines("OCNE. Sinfónico 03", {
            "William Walton": "composer_candidate", "Serguéi Rajmáninov": "composer_candidate",
            "Concierto para violín": "work_candidate", "Sinfonía núm. 2 en Mi menor, op. 27": "work_candidate",
        })
        self.assert_lines("CNDM. Lea Desandre", {
            "Reynaldo Hahn (1874-1947)": "composer_candidate", "Néère, de Études latines (1900)": "work_candidate",
            "À Chloris (1913)": "work_candidate", "Françoise Hardy (1944-2024)": "composer_candidate",
            "Le temps de l’amour (1966)": "work_candidate", "Gnossienne n.º 1 (1890)": "work_candidate",
        })
        self.assert_lines("CNDM. Barbara Hannigan", {
            "Olivier Messiaen (1908-1992)": "composer_candidate", "Chants de terre et de ciel (1938)": "work_candidate",
        })
        self.assert_lines("Orquesta Sinfónica de Madrid. Alexander Prior", {
            "I": "section_heading", "II": "section_heading", "CURTIS PHILL HSU, PIANO": "artist_candidate",
        })
        self.assert_lines("OCNE. Satélite 01", {
            "Luigi Boccherini": "composer_candidate", "Quinteto de cuerdas en Re Mayor, G. 339": "work_candidate",
            "George Onslow": "composer_candidate", "Darius Milhaud": "composer_candidate",
        })
        self.assert_lines("OCNE. Satélite 02", {
            "Carlos Guastavino": "composer_candidate", "Jeromita Linares": "work_candidate",
            "Alicia Terzian": "composer_candidate", "Canción del atardecer (del opus 5)": "work_candidate",
        })

    def test_heading_ensemble_and_note_regressions(self):
        page = self.page("UAM. Spark")
        indexed = {line["raw_text"]: line for line in page["classified_lines"]}
        for heading in ("OVERTURE", "BAILE Y ENSOÑACIÓN", "LA FLAUTA BOHEMIA", "FASCINACIÓN CARMEN", "LIKE A BOHO", "RAPSODIA ROMANÍ"):
            self.assertNotEqual(indexed[heading]["classification"], "composer_candidate")
        self.assertEqual(indexed["Con motivos de piezas de Hector Berlioz, Giacomo Meyerbeer y Frédéric Chopin"]["classification"], "annotation")
        for ensemble in ("SPARK",):
            self.assertNotEqual(indexed[ensemble]["classification"], "composer_candidate")

    def test_inline_fragments_are_raw(self):
        page = self.page("Excelentia. Violín Chaikovsky")
        line = next(line for line in page["classified_lines"] if line["raw_text"] == "Dvořák · Carnaval, obertura")
        self.assertEqual(line["inline_composer_work"], {"raw_composer_fragment": "Dvořák", "raw_work_fragment": "Carnaval, obertura"})

    def test_composer_candidate_quality_gate(self):
        for page in self.pages.values():
            for line in page["classified_lines"]:
                self.assertNotEqual(line["classification"] == "composer_candidate" and line["raw_text"].strip() in {"I", "II", "III", "IV"}, True)
                self.assertFalse(line["classification"] == "composer_candidate" and any(signal in line["signals"] for signal in ("artist_role_override", "ensemble_override")), line["raw_text"])
        self.assertEqual(next(line["classification"] for line in self.page("CNDM. Lea Desandre")["classified_lines"] if line["raw_text"] == "Reynaldo Hahn (1874-1947)"), "composer_candidate")
        self.assertEqual(next(line["classification"] for line in self.page("CNDM. Lea Desandre")["classified_lines"] if line["raw_text"] == "Gnossienne n.º 1 (1890)"), "work_candidate")

    def test_phase_22_artist_role_ensemble_and_cast_gates(self):
        self.assert_lines("OCNE. Satélite 03. Purcell en la Taberna", {"Marija Pendeva": "artist_candidate"})
        self.assert_lines("OCNE. Satélite 05. Orfeón XIX", {"Enrique Sánchez-Ramos": "artist_candidate"})
        self.assert_lines("Hispania Concertalia. Gustav Mahler Jugendorchester", {"Gustav Mahler Jugendorchester": "artist_candidate"})
        self.assert_lines("Excelentia. La Flauta Mágica de Mozart", {
            "Reina de la Noche – Yewon Han": "cast_candidate",
            "Papageno – Igor Voievodin": "cast_candidate",
            "Sarastro – David Cervera": "cast_candidate",
        })

    def test_phase_22_inline_work_fragments_and_composition_years(self):
        expected = {
            "Piazzolla: Oblivion": ("work_candidate", "Piazzolla", "Oblivion"),
            "Bernstein, Candide. Obertura & Suite": ("work_candidate", "Bernstein", "Candide. Obertura & Suite"),
            "J.Turina.- La Procesión del Rocío": ("work_candidate", "J.Turina", "La Procesión del Rocío"),
            "Respighi.- Pinos de Roma": ("work_candidate", "Respighi", "Pinos de Roma"),
            "Stabat Mater, A. Vivaldi": ("work_candidate", "A. Vivaldi", "Stabat Mater"),
            "Nisi Dominus, A. Vivaldi": ("work_candidate", "A. Vivaldi", "Nisi Dominus"),
            "Piano Sonata. Igor Stravinsky (1882–1971)": ("work_candidate", "Igor Stravinsky (1882–1971)", "Piano Sonata"),
            "Dança Negra. Mozart Camargo Guarnieri (1907 – 1993)": ("work_candidate", "Mozart Camargo Guarnieri (1907 – 1993)", "Dança Negra"),
            "Lili Boulanger Nocturne": ("work_candidate", "Lili Boulanger", "Nocturne"),
        }
        for raw_text, (classification, composer, work) in expected.items():
            line = next(line for page in self.pages.values() for line in page["classified_lines"] if line["raw_text"] == raw_text)
            self.assertEqual(line["classification"], classification, raw_text)
            self.assertEqual(line["inline_composer_work"]["raw_composer_fragment"], composer, raw_text)
            self.assertEqual(line["inline_composer_work"]["raw_work_fragment"], work, raw_text)
        for fragment in ("Voices-Stimmen", "Klavierstück IX", "Opening, de Glassworks", "Invocación y danza", "Liturgia del Sonido"):
            line = next(line for page in self.pages.values() for line in page["classified_lines"] if fragment in line["raw_text"])
            self.assertNotEqual(line["classification"], "composer_candidate", fragment)
        self.assertFalse(any(line["classification"] == "composer_candidate" and line["raw_text"].startswith("Obras de") for page in self.pages.values() for line in page["classified_lines"]))

    def test_phase_23_ocne_09_cross_line_composer_work_contract(self):
        lines = self.page("OCNE. Sinfónico 09")["classified_lines"]
        elgar = next(line for line in lines if line["raw_text"] == "Edward Elgar Variaciones")
        self.assertEqual(elgar["classification"], "work_candidate")
        self.assertEqual(elgar["raw_text"], "Edward Elgar Variaciones")
        self.assertEqual(elgar["inline_composer_work"], {
            "raw_composer_fragment": "Edward Elgar",
            "raw_work_fragment": "Variaciones\nEnigma, op. 36",
        })
        self.assertNotEqual(elgar["inline_composer_work"]["raw_composer_fragment"], elgar["raw_text"])

    def test_phase_23_mixed_traditional_named_attribution_contract(self):
        line = next(
            line for page in self.pages.values() for line in page["classified_lines"]
            if line["raw_text"] == "Tradicional de Venezuela/Alonso Mudarra (ca. 1510-1580)"
        )
        self.assertEqual(line["classification"], "composer_attribution")
        self.assertEqual(line["attribution_type"], "mixed_traditional_named")
        self.assertEqual(line["raw_named_composer_fragments"], ["Alonso Mudarra (ca. 1510-1580)"])
        self.assertEqual(line["raw_non_person_attribution_fragments"], ["Tradicional de Venezuela"])


if __name__ == "__main__":
    unittest.main()
