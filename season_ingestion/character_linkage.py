"""Read-only classification for unlinked work-character staging rows."""

from __future__ import annotations

from typing import Any

from .global_master import normalize_identity


NON_CHARACTER_LABELS = {
    "conductor", "musical conductor", "stage director", "director", "lighting",
    "set designer", "sets", "costume", "costumes", "choreography",
    "chorus conductor", "chorus master", "orchestra", "choir", "ensemble",
    "dramaturg", "dramaturgy",
}


def classify_unlinked_character(row: dict[str, Any], snapshot: Any, *, work_label_counts: dict[str, int] | None = None) -> dict[str, Any]:
    label = str(row.get("canonical_name") or "").strip()
    key = normalize_identity(label)
    if key in {normalize_identity(value) for value in NON_CHARACTER_LABELS}:
        classification = "NON_CHARACTER_CONTAMINATION"
        reason = "production/artistic role hard-blocked from global character identity"
        proposed = None
    else:
        matches = []
        for character in snapshot.entities.get("character", []):
            if normalize_identity(character.get("canonical_name")) == key:
                matches.append(character)
        for alias in getattr(snapshot, "character_aliases", []):
            if normalize_identity(alias.get("alias")) == key:
                matches.extend(character for character in snapshot.entities.get("character", []) if character.get("id") == alias.get("character_id"))
        matches = list({character.get("id"): character for character in matches}.values())
        if len(matches) == 1:
            classification = "SAFE_LINK_EXISTING_CHARACTER"
            reason = "exact canonical or existing alias match"
            proposed = matches[0].get("id")
        elif len(matches) > 1 or (work_label_counts or {}).get(key, 0) > 1:
            classification = "REVIEW_CHARACTER_IDENTITY"
            reason = "ambiguous global or cross-work identity; no blind merge"
            proposed = None
        elif key:
            classification = "SAFE_NEW_GLOBAL_CHARACTER"
            reason = "unique work-scoped dramatic role with no global match"
            proposed = None
        else:
            classification = "REVIEW_CHARACTER_IDENTITY"
            reason = "empty character identity"
            proposed = None
    return {**row, "proposed_character_id": proposed, "classification": classification, "reason": reason}

