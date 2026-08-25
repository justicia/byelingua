import re
import unicodedata
from pathlib import Path

import yaml


REGISTRY_PATH = (
    Path(__file__).resolve().parent
    / "character_registry.yaml"
)


NON_CHARACTER_TERMS = {
    "soliste",
    "danseur",
    "danseuse",
    "soprano",
    "tenor",
    "ténor",
    "baryton",
    "mezzo-soprano",
    "violon",
    "violoncelle",
    "flute",
    "flûte",
    "piano",
    "basson",
    "cor",
    "percussions",
    "saxophone",
    "musique",
    "choregraphie",
    "chorégraphie",
    "costumes",
    "lumieres",
    "lumières",
    "musical conductor",
    "stage director",
    "chorus conductor",
    "lighting",
    "set designer",
    "costumes",
    "choreography",
    "orchestra",
    "szenische einstudierung",
    "textbearbeitung",
    "kampfmeister",
    "puppenbau",
    "puppencoach",
    "iluminator",
    "children's chorus director",
    "bajo",
    "contratenor",
    "bass",
    "baritone",
    "mezzo",
}

VOICE_TYPE_TERMS = {
    "soprano", "mezzo", "mezzo-soprano", "tenor", "bass", "baritone",
    "contratenor", "bajo", "sopran", "mezzosopran", "bariton",
}

ENSEMBLE_TERMS = {
    "ensemble", "chorus", "choir", "chor", "children's chorus",
    "vier edelknaben", "three ladies", "three boys",
}

PRODUCTION_ROLE_TERMS = {
    "conductor", "musical conductor", "stage director", "chorus conductor",
    "lighting", "set designer", "costumes", "choreography", "orchestra",
    "szenische einstudierung", "textbearbeitung", "kampfmeister", "puppenbau",
    "puppencoach", "iluminator", "children's chorus director", "director",
}


def normalize_key(value):
    value = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = value.casefold().strip()

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value,
    )

    return value.strip("-")


def is_character(raw_character):
    if not raw_character:
        return False

    key = normalize_key(
        raw_character
    ).replace("-", " ")

    non_character_keys = {
        normalize_key(value).replace("-", " ")
        for value in NON_CHARACTER_TERMS
    }

    return key not in non_character_keys


def _clean_lookup_label(value):
    """Return a lookup-only label while preserving the caller's raw value."""
    value = str(value or "").strip()
    value = re.sub(r"\s*[/／]\s*$", "", value).strip()
    return value


def parse_source_label(raw_character):
    """Classify a legacy source label without assigning global identity."""
    raw = str(raw_character or "").strip()
    lookup = _clean_lookup_label(raw)
    key = normalize_key(lookup).replace("-", " ")

    if not raw:
        return {"class": "AMBIGUOUS", "raw": raw, "lookup": lookup}
    if key in {normalize_key(v).replace("-", " ") for v in VOICE_TYPE_TERMS}:
        return {"class": "VOICE_TYPE", "raw": raw, "lookup": lookup}
    if key in {normalize_key(v).replace("-", " ") for v in ENSEMBLE_TERMS}:
        return {"class": "ENSEMBLE", "raw": raw, "lookup": lookup}
    if key in {normalize_key(v).replace("-", " ") for v in PRODUCTION_ROLE_TERMS}:
        return {"class": "PRODUCTION_ROLE", "raw": raw, "lookup": lookup}
    if "/" in lookup or "／" in lookup:
        return {"class": "COMPOSITE_DOUBLE_ROLE", "raw": raw, "lookup": lookup}
    if re.search(r"\s[-–—]\s*(?:schauspieler(?:in)?|actor|actress)\s*$", lookup, re.I):
        base = re.sub(r"\s[-–—]\s*(?:schauspieler(?:in)?|actor|actress)\s*$", "", lookup, flags=re.I).strip()
        return {"class": "PERFORMER_VARIANT", "raw": raw, "lookup": base, "descriptor": lookup[len(base):].strip()}
    if "," in lookup:
        base, descriptor = lookup.split(",", 1)
        if base.strip() and descriptor.strip():
            return {"class": "DESCRIPTOR_CHARACTER", "raw": raw, "lookup": base.strip(), "descriptor": descriptor.strip()}
    if not is_character(lookup):
        return {"class": "PRODUCTION_ROLE", "raw": raw, "lookup": lookup}
    return {"class": "SIMPLE_CHARACTER", "raw": raw, "lookup": lookup}


def load_character_registry():
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(
            f"Character registry not found: "
            f"{REGISTRY_PATH}"
        )

    with REGISTRY_PATH.open(
        "r",
        encoding="utf-8",
    ) as handle:
        data = yaml.safe_load(handle) or {}

    characters = data.get("characters")

    if not isinstance(characters, dict):
        raise ValueError(
            "character_registry.yaml must contain "
            "a 'characters' mapping."
        )

    return data


def resolve_character(
    raw_character,
    composer,
    work_title,
    registry=None,
):
    raw_character = str(
        raw_character or ""
    ).strip()

    composer = str(
        composer or ""
    ).strip()

    work_title = str(
        work_title or ""
    ).strip()

    if not raw_character:
        return {
            "kind": "empty",
            "raw_character": "",
        }

    if not is_character(raw_character):
        return {
            "kind": "non_character",
            "raw_character": raw_character,
        }

    if registry is None:
        registry = load_character_registry()

    raw_key = normalize_key(
        raw_character
    )

    work_key = normalize_key(
        work_title
    )

    characters = registry.get(
        "characters",
        {},
    )

    for identity_key, config in characters.items():
        canonical_name = str(
            config.get("canonical_name") or ""
        ).strip()

        if not canonical_name:
            continue

        searchable_names = {
            normalize_key(canonical_name)
        }

        aliases = (
            config.get("aliases")
            or {}
        )

        for alias_group in aliases.values():
            for alias in alias_group or []:
                searchable_names.add(
                    normalize_key(alias)
                )

        allowed_works = {
            normalize_key(work)
            for work in (
                config.get("works")
                or []
            )
        }

        if (
            raw_key in searchable_names
            and work_key in allowed_works
        ):
            return {
                "kind": "character",
                "identity_key": identity_key,
                "canonical_name": canonical_name,
                "raw_character": raw_character,
                "composer": composer,
                "work_title": work_title,
                "aliases": aliases,
                "source": "registry",
            }

    return {
        "kind": "review",
        "review_code": "REVIEW_CANONICAL_NAME",
        "identity_key": None,
        "canonical_name": None,
        "raw_character": raw_character,
        "composer": composer,
        "work_title": work_title,
        "aliases": {},
        "source": "unresolved",
    }

def normalize_character_credit(
    credit,
    *,
    composer,
    work_title,
    registry=None,
):
    normalized = dict(credit or {})

    raw_character = str(
        normalized.get("character") or ""
    ).strip()

    if not raw_character:
        return normalized

    resolved = resolve_character(
        raw_character,
        composer,
        work_title,
        registry=registry,
    )

    normalized["raw_character"] = raw_character
    normalized["character_kind"] = resolved.get("kind")

    if resolved.get("kind") != "character":
        normalized["character"] = None
        normalized["character_identity_key"] = None
        normalized["character_resolution_source"] = None
        return normalized

    normalized["character"] = resolved.get(
        "canonical_name"
    )

    normalized["character_identity_key"] = (
        resolved.get("identity_key")
    )

    normalized["character_resolution_source"] = (
        resolved.get("source")
    )

    return normalized


def normalize_event_character_credits(
    event,
    *,
    registry=None,
):
    if hasattr(event, "to_dict"):
        event_data = event.to_dict()
    else:
        event_data = dict(event or {})

    programme = event_data.get("programme") or []
    credits = event_data.get("credits") or []

    work_candidates = []

    for item in programme:
        title = str(
            item.get("title") or ""
        ).strip()

        composer = str(
            item.get("composer") or ""
        ).strip()

        if not title:
            continue

        candidate = (
            composer,
            title,
        )

        if candidate not in work_candidates:
            work_candidates.append(candidate)

    normalized_credits = []

    for credit in credits:
        raw_character = str(
            credit.get("character") or ""
        ).strip()

        if not raw_character:
            normalized_credits.append(
                dict(credit)
            )
            continue

        if len(work_candidates) != 1:
            unresolved = dict(credit)

            unresolved["raw_character"] = (
                raw_character
            )

            unresolved["character_kind"] = (
                "unresolved"
            )

            unresolved[
                "character_identity_key"
            ] = None

            unresolved[
                "character_resolution_source"
            ] = "ambiguous_programme"

            normalized_credits.append(
                unresolved
            )

            continue

        composer, work_title = (
            work_candidates[0]
        )

        normalized_credits.append(
            normalize_character_credit(
                credit,
                composer=composer,
                work_title=work_title,
                registry=registry,
            )
        )

    event_data["credits"] = (
        normalized_credits
    )

    return event_data
