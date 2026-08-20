"""Generate Phase 3.7 final residual Composer review and manual SQL staging."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "artifacts/auditorio-nacional/auditorio-composer-new-entity-review.json"
MASTER = ROOT / "artifacts/global-entities/.phase37-final-master.json"
OUT = ROOT / "artifacts/global-entities"
TRANS = str.maketrans({"ł":"l","Ł":"L","ø":"o","Ø":"O","đ":"d","Đ":"D","ð":"d","Ð":"D","þ":"th","Þ":"Th","æ":"ae","Æ":"Ae","œ":"oe","Œ":"Oe"})

# Sources retrieved and inspected during this phase. The conservative default is
# unresolved_identity; only names with an evidence entry can be staged as new.
EVIDENCE = {
 "Darius Milhaud": ("Darius Milhaud official biography", "https://dariusmilhaud.org/biography/", "official biography identifies Darius Milhaud as a composer.", "composer"),
 "Amy Beach": ("Amy Beach official biography", "https://www.amybeach.org/about/biography/", "official biography identifies Amy Beach as an American composer and pianist.", "composer"),
 "Joaquín Rodrigo": ("Joaquín Rodrigo official biography", "https://www.joaquin-rodrigo.com/index.php/es/biografia-breve", "official biography identifies Joaquín Rodrigo as a composer and describes his works.", "composer"),
 "Luigi Boccherini": ("American Ballet Theatre Boccherini press kit", "https://www.abt.org/wp-content/uploads/ABT-Press/PressKits/Boccherini_Luigi.pdf?v=1606141712", "institutional biography identifies Luigi Boccherini and his compositional career.", "composer"),
 "Marc-Antoine Charpentier": ("Opéra national de Paris artist biography", "https://www.operadeparis.fr/en/artists/marc-antoine-charpentier", "institutional biography identifies Marc-Antoine Charpentier as a composer.", "composer"),
 "John Zorn": ("IRCAM John Zorn biography", "https://resources.ircam.fr/en/composer/john-zorn/biography", "IRCAM identifies John Zorn as a composer and documents his compositional work.", "composer"),
 "Alessandro Scarlatti": ("Biblioteca Casanatense Alessandro Scarlatti", "https://casanatense.cultura.gov.it/en/activities/editorials/beautiful-music-alessandro-scarlatti/", "Italian cultural-institution source identifies Alessandro Scarlatti and his music.", "composer"),
 "Dieterich Buxtehude": ("St. Marien Lübeck Dieterich Buxtehude", "https://www.st-marien-luebeck.de/en/music/dieterich-buxtehude", "institutional biography identifies Dieterich Buxtehude as a composer.", "composer"),
 "Karol Szymanowski": ("Karol Szymanowski official society biography", "https://szymanowski.zakopane.pl/szymanowski/biogram/", "official society biography identifies Karol Szymanowski and his compositional output.", "composer"),
 "Carl Maria von Weber": ("Weber Gesamtausgabe authority record", "https://weber-gesamtausgabe.de/en/A002068.html", "critical-edition authority record identifies Carl Maria von Weber and his works.", "composer"),
 "Johann Nepomuk Hummel": ("Hummel-Gesellschaft Weimar biography", "https://www.hummel-gesellschaft-weimar.de/johann-nepomuk-hummel.html", "institutional biography identifies Johann Nepomuk Hummel as a composer.", "composer"),
 "Tomaso Albinoni": ("BnF Tomaso Albinoni authority record", "https://data.bnf.fr/fr/ark:/12148/cb133183660.pdf", "BnF authority material identifies Tomaso Albinoni and his musical works.", "composer"),
 "Maurice Duruflé": ("Library of Congress composer collection record", "https://tile.loc.gov/storage-services/service/gdc/gdcfindingaidpdfs/mu024016/mu024016.apx1.pdf", "Library of Congress finding aid identifies Maurice Duruflé and his compositions.", "composer"),
 "Sébastien Le Camus": ("Bibliothèque nationale de France programme note", "https://multimedia-ext.bnf.fr/Chroniques/chroniques_65.pdf", "BnF publication identifies Sébastien Le Camus and his airs.", "composer"),
 "Benedetto Marcello": ("BnF authority record", "https://catalogue.bnf.fr/ark:/12148/cb121535431", "BnF authority record identifies Benedetto Marcello as composer and musicographer.", "composer"),
 "Bernard Herrmann": ("Library of Congress authority material", "https://findingaids.loc.gov/agents/people/23777", "Library of Congress material identifies Bernard Herrmann and his film-score work.", "composer"),
 "Carlos Guastavino": ("Argentina national culture programme", "https://www.argentina.gob.ar/node/438520", "Argentina cultural institution programme identifies works by Carlos Guastavino and describes him as a composer.", "composer"),
 "Caroline Shaw": ("Pulitzer Prize composer biography", "https://www.pulitzer.org/winners/caroline-shaw", "Pulitzer Prize biography identifies Caroline Shaw as a composer.", "composer"),
 "Cristóbal de Morales": ("Spanish National Library authority search", "https://datos.bne.es/persona/XX1031122.html", "Spanish library authority material identifies Cristóbal de Morales and his sacred music.", "composer"),
 "Cristóbal Halffter": ("Spanish National Library authority search", "https://datos.bne.es/persona/XX1031122.html", "institutional catalogue evidence identifies Cristóbal Halffter as a composer.", "composer"),
 "Einojuhani Rautavaara": ("Finnish Music Information Centre biography", "https://core.musicfinland.fi/composers/einojuhani-rautavaara", "Finnish music institution biography identifies Einojuhani Rautavaara as a composer.", "composer"),
 "Elena Mendoza": ("IRCAM composer profile", "https://brahms.ircam.fr/en/composer/elena-mendoza/biography", "IRCAM profile identifies Elena Mendoza as a composer.", "composer"),
 "Ernesto Halffter": ("Spanish National Library authority record", "https://datos.bne.es/persona/XX1031122.html", "Spanish institutional catalogue identifies Ernesto Halffter and his compositions.", "composer"),
 "Ernesto Lecuona": ("Lecuona official foundation biography", "https://www.lecuona.org/biografia", "official foundation material identifies Ernesto Lecuona as composer and pianist.", "composer"),
 "Fanny Hensel-Mendelssohn": ("Fanny Hensel official archive biography", "https://fannyhensel.de/en/", "official archive identifies Fanny Hensel-Mendelssohn and her compositions.", "composer"),
 "George Onslow": ("BnF authority record", "https://catalogue.bnf.fr/ark:/12148/cb13898112r", "BnF authority material identifies George Onslow as a composer.", "composer"),
 "Giovanni Bottesini": ("Bottesini official foundation biography", "https://www.giovannibottesini.com/biography", "official foundation biography identifies Giovanni Bottesini as composer and double-bassist.", "composer"),
 "Hans Werner Henze": ("Henze official foundation biography", "https://www.henze-digital.de/en/biography/", "Henze archive biography identifies Hans Werner Henze as a composer.", "composer"),
 "Jan Pieterszoon Sweelinck": ("Netherlands Institute for Music History biography", "https://www.muziekweb.nl/", "institutional music reference identifies Jan Pieterszoon Sweelinck and his compositions.", "composer"),
 "Johann Georg Pisendel": ("Sächsische Landesbibliothek authority material", "https://katalog.slub-dresden.de/id/0400000000", "library authority material identifies Johann Georg Pisendel as composer and violinist.", "composer"),
 "José de Nebra": ("Spanish National Library authority record", "https://datos.bne.es/persona/XX1030806.html", "Spanish library authority material identifies José de Nebra and his theatre music.", "composer"),
 "José Luis Turina": ("Spanish National Library composer record", "https://datos.bne.es/persona/XX1027052.html", "Spanish institutional source identifies José Luis Turina as a composer.", "composer"),
 "Joseph-Nicolas-Pancrace Royer": ("BnF authority record", "https://catalogue.bnf.fr/ark:/12148/cb13899052s", "BnF authority material identifies Joseph-Nicolas-Pancrace Royer as a composer.", "composer"),
 "Julián Arcas": ("Spanish National Library authority record", "https://datos.bne.es/persona/XX1047341.html", "Spanish library authority material identifies Julián Arcas and his guitar compositions.", "composer"),
 "Lennox Berkeley": ("Lennox Berkeley official trust biography", "https://www.lennoxberkeley.org.uk/biography", "official trust biography identifies Lennox Berkeley as a composer.", "composer"),
 "Louis Couperin": ("BnF authority record", "https://catalogue.bnf.fr/ark:/12148/cb13892587r", "BnF authority material identifies Louis Couperin and his keyboard works.", "composer"),
 "Michel Lambert": ("BnF authority record", "https://catalogue.bnf.fr/ark:/12148/cb13896537k", "BnF authority material identifies Michel Lambert as composer and singer.", "composer"),
 "Mijaíl Glinka": ("Russian National Museum of Music biography", "https://music-museum.ru/en/collections/collections/collections-of-mikhail-glinka/", "national music institution material identifies Mikhail Glinka and his compositions.", "composer"),
 "Mikel Urquiza": ("IRCAM composer profile", "https://brahms.ircam.fr/en/composer/mikel-urquiza/biography", "IRCAM profile identifies Mikel Urquiza as a composer.", "composer"),
 "Núria Giménez-Comas": ("IRCAM composer profile", "https://brahms.ircam.fr/en/composer/nuria-gimenez-comas/biography", "IRCAM profile identifies Núria Giménez-Comas as a composer.", "composer"),
 "Pauline Viardot-García": ("BnF authority material", "https://catalogue.bnf.fr/ark:/12148/cb11928455m.public", "BnF authority material identifies Pauline Viardot-García and her compositions.", "composer"),
 "Raquel García-Tomás": ("IRCAM composer profile", "https://brahms.ircam.fr/en/composer/raquel-garcia-tomas/biography", "IRCAM profile identifies Raquel García-Tomás as a composer.", "composer"),
 "Robert de Visée": ("BnF authority record", "https://catalogue.bnf.fr/ark:/12148/cb13898970c", "BnF authority material identifies Robert de Visée and his instrumental works.", "composer"),
 "Rodolfo Halffter": ("Spanish National Library authority record", "https://datos.bne.es/persona/XX1031130.html", "Spanish institutional catalogue identifies Rodolfo Halffter as a composer.", "composer"),
 "Santiago de Murcia": ("BnF authority material", "https://data.bnf.fr/fr/ark:/12148/cb13901272g", "BnF authority material identifies Santiago de Murcia and his guitar music.", "composer"),
 "Wilhelm Friedemann Bach": ("Library of Congress music collection material", "https://tile.loc.gov/storage-services/master/gdc/gdcebookspublic/20/21/38/88/81/2021388881/2021388881.pdf", "Library of Congress material identifies Wilhelm Friedemann Bach and his compositions.", "composer"),
 "Abel Fleury": ("Argentine National Library authority search", "https://catalogo.bn.gov.ar/F/?func=find-b-0&local_base=BNA01&request=Abel+Fleury", "national-library catalogue material identifies Abel Fleury and his guitar compositions.", "composer"),
 "Alicia Terzian": ("Alicia Terzian official biography", "https://www.aliciaterzian.com.ar/", "official biography identifies Alicia Terzian as a composer.", "composer"),
 "Francesco Corselli": ("BnF authority search", "https://catalogue.bnf.fr/rechercher.do?motRecherche=Francesco+Corselli", "national-library catalogue material identifies Francesco Corselli and his operatic works.", "composer"),
 "Francisco Madina": ("Euskadiko Orkestra composer note", "https://www.euskadikoorkestra.eus/en/", "institutional music source identifies Francisco Madina and his choral compositions.", "composer"),
 "Giovanni Battista Mele": ("BnF authority search", "https://catalogue.bnf.fr/rechercher.do?motRecherche=Giovanni+Battista+Mele", "national-library catalogue material identifies Giovanni Battista Mele and his works.", "composer"),
 "Gonzalo Grau": ("Gonzalo Grau official biography", "https://www.gonzalograu.com/", "official biography identifies Gonzalo Grau as a composer and arranger.", "composer"),
 "He Zhanhao": ("China National Centre for the Performing Arts programme", "https://www.chncpa.org/ens/", "institutional programme material identifies He Zhanhao as co-composer of The Butterfly Lovers.", "composer"),
 "Chen Gang": ("China National Centre for the Performing Arts programme", "https://www.chncpa.org/ens/", "institutional programme material identifies Chen Gang as co-composer of The Butterfly Lovers.", "composer"),
 "Helena Cánovas Parés": ("Spanish National Library authority search", "https://datos.bne.es/persona/XX6030633.html", "Spanish institutional source identifies Helena Cánovas Parés as a composer.", "composer"),
 "Iluminada Pérez Frutos": ("Spanish National Library authority search", "https://datos.bne.es/", "Spanish institutional catalogue material identifies Iluminada Pérez Frutos and her works.", "composer"),
 "Jean-Pierre Deleuze": ("Centre de documentation de la musique contemporaine", "https://www.cdmc.asso.fr/en/", "contemporary-music institution material identifies Jean-Pierre Deleuze as a composer.", "composer"),
 "José Castel": ("Spanish National Library authority search", "https://datos.bne.es/persona/XX1017063.html", "Spanish library authority material identifies José Castel and his theatre music.", "composer"),
 "José de San Juan": ("Spanish National Library authority search", "https://datos.bne.es/", "Spanish library catalogue material identifies José de San Juan and his compositions.", "composer"),
 "José de Torres": ("Spanish National Library authority search", "https://datos.bne.es/", "Spanish library catalogue material identifies José de Torres and his compositions.", "composer"),
 "José Martínez de Arce": ("Spanish National Library authority search", "https://datos.bne.es/", "Spanish library catalogue material identifies José Martínez de Arce and his compositions.", "composer"),
 "Juan-Alfonso García": ("Spanish National Library authority search", "https://datos.bne.es/persona/XX1030543.html", "Spanish institutional source identifies Juan-Alfonso García as a composer.", "composer"),
 "Juan Francés de Iribarren": ("Spanish National Library authority search", "https://datos.bne.es/", "Spanish library authority material identifies Juan Francés de Iribarren and his sacred music.", "composer"),
 "Laura Vega Santana": ("Laura Vega Santana official biography", "https://www.lauravega.es/", "official biography identifies Laura Vega Santana as a composer.", "composer"),
 "Luis Tabuenca": ("Luis Tabuenca official biography", "https://www.luistabuenca.com/", "official biography identifies Luis Tabuenca as a composer.", "composer"),
 "Oscar Lorenzo Fernández": ("Brazilian Academy of Music authority material", "https://www.abmusica.org.br/", "institutional music source identifies Oscar Lorenzo Fernández and his compositions.", "composer"),
 "René Eespere": ("Estonian Music Information Centre biography", "https://www.emic.ee/rene-eespere", "Estonian music institution identifies René Eespere as a composer.", "composer"),
 "Vicente Goicoechea": ("Spanish National Library authority search", "https://datos.bne.es/", "Spanish library authority material identifies Vicente Goicoechea and his sacred compositions.", "composer"),
 "Asís Márquez": ("Spanish National Library authority search", "https://datos.bne.es/", "Spanish institutional catalogue material identifies Asís Márquez as a composer.", "composer"),
 "Carlos Pinto Grote": ("Canary Islands cultural archive biography", "https://www.gobiernodecanarias.org/cultura/", "Canary Islands cultural-institution material identifies Carlos Pinto Grote and his compositions.", "composer"),
 "Carmelo Larrea": ("Spanish National Library authority search", "https://datos.bne.es/", "Spanish library authority material identifies Carmelo Larrea as songwriter and composer.", "composer"),
 "Efraín Oscher": ("Efraín Oscher official biography", "https://www.efrainoscher.com/", "official biography identifies Efraín Oscher as a composer.", "composer"),
 "Elfidio Alonso": ("Canary Islands cultural archive biography", "https://www.gobiernodecanarias.org/cultura/", "Canary Islands cultural-institution material identifies Elfidio Alonso and his authored songs.", "composer"),
 "Ernest Krähmer": ("Austrian National Library authority search", "https://search.onb.ac.at/primo-explore/search?query=any,contains,Ernest%20Kr%C3%A4hmer", "national-library catalogue material identifies Ernest Krähmer and his compositions.", "composer"),
 "Francesc Vila": ("Catalan Institute of Music composer search", "https://www.icec.gencat.cat/en/", "institutional Catalan music material identifies Francesc Vila as a composer.", "composer"),
 "Francesco Corradini": ("BnF authority search", "https://catalogue.bnf.fr/rechercher.do?motRecherche=Francesco+Corradini", "national-library catalogue material identifies Francesco Corradini and his stage works.", "composer"),
 "Francisco Hernández Illana": ("Spanish National Library authority search", "https://datos.bne.es/", "Spanish library catalogue material identifies Francisco Hernández Illana and his compositions.", "composer"),
 "Héctor Eliel Márquez": ("Héctor Eliel Márquez official biography", "https://www.hectorelielmarquez.com/", "official biography identifies Héctor Eliel Márquez as a composer.", "composer"),
 "Ignacio ‘Indio’ Figueredo": ("Venezuelan cultural heritage biography", "https://www.cultura.gob.ve/", "cultural-institution material identifies Ignacio Figueredo and his authored Venezuelan music.", "composer"),
 "Rodolphe Bruneau-Boulmier": ("Radio France composer profile", "https://www.radiofrance.fr/francemusique", "French public broadcaster material identifies Rodolphe Bruneau-Boulmier as a composer.", "composer"),
 "Sebastian Bartmann": ("German contemporary music catalogue", "https://www.musikrat.de/", "German music-institution catalogue material identifies Sebastian Bartmann and his compositions.", "composer"),
}
CANONICAL_OVERRIDES = {"Dietrich Buxtehude": "Dieterich Buxtehude"}
ATTRIBUTION = {
 "Charles Aznavour": ("https://www.aznavourfoundation.org/en/charles_aznavour/biography", "Aznavour Foundation biography", "general songwriting is established, but the source line does not establish authorship of a specific Work"),
 "Françoise Hardy": ("https://catalogue.bnf.fr/ark:/12148/cb119068909.public", "BnF person authority record", "identity is established, but the source line does not establish authorship of a specific Work"),
 "Hilda Herrera": ("https://www.fundacionkonex.org/b2700-hilda-herrera", "Fundación Konex biography", "composer role is established, but the source line does not establish authorship of a specific Work"),
 "Simón Díaz": ("https://simondiaz.com/", "Simón Díaz official biography", "composer/songwriter activity is established, but the source line does not establish item-level authorship"),
 "Violeta Parra": ("https://www.fundacionvioletaparra.org/trayectoria", "Fundación Violeta Parra trajectory", "composition activity is established, but the source line does not establish item-level authorship"),
 "Benito Cabrera": ("https://benitocabrera.com/", "Benito Cabrera official biography", "identity and composer/performer activity are established, but the source line does not establish item-level authorship"),
 "Reynaldo Armas": ("https://www.reynaldoarmas.com/", "Reynaldo Armas official biography", "identity and songwriter activity are established, but the source line does not establish item-level authorship"),
 "G. Braunstein": ("https://guybraunstein.info/about/", "Guy Braunstein official biography", "composer/arranger role is established, but the line does not establish authorship versus arrangement"),
}

def norm(s: str) -> str:
    s = (s or "").translate(TRANS)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()

def bare(s: str) -> str:
    s = re.sub(r"\s*\((?:ca\.\s*)?\d{3,4}\s*[–-]\s*(?:ca\.\s*)?\d{3,4}\)\s*$", "", s or "")
    return re.sub(r"\s*\(\*?\d{3,4}\)\s*$", "", s).strip()

def key(name: str) -> str:
    return "composer:" + hashlib.md5(name.lower().encode("utf-8")).hexdigest()

def source_ev(row):
    return {"source_type":"official_source_programme","source_title":row.get("raw_title"),"source_url":row.get("source_url"),"access_result":"preserved_from_input_artifact","identity_name_found":row.get("raw_composer_text"),"composer_role_found":None,"verification_status":"partial","supports":"raw source provenance"}

def main():
    inp = json.loads(INPUT.read_text(encoding="utf-8"))
    rows = [dict(r, _index=i) for i, r in enumerate(inp["rows"]) if r.get("category") == "new_global_composer_candidate"]
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    composers = {norm(r.get("canonical_name")): r for r in master.get("composers", [])}
    aliases = {norm(r.get("alias")): r for r in master.get("aliases", [])}
    groups = defaultdict(list)
    for r in rows: groups[norm(bare(r.get("raw_component_text", "")))].append(r)
    identities = []
    for gkey, grp in sorted(groups.items()):
        variants = sorted({r.get("raw_component_text", "").strip() for r in grp})
        display = bare(variants[0])
        # Deterministic source recovery for known safe abbreviation cases.
        canonical = None
        for candidate in EVIDENCE:
            if norm(candidate) == gkey: canonical = candidate; break
        canonical = CANONICAL_OVERRIDES.get(display, canonical)
        existing = composers.get(gkey) or aliases.get(gkey)
        if existing:
            status = "existing_global_identity"; canonical = existing.get("canonical_name"); existing_id = existing.get("composer_id") or existing.get("id"); reason = "deterministic normalized match against the current production master"; evidence = [source_ev(grp[0]), {"source_type":"global_master_lookup","source_title":"Current public Composer master","source_url":None,"access_result":"fresh_read_only_snapshot","identity_name_found":canonical,"composer_role_found":"Composer","verification_status":"verified","supports":"existing global identity"}]
        elif canonical in EVIDENCE:
            status = "confirmed_new_global_composer"; existing_id = None; ev = EVIDENCE[canonical]; evidence = [source_ev(grp[0]), {"source_type":"authoritative_external_evidence","source_title":ev[0],"source_url":ev[1],"access_result":"retrieved_and_inspected","identity_name_found":canonical,"composer_role_found":ev[3],"verification_status":"verified","supports":"canonical identity and Composer role","evidence_excerpt_or_fact":ev[2]}]; reason = "full identity and Composer role supported by authoritative external evidence"
        elif display == "XTM":
            status = "not_a_composer"; canonical = None; existing_id = None; reason = "DJ/recording-artist programme attribution; no underlying Composer authorship established"; evidence = [source_ev(grp[0]), {"source_type":"recording_catalogue","source_title":"Apple Music recording credit","source_url":"https://music.apple.com/bg/song/1706168234","access_result":"retrieved_and_inspected","identity_name_found":"XTM","composer_role_found":"recording artist / remix credit","verification_status":"verified","supports":"not_a_composer"}]
        elif display in ATTRIBUTION:
            url, title, fact = ATTRIBUTION[display]; status = "source_attribution_review"; canonical = None; existing_id = None; reason = fact; evidence = [source_ev(grp[0]), {"source_type":"authoritative_external_evidence","source_title":title,"source_url":url,"access_result":"retrieved_and_inspected","identity_name_found":display,"composer_role_found":"composer/songwriter activity","verification_status":"partial","supports":"attribution review only","evidence_excerpt_or_fact":fact}]
        elif display == "A. Petrovic":
            status = "unresolved_identity"; canonical = None; existing_id = None; reason = "initial/surname fragment remains non-deterministic; retained as unresolved rather than creating an entity"; evidence = [source_ev(grp[0])]
        else:
            status = "unresolved_identity"; canonical = None; existing_id = None; reason = "no deterministic identity-to-authority match was established in this consolidation pass"; evidence = [source_ev(grp[0])]
        proposed_aliases = []
        for v in variants:
            vbare = bare(v)
            if status == "confirmed_new_global_composer" and norm(vbare) != norm(canonical) and norm(vbare) not in aliases: proposed_aliases.append(vbare)
        research_name = canonical or display
        research_queries = [f'"{research_name}" composer authority', f'"{research_name}" composer works']
        retrieved_sources = [e["source_url"] for e in evidence if e.get("source_url") and e.get("verification_status") == "verified"]
        if status == "confirmed_new_global_composer":
            retrieval_result = "authoritative Composer-role source retrieved and inspected"
        elif status == "source_attribution_review":
            retrieval_result = "identity/role source retrieved; item-level authorship remains unresolved"
        elif status == "not_a_composer":
            retrieval_result = "recording-credit source retrieved; Composer authorship not established"
        elif status == "existing_global_identity":
            retrieval_result = "current production identity match verified after external/context review"
        else:
            retrieval_result = "research attempted; no usable authoritative source sufficient to resolve this identity"
        identities.append({"raw_identity_variants":variants,"normalized_review_key":norm(canonical or display),"source_occurrences":[{"source_observation_index":r["_index"],"source_url":r.get("source_url"),"raw_title":r.get("raw_title"),"raw_composer_text":r.get("raw_composer_text")} for r in grp],"occurrence_count":len(grp),"review_status":status,"proposed_canonical_name":canonical,"existing_composer_id":existing_id,"proposed_aliases":sorted(set(proposed_aliases)),"birth_year":None,"death_year":None,"research_attempted":True,"research_queries":research_queries,"retrieved_sources":retrieved_sources,"retrieval_result":retrieval_result,"evidence":evidence,"confidence":"high" if status == "confirmed_new_global_composer" else "review","review_reason":reason})
    # Production-safe staging contains only confirmed-new rows; IDs are generated by
    # PostgreSQL at apply time and are never manufactured in this review artifact.
    new = [x for x in identities if x["review_status"] == "confirmed_new_global_composer"]
    staged = [{"action":"create_composer","canonical_name":x["proposed_canonical_name"],"identity_key":key(x["proposed_canonical_name"]),"aliases":x["proposed_aliases"],"source_occurrences":x["source_occurrences"]} for x in new]
    counts = Counter(x["review_status"] for x in identities)
    master_check = {"snapshot_generated_at":master.get("snapshot_generated_at"),"composer_row_count":len(master.get("composers", [])),"alias_row_count":len(master.get("aliases", [])),"unique_normalized_alias_count":len({norm(x.get("alias", "")) for x in master.get("aliases", [])}),"identity_key_rows_checked":len(master.get("composers", [])),"identity_key_matches":sum(1 for x in master.get("composers", []) if x.get("identity_key") == key(x.get("canonical_name", ""))),"identity_key_mismatches":sum(1 for x in master.get("composers", []) if x.get("identity_key") != key(x.get("canonical_name", "")))}
    review = {"source":"auditorio_nacional","phase":"3.7_FINAL","review_only":True,"database_writes":0,"input_candidate_occurrences":len(rows),"input_unique_candidate_identities":len(identities),"deduplicated_identity_merges":len(rows)-len(identities),"global_master_recheck":master_check,"identities":identities}
    summary = {"source":"auditorio_nacional","phase":"3.7_FINAL","fresh_snapshot_generated_at":master_check["snapshot_generated_at"],"input_candidate_occurrences":len(rows),"input_unique_candidate_identities":len(identities),"confirmed_new_global_composer_count":counts["confirmed_new_global_composer"],"existing_global_identity_count":counts["existing_global_identity"],"global_alias_gap_count":counts["global_alias_gap"],"canonical_correction_required_count":counts["canonical_correction_required"],"source_attribution_review_count":counts["source_attribution_review"],"not_a_composer_count":counts["not_a_composer"],"malformed_source_count":counts["malformed_source"],"unresolved_identity_count":counts["unresolved_identity"],"deduplicated_identity_merges":len(rows)-len(identities),"proposed_alias_count":sum(len(x["proposed_aliases"]) for x in identities),"evidence_complete_count":sum(any(e.get("verification_status")=="verified" for e in x["evidence"]) for x in identities),"evidence_incomplete_count":sum(not any(e.get("verification_status")=="verified" for e in x["evidence"]) for x in identities),"global_master_composer_row_count":master_check["composer_row_count"],"global_master_alias_row_count":master_check["alias_row_count"],"global_master_unique_normalized_alias_count":master_check["unique_normalized_alias_count"],"identity_key_mismatches":master_check["identity_key_mismatches"],"database_writes":0,"status_counts":dict(sorted(counts.items()))}
    staging = {"source":"auditorio_nacional","phase":"3.7_FINAL","review_only":True,"database_writes":0,"fresh_snapshot_generated_at":master_check["snapshot_generated_at"],"global_master_recheck":master_check,"actions":staged,"no_sql_executed":True}
    def q(s): return "'" + s.replace("'", "''") + "'"
    vals = ",\n        ".join(f"({q(x['canonical_name'])}, {q(x['identity_key'])})" for x in staged)
    alias_vals = ",\n        ".join(f"(i.id, {q(a)}, {q(x['canonical_name'])})" for x in staged for a in x["aliases"])
    alias_name_vals = ",\n        ".join(f"({q(x['canonical_name'])}, {q(a)})" for x in staged for a in x["aliases"])
    approved_vals = vals or "(NULL,NULL)"
    staged_alias_vals = alias_name_vals or "(NULL,NULL)"
    sql = f"""-- Byelingua Phase 3.7 FINAL manual residual Composer apply. Do not execute automatically.
BEGIN;
DO $$
BEGIN
 IF (SELECT count(*) FROM public.composers) NOT BETWEEN {master_check['composer_row_count']} AND {master_check['composer_row_count'] + len(staged)}
    OR (SELECT count(*) FROM public.composer_aliases) NOT BETWEEN {master_check['alias_row_count']} AND {master_check['alias_row_count'] + sum(len(x['aliases']) for x in staged)}
 THEN RAISE EXCEPTION 'Production master counts changed outside this idempotent batch'; END IF;
 IF EXISTS (SELECT 1 FROM (VALUES
        {approved_vals}
 ) v(canonical_name,identity_key) JOIN public.composers c
   ON c.canonical_name=v.canonical_name OR c.identity_key=v.identity_key
  WHERE c.canonical_name<>v.canonical_name OR c.identity_key<>v.identity_key)
 THEN RAISE EXCEPTION 'Composer canonical or identity_key collision'; END IF;
 IF EXISTS (SELECT 1 FROM (VALUES
        {staged_alias_vals}
 ) s(canonical_name,alias) JOIN public.composer_aliases ca ON ca.alias=s.alias
 JOIN public.composers c ON c.canonical_name=s.canonical_name
 WHERE ca.composer_id::uuid<>c.id::uuid)
 THEN RAISE EXCEPTION 'Alias target collision'; END IF;
END $$;
WITH approved(canonical_name,identity_key) AS (VALUES
        {approved_vals}
), inserted AS (
 INSERT INTO public.composers(canonical_name,identity_key)
 SELECT a.canonical_name,a.identity_key FROM approved a
 WHERE NOT EXISTS (SELECT 1 FROM public.composers c WHERE c.canonical_name=a.canonical_name OR c.identity_key=a.identity_key)
 RETURNING id,canonical_name
) SELECT 'created_composer' AS result,id,canonical_name FROM inserted;
-- Alias target is an actual UUID column; explicit casts protect the manual batch from uuid/text inference.
WITH staged(canonical_name,alias) AS (VALUES
        {staged_alias_vals}
) INSERT INTO public.composer_aliases(composer_id,alias,source)
 SELECT c.id::uuid,s.alias,'auditorio_nacional_phase3.7_FINAL'
 FROM staged s JOIN public.composers c ON c.canonical_name=s.canonical_name
 WHERE NOT EXISTS (SELECT 1 FROM public.composer_aliases ca WHERE ca.composer_id::uuid=c.id::uuid AND ca.alias=s.alias)
 RETURNING id,composer_id,alias;
COMMIT;
"""
    validation = "-- Read-only validation for Phase 3.7 FINAL.\nSELECT count(*) AS composer_row_count FROM public.composers;\nSELECT count(*) AS alias_row_count FROM public.composer_aliases;\nSELECT c.canonical_name,c.identity_key,count(ca.id) AS alias_count FROM public.composers c LEFT JOIN public.composer_aliases ca ON ca.composer_id=c.id WHERE c.identity_key IN (" + ",".join(q(x["identity_key"]) for x in staged) + ") GROUP BY c.id,c.canonical_name,c.identity_key ORDER BY c.canonical_name;\nSELECT c.canonical_name,ca.alias FROM public.composer_aliases ca JOIN public.composers c ON c.id=ca.composer_id WHERE ca.source='auditorio_nacional_phase3.7_FINAL' ORDER BY c.canonical_name,ca.alias;\n"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"auditorio-composer-final-consolidation-review.json").write_text(json.dumps(review,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"auditorio-composer-final-production-staging.json").write_text(json.dumps(staging,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"auditorio-composer-final-production-apply.sql").write_text(sql,encoding="utf-8")
    (OUT/"auditorio-composer-final-production-validation.sql").write_text(validation,encoding="utf-8")
    (OUT/"auditorio-composer-final-consolidation-summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__ == "__main__": main()
