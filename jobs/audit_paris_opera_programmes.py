from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    "",
).strip().rstrip("/")

SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY",
    "",
).strip()

OUTPUT_FILE = "paris-opera-programme-dry-run.json"

PARSER_VERSION = "paris_opera_programme_v4"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/151 Safari/537.36"
    )
}


# ============================================================
# GENERIC TEXT HELPERS
# ============================================================

def normalize_space(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def norm(value: str) -> str:
    value = normalize_space(value)

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        ch
        for ch in value
        if not unicodedata.combining(ch)
    )

    return value.casefold()


# ============================================================
# SUPABASE READ-ONLY
# ============================================================

def validate_environment() -> None:
    if not SUPABASE_URL:
        raise RuntimeError(
            "Missing SUPABASE_URL."
        )

    if not SUPABASE_KEY:
        raise RuntimeError(
            "Missing SUPABASE_SERVICE_ROLE_KEY."
        )

    if SUPABASE_URL == "[SENSITIVE]":
        raise RuntimeError(
            "SUPABASE_URL contains Vercel [SENSITIVE] placeholder."
        )

    if SUPABASE_KEY == "[SENSITIVE]":
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY contains "
            "Vercel [SENSITIVE] placeholder."
        )


def supabase_get(
    path: str,
    params: dict | None = None,
):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{path}",
        params=params,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": (
                f"Bearer {SUPABASE_KEY}"
            ),
        },
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def get_queue():
    return supabase_get(
        "canonical_rebuild_source_programme_queue",
        {
            "select": (
                "source_url,"
                "event_type,"
                "source_titles,"
                "event_ids,"
                "event_count,"
                "status"
            ),
            "status": "eq.pending",
            "order": (
                "event_type.asc,"
                "source_url.asc"
            ),
            "limit": "1000",
        },
    )


def get_composer_names():
    composers = supabase_get(
        "composers",
        {
            "select": "canonical_name",
            "limit": "5000",
        },
    )

    aliases = supabase_get(
        "composer_aliases",
        {
            "select": "alias",
            "limit": "5000",
        },
    )

    names: dict[str, str] = {}

    for row in composers:
        name = row.get(
            "canonical_name"
        )

        if name:
            names[norm(name)] = name

    for row in aliases:
        alias = row.get("alias")

        if alias:
            names.setdefault(
                norm(alias),
                alias,
            )

    return names


# ============================================================
# WEB PAGE → CLEAN TEXT LINES
# ============================================================

def fetch_lines(url: str):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=60,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    for tag in soup(
        [
            "script",
            "style",
            "noscript",
        ]
    ):
        tag.decompose()

    raw = soup.get_text("\n")

    lines: list[str] = []

    for raw_line in raw.splitlines():
        line = normalize_space(
            raw_line
        )

        if line:
            lines.append(line)

    return lines


# ============================================================
# SHARED ROLE / UI LABELS
# ============================================================

ROLE_WORDS = {
    "Direction musicale",
    "Chef d'orchestre",
    "Chef d’orchestre",
    "Soprano",
    "Mezzo-soprano",
    "Ténor",
    "Tenor",
    "Baryton",
    "Basse",
    "Piano",
    "Violon",
    "Alto",
    "Violoncelle",
    "Contrebasse",
    "Flûte",
    "Flute",
    "Hautbois",
    "Clarinette",
    "Basson",
    "Cor",
    "Trompette",
    "Trombone",
    "Percussions",
    "Orchestre",
    "Chœur",
    "Choeur",
    "Chorégraphie",
    "Choregraphie",
    "Scénographie",
    "Scenographie",
    "Costumes",
    "Lumières",
    "Lumieres",
    "Vidéo",
    "Video",
}


def is_role_line(
    line: str,
) -> bool:
    key = norm(line)

    for role in ROLE_WORDS:
        role_key = norm(role)

        if (
            key == role_key
            or key.startswith(
                role_key + " "
            )
        ):
            return True

    return False


# ============================================================
# BALLET PARSER
# ============================================================

BALLET_ANNOTATIONS = {
    "Artistes",
    "Équipe artistique",
    "Equipe artistique",
    "Nouveau",
    "Création",
    "Creation",
    "Entrée au répertoire",
    "Entree au repertoire",
    "Première mondiale",
    "Premiere mondiale",
}

BALLET_NON_TITLES = {
    "Distribution",
    "Artistes",
    "Équipe artistique",
    "Equipe artistique",
    "Lumières",
    "Lumieres",
    "Costumes",
    "Décors",
    "Decors",
    "Scénographie",
    "Scenographie",
    "Chorégraphie",
    "Choregraphie",
    "Musique",
    "Direction musicale",
}

BALLET_DESCRIPTION_PREFIXES = (
    "D’après ",
    "D'apres ",
    "D'après ",
    "D’apres ",
    "Ballet en ",
    "Ballet pour ",
)

BALLET_STOP_LINES = {
    "Galerie médias",
    "Galerie medias",
    "Accès et services",
    "Acces et services",
    "Vous aimerez aussi",
    "Services",
    "Boutiques",
}


def is_ballet_description(
    line: str,
) -> bool:
    key = norm(line)

    for prefix in (
        BALLET_DESCRIPTION_PREFIXES
    ):
        if key.startswith(
            norm(prefix)
        ):
            return True

    if len(line) > 120:
        return True

    return False


def is_plausible_ballet_title(
    line: str,
) -> bool:
    if not line:
        return False

    if line.startswith(
        "[Button"
    ):
        return False

    if norm(line) in {
        norm(value)
        for value
        in BALLET_NON_TITLES
    }:
        return False

    if is_role_line(line):
        return False

    if is_ballet_description(
        line
    ):
        return False

    return True


def find_ballet_title(
    lines,
    team_index: int,
):
    if team_index <= 0:
        return None

    first_index = (
        team_index - 1
    )

    first = lines[
        first_index
    ]

    # Typical:
    #
    # Work title
    # Création
    # Équipe artistique

    if norm(first) in {
        norm(value)
        for value
        in BALLET_ANNOTATIONS
    }:
        candidate_index = (
            first_index - 1
        )

        if candidate_index < 0:
            return None

        candidate = lines[
            candidate_index
        ]

        if (
            is_plausible_ballet_title(
                candidate
            )
        ):
            return candidate

        return None

    # Typical:
    #
    # Ma mère l’Oye
    # Ballet en ...
    # D’après ...
    # Équipe artistique

    lower_bound = max(
        -1,
        team_index - 8,
    )

    for i in range(
        team_index - 1,
        lower_bound,
        -1,
    ):
        line = lines[i]

        if (
            norm(line)
            == norm(
                "Équipe artistique"
            )
        ):
            break

        if is_ballet_description(
            line
        ):
            continue

        if norm(line) in {
            norm(value)
            for value
            in BALLET_ANNOTATIONS
        }:
            continue

        if (
            is_plausible_ballet_title(
                line
            )
        ):
            return line

    return None


def parse_music_credit(
    lines,
    index: int,
):
    line = lines[index]

    # Example:
    # The Magnetic Fields Musique

    match = re.match(
        r"^(.*?)\s+"
        r"Musique(?:\s*\(|$)",
        line,
        flags=re.IGNORECASE,
    )

    if (
        match
        and match.group(1).strip()
    ):
        return normalize_space(
            match.group(1)
        )

    # Example:
    #
    # Max Richter
    # Musique (1966)

    if re.match(
        r"^Musique(?:\s*\(|$)",
        line,
        flags=re.IGNORECASE,
    ):
        if index > 0:
            return normalize_space(
                lines[index - 1]
            )

    return None


def extract_ballet(lines):
    items = []

    team_indexes = [
        i
        for i, line
        in enumerate(lines)
        if (
            norm(line)
            == norm(
                "Équipe artistique"
            )
        )
    ]

    for (
        position,
        team_index,
    ) in enumerate(
        team_indexes
    ):
        title = find_ballet_title(
            lines,
            team_index,
        )

        if (
            position + 1
            < len(team_indexes)
        ):
            end = team_indexes[
                position + 1
            ]
        else:
            end = len(lines)

        composers = []

        for i in range(
            team_index + 1,
            end,
        ):
            line = lines[i]

            if (
                line
                in BALLET_STOP_LINES
            ):
                break

            if (
                norm(line)
                == norm(
                    "Distribution"
                )
            ):
                break

            if line.startswith(
                "[Button"
            ):
                break

            composer = (
                parse_music_credit(
                    lines,
                    i,
                )
            )

            if (
                composer
                and composer
                not in composers
            ):
                composers.append(
                    composer
                )

        # Never generate a Work
        # without BOTH:
        # 1. reliable title
        # 2. music credit

        if title and composers:
            items.append(
                {
                    "raw_title":
                        title,
                    "raw_composers":
                        composers,
                    "source_section":
                        "artistes",
                }
            )

    return items


# ============================================================
# CONCERT / RECITAL PARSER
# ============================================================

CONCERT_PROGRAMME_MARKERS = (
    "Déroulé du concert",
    "Deroule du concert",
    "Déroulé du récital",
    "Deroule du recital",
    "Programme du concert",
    "Programme du récital",
)

CONCERT_END_MARKERS = {
    "Mécènes et partenaires",
    "Mecenes et partenaires",
    "Vous aimerez aussi",
    "Galerie médias",
    "Galerie medias",
    "Accès et services",
    "Acces et services",
}

CONCERT_END_PREFIXES = (
    "Plongez dans l’univers Opéra de Paris",
    "Plongez dans l'univers Opéra de Paris",
    "Inscrivez-vous à notre newsletter",
    "Toute notre actualité",
    "© ",
)

CONCERT_JUNK_LINES = {
    "voir plus",
    "voir moins",
    "en savoir plus",
    "lire la suite",
    "fermer",
    "ouvrir",
    "boutique",
    "newsletter",
    "facebook",
    "instagram",
    "threads",
    "tiktok",
    "youtube",
    "twitter",
    "linkedin",
    "haut de page",
    "annuler",
}

MUSICAL_WORK_HINT_RE = re.compile(
    r"\b("
    r"symphonie|symphony|"
    r"sonate|sonata|"
    r"quatuor|quartet|"
    r"quintette|quintet|"
    r"trio|"
    r"sextuor|sextet|"
    r"septuor|"
    r"octuor|"
    r"concerto|"
    r"fantaisie|fantasy|"
    r"phantasy|"
    r"poème|poeme|"
    r"mazurka|"
    r"suite|"
    r"ouverture|overture|"
    r"hymne|hymnen|"
    r"lied|lieder|"
    r"walzer|"
    r"valse|"
    r"rhapsod|"
    r"nocturne|"
    r"scherzo|"
    r"variation|"
    r"messe|mass|"
    r"requiem|"
    r"serenade|sérénade|"
    r"danse|"
    r"romance|"
    r"capriccio|cappricio"
    r")\b",
    flags=re.IGNORECASE,
)

CATALOGUE_HINT_RE = re.compile(
    r"("
    r"\bop\.?\s*\d+|"
    r"\bkv\s*\d+|"
    r"\bbwv\s*\d+|"
    r"\bd\.?\s*\d+|"
    r"\bh\s*\d+|"
    r"\bn[º°o]\s*\d+|"
    r"\(\s*\d+\s*[’']\s*\)|"
    r"\(\s*\d+\s*[’']"
    r"\d+\s*\)"
    r")",
    flags=re.IGNORECASE,
)


def is_concert_footer_line(
    line: str,
) -> bool:
    if line in CONCERT_END_MARKERS:
        return True

    for prefix in (
        CONCERT_END_PREFIXES
    ):
        if line.startswith(
            prefix
        ):
            return True

    return False


def is_concert_junk_line(
    line: str,
) -> bool:
    return (
        norm(line)
        in {
            norm(value)
            for value
            in CONCERT_JUNK_LINES
        }
    )


def is_concert_nonwork_line(
    line: str,
) -> bool:
    if not line:
        return True

    if is_concert_footer_line(
        line
    ):
        return True

    if is_concert_junk_line(
        line
    ):
        return True

    if line.startswith(
        "[Button"
    ):
        return True

    if is_role_line(line):
        return True

    # These belong to the personnel
    # section but are NOT hard stops.

    if norm(line) in {
        norm("Équipe artistique"),
        norm("Equipe artistique"),
        norm("Artistes"),
        norm("Distribution"),
    }:
        return True

    if line.startswith(
        "Orchestre de"
    ):
        return True

    if line.startswith(
        "Chœur de"
    ):
        return True

    if line.startswith(
        "Choeur de"
    ):
        return True

    return False


def match_composer_line(
    line: str,
    composer_names,
) -> bool:
    key = norm(line)

    if key in composer_names:
        return True

    # Example:
    #
    # canonical:
    # Felix Mendelssohn
    #
    # source:
    # Felix Mendelssohn-Bartholdy

    for known_key in composer_names:
        if len(known_key) < 8:
            continue

        if (
            key.startswith(
                known_key + "-"
            )
            or known_key.startswith(
                key + "-"
            )
        ):
            return True

    return False


def looks_like_person_name(
    line: str,
) -> bool:
    if not line:
        return False

    if len(line) > 80:
        return False

    if is_concert_junk_line(
        line
    ):
        return False

    if any(
        char.isdigit()
        for char in line
    ):
        return False

    if any(
        symbol in line
        for symbol in (
            ":",
            ";",
            "(",
            ")",
            "«",
            "»",
        )
    ):
        return False

    if MUSICAL_WORK_HINT_RE.search(
        line
    ):
        return False

    tokens = (
        line
        .replace("’", "'")
        .split()
    )

    if not (
        2 <= len(tokens) <= 5
    ):
        return False

    particles = {
        "de",
        "del",
        "da",
        "di",
        "du",
        "des",
        "van",
        "von",
        "le",
        "la",
    }

    meaningful = 0

    for token in tokens:
        clean = token.strip(
            ".,'"
        )

        if not clean:
            continue

        if (
            clean.casefold()
            in particles
        ):
            continue

        meaningful += 1

        if not clean[0].isupper():
            return False

    return meaningful >= 2


def looks_like_work_line(
    line: str,
    composer_names,
) -> bool:
    if (
        is_concert_nonwork_line(
            line
        )
    ):
        return False

    if match_composer_line(
        line,
        composer_names,
    ):
        return False

    if (
        MUSICAL_WORK_HINT_RE
        .search(line)
    ):
        return True

    if CATALOGUE_HINT_RE.search(
        line
    ):
        return True

    return False


def next_meaningful_line(
    lines,
    index: int,
    end: int,
):
    i = index + 1

    while i < end:
        value = normalize_space(
            lines[i]
        )

        if value:
            return value

        i += 1

    return None


def next_line_is_role(
    lines,
    index: int,
    end: int,
) -> bool:
    next_line = (
        next_meaningful_line(
            lines,
            index,
            end,
        )
    )

    if not next_line:
        return False

    return is_role_line(
        next_line
    )


def find_concert_programme_start(
    lines,
    composer_names,
):
    # Prefer explicit specific markers.

    for marker in (
        CONCERT_PROGRAMME_MARKERS
    ):
        for i, line in enumerate(
            lines
        ):
            if (
                norm(line)
                == norm(marker)
            ):
                return i + 1

    # Conservative fallback:
    # generic "Programme" is accepted
    # only if musical evidence follows.

    for i, line in enumerate(
        lines
    ):
        if norm(line) != "programme":
            continue

        window_end = min(
            len(lines),
            i + 20,
        )

        for j in range(
            i + 1,
            window_end,
        ):
            candidate = lines[j]

            if match_composer_line(
                candidate,
                composer_names,
            ):
                return i + 1

            next_line = (
                next_meaningful_line(
                    lines,
                    j,
                    window_end,
                )
            )

            if (
                looks_like_person_name(
                    candidate
                )
                and next_line
                and looks_like_work_line(
                    next_line,
                    composer_names,
                )
            ):
                return i + 1

    return None


def split_inline_composer_work(
    line: str,
    composer_names,
):
    # Example:
    #
    # Piotr Ilytch Tchaïkovsky :
    # trio en la mineur, op. 50

    if ":" not in line:
        return None

    left, right = line.split(
        ":",
        1,
    )

    left = normalize_space(
        left
    )

    right = normalize_space(
        right
    )

    if not left or not right:
        return None

    composer_like = (
        match_composer_line(
            left,
            composer_names,
        )
        or looks_like_person_name(
            left
        )
    )

    if not composer_like:
        return None

    if not looks_like_work_line(
        right,
        composer_names,
    ):
        return None

    return left, right


def is_concert_work_candidate(
    line: str,
    composer_names,
) -> bool:
    if (
        is_concert_nonwork_line(
            line
        )
    ):
        return False

    if match_composer_line(
        line,
        composer_names,
    ):
        return False

    if len(line) > 220:
        return False

    return True


def extract_concert(
    lines,
    composer_names,
):
    start = (
        find_concert_programme_start(
            lines,
            composer_names,
        )
    )

    if start is None:
        return []

    # Hard programme boundary.
    #
    # This prevents:
    # Boutique / newsletter /
    # social links / footer
    # from becoming fake Works.

    end = len(lines)

    for i in range(
        start,
        len(lines),
    ):
        if is_concert_footer_line(
            lines[i]
        ):
            end = i
            break

    items = []

    current_composer = None

    programme_started = False

    i = start

    while i < end:
        line = normalize_space(
            lines[i]
        )

        if not line:
            i += 1
            continue

        if is_concert_junk_line(
            line
        ):
            i += 1
            continue

        if is_concert_footer_line(
            line
        ):
            break

        # --------------------------------
        # Inline:
        # Composer : Work
        # --------------------------------

        inline = (
            split_inline_composer_work(
                line,
                composer_names,
            )
        )

        if inline:
            (
                composer,
                work,
            ) = inline

            items.append(
                {
                    "raw_title":
                        work,
                    "raw_composers":
                        [composer],
                    "source_section":
                        "deroule_du_concert",
                }
            )

            current_composer = (
                composer
            )

            programme_started = True

            i += 1
            continue

        next_line = (
            next_meaningful_line(
                lines,
                i,
                end,
            )
        )

        # --------------------------------
        # Composer detection
        # --------------------------------

        known_composer = (
            match_composer_line(
                line,
                composer_names,
            )
        )

        inferred_composer = (
            looks_like_person_name(
                line
            )
            and next_line
            is not None
            and looks_like_work_line(
                next_line,
                composer_names,
            )
        )

        if (
            known_composer
            or inferred_composer
        ):
            # A Composer can also occur
            # in the artistic team:
            #
            # Thomas Adès
            # Direction musicale
            #
            # That must NOT start the
            # programme.

            if (
                not programme_started
                and next_line_is_role(
                    lines,
                    i,
                    end,
                )
            ):
                i += 1
                continue

            current_composer = line

            programme_started = True

            i += 1
            continue

        # --------------------------------
        # Work candidate
        # --------------------------------

        if (
            programme_started
            and current_composer
            and is_concert_work_candidate(
                line,
                composer_names,
            )
        ):
            items.append(
                {
                    "raw_title":
                        line,
                    "raw_composers":
                        [
                            current_composer
                        ],
                    "source_section":
                        "deroule_du_concert",
                }
            )

        i += 1

    return items


# ============================================================
# RESULT CLEANUP
# ============================================================

def dedupe_items(items):
    result = []

    seen = set()

    for item in items:
        title = normalize_space(
            item.get(
                "raw_title",
                "",
            )
        )

        composers = [
            normalize_space(value)
            for value
            in item.get(
                "raw_composers",
                [],
            )
            if normalize_space(value)
        ]

        # Never allow obvious page UI
        # into output.

        if (
            is_concert_junk_line(
                title
            )
        ):
            continue

        key = (
            norm(title),
            tuple(
                norm(value)
                for value
                in composers
            ),
        )

        if key in seen:
            continue

        seen.add(key)

        result.append(
            {
                **item,
                "raw_title":
                    title,
                "raw_composers":
                    composers,
            }
        )

    for index, item in enumerate(
        result,
        start=1,
    ):
        item["order"] = index

    return result


# ============================================================
# PAGE ROUTER
# ============================================================

def parse_page(
    row,
    composer_names,
):
    url = row[
        "source_url"
    ]

    event_type = row.get(
        "event_type"
    )

    result = {
        "source_url":
            url,
        "event_type":
            event_type,
        "source_titles":
            row.get(
                "source_titles"
            )
            or [],
        "event_count":
            row.get(
                "event_count"
            )
            or 0,
        "parser":
            None,
        "parser_version":
            PARSER_VERSION,
        "items":
            [],
        "warnings":
            [],
        "ok":
            False,
    }

    try:
        lines = fetch_lines(
            url
        )

        if event_type == "Ballet":
            result["parser"] = (
                "ballet_artistic_sections_v2"
            )

            items = extract_ballet(
                lines
            )

        elif (
            event_type
            == "Concert et Récital"
        ):
            result["parser"] = (
                "concert_programme_v4"
            )

            items = extract_concert(
                lines,
                composer_names,
            )

        else:
            # Jeune Public and
            # composite Opera pages remain
            # intentionally conservative.
            #
            # Do not invent Work relations.

            result["parser"] = (
                "unresolved_structure_v1"
            )

            items = []

        result["items"] = (
            dedupe_items(
                items
            )
        )

        if result["items"]:
            result["ok"] = True

        else:
            result[
                "warnings"
            ].append(
                "No programme items "
                "extracted automatically."
            )

    except Exception as exc:
        result[
            "warnings"
        ].append(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

    return result


# ============================================================
# REPORT
# ============================================================

def build_summary_by_type(
    results,
):
    summary = {}

    for row in results:
        event_type = (
            row.get(
                "event_type"
            )
            or "Unknown"
        )

        bucket = (
            summary.setdefault(
                event_type,
                {
                    "source_pages": 0,
                    "success_pages": 0,
                    "review_pages": 0,
                    "programme_items": 0,
                },
            )
        )

        bucket[
            "source_pages"
        ] += 1

        bucket[
            "programme_items"
        ] += len(
            row.get(
                "items",
                [],
            )
        )

        if row.get("ok"):
            bucket[
                "success_pages"
            ] += 1
        else:
            bucket[
                "review_pages"
            ] += 1

    return summary


def main():
    validate_environment()

    queue = get_queue()

    composer_names = (
        get_composer_names()
    )

    print(
        f"Pending source pages: "
        f"{len(queue)}"
    )

    results = []

    for index, row in enumerate(
        queue,
        start=1,
    ):
        print(
            f"[{index}/{len(queue)}] "
            f"{row.get('event_type')} "
            f"{row.get('source_url')}"
        )

        result = parse_page(
            row,
            composer_names,
        )

        results.append(
            result
        )

        print(
            "    "
            f"parser="
            f"{result['parser']} "
            f"items="
            f"{len(result['items'])} "
            f"ok="
            f"{result['ok']}"
        )

    report = {
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "parser_version":
            PARSER_VERSION,
        "source_pages":
            len(results),
        "success_pages":
            sum(
                1
                for row in results
                if row["ok"]
            ),
        "review_pages":
            sum(
                1
                for row in results
                if not row["ok"]
            ),
        "programme_items":
            sum(
                len(
                    row["items"]
                )
                for row
                in results
            ),
        "summary_by_type":
            build_summary_by_type(
                results
            ),
        "pages":
            results,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as fh:
        json.dump(
            report,
            fh,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        "===== SUMMARY ====="
    )

    print(
        json.dumps(
            {
                "source_pages":
                    report[
                        "source_pages"
                    ],
                "success_pages":
                    report[
                        "success_pages"
                    ],
                "review_pages":
                    report[
                        "review_pages"
                    ],
                "programme_items":
                    report[
                        "programme_items"
                    ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print(
        "===== BY TYPE ====="
    )

    print(
        json.dumps(
            report[
                "summary_by_type"
            ],
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print(
        f"Saved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print(
            "ERROR: "
            f"{type(exc).__name__}: "
            f"{exc}",
            file=sys.stderr,
        )

        raise