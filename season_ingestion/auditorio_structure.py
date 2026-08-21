"""Deterministic, non-canonical structure classification for Auditorio pages."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


STRUCTURES = (
    "SEPARATE_ARTIST_PROGRAMME_BLOCKS",
    "MIXED_COMPOSER_WORK_BLOCK",
    "INLINE_COMPOSER_WORK",
    "COMPOSER_LIFESPAN_SEQUENCE",
    "PROGRAMME_MARKER_MIXED_BLOCK",
    "ARTIST_ROLE_ALTERNATING",
    "FREEFORM_PROGRAMME",
    "CAST_OR_STAGED_WORK",
    "STATUS_NOTICE_PLUS_CONTENT",
    "UNKNOWN",
)

LINE_CLASSES = (
    "artist_candidate", "role_candidate", "composer_candidate", "work_candidate",
    "composer_attribution",
    "movement_candidate", "programme_heading", "section_heading", "annotation",
    "status_notice", "freeform_programme", "cast_candidate",
    "artistic_team_candidate", "unknown",
)

PROGRAMME_MARKERS = {"programa", "programme", "obras", "repertorio"}
SECTION_MARKERS = {
    "primera parte", "segunda parte", "1a parte", "2a parte", "1ª parte", "2ª parte",
    "intervalo", "pausa", "------pausa-----",
}
ROLE_WORDS = {
    "director", "directora", "director musical", "dirección", "direccion",
    "piano", "pianista", "violín", "violin", "violines", "viola", "violas",
    "violonchelo", "violonchelista", "cello", "contrabajo", "soprano", "mezzosoprano",
    "tenor", "tenores", "barítono", "baritono", "bajo", "contralto", "alto", "flauta",
    "flautín", "flautin", "fagot", "trompa", "corno inglés", "corno ingles", "clave",
    "órgano", "organo", "oboe", "clarinete", "saxofón", "saxofon",
    "oboe", "clarinete", "trompeta", "trombón", "trombon", "arpa", "guitarra",
    "solista", "corifeo", "concertino", "cantaora", "cantante",
    "narrador", "narradora", "movimiento escénico", "movimiento escenico",
    "puesta en escena", "regiduría", "regiduria", "coreografía", "coreografia",
}
COMPOSER_HINTS = {
    "bach", "mahler", "debussy", "turina", "falla", "halffter", "dvorak", "dvořák",
    "chaikovsky", "tchaikovsky", "sibelius", "beethoven", "brahms", "weinberg",
    "messiaen", "scriabin", "zorn", "albinoni", "vivaldi", "mozart", "haydn",
    "haendel", "handel", "saint-saëns", "saint-saens", "saens", "prokofiev",
    "stravinski", "stravinsky", "elgar", "shostakóvich", "shostakovich", "gounod", "adams",
    "reynaldo hahn", "françoise hardy", "honoré d'ambruys", "honore d'ambruys", "terzian", "onslow", "milhaud", "piazzolla", "bernstein", "turina", "respighi", "stravinsky", "mozart camargo guarnieri",
    "verdi", "puccini", "gershwin", "bernstein", "petrovic", "chen gang", "zhanhao",
}
WORK_WORDS = (
    "sinfonía", "sinfonia", "concierto", "suite", "sonata", "obertura", "overture",
    "carnaval", "preludio", "réquiem", "requiem", "canciones", "canto", "catedral",
    "el mar", "atlàntida", "atlantida", "romeo y julieta", "las cuatro estaciones",
    "rhapsody", "poème", "poeme", "vers la flamme", "jumalattaret", "mesías", "mesias",
    "à chloris", "le temps de l’amour", "le temps de l'amour", "le premier bonheur du jour",
    "gnossienne", "gymnopédie", "gymnopedie", "graffiti", "chants de terre et de ciel", "quinteto",
    "invocación y danza", "invocacion y danza", "liturgia del sonido", "opening", "voices-stimmen",
    "klavierstück", "klavierstuck", "piano sonata", "dança negra", "danca negra", "obras de",
    "stabat mater", "nisi dominus", "procesión del rocío", "procesion del rocio", "nocturne",
    "de airs", "la bohème", "la boheme", "fast blue village",
)
MOVEMENT_RE = re.compile(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|\d+)[.)]?\s+\S+", re.I)
LIFESPAN_RE = re.compile(r"\((?:\*|ca\.\s*)?\d{3,4}(?:\s*[–—-]\s*(?:\*|ca\.\s*)?\d{2,4})?\)")
STATUS_RE = re.compile(r"\b(?:aplazad[oa]|cancelad[oa]|suspendid[oa])\b|^al\s+\d", re.I)
CAST_RE = re.compile(r"^.{2,60}\s+[–—-]\s+.{2,}$")
INLINE_RE = re.compile(r"^.{2,60}\s*(?:·|:|—|–)\s*.+$")


def fold(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def is_role(value: str) -> bool:
    text = fold(value).strip(" .:,")
    return text in ROLE_WORDS


def has_role_suffix(value: str) -> bool:
    role = r"(?:director(?:a)?|piano|violín|violin|soprano|mezzosoprano|tenor|bajo|viola|violonchelo|corifeo|coro|clave|dirección|direccion|laúd|laud|tiorba|guitarra|flauta|melodica)(?:\s+y\s+[^,]+)?"
    comma = re.match(r"^(.+?),\s*" + role + r"$", value, re.I)
    if comma:
        return person_like(comma.group(1))
    suffix = re.match(r"^(.+?)\s+" + role + r"$", value, re.I)
    return bool(suffix and person_like(suffix.group(1)) and not work_signal(suffix.group(1)))


def has_lifespan(value: str) -> bool:
    return bool(LIFESPAN_RE.search(value))


def composer_signal(value: str) -> bool:
    text = fold(value)
    lifespan_name = re.sub(LIFESPAN_RE, "", value).strip()
    if has_lifespan(value) and person_like(lifespan_name) and len(re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ.’'-]+", lifespan_name)) >= 2 and not work_signal(value) and "**" not in value and len(value.split()) <= 7:
        return True
    if any(re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text) for token in COMPOSER_HINTS):
        return True
    # Initialed / all-capital composer source lines, kept raw and unresolved.
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ.’'-]+", value)
    return bool(words and len(words) <= 5 and all(
        word.isupper() or re.fullmatch(r"[A-ZÁÉÍÓÚÜÑ]\.?", word)
        for word in words
    ) and not is_role(value))


def inline_signal(value: str) -> bool:
    if has_lifespan(value):
        return False
    if not INLINE_RE.match(value):
        return False
    left = re.split(r"·|:|—|–", value, maxsplit=1)[0].strip()
    return composer_signal(left) or bool(re.fullmatch(r"[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ .'-]+", left))


def work_signal(value: str) -> bool:
    text = fold(value)
    return any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) for word in WORK_WORDS) or bool(re.search(r"\b(?:BWV|KV|K\.|Op\.?|Hob\.?|RV|HWV|D\.)\s*[.\d]", value, re.I))


def artist_signal(value: str) -> bool:
    if is_role(value) or composer_signal(value) or work_signal(value):
        return False
    if has_role_suffix(value):
        return True
    text = fold(value)
    return any(token in text for token in (
        "orquesta", "orchestra", "coro", "ensemble", "quartet", "cuarteto",
        "orcam", "ocne", "cantores", "filarmónica", "filarmonica",
    ))


def person_like(value: str) -> bool:
    if re.search(r"\d", value):
        return False
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀ-ÿ.’'-]+", value)
    if not 1 <= len(words) <= 6:
        return False
    connectors = {"de", "del", "d", "van", "von", "y", "la", "le"}
    return all(word.casefold().strip(".") in connectors or word[:1].isupper() for word in words)


def lifespan_name_like(value: str) -> bool:
    """Recognize accented personal names after removing a lifespan suffix."""
    stripped = re.sub(LIFESPAN_RE, "", value).strip()
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž'’-]+", stripped)
    connectors = {"de", "del", "d", "van", "von", "y", "la", "le"}
    return len(words) >= 2 and all(word.casefold() in connectors or word[:1].isupper() for word in words)


def ensemble_signal(value: str) -> bool:
    if work_signal(value):
        return False
    text = fold(value)
    return any(re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text) for token in (
    "orquesta", "orchestra", "orquestra", "orchester", "coro", "choir", "ensemble", "ensamble", "quartet",
        "cuarteto", "quinteto", "quintet", "orcam", "ocne", "cantores", "filarmónica", "filarmonica",
        "philharmonic", "jugendorchester", "collegium", "joven orquesta", "miembros del", "spark", "musiciens du louvre",
    ))


def standalone_roman(value: str) -> bool:
    return bool(re.fullmatch(r"[IVXLCDM]+", value.strip(), re.I))


def inline_fragments(value: str) -> dict[str, str] | None:
    lifespan_name = re.sub(LIFESPAN_RE, "", value).strip()
    if has_lifespan(value) and lifespan_name_like(lifespan_name) and len(lifespan_name.split()) >= 2 and not work_signal(value):
        return None
    match = re.match(r"^(.+?)\.\s+(.+?)\s*(\((?:\*|ca\.\s*)?\d{3,4}(?:\s*[–—-]\s*(?:\*|ca\.\s*)?\d{2,4})?\))$", value)
    if match and lifespan_name_like(match.group(2)):
        return {"raw_work_fragment": match.group(1).strip(), "raw_composer_fragment": match.group(2).strip() + " " + match.group(3)}
    match = re.match(r"^(.+?)\s*(?:·|:|—|–|,|\.-)\s*(.+)$", value)
    if match:
        composer, work = match.groups()
        composer_fragment = composer.strip().rstrip(",")
        if composer_signal(composer_fragment) or bool(re.fullmatch(r"[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ .'-]+", composer_fragment)):
            return {"raw_composer_fragment": composer_fragment, "raw_work_fragment": work.strip()}
        if person_like(work) and (composer_signal(work) or has_lifespan(work)):
            return {"raw_work_fragment": composer.strip(), "raw_composer_fragment": work.strip()}
    # Work-first suffix, only when the parenthetical fragment is a clear name.
    match = re.match(r"^(.+?)\s*\(([^()]+)\)$", value)
    if match and person_like(re.sub(LIFESPAN_RE, "", match.group(2)).strip()):
        return {"raw_work_fragment": match.group(1).strip(), "raw_composer_fragment": match.group(2).strip()}
    for composer_name in ("lili boulanger", "mozart camargo guarnieri", "igor stravinsky"):
        if fold(value).startswith(composer_name + " "):
            return {"raw_composer_fragment": value[:len(composer_name)], "raw_work_fragment": value[len(composer_name):].strip()}
    match = re.match(r"^([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ.'-]*)\s+(.+)$", value)
    if match and fold(match.group(1)) in COMPOSER_HINTS:
        return {"raw_composer_fragment": match.group(1).strip(), "raw_work_fragment": match.group(2).strip()}
    return None


def cross_line_inline_fragments(value: str, next_value: str) -> dict[str, str] | None:
    """Split a deterministic composer/work prefix while preserving both source lines."""
    if not next_value:
        return None
    words = value.split()
    for split in range(len(words) - 1, 0, -1):
        composer = " ".join(words[:split])
        work = " ".join(words[split:])
        if person_like(composer) and composer_signal(composer) and fold(work) == "variaciones":
            return {"raw_composer_fragment": composer, "raw_work_fragment": work + "\n" + next_value}
    return None


def mixed_traditional_attribution(value: str) -> dict[str, Any] | None:
    """Represent traditional plus named attribution without creating a composer identity."""
    match = re.fullmatch(r"(.+?)/(.*\([^)]*\d{3,4}[^)]*\))", value)
    if not match:
        return None
    non_person, named = (part.strip() for part in match.groups())
    if fold(non_person).startswith("tradicional de ") and person_like(re.sub(LIFESPAN_RE, "", named).strip()):
        return {
            "attribution_type": "mixed_traditional_named",
            "raw_named_composer_fragments": [named],
            "raw_non_person_attribution_fragments": [non_person],
        }
    return None


def cast_line(value: str) -> bool:
    if not CAST_RE.match(value) or composer_signal(value):
        return False
    left, right = re.split(r"\s+[–—-]\s+", value, maxsplit=1)
    return person_like(right) and not work_signal(left) and len(left.split()) <= 8


def structure_hint(page: dict[str, Any]) -> str:
    title = page.get("raw_title") or ""
    lines = [line for block in page.get("raw_content_blocks") or [] for line in block.get("raw_lines") or []]
    normalized = [fold(line).strip(" .:") for line in lines]
    if re.search(r"film symphony|red bull symphonic", title, re.I):
        return "FREEFORM_PROGRAMME"
    if re.search(r"ópera|opera|trovatore", title, re.I) or any(cast_line(line) for line in lines):
        return "CAST_OR_STAGED_WORK"
    if any(value in PROGRAMME_MARKERS or value.startswith("programa:") for value in normalized):
        return "PROGRAMME_MARKER_MIXED_BLOCK"
    if any(inline_fragments(line) and inline_fragments(line).get("raw_composer_fragment") for line in lines):
        return "INLINE_COMPOSER_WORK"
    if sum(has_lifespan(line) and person_like(re.sub(LIFESPAN_RE, "", line).strip()) for line in lines) >= 2:
        return "COMPOSER_LIFESPAN_SEQUENCE"
    if sum(is_role(line) for line in lines) >= 2:
        return "ARTIST_ROLE_ALTERNATING"
    if len(page.get("raw_content_blocks") or []) >= 2:
        return "SEPARATE_ARTIST_PROGRAMME_BLOCKS"
    return "MIXED_COMPOSER_WORK_BLOCK"


def _flat_lines(page: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for block_index, block in enumerate(page.get("raw_content_blocks") or []):
        for line_index, raw_text in enumerate(block.get("raw_lines") or []):
            result.append({
                "raw_text": raw_text,
                "block_order": block_index,
                "line_order": line_index,
            })
    return result


def _classify_lines(page: dict[str, Any], lines: list[dict[str, Any]], hint: str) -> None:
    title = page.get("raw_title") or page.get("raw_detail_title") or ""
    freeform_page = hint == "FREEFORM_PROGRAMME"
    programme_started = False
    sequence_transitioned = False
    awaiting_work = False
    role_seen = False
    role_override_count = 0
    transition_count = 0
    composer_context = False
    for index, item in enumerate(lines):
        value = item["raw_text"]
        normalized = fold(value).strip(" .:")
        signals: list[str] = []
        classification = "unknown"
        next_value = lines[index + 1]["raw_text"] if index + 1 < len(lines) else ""
        explicit_role = has_role_suffix(value)
        ensemble_override = ensemble_signal(value) and not inline_fragments(value)
        mixed_attribution = mixed_traditional_attribution(value)
        cross_line_fragments = cross_line_inline_fragments(value, next_value)
        if mixed_attribution:
            classification, signals = "composer_attribution", ["mixed_traditional_named"]
            item.update(mixed_attribution)
        elif cross_line_fragments:
            classification, signals = "work_candidate", ["inline_composer_work", "cross_line_inline_composer_work"]
            item["inline_composer_work"] = cross_line_fragments
            programme_started = True
            awaiting_work = False
        elif STATUS_RE.search(value) and (index < 3 or normalized.startswith("al ")):
            classification, signals = "status_notice", ["status_pattern"]
        elif normalized in PROGRAMME_MARKERS or normalized.startswith("programa:"):
            classification, programme_started, signals = "programme_heading", True, ["programme_marker"]
        elif normalized in SECTION_MARKERS:
            classification, signals = "section_heading", ["section_marker"]
        elif value.startswith(("*", "**", "+", "++")) or normalized.startswith("obras de") or re.search(r"estreno|encargo|primera vez|colaboración|colaboracion", normalized):
            classification, signals = "annotation", ["annotation_pattern"]
        elif normalized in {"movimiento escénico", "movimiento escenico", "puesta en escena"} or "puesta en escena" in normalized:
            classification, signals = "artistic_team_candidate", ["artistic_team_label"]
        elif standalone_roman(value):
            classification, signals = "section_heading", ["standalone_roman"]
        elif explicit_role or ensemble_override:
            classification, signals = "artist_candidate", ["artist_role_override" if explicit_role else "ensemble_override"]
            if explicit_role:
                role_override_count += 1
        elif cast_line(value):
            left = value.split("–", 1)[0].split("—", 1)[0].split("-", 1)[0]
            if fold(left).strip() in {"movimiento escénico", "movimiento escenico", "puesta en escena"}:
                classification, signals = "artistic_team_candidate", ["artistic_team_label", "cast_separator"]
            elif is_role(left) or len(left.split()) <= 8:
                classification, signals = "cast_candidate", ["cast_separator"]
        elif is_role(value):
            classification, signals = "role_candidate", ["role_dictionary"]
            role_seen = True
        elif value.isupper() and len(value.split()) <= 6:
            classification, signals = "section_heading", ["uppercase_heading"]
        elif freeform_page and index >= 2:
            classification, signals = "freeform_programme", ["freeform_page_signal"]
        elif hint == "SEPARATE_ARTIST_PROGRAMME_BLOCKS" and item["block_order"] >= 1:
            programme_started = True
            fragments = inline_fragments(value)
            if fragments:
                classification, signals = "work_candidate", ["inline_composer_work"]
                item["inline_composer_work"] = fragments
                awaiting_work = False
            elif awaiting_work:
                classification, signals = "work_candidate", ["programme_sequence_work"]
                awaiting_work = False
            elif person_like(value) and (person_like(next_value) or work_signal(next_value) or next_value):
                classification, signals = "composer_candidate", ["programme_sequence_composer"]
                awaiting_work = True
            elif MOVEMENT_RE.match(value):
                classification, signals = "movement_candidate", ["movement_pattern"]
            else:
                classification, signals = "work_candidate", ["programme_sequence_work"]
        elif hint == "ARTIST_ROLE_ALTERNATING" and not sequence_transitioned:
            next_next = lines[index + 2]["raw_text"] if index + 2 < len(lines) else ""
            if person_like(value) and is_role(next_value):
                classification, signals = "artist_candidate", ["artist_role_lookahead_override"]
            elif work_signal(value):
                classification, signals = "work_candidate", ["work_vocab_override"]
                programme_started = True
            elif work_signal(next_value) or (role_seen and person_like(value) and person_like(next_value) and work_signal(next_next)):
                sequence_transitioned = True
                programme_started = True
                transition_count += 1
                classification, signals = "composer_candidate", ["sequence_transition"]
                awaiting_work = True
            elif is_role(value):
                classification, signals = "role_candidate", ["role_dictionary"]
            else:
                classification, signals = "artist_candidate", ["artist_sequence"]
        elif sequence_transitioned and awaiting_work:
            classification, signals = "work_candidate", ["sequence_transition_work"]
            awaiting_work = False
        elif inline_fragments(value):
            fragments = inline_fragments(value)
            classification, signals = "work_candidate", ["inline_composer_work"]
            item["inline_composer_work"] = fragments
            programme_started = True
            composer_context = False
        elif composer_signal(value) and (has_lifespan(value) and person_like(re.sub(LIFESPAN_RE, "", value).strip()) or person_like(value) or (programme_started and not work_signal(value))):
            classification, signals = "composer_candidate", ["composer_signal"]
            composer_context = True
            programme_started = True
            awaiting_work = True
        elif MOVEMENT_RE.match(value) or (normalized in {"allegro", "adagio", "presto", "andante", "vivace", "largo"}):
            classification, signals = "movement_candidate", ["movement_pattern"]
        elif artist_signal(value):
            classification, signals = "artist_candidate", ["artist_or_credit_signal"]
        elif work_signal(value) or composer_context or programme_started and index > 0:
            classification, signals = "work_candidate", (["catalogue_or_work_signal"] if work_signal(value) else ["after_programme_context"])
            composer_context = False if work_signal(value) else composer_context
        elif index < 8 and not programme_started and len(value.split()) <= 8:
            classification, signals = "artist_candidate", ["artist_or_credit_signal"]
        elif freeform_page and (value.startswith(('"', "“", "«")) or "bandas sonoras" in normalized or index > 1):
            classification, signals = "freeform_programme", ["freeform_page_signal"]
        if value.startswith(("Arreglo de", "Con motivos de", "Música de la película", "Musica de la pelicula")):
            classification, signals = "annotation", ["arrangement_or_source_note"]
        item["classification"] = classification
        item["signals"] = signals
    page["_artist_role_override_count"] = role_override_count
    page["_sequence_transition_count"] = transition_count


def classify_page(page: dict[str, Any]) -> dict[str, Any]:
    lines = _flat_lines(page)
    hint = structure_hint(page)
    _classify_lines(page, lines, hint)
    values = [line["raw_text"] for line in lines]
    classes = [line["classification"] for line in lines]
    blocks = page.get("raw_content_blocks") or []
    has_marker = any(c == "programme_heading" for c in classes)
    has_status = any(c == "status_notice" for c in classes)
    has_cast = any(c in {"cast_candidate", "artistic_team_candidate"} for c in classes)
    has_inline = any("inline_composer_work" in s for line in lines for s in line["signals"])
    lifespan_count = sum(c == "composer_candidate" and has_lifespan(line["raw_text"])
                         for line, c in zip(lines, classes))
    title = page.get("raw_title") or ""
    if has_status:
        structure = "STATUS_NOTICE_PLUS_CONTENT"
    elif has_cast or re.search(r"ópera|opera|trovatore", title, re.I):
        structure = "CAST_OR_STAGED_WORK"
    elif re.search(r"film symphony|red bull symphonic", title, re.I) or any(c == "freeform_programme" for c in classes):
        structure = "FREEFORM_PROGRAMME"
    elif has_marker:
        structure = "PROGRAMME_MARKER_MIXED_BLOCK"
    elif has_inline:
        structure = "INLINE_COMPOSER_WORK"
    elif lifespan_count >= 2:
        structure = "COMPOSER_LIFESPAN_SEQUENCE"
    elif sum(c == "role_candidate" for c in classes) >= 2:
        structure = "ARTIST_ROLE_ALTERNATING"
    elif len(blocks) >= 2 and any(c == "artist_candidate" for c in classes[:len(blocks[0].get("raw_lines") or [])]) and any(c in {"composer_candidate", "work_candidate"} for c in classes):
        structure = "SEPARATE_ARTIST_PROGRAMME_BLOCKS"
    elif any(c in {"composer_candidate", "work_candidate"} for c in classes):
        structure = "MIXED_COMPOSER_WORK_BLOCK"
    else:
        structure = "UNKNOWN"
    return {
        "source": page.get("source"),
        "source_url": page.get("source_url"),
        "raw_title": title,
        "raw_datetime_examples": [page.get("raw_datetime")],
        "raw_venue": page.get("raw_venue"),
        "structure_class": structure,
        "raw_artist_lines": page.get("raw_artist_lines") or [],
        "raw_programme_lines": page.get("raw_programme_lines") or [],
        "raw_content_blocks": page.get("raw_content_blocks") or [],
        "classified_lines": lines,
        "_artist_role_override_count": page.get("_artist_role_override_count", 0),
        "_sequence_transition_count": page.get("_sequence_transition_count", 0),
    }


def classify_artifact(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    unique: dict[str, dict[str, Any]] = {}
    for occurrence in data["occurrences"]:
        unique.setdefault(occurrence["source_url"], occurrence)
    return [classify_page(page) for page in unique.values()]


def parser_conflict(page: dict[str, Any]) -> bool:
    old_artist = set(page.get("raw_artist_lines") or [])
    old_programme = set(page.get("raw_programme_lines") or [])
    lines = page["classified_lines"]
    artist_like = {"artist_candidate", "role_candidate", "cast_candidate", "artistic_team_candidate"}
    programme_like = {"composer_candidate", "composer_attribution", "work_candidate", "movement_candidate", "programme_heading", "section_heading", "annotation", "freeform_programme"}
    return bool(
        any(line["raw_text"] in old_artist and line["classification"] in programme_like for line in lines)
        or any(line["raw_text"] in old_programme and line["classification"] in artist_like for line in lines)
    )


def composer_candidate_risk(line: dict[str, Any]) -> bool:
    """Return whether a composer candidate violates the Phase 2.2 input gate."""
    if line.get("classification") != "composer_candidate":
        return False
    raw = line.get("raw_text", "")
    return bool(
        ensemble_signal(raw)
        or cast_line(raw)
        or has_role_suffix(raw)
        or work_signal(raw)
        or inline_fragments(raw)
        or fold(raw).startswith("obras de")
        or (has_lifespan(raw) and not lifespan_name_like(raw))
    )


def summarize(pages: list[dict[str, Any]], source_path: str) -> dict[str, Any]:
    structures = Counter(page["structure_class"] for page in pages)
    lines = [line for page in pages for line in page["classified_lines"]]
    line_classes = Counter(line["classification"] for line in lines)
    special = {}
    for label, pattern in {
        "ocne_sinfonico_04_programme_not_artist": r"^OCNE\. Sinfónico 04$",
        "atlantida_las_4_estaciones": r"Atlántida Chamber Orchestra\. Las 4 Estaciones",
        "orcam_sinfonico_1": r"^ORCAM\. Sinfónico 1\. ",
        "excelentia_inline": r"Excelentia\. Violín Chaikovsky",
        "cndm_mario_brunello": r"CNDM\. Mario Brunello",
        "film_symphony_odisea": r"Film Symphony Orchestra\. Odisea",
        "il_trovatore": r"Excelentia\. Ópera: IL Trovatore",
        "cndm_aplazado": r"CNDM\. Barbara Hannigan",
    }.items():
        matches = [p for p in pages if re.search(pattern, p["raw_title"], re.I)]
        special[label] = {"pages": len(matches), "structure_classes": sorted({p["structure_class"] for p in matches})}
    all_lines = [line for page in pages for line in page["classified_lines"]]
    composer_lines = [line for line in all_lines if line["classification"] == "composer_candidate"]
    mixed_attribution_lines = [line for line in all_lines if line["classification"] == "composer_attribution"]
    high_risk = sum(composer_candidate_risk(line) for line in composer_lines)
    inline_lines = [line for line in all_lines if "inline_composer_work" in line["signals"]]
    work_first_inline = sum(
        line.get("inline_composer_work", {}).get("raw_composer_fragment", "")
        and line.get("inline_composer_work", {}).get("raw_work_fragment", "")
        and line["raw_text"].find(line["inline_composer_work"]["raw_composer_fragment"])
        > line["raw_text"].find(line["inline_composer_work"]["raw_work_fragment"])
        for line in inline_lines
    )
    return {
        "source": "auditorio_nacional",
        "input_artifact": source_path,
        "unique_detail_pages_classified": len(pages),
        "structure_class_distribution": dict(sorted(structures.items())),
        "raw_line_count": len(lines),
        "line_classification_distribution": dict(sorted(line_classes.items())),
        "unknown_line_count": line_classes.get("unknown", 0),
        "unknown_page_count": structures.get("UNKNOWN", 0),
        "status_notice_count": line_classes.get("status_notice", 0),
        "freeform_programme_page_count": structures.get("FREEFORM_PROGRAMME", 0),
        "cast_staged_work_page_count": structures.get("CAST_OR_STAGED_WORK", 0),
        "movement_candidate_count": line_classes.get("movement_candidate", 0),
        "annotation_count": line_classes.get("annotation", 0),
        "pages_where_current_parser_split_conflicts": sum(parser_conflict(p) for p in pages),
        "composer_candidate_count": len(composer_lines),
        "mixed_composer_attribution_count": len(mixed_attribution_lines),
        "composer_candidate_unique_raw_count": len({line["raw_text"] for line in composer_lines}),
        "composer_candidate_high_risk_count": high_risk,
        "inline_composer_work_count": len(inline_lines),
        "work_first_inline_composer_count": work_first_inline,
        "ensemble_override_count": sum("ensemble_override" in line["signals"] for line in all_lines),
        "cast_override_count": sum(line["classification"] == "cast_candidate" for line in all_lines),
        "artist_role_override_count": sum(page.get("_artist_role_override_count", 0) for page in pages),
        "artist_role_lookahead_override_count": sum("artist_role_lookahead_override" in line["signals"] for line in all_lines),
        "sequence_transition_count": sum(page.get("_sequence_transition_count", 0) for page in pages),
        "parser_classifier_conflict_count": sum(parser_conflict(p) for p in pages),
        "quality_gate_violations": high_risk,
        "database_writes": 0,
        "special_case_pages": special,
    }
